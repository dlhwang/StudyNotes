"""비동기 DB 세션. 연결 풀은 프로세스당 하나 (AGENTS.md §3.1).

사용::

    async with session_scope() as s:
        s.add(AuditLog(run_id=..., thread_id=..., data={...}))

그래프 노드·도구에서 직접 쓰지 않고 db/ 안의 함수에서만 쓴다.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from study_notes.config import DbSettings


def async_url(db: DbSettings) -> str:
    """postgresql://… → postgresql+asyncpg://… (sslmode는 asyncpg가 'ssl'로 받는다)."""
    url = db.dsn().replace("postgresql://", "postgresql+asyncpg://", 1)
    return url.replace("?sslmode=", "?ssl=")


@lru_cache(maxsize=1)
def get_engine() -> AsyncEngine:
    return create_async_engine(async_url(DbSettings()), pool_size=5, max_overflow=5, pool_pre_ping=True)


@lru_cache(maxsize=1)
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False)


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """한 단위 작업. 끝나면 커밋, 오류면 되돌린다."""
    async with get_sessionmaker()() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
