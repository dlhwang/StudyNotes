from __future__ import annotations

import pytest

from notes_api.store.srs import MIN_EASE, next_due, schedule


@pytest.mark.parametrize(
    ("state", "grade", "expected"),
    [
        ((2.5, 0, 0), "good", (2.5, 1, 1)),
        ((2.5, 1, 1), "good", (2.5, 3, 2)),
        ((2.5, 3, 2), "good", (2.5, 8, 3)),
        ((2.5, 3, 2), "again", (2.3, 1, 0)),
        ((2.5, 3, 2), "hard", (2.35, 4, 3)),
        ((2.5, 0, 0), "hard", (2.35, 1, 1)),
        ((2.5, 0, 0), "easy", (2.65, 2, 1)),
        ((2.5, 3, 2), "easy", (2.65, 10, 3)),
    ],
)
def test_schedule(state: tuple[float, int, int], grade: str, expected: tuple[float, int, int]) -> None:
    assert schedule(*state, grade) == expected  # type: ignore[arg-type]


def test_ease_floor() -> None:
    ease = 1.35
    for _ in range(5):
        ease, _, _ = schedule(ease, 1, 0, "again")
    assert ease == MIN_EASE


def test_next_due() -> None:
    assert next_due("2026-11-30", 3) == "2026-12-03"
