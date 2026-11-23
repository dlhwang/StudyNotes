from __future__ import annotations

import pytest

from study_notes.agents.quiz.rules import QuizCard, cards_from_note, grounded, requested_count, term_question

BODY = (
    "## 큐\n큐는 먼저 넣은 것이 먼저 나온다.\n\n- enqueue: 뒤에 넣기\n- dequeue: 앞에서 꺼내기\n- 스택: 나중 것이 먼저"
)


@pytest.mark.parametrize(
    ("text", "n"), [("퀴즈 내줘", 3), ("퀴즈 5개 내줘", 5), ("문제 9문제", 5), ("카드 1장 만들어", 1)]
)
def test_requested_count(text: str, n: int) -> None:
    assert requested_count(text) == n


def test_term_question_particle() -> None:
    assert term_question("스택") == "스택이란 무엇인가?"
    assert term_question("리듀서") == "리듀서란 무엇인가?"
    assert term_question("thread_id") == "thread_id란 무엇인가?"
    assert term_question("enqueue") == "enqueue란 무엇인가?"


def test_cards_from_note_skips_existing() -> None:
    cards = cards_from_note(BODY, 3, existing=["enqueue란 무엇인가?"])
    assert [c.question for c in cards] == ["dequeue란 무엇인가?", "스택이란 무엇인가?"]
    assert cards[0].answer == "앞에서 꺼내기" and cards[0].evidence == "- dequeue: 앞에서 꺼내기"
    assert cards_from_note("본문만 있음", 3) == []


def test_grounded_drops_hallucinated_and_duplicates() -> None:
    cards = [
        QuizCard(question="큐의 순서는?", answer="먼저 넣은 것 먼저", evidence="큐는 먼저 넣은 것이 먼저 나온다."),
        QuizCard(question="큐의 발명자는?", answer="누군가", evidence="큐는 1950년에 발명되었다."),  # 노트에 없음
        QuizCard(question="큐의 순서는 ?", answer="중복", evidence="큐는 먼저 넣은 것이 먼저 나온다."),
        QuizCard(question="enqueue란?", answer="뒤에 넣기", evidence="- enqueue: 뒤에 넣기"),
        QuizCard(question="근거 없음", answer="x", evidence=""),
    ]
    out = grounded(cards, BODY, existing=["enqueue란?"], count=5)
    assert [c.question for c in out] == ["큐의 순서는?"]
