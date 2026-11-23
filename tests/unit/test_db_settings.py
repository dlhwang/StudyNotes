"""DB 접속 설정: .env의 POSTGRES_*·AGENT_DB_SCHEMA를 읽어 접속 주소를 만든다 (DB 없이 시험)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from study_notes.config import DbSettings


def test_reads_same_env_as_aegra(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POSTGRES_HOST", "10.0.0.12")
    monkeypatch.setenv("POSTGRES_PORT", "6543")
    monkeypatch.setenv("POSTGRES_DB", "app_dev")
    monkeypatch.setenv("POSTGRES_USER", "agent user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "p@ss:w/rd")
    monkeypatch.setenv("AGENT_DB_SCHEMA", "my_agent")
    db = DbSettings(_env_file=None)  # type: ignore[call-arg]
    assert db.dsn() == "postgresql://agent%20user:p%40ss%3Aw%2Frd@10.0.0.12:6543/app_dev"
    assert db.schema_name == "my_agent"
    assert "p@ss" not in db.describe()


def test_rejects_unsafe_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_DB_SCHEMA", "agent; drop table x")
    with pytest.raises(ValidationError):
        DbSettings(_env_file=None)  # type: ignore[call-arg]
