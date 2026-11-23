"""ID와 중복 방지 키 만들기.

중복 방지 키는 몇 번을 다시 실행해도 같은 값이 나와야 한다. 무작위 값·시각을 쓰지 않는다.
BE는 이 키에 유니크 제약을 걸어 같은 제안이 두 번 생기지 않게 한다 (docs/01 §5).
"""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

_MAX_THREAD_ID = 255


def new_thread_id(entry: str, user_id: str) -> str:
    """thread_id 형식: ``{진입점}:{사용자ID}:{uuid}`` (AGENTS.md §3)."""
    thread_id = f"{entry}:{user_id}:{uuid.uuid4()}"
    if len(thread_id) > _MAX_THREAD_ID:
        raise ValueError("thread_id는 255자를 넘을 수 없습니다")
    return thread_id


def dedupe_key(*parts: str) -> str:
    """같은 재료면 언제나 같은 키. 예: ``dedupe_key("overdue", subject_id, task_id, base_date)``."""
    if not parts or any(not p for p in parts):
        raise ValueError("중복 방지 키 재료가 비어 있습니다")
    raw = "\x1f".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:40]


def args_hash(args: Any) -> str:
    """실행 기록에 남길 인자 해시. 원문(개인정보·금액 상세)을 남기지 않는다 (AGENTS.md §6)."""
    data = json.dumps(args, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()[:16]
