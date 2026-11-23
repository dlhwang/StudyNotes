"""daily_review 그래프 — 예약 실행. 노트북마다 오늘 복습 계획 제안 초안을 돌려준다.

plan → 끝

- BE가 부르고(화면의 [오늘 계획 만들기] 또는 예약), 결과의 ``proposals``를 받아 저장한다. ai-agent는 BE에 쓰지 않는다.
- 판정은 agents/review/rules.py의 daily_plan(). 사람이 없으므로 읽기 전용 서비스 계정으로 조회한다.
- 초안마다 중복 방지 키(노트북·기준일)가 있어, 같은 날 두 번 돌아도 BE가 한 번만 저장한다.
"""

from __future__ import annotations

from typing import Any, TypedDict, cast

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.types import Checkpointer

from study_notes.agents.review import ReviewAgent
from study_notes.agents.review.rules import daily_plan
from study_notes.agents.review.tools import DueArgs, NoArgs
from study_notes.config import get_settings
from study_notes.deps import get_deps
from study_notes.graphs.scheduled import service_request, service_runner
from study_notes.observability.logging import get_logger
from study_notes.tools.be_client.protocol import Card

GRAPH = "daily_review"
log = get_logger("graphs.daily_review")


class DailyReviewState(TypedDict, total=False):
    base_date: str  # 입력: 기준일 YYYY-MM-DD
    subject_ids: list[str] | None  # 입력: 노트북 ID. 없으면 전체
    proposals: list[dict[str, Any]]  # 출력: ProposalDraft (BE가 저장)


async def plan(state: DailyReviewState, config: RunnableConfig) -> dict[str, Any]:
    deps, req = get_deps(), service_request(config, GRAPH)
    runner = service_runner(ReviewAgent, req, deps)
    base = state["base_date"]
    notebooks = state.get("subject_ids") or cast(list[str], await runner.call("review_list_notebooks", NoArgs()))
    proposals: list[dict[str, Any]] = []
    for nb in notebooks:
        cards = cast(
            list[Card], await runner.call("review_list_due", DueArgs(notebook_id=nb, base_date=base, limit=50))
        )
        draft = daily_plan(nb, cards, base)
        if draft is not None:
            proposals.append(draft.model_dump())
    log.info("복습 계획 완료", extra={"fields": {"notebooks": len(notebooks), "proposals": len(proposals)}})
    return {"proposals": proposals}


def build_daily_review_graph(checkpointer: Checkpointer = None) -> Any:
    g = StateGraph(DailyReviewState)
    g.add_node("plan", plan)
    g.add_edge(START, "plan")
    g.add_edge("plan", END)
    return g.compile(checkpointer=checkpointer, name=GRAPH).with_config(
        recursion_limit=get_settings().guard.recursion_limit
    )


# Aegra가 읽는 그래프 (aegra.json)
graph = build_daily_review_graph()
