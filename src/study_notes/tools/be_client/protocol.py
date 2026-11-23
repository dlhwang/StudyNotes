"""BE 도구 API 약속 (학습 노트 BE ``notes_api``의 ``/internal/agent/*``).

원칙
- 숫자 계산(복습 간격, 통계, 약한 노트)은 BE가 한다. Agent는 받은 숫자를 해석하고 설명한다.
- **조회만 있다.** ai-agent는 BE에 쓰지 않는다. 제안 저장·반영은 BE의 일이다 (docs/01 §5).
  쓰기로 보이는 이름(save, submit, create …)의 메서드가 생기면 시험이 실패한다.
- ``token``은 사용자 권한으로 부를 때의 토큰이다. None이면 서비스 계정(읽기 전용)으로 부른다.
- 아래 모델은 BE 응답과 같은 모양이다. Agent 패키지는 BE 패키지를 import하지 않는다.
"""

from __future__ import annotations

from typing import Literal, Protocol

from pydantic import BaseModel, Field, SecretStr

from study_notes.core.proposal import ProposalDraft

__all__ = [
    "BeClient",
    "Card",
    "ChunkHit",
    "LearnerProfile",
    "Note",
    "NoteSummary",
    "ProposalDraft",
    "ReviewStats",
    "TaskItem",
    "WeakNote",
]


class NoteSummary(BaseModel):
    id: str
    notebook_id: str
    title: str
    tags: list[str] = Field(default_factory=list)
    updated_at: str = ""
    snippet: str = ""


class Note(BaseModel):
    id: str
    notebook_id: str
    title: str
    body: str
    tags: list[str] = Field(default_factory=list)
    source: str = ""
    created_at: str = ""
    updated_at: str = ""


class ChunkHit(BaseModel):
    """RAG 검색 결과 한 조각. 출처(노트 제목·소제목·위치)를 함께 준다."""

    note_id: str
    chunk_id: str
    notebook_id: str
    title: str
    heading: str = ""
    text: str
    position: int = 0
    score: float = Field(description="1 - 코사인 거리. 클수록 가깝다")


class Card(BaseModel):
    id: str
    note_id: str
    note_title: str = ""
    question: str
    answer: str
    ease: float = 2.5
    interval_days: int = 0
    repetitions: int = 0
    due_date: str
    lapses: int = 0


class ReviewStats(BaseModel):
    notebook_id: str
    base_date: str
    total_cards: int
    due_today: int
    overdue: int
    new_cards: int
    reviewed_7d: int
    correct_rate_7d_pct: int | None
    streak_days: int


class WeakNote(BaseModel):
    note_id: str
    title: str
    again_count_14d: int


class LearnerProfile(BaseModel):
    """장기 메모리. 요약 길이·퀴즈 난이도(사용자 선호)와 BE가 계산한 약한 노트."""

    summary_length: Literal["short", "normal", "long"] = "normal"
    quiz_difficulty: Literal["easy", "normal", "hard"] = "normal"
    weak_notes: list[WeakNote] = Field(default_factory=list)


# ── 예시 업무: 할 일 (템플릿 예시. Unit 07에서 지운다) ─────────────────


class TaskItem(BaseModel):
    id: str
    subject_id: str
    title: str
    status: Literal["open", "done"]
    due_date: str = Field(description="마감일 YYYY-MM-DD")
    owner: str = ""
    note: str = Field(default="", description="왜 생긴 할 일인지 (근거)")


class BeClient(Protocol):
    # 노트북(= subject) 목록. 예약 실행이 돈다
    async def list_subjects(self, *, token: SecretStr | None) -> list[str]: ...
    async def list_notes(
        self, notebook_id: str, *, query: str | None = None, limit: int = 10, token: SecretStr | None
    ) -> list[NoteSummary]: ...
    async def get_note(self, note_id: str, *, token: SecretStr | None) -> Note: ...
    async def search_chunks(
        self, notebook_id: str, query: str, *, k: int = 5, token: SecretStr | None
    ) -> list[ChunkHit]: ...
    async def list_cards(
        self, notebook_id: str, *, note_id: str | None = None, token: SecretStr | None
    ) -> list[Card]: ...
    async def list_due_cards(
        self, notebook_id: str, base_date: str, *, limit: int = 20, token: SecretStr | None
    ) -> list[Card]: ...
    async def get_review_stats(self, notebook_id: str, base_date: str, *, token: SecretStr | None) -> ReviewStats: ...
    async def get_learner_profile(self, *, token: SecretStr | None, base_date: str | None = None) -> LearnerProfile: ...
    # 예시 업무: 할 일
    async def list_tasks(self, subject_id: str, *, token: SecretStr | None) -> list[TaskItem]: ...
