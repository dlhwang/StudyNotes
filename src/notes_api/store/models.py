"""BE 데이터 모델. API 응답에 그대로 쓴다.

Agent 쪽(``study_notes.tools.be_client.protocol``)에 같은 모양의 모델이 따로 있다.
Agent 패키지는 이 패키지를 import하지 않는다 — BE와 Agent는 HTTP 약속으로만 잇는다.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Grade = Literal["again", "hard", "good", "easy"]
SummaryLength = Literal["short", "normal", "long"]
QuizDifficulty = Literal["easy", "normal", "hard"]


class Notebook(BaseModel):
    id: str = Field(description="노트북 ID. 예: NB-1")
    name: str


class Note(BaseModel):
    id: str = Field(description="노트 ID. 예: N-1")
    notebook_id: str
    title: str
    body: str
    tags: list[str] = Field(default_factory=list)
    source: str = ""
    created_at: str
    updated_at: str


class NoteSummary(BaseModel):
    id: str
    notebook_id: str
    title: str
    tags: list[str] = Field(default_factory=list)
    updated_at: str
    snippet: str = Field(description="본문 앞 120자")


class Card(BaseModel):
    id: str = Field(description="카드 ID. 예: C-1")
    note_id: str
    note_title: str
    question: str
    answer: str
    ease: float
    interval_days: int
    repetitions: int
    due_date: str = Field(description="다음 복습일 YYYY-MM-DD")
    lapses: int


class ReviewStats(BaseModel):
    """BE가 계산한 학습 통계. Agent는 이 숫자를 설명만 한다."""

    notebook_id: str
    base_date: str
    total_cards: int
    due_today: int = Field(description="due_date <= base_date")
    overdue: int = Field(description="due_date < base_date")
    new_cards: int = Field(description="한 번도 복습하지 않은 카드")
    reviewed_7d: int = Field(description="base_date 포함 최근 7일 복습 횟수")
    correct_rate_7d_pct: int | None = Field(description="최근 7일 again이 아닌 비율(%). 복습이 없으면 None")
    streak_days: int = Field(description="base_date부터 거꾸로 빠짐없이 복습한 날 수")


class WeakNote(BaseModel):
    note_id: str
    title: str
    again_count_14d: int


class LearnerProfile(BaseModel):
    """장기 메모리. 선호는 사용자가 정하고, 약한 노트는 BE가 복습 기록으로 계산한다."""

    summary_length: SummaryLength = "normal"
    quiz_difficulty: QuizDifficulty = "normal"
    weak_notes: list[WeakNote] = Field(default_factory=list)


class ProposalRecord(BaseModel):
    id: int
    dedupe_key: str
    kind: str
    subject_id: str
    title: str
    payload: dict[str, Any] = Field(default_factory=dict)
    reasons: list[str] = Field(default_factory=list)
    source: str
    status: Literal["saved", "applied"]
    created_at: str
    applied: dict[str, Any] = Field(default_factory=dict)
