from __future__ import annotations

import pytest

from study_notes.agents.registry import all_intents, check_registry
from study_notes.agents.tasks.rules import find_task, overdue_notices
from study_notes.core.ids import dedupe_key
from study_notes.orchestrator.intents import IntentSpec, classify_by_rules
from study_notes.tools.fakes.be import FakeBeClient


@pytest.mark.parametrize(
    ("text", "intents"),
    [
        ("오늘 할 일 보여줘", ["task_list"]),
        ("해야 할 것 있어?", ["task_list"]),
        ("견적서 검토 할 일 왜 생겼어?", ["task_explain"]),
        ("이 할일 근거가 뭐야", ["task_explain"]),
        ("안녕하세요", []),
    ],
)
def test_classify_by_rules(text: str, intents: list[str]) -> None:
    assert classify_by_rules(text, all_intents()) == intents


def test_registry_has_one_owner_per_intent() -> None:
    assert check_registry() == []


def test_intent_name_rule() -> None:
    with pytest.raises(ValueError):
        IntentSpec("Task-List", "x")


def test_dedupe_key_is_stable() -> None:
    assert dedupe_key("t1", "p1") == dedupe_key("t1", "p1")
    assert dedupe_key("t1", "p1") != dedupe_key("t1", "p2")
    with pytest.raises(ValueError):
        dedupe_key("t1", "")


def test_task_rules() -> None:
    tasks = FakeBeClient().tasks["NB-1"]
    found = find_task(tasks, "월간 보고서 작성 왜 생겼어")
    assert found is not None and found.id == "T-2"
    notices = overdue_notices(tasks, "2026-11-23")
    assert [n.source_ref for n in notices] == ["T-1"]  # 끝난 T-3, 마감 전 T-2는 빠진다
    assert overdue_notices(tasks, "2026-11-01") == []
