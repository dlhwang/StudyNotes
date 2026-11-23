from __future__ import annotations

import pytest

from study_notes.agents.registry import all_intents
from study_notes.agents.review.rules import daily_plan, due_text, parse_preference
from study_notes.orchestrator.intents import classify_by_rules
from study_notes.tools.fakes.be import DEMO_DATE, FakeBeClient


@pytest.mark.parametrize(
    ("text", "prefs"),
    [
        ("앞으로 요약은 짧게 해줘", {"summary_length": "short"}),
        ("이제부터 요약 자세히", {"summary_length": "long"}),
        ("앞으로 퀴즈는 어렵게 내줘", {"quiz_difficulty": "hard"}),
        ("항상 쉽게 퀴즈 내줘", {"quiz_difficulty": "easy"}),
        ("앞으로 요약은 짧게, 퀴즈는 쉽게", {"summary_length": "short", "quiz_difficulty": "easy"}),
        ("앞으로 잘 부탁해", {}),
    ],
)
def test_parse_preference(text: str, prefs: dict[str, str]) -> None:
    assert parse_preference(text) == prefs


@pytest.mark.parametrize(
    ("text", "intents"),
    [
        ("오늘 뭐 복습해?", ["review_today"]),
        ("외워야 할 카드 있어?", ["review_today"]),
        ("복습 현황 알려줘", ["review_stats"]),
        ("공부 현황 어때?", ["review_stats"]),
        ("내가 약한 노트 뭐야?", ["review_stats"]),
        ("앞으로 요약은 짧게 해줘", ["profile_update"]),
        ("앞으로 퀴즈는 어렵게 내줘", ["profile_update"]),
    ],
)
def test_review_intents_do_not_collide(text: str, intents: list[str]) -> None:
    assert classify_by_rules(text, all_intents()) == intents


def test_daily_plan_key_is_stable() -> None:
    cards = FakeBeClient().cards[:3]
    a = daily_plan("NB-1", cards, DEMO_DATE)
    b = daily_plan("NB-1", list(reversed(cards)), DEMO_DATE)
    c = daily_plan("NB-1", cards, "2026-11-24")
    assert a is not None and b is not None and c is not None
    assert a.dedupe_key == b.dedupe_key != c.dedupe_key
    assert a.kind == "review.daily_plan" and a.source == "agent" and a.payload["card_ids"] == ["C-1", "C-2", "C-3"]
    assert daily_plan("NB-1", [], DEMO_DATE) is None


def test_due_text_counts_overdue() -> None:
    cards = FakeBeClient().cards[:3]
    text = due_text(cards, DEMO_DATE, preview=2)
    assert text.startswith("오늘 복습할 카드 3장(밀린 카드 1장)") and "…외 1장" in text
