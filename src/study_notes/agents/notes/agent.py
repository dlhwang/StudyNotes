"""notes 하위 Agent — 노트 찾기·요약·노트 기반 질의(RAG).

| 의도 | 하는 일 | 모델 | 규칙 답 |
|---|---|---|---|
| note_search | 키워드 목록 + 의미 검색을 노트 단위로 합침 | 쓰지 않음 | 항상 |
| note_summary | 노트 하나 요약 (Structured Output) | worker | 소제목 첫 문장 + 용어 줄 |
| note_qa | ReAct: 모델이 검색·노트 읽기 도구를 골라 근거를 모은 뒤 답 | worker | 상위 검색 조각 발췌 |

모든 답의 ``data.focus_note_ids``로 다룬 노트를 알린다 → chat 그래프가 대화 메모리에 저장한다.
"""

from __future__ import annotations

from typing import Any, cast

from pydantic import BaseModel, Field

from study_notes.agents.base import AgentRequest, BaseAgent
from study_notes.agents.notes import rules
from study_notes.agents.notes.tools import ChunkSearchArgs, NoteIdArgs, NoteListArgs, ProfileArgs
from study_notes.core.errors import LlmUnavailableError
from study_notes.core.reply import AgentResult, Citation, UiAction
from study_notes.orchestrator.intents import IntentSpec
from study_notes.tools.be_client.protocol import ChunkHit, LearnerProfile, Note, NoteSummary

NOTE_SUMMARY = IntentSpec("note_summary", "노트 요약하기", (r"(요약|정리해|핵심만)",))
NOTE_SEARCH = IntentSpec(
    "note_search",
    "노트 찾기·목록 보기",
    (r"^(?!.*(요약|정리해|핵심만)).*(노트|메모).*(찾아|검색|목록|뭐있|보여)", r"(찾아줘|검색해)"),
)
NOTE_QA = IntentSpec(
    "note_qa",
    "노트 내용으로 질문에 답하기",
    (r"^(?!.*(퀴즈|문제|복습|요약|정리|찾아|검색|목록)).*(뭐야|뭐지|뭔데|무엇|차이|어떻게|왜|설명해|알려줘)",),
)


class SummaryOut(BaseModel):
    """요약 구조화 출력. reasoning은 단계적 사고 칸으로 화면에 내지 않는다."""

    reasoning: str = ""
    key_points: list[str] = Field(min_length=1, max_length=6)
    one_line: str = ""


