from __future__ import annotations

from datetime import datetime

import pytest

from notes_api.store import InvalidInputError, NotFoundError, Store, seed_demo

TODAY = "2026-11-23"


def _clock() -> datetime:
    return datetime(2026, 11, 23, 9, 0, 0)


@pytest.fixture
def store() -> Store:
    return Store(":memory:", clock=_clock)


@pytest.fixture
def seeded(store: Store) -> Store:
    assert seed_demo(store, TODAY)
    return store


def test_seed_demo(seeded: Store) -> None:
    nbs = seeded.list_notebooks()
    assert [n.id for n in nbs] == ["NB-1", "NB-2"]
    assert len(seeded.all_notes()) == 5
    assert seed_demo(seeded, TODAY) is False  # 두 번째는 넣지 않는다
    profile = seeded.get_profile(TODAY)
    assert profile.weak_notes and profile.weak_notes[0].title == "체크포인터와 메모리"
    assert profile.weak_notes[0].again_count_14d == 3


def test_note_crud_and_keyword_search(store: Store) -> None:
    nb = store.create_notebook("시험")
    a = store.create_note(nb.id, "그래프 노드", "노드는 함수다", ["graph"])
    b = store.create_note(nb.id, "엣지", "엣지는 노드를 잇는다", ["노드"])
    store.create_note(nb.id, "관계없음", "다른 이야기", [])
    found = store.list_notes(nb.id, query="노드")
    assert [n.id for n in found] == [a.id, b.id]  # 제목 3+본문 1 > 태그 2+본문 1
    assert store.list_notes(nb.id, query="없는단어") == []
    updated = store.update_note(a.id, title="그래프 노드", body="바뀐 본문", tags=["g"])
    assert updated.body == "바뀐 본문" and updated.tags == ["g"]
    store.delete_note(b.id)
    assert store.get_note(b.id) is None
    with pytest.raises(NotFoundError, match="노트 목록"):
        store.require_note("N-999")
    with pytest.raises(InvalidInputError):
        store.create_note(nb.id, " ", "본문", [])


def test_cards_dedupe(store: Store) -> None:
    nb = store.create_notebook("시험")
    note = store.create_note(nb.id, "제목", "본문", [])
    first = store.add_cards(note.id, [("노드란?", "함수"), ("엣지란?", "연결")], TODAY)
    again = store.add_cards(note.id, [("노드 란?", "다른 답")], TODAY)  # 공백만 다른 같은 질문
    assert len(first) == 2 and again == []
    assert len(store.list_cards(nb.id)) == 2
    assert first[0].due_date == TODAY and first[0].note_title == "제목"


def test_accept_proposal_is_idempotent(store: Store) -> None:
    nb = store.create_notebook("시험")
    note = store.create_note(nb.id, "제목", "본문", [])
    draft = {
        "kind": "quiz.cards_add",
        "subject_id": nb.id,
        "title": "카드 2장",
        "payload": {
            "note_id": note.id,
            "cards": [{"question": "Q1", "answer": "A1"}, {"question": "Q2", "answer": "A2"}],
        },
        "reasons": ["사용자 요청"],
        "source": "chat",
        "dedupe_key": "k-1",
    }
    rec1 = store.accept_proposal(draft, TODAY)
    rec2 = store.accept_proposal(draft, TODAY)
    assert rec1.id == rec2.id and rec1.status == "applied" and len(rec1.applied["card_ids"]) == 2
    assert len(store.list_cards(nb.id)) == 2

    pref = {"kind": "profile.update", "subject_id": nb.id, "title": "짧게", "payload": {"summary_length": "short"}}
    store.accept_proposal({**pref, "dedupe_key": "k-2"}, TODAY)
    assert store.get_profile().summary_length == "short"

    plan = {"kind": "review.daily_plan", "subject_id": nb.id, "title": "계획", "dedupe_key": "k-3"}
    store.accept_proposal({**plan, "payload": {"base_date": TODAY, "card_ids": ["C-1"]}, "source": "agent"}, TODAY)
    got = store.get_daily_plan(nb.id, TODAY)
    assert got is not None and got.payload["card_ids"] == ["C-1"] and got.source == "agent"
    assert store.get_daily_plan(nb.id, "2026-11-24") is None

    with pytest.raises(InvalidInputError):
        store.accept_proposal({"kind": "x"}, TODAY)


def test_review_and_stats(seeded: Store) -> None:
    stats = seeded.review_stats("NB-1", TODAY)
    assert stats.total_cards == 7
    assert stats.reviewed_7d == 9 and stats.correct_rate_7d_pct == 56  # again 4번 / 9번
    assert stats.streak_days == 0  # 오늘은 아직 복습 안 함
    due_before = stats.due_today
    card = seeded.list_due_cards("NB-1", TODAY)[0]
    after = seeded.record_review(card.id, "good", TODAY)
    assert after.due_date > TODAY
    stats2 = seeded.review_stats("NB-1", TODAY)
    assert stats2.due_today == due_before - 1 and stats2.streak_days == 5 and stats2.reviewed_7d == 10


def test_review_again_counts_lapse(seeded: Store) -> None:
    card = seeded.list_cards("NB-2")[0]
    after = seeded.record_review(card.id, "again", TODAY)
    assert after.lapses == 1 and after.repetitions == 0 and after.due_date == "2026-11-24"
    with pytest.raises(InvalidInputError):
        seeded.record_review(card.id, "bad", TODAY)  # type: ignore[arg-type]
    with pytest.raises(InvalidInputError):
        seeded.review_stats("NB-2", "2026/11/23")
