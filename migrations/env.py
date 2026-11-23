"""Alembic 실행 환경. 우리 스키마(AGENT_DB_SCHEMA)만 보고, Aegra 테이블(보통 public)은 보지도 만지지도 않는다."""

from __future__ import annotations

import asyncio

from alembic import context
from sqlalchemy import pool, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from study_notes.config import DbSettings
from study_notes.db.models import SCHEMA, Base
from study_notes.db.session import async_url

target_metadata = Base.metadata


def include_name(name: str | None, type_: str, parent_names: object) -> bool:
    """autogenerate가 비교할 대상: 우리 스키마만. 다른 스키마의 테이블(Aegra 등)은 무시한다."""
    if type_ == "schema":
        return name == SCHEMA
    return True


def _configure(**kw: object) -> None:
    context.configure(
        target_metadata=target_metadata,
        include_schemas=True,
        include_name=include_name,
        version_table_schema=SCHEMA,
        compare_type=True,
        **kw,  # type: ignore[arg-type]
    )


def run_offline() -> None:
    """DB 없이 DDL만 출력한다 (python -m study_notes.db sql)."""
    _configure(url=async_url(DbSettings()).replace("+asyncpg", ""), literal_binds=True)
    with context.begin_transaction():
        context.execute(f'CREATE SCHEMA IF NOT EXISTS "{SCHEMA}"')
        context.run_migrations()


def _run(connection: Connection) -> None:
    connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{SCHEMA}"'))
    _configure(connection=connection)
    with context.begin_transaction():
        context.run_migrations()


async def run_online() -> None:
    engine = create_async_engine(async_url(DbSettings()), poolclass=pool.NullPool)
    async with engine.connect() as conn:
        await conn.run_sync(_run)
        await conn.commit()
    await engine.dispose()


if context.is_offline_mode():
    run_offline()
else:
    asyncio.run(run_online())
