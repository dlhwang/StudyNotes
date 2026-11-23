"""실행 기록을 PostgreSQL ``AGENT_DB_SCHEMA`` 스키마에 남긴다 (ORM: db/models.py).

필요한 것: ``pip install -e .[postgres]``, ``.env``의 POSTGRES_* 값, ``python -m study_notes.db migrate``.
기록 저장이 실패해도 답은 나가야 하므로 예외는 safe_record()가 삼킨다.
"""

from __future__ import annotations

from study_notes.db.models import RECORD_MODELS
from study_notes.db.session import session_scope
from study_notes.observability.recorder import Record


class PostgresRecorder:
    async def record(self, rec: Record) -> None:
        model = RECORD_MODELS[rec.kind]
        async with session_scope() as s:
            s.add(model(run_id=rec.run_id, thread_id=rec.thread_id, data=rec.data))  # type: ignore[call-arg]
