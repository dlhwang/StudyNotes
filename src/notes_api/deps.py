"""BE 앱 상태(저장소·색인·설정). 라우트는 ``Depends(app_state)``로 받는다."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import Request

from notes_api.config import ApiSettings
from notes_api.rag import NoteIndex
from notes_api.store import Store


@dataclass
class AppState:
    settings: ApiSettings
    store: Store
    index: NoteIndex
    # Agent 호출 중계 (Unit 10에서 채운다)
    bridge: Any = None


def app_state(request: Request) -> AppState:
    state: AppState | None = getattr(request.app.state, "notes", None)
    if state is None:
        raise RuntimeError("BE가 아직 준비되지 않았습니다")
    return state
