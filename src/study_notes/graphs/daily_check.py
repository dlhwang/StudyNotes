"""daily_check 그래프 — 예약 실행 예시. 마감이 지난 할 일을 찾아 알림 제안 초안을 돌려준다 (docs/01 §6).

evaluate → 끝

- BE가 예약 시각에 이 그래프를 부르고, 결과의 ``proposals``를 받아 저장한다. ai-agent는 BE에 쓰지 않는다.
- 판정은 agents/tasks/rules.py의 overdue_notices(). 사람이 없으므로 읽기 전용 서비스 계정으로 조회한다.
- 초안마다 중복 방지 키가 있어, 같은 날 두 번 돌아도 BE가 한 번만 저장하면 된다.
"""

from __future__ import annotations

from typing import Any, TypedDict, cast

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.types import Checkpointer

from study_notes.agents.tasks import TasksAgent
from study_notes.agents.tasks.rules import overdue_notices
from study_notes.agents.tasks.tools import NoArgs, SubjectArgs
from study_notes.config import get_settings
from study_notes.deps import get_deps
from study_notes.graphs.scheduled import service_request, service_runner
from study_notes.observability.logging import get_logger
from study_notes.tools.be_client.protocol import TaskItem

GRAPH = "daily_check"
log = get_logger("graphs.daily_check")


class DailyCheckState(TypedDict, total=False):
    base_date: str  # 입력: 기준일 YYYY-MM-DD
    subject_ids: list[str] | None  # 입력: 없으면 전체
    proposals: list[dict[str, Any]]  # 출력: ProposalDraft (BE가 저장)


async def evaluate(state: DailyCheckState, config: RunnableConfig) -> dict[str, Any]:
    deps, req = get_deps(), service_request(config, GRAPH)
    runner = service_runner(TasksAgent, req, deps)
    subjects = state.get("subject_ids") or cast(list[str], await runner.call("tasks_list_subjects", NoArgs()))
    proposals = []
    for sid in subjects:
        tasks = cast(list[TaskItem], await runner.call("tasks_list_items", SubjectArgs(subject_id=sid)))
        proposals += [p.model_dump() for p in overdue_notices(tasks, state["base_date"])]
    log.info("예약 점검 완료", extra={"fields": {"subjects": len(subjects), "proposals": len(proposals)}})
    return {"proposals": proposals}


def build_daily_check_graph(checkpointer: Checkpointer = None) -> Any:
    g = StateGraph(DailyCheckState)
    g.add_node("evaluate", evaluate)
    g.add_edge(START, "evaluate")
    g.add_edge("evaluate", END)
    return g.compile(checkpointer=checkpointer, name=GRAPH).with_config(
        recursion_limit=get_settings().guard.recursion_limit
    )


graph = build_daily_check_graph()
