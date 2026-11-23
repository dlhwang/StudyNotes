"""DB 확인과 우리 테이블 마이그레이션. .env의 POSTGRES_*·AGENT_DB_SCHEMA를 쓴다.

    python -m study_notes.db check     # 접속되는지, 스키마·적용 버전
    python -m study_notes.db migrate   # Alembic: 최신 리비전까지 적용
    python -m study_notes.db sql       # DB 없이 DDL만 출력 (운영 DB 담당에게 줄 때)

``pip install -e .[postgres]``가 필요하다. Aegra 테이블은 aegra serve가 처음 뜰 때 스스로 만든다 — 여기서 다루지 않는다.
모델을 바꾼 뒤 새 리비전은 Alembic CLI로 만든다: ``alembic revision --autogenerate -m "..."``.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

try:
    from alembic import command
    from alembic.config import Config
except ImportError as e:  # postgres 묶음을 안 깔았을 때
    raise SystemExit("alembic이 없습니다: pip install -e .[postgres]") from e

from study_notes.config import DbSettings
from study_notes.db.session import async_url

ROOT = Path(__file__).resolve().parents[3]


def out(line: str) -> None:
    sys.stdout.write(line + "\n")


def _alembic_config() -> Config:
    return Config(str(ROOT / "alembic.ini"))


async def check(db: DbSettings) -> int:
    engine = create_async_engine(async_url(db))
    try:
        async with engine.connect() as conn:
            version = (await conn.execute(text("select version()"))).scalar_one()
            has_schema = (
                await conn.execute(
                    text("select exists(select 1 from information_schema.schemata where schema_name = :s)"),
                    {"s": db.schema_name},
                )
            ).scalar_one()
            applied = None
            if has_schema:
                exists = (
                    await conn.execute(
                        text(
                            "select exists(select 1 from information_schema.tables "
                            "where table_schema = :s and table_name = 'alembic_version')"
                        ),
                        {"s": db.schema_name},
                    )
                ).scalar_one()
                if exists:
                    applied = (
                        await conn.execute(text(f'select version_num from "{db.schema_name}".alembic_version'))  # noqa: S608
                    ).scalar_one_or_none()
    except Exception as e:  # 원인을 그대로 보여 준다(비밀번호는 출력하지 않는다)
        raise SystemExit(f"접속 실패: {db.describe()} — {type(e).__name__}: {e}") from e
    finally:
        await engine.dispose()
    out(f"접속됨: {db.describe()}")
    out(f"  {version}")
    out(f"  스키마 {db.schema_name}: {'있음' if has_schema else '없음'}, 적용 버전: {applied or '없음'}")
    if not applied:
        out("  → python -m study_notes.db migrate")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="ai-agent DB 확인·마이그레이션 (.env의 POSTGRES_* 사용)")
    p.add_argument("command", choices=["check", "migrate", "sql"])
    args = p.parse_args()
    db = DbSettings()
    if args.command == "check":
        return asyncio.run(check(db))
    cfg = _alembic_config()
    if args.command == "migrate":
        out(f"마이그레이션: {db.describe()}")
        command.upgrade(cfg, "head")
    else:
        command.upgrade(cfg, "head", sql=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
