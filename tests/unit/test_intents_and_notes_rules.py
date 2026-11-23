from __future__ import annotations

import pytest

from study_notes.agents.notes.rules import excerpt, key_points, resolve_note_id, search_query
from study_notes.agents.registry import all_intents, check_registry
from study_notes.core.ids import dedupe_key
from study_notes.orchestrator.intents import IntentSpec, classify_by_rules
from study_notes.tools.be_client.protocol import ChunkHit, NoteSummary
from study_notes.tools.fakes.be import FakeBeClient


@pytest.mark.parametrize(
    ("text", "intents"),
    [
        ("StateGraph 기초 요약해줘", ["note_summary"]),
        ("그 노트 핵심만 다시", ["note_summary"]),
        ("LangGraph 노트 찾아줘", ["note_search"]),
        ("노트 목록 보여줘", ["note_search"]),
        ("체크포인터가 뭐야?", ["note_qa"]),
        ("동시성과 병렬성 차이 알려줘", ["note_qa"]),
        ("안녕하세요", []),
    ],
)
def test_classify_by_rules(text: str, intents: list[str]) -> None:
    assert classify_by_rules(text, all_intents())[: len(intents) or None] == intents


def test_registry_has_one_owner_per_intent() -> None:
    assert check_registry() == []


def test_intent_name_rule() -> None:
    with pytest.raises(ValueError):
        IntentSpec("Note-Search", "x")


def test_dedupe_key_is_stable() -> None:
    assert dedupe_key("t1", "p1") == dedupe_key("t1", "p1")
    assert dedupe_key("t1", "p1") != dedupe_key("t1", "p2")
    with pytest.raises(ValueError):
        dedupe_key("t1", "")


NOTES = [
    NoteSummary(id="N-1", notebook_id="NB-1", title="StateGraph 기초"),
    NoteSummary(id="N-2", notebook_id="NB-1", title="체크포인터와 메모리"),
]


@pytest.mark.parametrize(
    ("text", "screen", "focus", "expected"),
    [
        ("체크포인터와 메모리 요약해줘", "N-1", ["N-1"], "N-2"),  # 제목이 가장 먼저
        ("이 노트 요약해줘", "N-1", ["N-2"], "N-1"),  # "이 노트" = 보고 있는 노트
        ("그 노트 핵심만 다시", "N-1", ["N-2"], "N-2"),  # "그 노트" = 대화 메모리
        ("요약해줘", None, ["N-2"], "N-2"),
        ("요약해줘", None, [], None),
    ],
)
def test_resolve_note_id(text: str, screen: str | None, focus: list[str], expected: str | None) -> None:
    assert resolve_note_id(text, NOTES, screen, focus) == expected


def test_search_query_strips_request_words() -> None:
    assert search_query("체크포인터가 뭐야?") == "체크포인터가"
    assert search_query("LangGraph 노트 찾아줘") == "LangGraph"
    assert search_query("노트 목록 보여줘") == ""


def test_key_points_and_excerpt() -> None:
    body = FakeBeClient().notes[0].body
    points = key_points(body, 4)
    assert points[0].startswith("StateGraph는 상태 스키마를 정하고")
    assert points[1].startswith("add_conditional_edges로")
    assert points[2] == "노드: 상태를 받아 부분 업데이트를 돌려주는 함수"
    assert len(key_points(body, 3)) == 3
    hit = ChunkHit(note_id="N-1", chunk_id="N-1#0", notebook_id="NB-1", title="t", text="t > h\n" + "가" * 200, score=1)
    assert excerpt(hit, 10) == "가" * 10 + "…"
