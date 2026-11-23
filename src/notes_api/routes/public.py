"""공개 API — Streamlit 화면이 부른다. 저장·반영은 여기서만 한다."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, Field

from notes_api.deps import AppState, app_state
from notes_api.rag import reindex_all
from notes_api.store import Card, Grade, LearnerProfile, Note, Notebook, NoteSummary, ProposalRecord, ReviewStats
from notes_api.store.models import QuizDifficulty, SummaryLength

router = APIRouter()


class NotebookIn(BaseModel):
    name: str


class NoteIn(BaseModel):
    title: str
    body: str
    tags: list[str] = Field(default_factory=list)
    source: str = ""


class NoteOut(Note):
    chunks: int = Field(default=0, description="이번 저장으로 적재된 청크 수")


class ReviewIn(BaseModel):
    grade: Grade
    reviewed_on: str


class ProfileIn(BaseModel):
    summary_length: SummaryLength | None = None
    quiz_difficulty: QuizDifficulty | None = None


class AcceptIn(BaseModel):
    proposal: dict[str, Any]
    accepted_on: str | None = None


class DailyPlanOut(BaseModel):
    plan: ProposalRecord | None
    cards: list[Card]


@router.get("/health")
def health(s: AppState = Depends(app_state)) -> dict[str, Any]:
    return {
        "status": "ok",
        "notes": len(s.store.all_notes()),
        "chunks": s.index.count(),
        "agent": s.settings.agent_mode,
    }


@router.get("/notebooks")
def list_notebooks(s: AppState = Depends(app_state)) -> list[Notebook]:
    return s.store.list_notebooks()


@router.post("/notebooks")
def create_notebook(body: NotebookIn, s: AppState = Depends(app_state)) -> Notebook:
    return s.store.create_notebook(body.name)


@router.get("/notebooks/{notebook_id}/notes")
def list_notes(
    notebook_id: str, query: str | None = None, limit: int = Query(50, ge=1, le=200), s: AppState = Depends(app_state)
) -> list[NoteSummary]:
    return s.store.list_notes(notebook_id, query=query, limit=limit)


@router.post("/notebooks/{notebook_id}/notes")
def create_note(notebook_id: str, body: NoteIn, s: AppState = Depends(app_state)) -> NoteOut:
    note = s.store.create_note(notebook_id, body.title, body.body, body.tags, body.source)
    return NoteOut(**note.model_dump(), chunks=s.index.upsert_note(note))


@router.get("/notes/{note_id}")
def get_note(note_id: str, s: AppState = Depends(app_state)) -> Note:
    return s.store.require_note(note_id)


@router.put("/notes/{note_id}")
def update_note(note_id: str, body: NoteIn, s: AppState = Depends(app_state)) -> NoteOut:
    note = s.store.update_note(note_id, title=body.title, body=body.body, tags=body.tags, source=body.source)
    return NoteOut(**note.model_dump(), chunks=s.index.upsert_note(note))


@router.delete("/notes/{note_id}", status_code=204)
def delete_note(note_id: str, s: AppState = Depends(app_state)) -> Response:
    s.store.delete_note(note_id)
    s.index.delete_note(note_id)
    return Response(status_code=204)


@router.get("/notebooks/{notebook_id}/cards")
def list_cards(notebook_id: str, note_id: str | None = None, s: AppState = Depends(app_state)) -> list[Card]:
    return s.store.list_cards(notebook_id, note_id)


@router.get("/notebooks/{notebook_id}/due")
def list_due(
    notebook_id: str, base_date: str, limit: int = Query(20, ge=1, le=200), s: AppState = Depends(app_state)
) -> list[Card]:
    return s.store.list_due_cards(notebook_id, base_date, limit)


@router.post("/cards/{card_id}/review")
def review_card(card_id: str, body: ReviewIn, s: AppState = Depends(app_state)) -> Card:
    return s.store.record_review(card_id, body.grade, body.reviewed_on)


@router.get("/notebooks/{notebook_id}/stats")
def stats(notebook_id: str, base_date: str, s: AppState = Depends(app_state)) -> ReviewStats:
    return s.store.review_stats(notebook_id, base_date)


@router.get("/profile")
def get_profile(base_date: str | None = None, s: AppState = Depends(app_state)) -> LearnerProfile:
    return s.store.get_profile(base_date)


@router.put("/profile")
def put_profile(body: ProfileIn, s: AppState = Depends(app_state)) -> LearnerProfile:
    return s.store.set_preferences(body.summary_length, body.quiz_difficulty)


@router.post("/proposals/accept")
def accept_proposal(body: AcceptIn, s: AppState = Depends(app_state)) -> ProposalRecord:
    """사용자가 버튼(save_proposal)을 눌러 수락한 제안을 저장·반영한다. 같은 dedupe_key는 한 번만."""
    return s.store.accept_proposal(body.proposal, body.accepted_on or s.store.today())


@router.get("/proposals")
def list_proposals(
    subject_id: str | None = None, kind: str | None = None, s: AppState = Depends(app_state)
) -> list[ProposalRecord]:
    return s.store.list_proposals(subject_id, kind)


@router.get("/notebooks/{notebook_id}/daily-plan")
def daily_plan(notebook_id: str, base_date: str, s: AppState = Depends(app_state)) -> DailyPlanOut:
    plan = s.store.get_daily_plan(notebook_id, base_date)
    cards: list[Card] = []
    if plan is not None:
        for cid in plan.payload.get("card_ids") or []:
            card = s.store.get_card(str(cid))
            if card is not None:
                cards.append(card)
    return DailyPlanOut(plan=plan, cards=cards)


@router.post("/admin/reindex")
def reindex(s: AppState = Depends(app_state)) -> dict[str, int]:
    return {"chunks": reindex_all(s.index, s.store.all_notes())}
