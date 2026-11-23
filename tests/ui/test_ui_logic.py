"""화면 로직(Streamlit 없이): SSE 읽기, 버튼 처리, 이벤트 → 화면 데이터, BE 클라이언트 왕복."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from notes_ui.actions import handle_action
from notes_ui.api import BeApi, BeApiError
from notes_ui.sse import parse_sse_lines
from notes_ui.view import turn_view
from study_notes.deps import set_deps
from tests.api.conftest import TODAY, make_test_app


def test_parse_sse_lines() -> None:
    lines = [
        'data: {"type": "orchestrator", "text": "안내"}',
        "",
        ": keep-alive",
        "data: {깨짐",
        'data: {"type": "done"}',
        'data: {"type": "agent_reply"}',
    ]
    assert list(parse_sse_lines(lines)) == [
        {"type": "orchestrator", "text": "안내"},
        {"type": "error", "text": "응답을 읽을 수 없습니다"},
    ]


class FakeApi:
    def __init__(self, fail: bool = False) -> None:
        self.accepted: list[dict[str, Any]] = []
        self.fail = fail

    def accept(self, proposal: dict[str, Any], accepted_on: str) -> dict[str, Any]:
        if self.fail:
            raise BeApiError(400, "카드가 없습니다")
        self.accepted.append(proposal)
        return {"kind": proposal["kind"], "title": "t", "applied": {"card_ids": ["C-9", "C-10"]}}


REPLY = {"proposals": [{"kind": "quiz.cards_add", "dedupe_key": "k"}]}


def test_handle_action_kinds() -> None:
    api = FakeApi()
    ask = handle_action(api, REPLY, {"kind": "ask", "label": "퀴즈", "text": "퀴즈 내줘"}, TODAY)
    assert ask.kind == "ask" and ask.ask_text == "퀴즈 내줘"
    nav = handle_action(api, REPLY, {"kind": "navigate", "target": "review"}, TODAY)
    assert nav.page == "review"
    saved = handle_action(api, REPLY, {"kind": "save_proposal", "params": {"index": 0}}, TODAY)
    assert saved.ok and saved.message == "카드 2장을 저장했습니다." and api.accepted == REPLY["proposals"]
    missing = handle_action(api, REPLY, {"kind": "save_proposal", "params": {"index": 3}}, TODAY)
    assert not missing.ok
    failed = handle_action(FakeApi(fail=True), REPLY, {"kind": "save_proposal", "params": {"index": 0}}, TODAY)
    assert not failed.ok and "카드가 없습니다" in (failed.message or "")


def test_turn_view() -> None:
    events = [
        {"type": "orchestrator", "agents": ["노트 Agent"], "text": "이 질문은 노트 Agent가 담당합니다."},
        {
            "type": "agent_reply",
            "reply": {
                "agent": "notes",
                "text": "답",
                "source": "ai",
                "prompt_version": "notes.qa.v1",
                "data": {"trace": [{"step": 1, "tool": "notes_search_chunks"}]},
                "citations": [{"title": "t", "location": "N-1"}],
            },
        },
        {
            "type": "agent_reply",
            "reply": {"agent": "review", "text": "통계", "source": "rule", "data": {"stats": {"due_today": 3}}},
        },
        {"type": "error", "text": "실패"},
    ]
    turn = turn_view(events)
    assert turn.header.startswith("이 질문은") and turn.errors == ["실패"]
    first, second = turn.replies
    assert first.label == "노트 Agent" and first.badge == "AI 답 · notes.qa.v1" and first.trace
    assert second.badge == "규칙 답(모델 없이)" and second.table[0] == {"항목": "오늘 복습", "값": 3}


@pytest.fixture
def api() -> Iterator[BeApi]:
    yield BeApi(client=TestClient(make_test_app()))
    set_deps(None)


def test_be_api_roundtrip(api: BeApi) -> None:
    assert [nb["id"] for nb in api.notebooks()] == ["NB-1", "NB-2"]
    created = api.create_note("NB-1", "새 노트", "## 소제목\n- 용어: 설명", ["t"])
    assert created["chunks"] == 1 and api.note(created["id"])["title"] == "새 노트"
    thread = api.new_thread()
    events = list(api.stream_chat(thread, "새 노트 퀴즈 내줘", "NB-1", {"base_date": TODAY}))
    turn = turn_view(events)
    (reply,) = turn.replies
    outcome = handle_action(api, reply.raw, reply.actions[0], TODAY)
    assert outcome.ok and outcome.message == "카드 1장을 저장했습니다."
    assert len(api.cards("NB-1", created["id"])) == 1
    with pytest.raises(BeApiError) as e:
        api.note("N-99")
    assert e.value.status == 404 and "노트 목록" in e.value.detail
