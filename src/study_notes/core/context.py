"""요청 정보. 누가, 무엇에 대해, 어느 화면을 보며 물었는가.

- 사용자 정보는 Aegra 인증 핸들러가 ``config["configurable"]["langgraph_auth_user"]``에 넣는다.
- 대상(subject)·화면은 BE가 실행을 만들 때 ``context``로 넘긴다 (``AgentContext``).
- 토큰은 State·로그·프롬프트에 넣지 않는다. ``RequestInfo.be_token``은 BE 클라이언트만 읽는다.
  토큰 전달 방식은 프로젝트마다 BE와 정한다 (docs/01 §10).
- ai-agent는 BE에 조회만 한다. 쓰기·승인은 BE의 일이다 (docs/01 §5).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from langchain_core.runnables import RunnableConfig
from pydantic import SecretStr


@dataclass
class AgentContext:
    """그래프의 ``context_schema``. BE가 실행마다 넘기는 값."""

    # 질문이 가리키는 대상. 예: 프로젝트 코드, 주문 번호. 프로젝트에 맞는 이름으로 바꿔도 된다
    subject_id: str | None = None
    # 화면 식별 정보: screen_id, state 등
    screen: dict[str, Any] = field(default_factory=dict)
    trace_id: str | None = None


@dataclass(frozen=True)
class UserInfo:
    user_id: str
    display_name: str = ""
    role: str = "user"  # 프로젝트에서 정한다. 예약 실행은 service


@dataclass(frozen=True)
class RequestInfo:
    """노드·도구가 쓰는 요청 정보 묶음."""

    user: UserInfo
    thread_id: str
    run_id: str
    graph: str
    subject_id: str | None = None
    screen: dict[str, Any] = field(default_factory=dict)
    be_token: SecretStr | None = field(default=None, repr=False)


SERVICE_USER = UserInfo(user_id="svc-agent", display_name="예약 실행", role="service")


def request_info(config: RunnableConfig, context: AgentContext | None, graph: str) -> RequestInfo:
    """RunnableConfig와 실행 context에서 RequestInfo를 만든다."""
    conf: dict[str, Any] = dict(config.get("configurable") or {})
    auth_user: dict[str, Any] = dict(conf.get("langgraph_auth_user") or {})
    user = UserInfo(
        user_id=str(auth_user.get("identity") or conf.get("user_id") or "anonymous"),
        display_name=str(auth_user.get("display_name") or ""),
        role=str(auth_user.get("role") or "user"),
    )
    token_raw = auth_user.get("be_token")
    ctx = context or AgentContext()
    subject_id = ctx.subject_id or conf.get("subject_id")
    return RequestInfo(
        user=user,
        thread_id=str(conf.get("thread_id") or ""),
        run_id=str(config.get("run_id") or conf.get("run_id") or (config.get("metadata") or {}).get("run_id") or ""),
        graph=graph,
        subject_id=str(subject_id) if subject_id else None,
        screen=dict(ctx.screen or conf.get("screen") or {}),
        be_token=SecretStr(str(token_raw)) if token_raw else None,
    )
