"""SSE 줄 읽기. BE ``/chat/stream``은 이벤트마다 ``data: {json}`` 한 줄을 보낸다."""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from typing import Any


def parse_sse_lines(lines: Iterable[str]) -> Iterator[dict[str, Any]]:
    """``data:`` 줄만 JSON으로 읽는다. ``{"type": "done"}``을 만나면 멈춘다. 깨진 줄은 error 이벤트로."""
    for raw in lines:
        line = raw.strip()
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        try:
            event = json.loads(payload)
        except json.JSONDecodeError:
            yield {"type": "error", "text": "응답을 읽을 수 없습니다"}
            continue
        if not isinstance(event, dict):
            continue
        if event.get("type") == "done":
            return
        yield event
