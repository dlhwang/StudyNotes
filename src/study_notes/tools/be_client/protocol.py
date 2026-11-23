"""BE 도구 API 약속.

BE가 OpenAPI를 내면 그것에서 만든 클라이언트로 바꾸고, 이 ``BeClient`` 약속은 그 클라이언트를 감싸는
얇은 층으로 남긴다 (AGENTS.md §4.1, §4.6).

원칙
- 숫자 계산(합계, 한도 대조, 시뮬레이션)은 BE가 한다. Agent는 받은 숫자를 해석하고 설명한다.
- **조회만 있다.** ai-agent는 BE에 쓰지 않는다. 제안 저장·승인·반영은 BE의 일이다 (docs/01 §5).
  쓰기로 보이는 이름(save, submit, create …)의 메서드가 생기면 시험이 실패한다.
- ``token``은 사용자 권한으로 부를 때의 토큰이다. None이면 서비스 계정(읽기 전용)으로 부른다.

아래 ``TaskItem``·메서드는 예시 Agent(agents/tasks)용이다. 프로젝트 업무에 맞게 바꾼다.
"""

from __future__ import annotations

from typing import Literal, Protocol

from pydantic import BaseModel, Field, SecretStr

from study_notes.core.proposal import ProposalDraft

__all__ = ["BeClient", "ProposalDraft", "TaskItem"]


# ── 예시 업무: 할 일 ─────────────────────────────────────────────────


class TaskItem(BaseModel):
    id: str
    subject_id: str
    title: str
    status: Literal["open", "done"]
    due_date: str = Field(description="마감일 YYYY-MM-DD")
    owner: str = ""
    note: str = Field(default="", description="왜 생긴 할 일인지 (근거)")


class BeClient(Protocol):
    # 예시 업무: 할 일
    async def list_tasks(self, subject_id: str, *, token: SecretStr | None) -> list[TaskItem]: ...
    # 예약 실행이 돌 대상 목록
    async def list_subjects(self, *, token: SecretStr | None) -> list[str]: ...
