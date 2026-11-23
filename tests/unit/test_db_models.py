"""ORM 모델과 Alembic 리비전이 맞는지, Aegra 테이블을 건드리지 않는지 (DB 없이 시험)."""

from __future__ import annotations

import io
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from study_notes.db.models import RECORD_MODELS, SCHEMA, Base

ROOT = Path(__file__).resolve().parents[2]


def test_models_live_in_our_schema() -> None:
    assert Base.metadata.tables
    assert all(t.schema == SCHEMA for t in Base.metadata.tables.values())
    assert set(RECORD_MODELS) == {"run", "llm_call", "tool_call", "eval"}


def test_offline_ddl_matches_models_and_skips_aegra() -> None:
    alembic = pytest.importorskip("alembic")
    from alembic import command
    from alembic.config import Config

    assert alembic
    buf = io.StringIO()
    with redirect_stdout(buf):
        command.upgrade(Config(str(ROOT / "alembic.ini")), "head", sql=True)
    ddl = buf.getvalue()
    assert f'CREATE SCHEMA IF NOT EXISTS "{SCHEMA}"' in ddl
    assert f"CREATE TABLE {SCHEMA}.alembic_version" in ddl
    for table in Base.metadata.tables.values():
        assert f"CREATE TABLE {SCHEMA}.{table.name} (" in ddl, table.name
        for idx in table.indexes:
            assert f"CREATE INDEX {idx.name} ON {SCHEMA}.{table.name}" in ddl, idx.name
    # Aegra 테이블은 만들지 않는다
    for aegra_table in ("thread", "runs ", "checkpoints", "assistant", "crons"):
        assert f"CREATE TABLE public.{aegra_table}" not in ddl
