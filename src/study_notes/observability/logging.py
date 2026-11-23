"""JSON 구조화 로그. 공통 필드: run_id, thread_id, trace_id, graph, node (AGENTS.md §5).

토큰·프롬프트 원문은 로그에 쓰지 않는다. ``print``를 쓰지 않는다.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

_FIELDS = ("run_id", "thread_id", "trace_id", "graph", "node", "agent")
_ctx: ContextVar[dict[str, str]] = ContextVar("study_notes_log_ctx", default={})  # noqa: B039


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        data.update(_ctx.get())
        extra = getattr(record, "fields", None)
        if isinstance(extra, dict):
            data.update(extra)
        if record.exc_info:
            data["exc"] = self.formatException(record.exc_info)
        return json.dumps(data, ensure_ascii=False, default=str)


def setup_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger("study_notes")
    root.handlers = [handler]
    root.setLevel(level)
    root.propagate = False


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name if name.startswith("study_notes") else f"study_notes.{name}")


@contextmanager
def log_context(**values: str | None) -> Iterator[None]:
    """이 블록 안의 로그에 공통 필드를 붙인다."""
    merged = dict(_ctx.get())
    merged.update({k: v for k, v in values.items() if k in _FIELDS and v})
    token = _ctx.set(merged)
    try:
        yield
    finally:
        _ctx.reset(token)
