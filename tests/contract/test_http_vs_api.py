"""계약 시험: Agent의 HttpBeClient가 실제 BE 앱(notes_api)의 내부 조회 API와 맞물리는지.

네트워크 없이 httpx ASGI 전송으로 같은 프로세스의 BE 앱을 부른다.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest

from study_notes.config import BeSettings
from study_notes.core.errors import ToolInputError
from study_notes.tools.be_client.http import HttpBeClient
from tests.api.conftest import TODAY, make_test_app


@pytest.fixture
async def be() -> AsyncIterator[HttpBeClient]:
    app = make_test_app()
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://be/internal/agent")
    yield HttpBeClient(BeSettings(read_retries=0), client=client)
    await client.aclose()


async def test_every_read_method_against_real_api(be: HttpBeClient) -> None:
    assert await be.list_subjects(token=None) == ["NB-1", "NB-2"]
    notes = await be.list_notes("NB-1", query="체크포인터", limit=3, token=None)
    assert notes[0].id == "N-2" and notes[0].snippet
    note = await be.get_note("N-1", token=None)
    assert note.title == "StateGraph 기초" and "리듀서" in note.body
    hits = await be.search_chunks("NB-1", "체크포인터가 뭐야", k=3, token=None)
    assert hits[0].note_id == "N-2" and hits[0].title == "체크포인터와 메모리" and 0 < hits[0].score <= 1
    cards = await be.list_cards("NB-1", note_id="N-1", token=None)
    assert len(cards) == 4 and cards[0].note_title == "StateGraph 기초"
    due = await be.list_due_cards("NB-1", TODAY, limit=50, token=None)
    assert due and all(c.due_date <= TODAY for c in due)
    stats = await be.get_review_stats("NB-1", TODAY, token=None)
    assert stats.total_cards == 7 and stats.correct_rate_7d_pct == 56
    profile = await be.get_learner_profile(token=None, base_date=TODAY)
    assert profile.summary_length == "normal" and profile.weak_notes[0].note_id == "N-2"


async def test_not_found_becomes_tool_input_error(be: HttpBeClient) -> None:
    with pytest.raises(ToolInputError) as e:
        await be.get_note("N-99", token=None)
    assert "노트 목록" in e.value.hint
    with pytest.raises(ToolInputError):
        await be.list_due_cards("NB-1", "어제", token=None)
