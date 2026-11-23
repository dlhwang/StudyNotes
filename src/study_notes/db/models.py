"""우리 테이블 (SQLAlchemy ORM). Aegra 테이블(thread·run·체크포인트·cron 등)은 여기 두지 않는다.

- 모든 테이블은 ``.env``의 ``AGENT_DB_SCHEMA`` 스키마에 만든다.
- 테이블을 추가·변경하면 Alembic 리비전을 만든다 (docs/02 §4.7):
    alembic revision --autogenerate -m "무엇을 바꿨는지"
    python -m study_notes.db migrate
- 운영 DB에 줄 DDL은 ``python -m study_notes.db sql`` 로 뽑는다.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, MetaData, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from study_notes.config import DbSettings

SCHEMA = DbSettings().schema_name

# 제약·인덱스 이름 규칙. Alembic이 바뀐 것을 정확히 찾게 한다
NAMING = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(schema=SCHEMA, naming_convention=NAMING)


class _RecordMixin:
    """실행 기록 공통 칸. 자주 묻는 값이 생기면 data에서 열로 뺀다."""

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(100), index=True)
    thread_id: Mapped[str] = mapped_column(String(255), default="", server_default="")
    data: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class RunRecord(_RecordMixin, Base):
    """실행 한 건 (그래프 시작·끝)."""

    __tablename__ = "runs"


class LlmCall(_RecordMixin, Base):
    """모델 호출: 역할 키, 프롬프트 ID, 토큰, 지연."""

    __tablename__ = "llm_calls"


class ToolCall(_RecordMixin, Base):
    """도구 호출: 도구명, 인자 해시, 결과, 지연."""

    __tablename__ = "tool_calls"


class EvalResult(_RecordMixin, Base):
    """평가 질문 결과 (docs/01 §7.3)."""

    __tablename__ = "eval_results"


# 기록 종류 → 테이블 (observability/recorder.py의 RecordKind)
RECORD_MODELS: dict[str, type[_RecordMixin]] = {
    "run": RunRecord,
    "llm_call": LlmCall,
    "tool_call": ToolCall,
    "eval": EvalResult,
}
