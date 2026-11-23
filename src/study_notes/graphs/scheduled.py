"""예약 그래프 공통. 사람 없는 실행이라 읽기 전용 서비스 계정으로 BE를 조회한다 (AGENTS.md §4.5).

예약 그래프는 BE가 부르고, 결과(제안 초안)를 돌려받아 BE가 저장한다.
ai-agent는 BE에 쓰지 않는다 (docs/01 §5). 서비스 계정 토큰은 설정 ``STUDY_NOTES_BE__SERVICE_TOKEN``.
"""

from __future__ import annotations

from langchain_core.runnables import RunnableConfig

from study_notes.agents.base import BaseAgent
from study_notes.core.context import SERVICE_USER, RequestInfo
from study_notes.deps import Deps
from study_notes.tools.guards import ToolRunner


def service_request(config: RunnableConfig, graph: str) -> RequestInfo:
    conf = dict(config.get("configurable") or {})
    return RequestInfo(
        user=SERVICE_USER,
        thread_id=str(conf.get("thread_id") or ""),
        run_id=str(config.get("run_id") or conf.get("run_id") or ""),
        graph=graph,
    )


def service_runner(agent: type[BaseAgent], req: RequestInfo, deps: Deps) -> ToolRunner:
    return ToolRunner(
        agent=agent.name,
        request=req,
        be=deps.be,
        recorder=deps.recorder,
        max_calls=10_000,  # 예약 실행은 여러 대상을 돈다. 상한은 입력 건수로 조절한다
    )
