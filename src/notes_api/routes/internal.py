"""Agent 전용 내부 조회 API (``/internal/agent``). **조회만 있다.**

Agent의 ``HttpBeClient``가 부른다. 검색은 본문(질의)이 있어 POST지만 상태를 바꾸지 않는다.
쓰기 메서드를 여기에 더하면 시험(tests/api/test_api.py)이 실패한다 — Agent는 BE에 쓰지 않는다.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from notes_api.deps import AppState, app_state
from notes_api.rag import ChunkHit
from notes_api.store import Card, LearnerProfile, Note, NoteSummary, ReviewStats

PREFIX = "/internal/agent"
# 상태를 바꾸지 않는 POST(계산·검색 조회)만 이 목록에 둔다
READ_ONLY_POSTS = {f"{PREFIX}/notebooks/{{notebook_id}}/search"}

router = APIRouter(prefix=PREFIX)


class SearchIn(BaseModel):
    query: str
    k: int = Field(default=5, ge=1, le=20)


@router.get("/notebooks")
def notebook_ids(s: AppState = Depends(app_state)) -> list[str]:
    return [nb.id for nb in s.store.list_notebooks()]


@router.get("/notebooks/{notebook_id}/notes")
def list_notes(
    notebook_id: str, query: str | None = None, limit: int = Query(10, ge=1, le=50), s: AppState = Depends(app_state)
) -> list[NoteSummary]:
    return s.store.list_notes(notebook_id, query=query, limit=limit)


@router.get("/notes/{note_id}")
def get_note(note_id: str, s: AppState = Depends(app_state)) -> Note:
    return s.store.require_note(note_id)


@router.post("/notebooks/{notebook_id}/search")
def search(notebook_id: str, body: SearchIn, s: AppState = Depends(app_state)) -> list[ChunkHit]:
    s.store.get_notebook(notebook_id)  # 없는 노트북이면 404
    return s.index.search(notebook_id, body.query, body.k)


@router.get("/notebooks/{notebook_id}/cards")
def list_cards(notebook_id: str, note_id: str | None = None, s: AppState = Depends(app_state)) -> list[Card]:
    return s.store.list_cards(notebook_id, note_id)


@router.get("/notebooks/{notebook_id}/due")
def list_due(
    notebook_id: str, base_date: str, limit: int = Query(20, ge=1, le=100), s: AppState = Depends(app_state)
) -> list[Card]:
    return s.store.list_due_cards(notebook_id, base_date, limit)


@router.get("/notebooks/{notebook_id}/stats")
def stats(notebook_id: str, base_date: str, s: AppState = Depends(app_state)) -> ReviewStats:
    return s.store.review_stats(notebook_id, base_date)


@router.get("/profile")
def profile(base_date: str | None = None, s: AppState = Depends(app_state)) -> LearnerProfile:
    return s.store.get_profile(base_date)
