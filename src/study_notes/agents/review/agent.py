"""review 하위 Agent — 복습 안내·학습 코칭·선호 기억(장기 메모리).

| 의도 | 하는 일 | 모델 |
|---|---|---|
| review_stats | BE 통계 + 약한 노트 → 코칭 | worker(실패 시 숫자 나열) |
| review_today | 오늘 복습할 카드 + [복습 시작] 버튼 | 쓰지 않음 |
| profile_update | "앞으로 요약은 짧게" → ``profile.update`` 제안 + [기억하기] | 쓰지 않음 |

숫자는 BE가 계산한 값만 쓴다(절대 규칙 4). 선호는 직접 바꾸지 않고 제안으로 돌려준다(절대 규칙 1).
"""

from __future__ import annotations

from typing import cast

from study_notes.agents.base import AgentRequest, BaseAgent
from study_notes.agents.review import rules
from study_notes.agents.review.tools import DueArgs, ReviewProfileArgs, StatsArgs
from study_notes.core.errors import LlmUnavailableError
from study_notes.core.reply import AgentResult, UiAction
from study_notes.orchestrator.intents import IntentSpec
from study_notes.tools.be_client.protocol import Card, LearnerProfile, ReviewStats

REVIEW_STATS = IntentSpec(
    "review_stats", "학습 현황·정답률·약한 노트 보기", (r"(현황|통계|정답률|진도|연속|얼마나공부|약한|취약|공부상태)",)
)
REVIEW_TODAY = IntentSpec(
    "review_today", "오늘 복습할 카드 보기", (r"^(?!.*(현황|통계|정답률|앞으로|기억해)).*(복습|외울|외워야|다시볼)",)
)
PROFILE_UPDATE = IntentSpec(
    "profile_update",
    "요약 길이·퀴즈 난이도 기억하기",
    (r"(앞으로|항상|기억해|이제부터).*(짧게|길게|자세히|간단히|쉽게|어렵게|보통)",),
)


class ReviewAgent(BaseAgent):
    name = "review"
    title = "복습 코치 Agent"
    intents = (REVIEW_STATS, REVIEW_TODAY, PROFILE_UPDATE)

    async def run(self, req: AgentRequest) -> AgentResult:
        if req.intent == PROFILE_UPDATE.name:
            return self._profile_update(req)
        notebook = self.subject_id()
        if req.intent == REVIEW_STATS.name:
            return await self._stats(req, notebook)
        return await self._today(notebook)

    async def _today(self, notebook: str) -> AgentResult:
        base = self.base_date()
        cards = cast(list[Card], await self.tool("review_list_due", DueArgs(notebook_id=notebook, base_date=base)))
        if not cards:
            return AgentResult(
                reply=self.reply(
                    "오늘 복습할 카드가 없습니다. 노트로 퀴즈를 만들어 카드를 늘려 보세요.",
                    actions=[UiAction(kind="ask", label="퀴즈 만들기", text="퀴즈 내줘")],
                    data={"cards": []},
                )
            )
        return AgentResult(
            reply=self.reply(
                rules.due_text(cards, base),
                actions=[UiAction(kind="navigate", label="복습 시작", target="review")],
                data={
                    "cards": [c.model_dump(include={"id", "question", "note_title", "due_date"}) for c in cards],
                    "focus_note_ids": list(dict.fromkeys(c.note_id for c in cards))[:3],
                },
            )
        )

    async def _stats(self, req: AgentRequest, notebook: str) -> AgentResult:
        base = self.base_date()
        stats = cast(ReviewStats, await self.tool("review_get_stats", StatsArgs(notebook_id=notebook, base_date=base)))
        profile = cast(LearnerProfile, await self.tool("review_get_profile", ReviewProfileArgs(base_date=base)))
        actions = [UiAction(kind="navigate", label="복습 시작", target="review")]
        if profile.weak_notes:
            weak = profile.weak_notes[0]
            actions.insert(0, UiAction(kind="ask", label=f"{weak.title} 다시 보기", text=f"{weak.title} 요약해줘"))
        data = {"stats": stats.model_dump(), "weak_notes": [w.model_dump() for w in profile.weak_notes]}
        try:
            prompt = self.prompt("coach")
            text, pid = await self.ask_llm(
                "worker", prompt, req.text, stats=rules.stats_text(stats), weak=rules.weak_text(profile)
            )
            return AgentResult(reply=self.reply(text, source="ai", actions=actions, data=data, prompt_version=pid))
        except LlmUnavailableError:
            text = rules.stats_text(stats) + " " + rules.weak_text(profile)
            return AgentResult(reply=self.reply(text, actions=actions, data=data))

    def _profile_update(self, req: AgentRequest) -> AgentResult:
        prefs = rules.parse_preference(req.text)
        if not prefs:
            return AgentResult(
                reply=self.reply(
                    "어떤 선호를 기억할지 모르겠습니다. 예: '앞으로 요약은 짧게 해줘', '앞으로 퀴즈는 어렵게 내줘'",
                )
            )
        label = rules.preference_label(prefs)
        draft = self.proposal(
            kind="profile.update",
            title=f"선호 기억: {label}",
            payload=dict(prefs),
            reasons=[f"사용자 요청: {req.text}"],
        )
        return AgentResult(
            reply=self.reply(
                f"'{label}'을(를) 기억할까요? 기억하면 다음 대화부터 반영됩니다.",
                actions=[UiAction(kind="save_proposal", label="기억하기", params={"index": 0})],
                proposals=[draft],
            )
        )
