"""하위 Agent가 돌려주는 답과 SSE ``custom`` 이벤트 형식 (docs/01 §3.3).

ai-agent는 승인을 다루지 않는다. 쓰기가 필요한 일은 답에 제안 초안(proposals)과 버튼(actions)을 담아 돌려주고,
버튼을 누른 뒤의 저장·승인·반영은 BE가 한다.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from study_notes.core.proposal import ProposalDraft

EVENT_SCHEMA_VERSION = 1


class UiAction(BaseModel):
    """답 아래 붙는 버튼. 누른 뒤의 처리는 FE·BE가 한다.

    kind
    - navigate: FE가 화면 이동 (target = 화면 키)
    - ask: FE가 text를 다음 질문으로 보냄
    - save_proposal: BE가 이 답의 proposals[params.index]를 저장
    - backend: BE가 params.action으로 정한 일을 처리 (예: 기안 화면 열기). 이름은 BE와 맞춘다
    """

    kind: Literal["navigate", "ask", "save_proposal", "backend"]
    label: str
    target: str | None = None
    text: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)


class Citation(BaseModel):
    """답의 근거. 문서 출처나 BE 데이터 위치."""

    title: str
    location: str = ""


class AgentReply(BaseModel):
    agent: str
    text: str
    # ai: 모델이 쓴 답 / rule: 규칙으로 만든 답
    source: Literal["ai", "rule"] = "rule"
    actions: list[UiAction] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    # 저장은 BE가 한다. 사용자가 save_proposal 버튼을 누를 때
    proposals: list[ProposalDraft] = Field(default_factory=list)
    # 화면이 표·숫자로 그릴 데이터. 요약만 넣는다(원문 X)
    data: dict[str, Any] = Field(default_factory=dict)
    prompt_version: str | None = None


class AgentResult(BaseModel):
    reply: AgentReply


# ── SSE custom 이벤트 (stream_mode="custom") ─────────────────────────


class OrchestratorEvent(BaseModel):
    type: Literal["orchestrator"] = "orchestrator"
    schema_version: int = EVENT_SCHEMA_VERSION
    agents: list[str]
    text: str


class AgentReplyEvent(BaseModel):
    type: Literal["agent_reply"] = "agent_reply"
    schema_version: int = EVENT_SCHEMA_VERSION
    reply: AgentReply
