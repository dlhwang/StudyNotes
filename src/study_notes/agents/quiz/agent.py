"""quiz 하위 Agent — 노트로 문답 카드 초안을 만들어 제안한다.

- 모델이 있으면 Structured Output(``QuizOut``, few-shot 프롬프트)으로 만들고,
  근거(evidence)가 노트에 없는 카드는 버린다.
- 모델이 없거나 남은 카드가 없으면 노트의 ``- 용어: 설명`` 줄로 만든다(규칙 답).
- **카드를 저장하지 않는다.** 제안 초안 ``quiz.cards_add`` + [카드 N장 저장] 버튼을 돌려주고,
  사용자가 누르면 BE(``POST /proposals/accept``)가 ``dedupe_key``로 한 번만 저장한다.
"""

from __future__ import annotations

from typing import cast

from pydantic import BaseModel, Field

from study_notes.agents.base import AgentRequest, BaseAgent
from study_notes.agents.note_ref import resolve_note_id
from study_notes.agents.quiz import rules
from study_notes.agents.quiz.rules import QuizCard
from study_notes.agents.quiz.tools import QuizCardsArgs, QuizNoteArgs, QuizNotesArgs, QuizProfileArgs
from study_notes.core.errors import LlmUnavailableError
from study_notes.core.reply import AgentResult, Citation, UiAction
from study_notes.orchestrator.intents import IntentSpec
from study_notes.tools.be_client.protocol import Card, LearnerProfile, Note, NoteSummary

QUIZ_MAKE = IntentSpec("quiz_make", "노트로 퀴즈 카드 만들기", (r"(퀴즈|문제).*(내|만들|줘|출제)", r"카드.*만들"))


class QuizOut(BaseModel):
    reasoning: str = ""
    cards: list[QuizCard] = Field(default_factory=list, max_length=10)


class QuizAgent(BaseAgent):
    name = "quiz"
    title = "퀴즈 Agent"
    intents = (QUIZ_MAKE,)

    async def run(self, req: AgentRequest) -> AgentResult:
        notebook = self.subject_id()
        count = rules.requested_count(req.text)
        notes = cast(list[NoteSummary], await self.tool("quiz_list_notes", QuizNotesArgs(notebook_id=notebook)))
        note_id = resolve_note_id(req.text, notes, self.screen_note_id(), req.focus_note_ids)
        if note_id is None:
            return AgentResult(
                reply=self.reply(
                    "어느 노트로 퀴즈를 낼까요? 노트 제목을 넣어 다시 물어 주세요.",
                    actions=[UiAction(kind="ask", label=n.title, text=f"{n.title} 퀴즈 내줘") for n in notes[:3]],
                )
            )
        note = cast(Note, await self.tool("quiz_get_note", QuizNoteArgs(note_id=note_id)))
        existing = [
            c.question
            for c in cast(
                list[Card], await self.tool("quiz_list_cards", QuizCardsArgs(notebook_id=notebook, note_id=note.id))
            )
        ]
        profile = cast(LearnerProfile, await self.tool("quiz_get_profile", QuizProfileArgs(base_date=self.base_date())))

        source, prompt_version = "rule", None
        try:
            prompt = self.prompt("make")
            out = await self.ask_llm_json(
                QuizOut,
                "worker",
                prompt,
                req.text,
                count=count,
                difficulty=profile.quiz_difficulty,
                existing="\n".join(f"- {q}" for q in existing) or "(없음)",
                title=note.title,
                body=note.body,
            )
            cards = rules.grounded(out.cards, note.body, existing, count)
            if not cards:
                raise LlmUnavailableError("근거가 확인된 카드가 없습니다")
            source, prompt_version = "ai", prompt.id
        except LlmUnavailableError:
            cards = rules.cards_from_note(note.body, count, existing)

        citation = Citation(title=note.title, location=note.id)
        focus = {"focus_note_ids": [note.id]}
        if not cards:
            return AgentResult(
                reply=self.reply(
                    f"'{note.title}'에서 새로 만들 카드가 없습니다. 이미 카드가 있거나, '- 용어: 설명' 줄이 없습니다.",
                    citations=[citation],
                    actions=[UiAction(kind="ask", label="다른 노트로", text="노트 목록 보여줘")],
                    data=focus,
                )
            )

        draft = self.proposal(
            kind="quiz.cards_add",
            title=f"'{note.title}' 카드 {len(cards)}장",
            payload={"note_id": note.id, "cards": [{"question": c.question, "answer": c.answer} for c in cards]},
            reasons=[f"사용자 요청: {req.text}", f"근거 노트: {note.title}({note.id})"],
        )
        lines = [f"{i}. {c.question}" for i, c in enumerate(cards, 1)]
        text = f"'{note.title}'로 퀴즈 {len(cards)}개를 만들었습니다. 저장하면 복습 카드가 됩니다.\n" + "\n".join(lines)
        return AgentResult(
            reply=self.reply(
                text,
                source=source,
                actions=[
                    UiAction(kind="save_proposal", label=f"카드 {len(cards)}장 저장", params={"index": 0}),
                    UiAction(kind="ask", label="다른 노트로 퀴즈", text="노트 목록 보여줘"),
                ],
                citations=[citation],
                proposals=[draft],
                data={**focus, "cards": [c.model_dump() for c in cards]},
                prompt_version=prompt_version,
            )
        )
