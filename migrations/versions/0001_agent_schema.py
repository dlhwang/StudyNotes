"""우리 테이블 처음 만들기: 실행 기록·LLM 호출·도구 호출·평가

리비전: 0001
이전:
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from study_notes.db.models import SCHEMA

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ("runs", "llm_calls", "tool_calls", "eval_results")


def upgrade() -> None:
    for name in TABLES:
        op.create_table(
            name,
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("run_id", sa.String(length=100), nullable=False),
            sa.Column("thread_id", sa.String(length=255), server_default="", nullable=False),
            sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.PrimaryKeyConstraint("id", name=f"pk_{name}"),
            schema=SCHEMA,
        )
        op.create_index(f"ix_{name}_run_id", name, ["run_id"], schema=SCHEMA)
        op.create_index(f"ix_{name}_created_at", name, ["created_at"], schema=SCHEMA)


def downgrade() -> None:
    for name in reversed(TABLES):
        op.drop_table(name, schema=SCHEMA)
