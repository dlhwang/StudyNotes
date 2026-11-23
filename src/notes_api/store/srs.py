"""복습 간격 계산 — SM-2를 단순화한 것. 숫자 계산은 BE가 한다 (AGENTS.md 절대 규칙 4).

| 등급 | 반복 수 | 간격 | ease |
|---|---|---|---|
| again | 0 | 1일 | -0.2 |
| hard | +1 | max(1, 간격×1.2) | -0.15 |
| good | +1 | 1 → 3 → 간격×ease | 그대로 |
| easy | +1 | max(2, good 간격×1.3) | +0.15 |

ease 하한은 1.3.
"""

from __future__ import annotations

from datetime import date, timedelta

from notes_api.store.models import Grade

MIN_EASE = 1.3


def _good_interval(interval_days: int, repetitions: int, ease: float) -> int:
    if repetitions == 0:
        return 1
    if repetitions == 1:
        return 3
    return max(1, round(interval_days * ease))


def schedule(ease: float, interval_days: int, repetitions: int, grade: Grade) -> tuple[float, int, int]:
    """(새 ease, 새 간격 일수, 새 반복 수)."""
    if grade == "again":
        return round(max(MIN_EASE, ease - 0.2), 2), 1, 0
    if grade == "hard":
        return round(max(MIN_EASE, ease - 0.15), 2), max(1, round(max(interval_days, 1) * 1.2)), repetitions + 1
    good = _good_interval(interval_days, repetitions, ease)
    if grade == "good":
        return round(ease, 2), good, repetitions + 1
    return round(ease + 0.15, 2), max(2, round(good * 1.3)), repetitions + 1


def next_due(reviewed_on: str, interval_days: int) -> str:
    return (date.fromisoformat(reviewed_on) + timedelta(days=interval_days)).isoformat()
