"""실행 기록. 한 실행 = 하나의 run_id 로 로그와 PostgreSQL 기록을 잇는다 .

- ``LogRecorder``: JSON 로그로만 남긴다(기본).
- ``MemoryRecorder``: 시험용. 남긴 것을 목록으로 들고 있다.
- ``PostgresRecorder``: ``agent`` 스키마 테이블에 남긴다 (study_notes.db.recorder).

기록 저장이 실패해도 사용자 답은 나가야 한다. 기록기는 예외를 밖으로 던지지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from study_notes.observability.logging import get_logger

log = get_logger("recorder")

RecordKind = Literal["run", "llm_call", "tool_call", "eval"]


@dataclass
class Record:
    kind: RecordKind
    run_id: str
    thread_id: str
    data: dict[str, Any] = field(default_factory=dict)


class RunRecorder(Protocol):
    async def record(self, rec: Record) -> None: ...


class LogRecorder:
    async def record(self, rec: Record) -> None:
        log.info(rec.kind, extra={"fields": {"record": rec.kind, "run_id": rec.run_id, **rec.data}})


class MemoryRecorder:
    def __init__(self) -> None:
        self.records: list[Record] = []

    async def record(self, rec: Record) -> None:
        self.records.append(rec)

    def of(self, kind: RecordKind) -> list[Record]:
        return [r for r in self.records if r.kind == kind]


async def safe_record(recorder: RunRecorder, rec: Record) -> None:
    """기록 실패가 답을 막지 않게 한다."""
    try:
        await recorder.record(rec)
    except Exception:  # 기록은 부가 기능이다
        log.exception("실행 기록 저장 실패", extra={"fields": {"record": rec.kind}})
