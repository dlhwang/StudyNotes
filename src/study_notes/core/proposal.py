"""제안 초안 — ai-agent가 만들어 BE에 넘기는 것 (docs/01 §5).

ai-agent는 BE에 쓰지 않는다. 제안을 저장하고 승인·반영하는 것은 모두 BE다.
- 채팅: 답(``AgentReply.proposals``)에 담아 돌려주고, 사용자가 버튼을 누르면 BE가 저장한다.
- 예약 실행: 그래프 출력(``proposals``)으로 돌려주고, 실행을 부른 BE가 저장한다.

``dedupe_key``는 같은 계기로 몇 번을 다시 돌려도 같은 값이다. BE는 이 값에 유니크 제약을 걸어 중복을 막는다.
업무마다 다른 내용은 ``payload``에 넣는다. 형식이 굳으면 프로젝트에서 이 클래스를 상속해 칸을 늘려도 된다.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ProposalDraft(BaseModel):
    """제안 한 건 (BE와 맞출 약속의 중심)."""

    kind: str = Field(description="제안 종류. BE가 이 값으로 처리 방법을 고른다. 예: task.overdue_notice")
    subject_id: str = Field(description="무엇에 대한 제안인가. 예: 프로젝트 코드, 주문 번호")
    title: str
    payload: dict[str, Any] = Field(default_factory=dict, description="업무별 내용. 숫자는 BE가 계산한 값만")
    reasons: list[str] = Field(default_factory=list, description="판단 근거 요약")
    source: Literal["agent", "chat"] = Field(default="agent", description="agent: 예약 실행 / chat: 대화")
    source_ref: str | None = Field(default=None, description="계기가 된 BE 데이터 ID (예약 실행)")
    dedupe_key: str = Field(description="중복 방지 키. 같은 계기·같은 내용이면 같은 값")