class NotesAgent(BaseAgent):
    name = "notes"
    title = "노트 Agent"
    intents = (NOTE_SUMMARY, NOTE_SEARCH, NOTE_QA)

    async def run(self, req: AgentRequest) -> AgentResult:
        notebook = self.subject_id()
        if req.intent == NOTE_SEARCH.name:
            return await self._search(req, notebook)
        if req.intent == NOTE_SUMMARY.name:
            return await self._summary(req, notebook)
        return await self._qa(req, notebook)

    # ── 공통 ─────────────────────────────────────────────────────────

    async def _notes(self, notebook: str, query: str | None = None, limit: int = 20) -> list[NoteSummary]:
        args = NoteListArgs(notebook_id=notebook, query=query or None, limit=limit)
        return cast(list[NoteSummary], await self.tool("notes_list_items", args))

    async def _hits(self, notebook: str, query: str, k: int = 4) -> list[ChunkHit]:
        if not query.strip():
            return []
        args = ChunkSearchArgs(notebook_id=notebook, query=query, k=k)
        return cast(list[ChunkHit], await self.tool("notes_search_chunks", args))

    async def _target_note(self, req: AgentRequest, notebook: str) -> Note | None:
        notes = await self._notes(notebook)
        note_id = rules.resolve_note_id(req.text, notes, self.screen_note_id(), req.focus_note_ids)
        if note_id is None:
            hits = await self._hits(notebook, rules.search_query(req.text) or req.text, k=1)
            if hits and hits[0].score >= rules.MIN_SCORE:
                note_id = hits[0].note_id
        if note_id is None:
            return None
        return cast(Note, await self.tool("notes_get_item", NoteIdArgs(note_id=note_id)))

    def _quiz_button(self, note: Note | NoteSummary | ChunkHit) -> UiAction:
        return UiAction(kind="ask", label="이 노트로 퀴즈", text=f"{note.title} 퀴즈 내줘")

    # ── 찾기 ─────────────────────────────────────────────────────────

    async def _search(self, req: AgentRequest, notebook: str) -> AgentResult:
        query = rules.search_query(req.text)
        found: list[dict[str, Any]] = []
        for n in await self._notes(notebook, query, limit=5):
            found.append({"id": n.id, "title": n.title, "why": n.snippet[:80]})
        for h in await self._hits(notebook, query, k=5):
            if h.score >= rules.MIN_SCORE and all(f["id"] != h.note_id for f in found):
                found.append({"id": h.note_id, "title": h.title, "why": rules.excerpt(h, 80)})
        found = found[:5]
        if not found:
            return AgentResult(
                reply=self.reply(
                    f"'{query}'와 관련된 노트를 찾지 못했습니다." if query else "노트가 아직 없습니다.",
                    actions=[UiAction(kind="ask", label="노트 목록", text="노트 목록 보여줘")] if query else [],
                )
            )
        head = f"'{query}' 관련 노트 {len(found)}개" if query else f"노트 {len(found)}개"
        text = f"{head}를 찾았습니다: " + " / ".join(f"{f['title']}({f['id']})" for f in found)
        return AgentResult(
            reply=self.reply(
                text,
                actions=[UiAction(kind="ask", label=f"{found[0]['title']} 요약", text=f"{found[0]['title']} 요약해줘")],
                citations=[Citation(title=f["title"], location=f["id"]) for f in found],
                data={"notes": found, "focus_note_ids": [f["id"] for f in found[:1]]},
            )
        )

    # ── 요약 ─────────────────────────────────────────────────────────

    async def _summary(self, req: AgentRequest, notebook: str) -> AgentResult:
        note = await self._target_note(req, notebook)
        if note is None:
            notes = await self._notes(notebook, limit=3)
            return AgentResult(
                reply=self.reply(
                    "어떤 노트를 요약할지 모르겠습니다. 노트 제목을 넣어 다시 물어 주세요.",
                    actions=[UiAction(kind="ask", label=f"{n.title} 요약", text=f"{n.title} 요약해줘") for n in notes],
                )
            )
        profile = cast(LearnerProfile, await self.tool("notes_get_profile", ProfileArgs(base_date=self.base_date())))
        count = rules.SUMMARY_POINTS[profile.summary_length]
        citation = Citation(title=note.title, location=note.id)
        actions = [self._quiz_button(note)]
        data: dict[str, Any] = {"focus_note_ids": [note.id]}
        try:
            out = await self.ask_llm_json(
                SummaryOut,
                "worker",
                self.prompt("summary"),
                req.text,
                title=note.title,
                body=note.body,
                count=count,
                length=profile.summary_length,
            )
            points = out.key_points[:count]
            head = f"'{note.title}' 요약" + (f" — {out.one_line}" if out.one_line else "")
            text = head + "\n" + "\n".join(f"- {p}" for p in points)
            return AgentResult(
                reply=self.reply(
                    text,
                    source="ai",
                    actions=actions,
                    citations=[citation],
                    data={**data, "key_points": points},
                    prompt_version=self.prompt("summary").id,
                )
            )
        except LlmUnavailableError:
            points = rules.key_points(note.body, count)
            text = f"'{note.title}' 핵심 {len(points)}가지입니다.\n" + "\n".join(f"- {p}" for p in points)
            return AgentResult(
                reply=self.reply(text, actions=actions, citations=[citation], data={**data, "key_points": points})
            )

    # ── 노트 기반 질의 (ReAct + RAG) ──────────────────────────────────

    async def _qa(self, req: AgentRequest, notebook: str) -> AgentResult:
        try:
            outcome = await self.react(
                "worker",
                self.prompt("qa"),
                req.text,
                tools=["notes_search_chunks", "notes_get_item"],
                notebook_id=notebook,
                history="\n".join(req.history) or "(없음)",
                focus=", ".join(req.focus_note_ids) or "(없음)",
            )
        except LlmUnavailableError:
            return await self._qa_rule(req, notebook)
        citations: list[Citation] = []
        note_ids: list[str] = []
        for obs in outcome.observations:
            items = obs if isinstance(obs, list) else [obs]
            for item in items:
                if isinstance(item, ChunkHit) and item.score >= rules.MIN_SCORE:
                    cite = Citation(title=item.title, location=rules.location(item))
                    nid = item.note_id
                elif isinstance(item, Note):
                    cite, nid = Citation(title=item.title, location=item.id), item.id
                else:
                    continue
                if nid not in note_ids:
                    note_ids.append(nid)
                    citations.append(cite)
        trace = [s.model_dump(include={"step", "tool", "args", "observation"}) for s in outcome.steps]
        return AgentResult(
            reply=self.reply(
                outcome.answer,
                source="ai",
                citations=citations[:3],
                actions=[UiAction(kind="ask", label="관련 퀴즈", text="그 노트로 퀴즈 내줘")] if note_ids else [],
                data={"trace": trace, "focus_note_ids": note_ids[:3]},
                prompt_version=outcome.prompt_id,
            )
        )

    async def _qa_rule(self, req: AgentRequest, notebook: str) -> AgentResult:
        query = rules.search_query(req.text)
        hits = [h for h in await self._hits(notebook, query or req.text, k=3) if h.score >= rules.MIN_SCORE]
        if not hits and req.focus_note_ids and not query:
            note = cast(Note, await self.tool("notes_get_item", NoteIdArgs(note_id=req.focus_note_ids[0])))
            points = rules.key_points(note.body, 3)
            text = f"'{note.title}' 노트의 내용입니다.\n" + "\n".join(f"- {p}" for p in points)
            return AgentResult(
                reply=self.reply(
                    text,
                    citations=[Citation(title=note.title, location=note.id)],
                    data={"focus_note_ids": [note.id]},
                )
            )
        if not hits:
            return AgentResult(
                reply=self.reply(
                    "노트에 관련 내용이 없습니다. 노트를 먼저 써 두면 그 내용으로 답할 수 있습니다.",
                    actions=[UiAction(kind="ask", label="노트 목록", text="노트 목록 보여줘")],
                )
            )
        lines = [f"- {rules.excerpt(h)} ({h.title})" for h in hits]
        note_ids = list(dict.fromkeys(h.note_id for h in hits))
        return AgentResult(
            reply=self.reply(
                "노트에서 찾은 내용입니다.\n" + "\n".join(lines),
                citations=[Citation(title=h.title, location=rules.location(h)) for h in hits],
                actions=[self._quiz_button(hits[0])],
                data={"focus_note_ids": note_ids[:3]},
            )
        )
