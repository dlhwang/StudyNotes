"""가짜 BE가 약속대로 동작하는지 (Agent 시험의 바탕)."""

from __future__ import annotations

import pytest

from study_notes.core.errors import ToolInputError
from study_notes.tools.fakes.be import DEMO_DATE, FakeBeClient


async def test_fake_notes_and_search() -> None:
    be = FakeBeClient()
    assert await be.list_subjects(token=None) == ["NB-1", "NB-2"]
    assert [n.id for n in await be.list_notes("NB-1", token=None)] == ["N-1", "N-2", "N-3"]
    assert [n.id for n in await be.list_notes("NB-1", query="체크포인터", token=None)] == ["N-2"]
    hits = await be.search_chunks("NB-1", "체크포인터가 뭐야", k=3, token=None)
    assert hits[0].note_id == "N-2" and hits[0].heading == "체크포인터" and hits[0].score > 0
    assert all(h.notebook_id == "NB-1" for h in hits)
    assert await be.search_chunks("NB-1", " ", token=None) == []


async def test_fake_cards_stats_profile() -> None:
    be = FakeBeClient()
    due = await be.list_due_cards("NB-1", DEMO_DATE, token=None)
    assert [c.id for c in due] == ["C-1", "C-2", "C-3"]
    assert [c.id for c in await be.list_cards("NB-1", note_id="N-2", token=None)] == ["C-3", "C-4"]
    stats = await be.get_review_stats("NB-1", "2026-11-24", token=None)
    assert stats.base_date == "2026-11-24" and stats.correct_rate_7d_pct == 56
    profile = await be.get_learner_profile(token=None)
    assert profile.weak_notes[0].note_id == "N-2"


async def test_fake_errors_have_hints() -> None:
    be = FakeBeClient()
    with pytest.raises(ToolInputError) as e:
        await be.get_note("N-99", token=None)
    assert "노트 목록" in e.value.hint
    with pytest.raises(ToolInputError):
        await be.list_notes("NB-9", token=None)
