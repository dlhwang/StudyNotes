"""review Agent의 규칙. 모델 없이 시험할 수 있는 순수 함수만 둔다. 숫자는 BE가 준 값을 그대로 쓴다."""

from __future__ import annotations

from typing import Any

from study_notes.core.ids import dedupe_key
from study_notes.core.proposal import ProposalDraft
from study_notes.orchestrator.intents import compact
from study_notes.tools.be_client.protocol import Card, LearnerProfile, ReviewStats

_PREFS: list[tuple[tuple[str, ...], str, str]] = [
    (("짧게", "간단히", "간결"), "summary_length", "short"),
    (("길게", "자세히", "상세"), "summary_length", "long"),
    (("보통길이", "적당히"), "summary_length", "normal"),
    (("쉽게", "쉬운"), "quiz_difficulty", "easy"),
    (("어렵게", "어려운", "까다롭"), "quiz_difficulty", "hard"),
]
_LABEL = {
    ("summary_length", "short"): "요약은 짧게",
    ("summary_length", "long"): "요약은 자세히",
    ("summary_length", "normal"): "요약은 보통 길이로",
    ("quiz_difficulty", "easy"): "퀴즈는 쉽게",
    ("quiz_difficulty", "hard"): "퀴즈는 어렵게",
}


def parse_preference(text: str) -> dict[str, str]:
    """질문에서 선호를 읽는다. "요약"·"퀴즈"가 같이 나오면 그쪽에만 건다. 못 읽으면 빈 dict."""
    t = compact(text)
    out: dict[str, str] = {}
    for words, key, value in _PREFS:
        if any(w in t for w in words) and key not in out:
            out[key] = value
    if "퀴즈" in t and "요약" not in t:
        out.pop("summary_length", None)
    if "요약" in t and "퀴즈" not in t:
        out.pop("quiz_difficulty", None)
    if "퀴즈" in t and "summary_length" in out and "quiz_difficulty" not in out:
        out = {}
    return out


def preference_label(prefs: dict[str, str]) -> str:
    return ", ".join(_LABEL[(k, v)] for k, v in prefs.items())


def stats_text(stats: ReviewStats) -> str:
    rate = f"정답률 {stats.correct_rate_7d_pct}%" if stats.correct_rate_7d_pct is not None else "정답률은 아직 없음"
    return (
        f"최근 7일 {stats.reviewed_7d}번 복습했고 {rate}, 연속 학습 {stats.streak_days}일입니다. "
        f"카드 {stats.total_cards}장 중 오늘 복습할 카드 {stats.due_today}장(밀린 카드 {stats.overdue}장), "
        f"새 카드 {stats.new_cards}장입니다."
    )


def weak_text(profile: LearnerProfile) -> str:
    if not profile.weak_notes:
        return "최근 2주에 자주 틀린 노트는 없습니다."
    w = profile.weak_notes[0]
    return f"가장 자주 틀린 노트는 '{w.title}'(최근 2주 {w.again_count_14d}번 다시)입니다. 요약을 다시 읽어 보세요."


def due_text(cards: list[Card], base_date: str, preview: int = 5) -> str:
    overdue = sum(1 for c in cards if c.due_date < base_date)
    head = f"오늘 복습할 카드 {len(cards)}장(밀린 카드 {overdue}장)입니다."
    lines = [f"- {c.question} ({c.note_title})" for c in cards[:preview]]
    more = [f"…외 {len(cards) - preview}장"] if len(cards) > preview else []
    return "\n".join([head, *lines, *more])


def daily_plan(notebook_id: str, cards: list[Card], base_date: str) -> ProposalDraft | None:
    """오늘 복습 계획 제안. 카드가 없으면 None. 같은 노트북·같은 날이면 키가 같다 → BE가 한 번만 저장."""
    if not cards:
        return None
    overdue = sum(1 for c in cards if c.due_date < base_date)
    payload: dict[str, Any] = {"base_date": base_date, "card_ids": [c.id for c in cards]}
    return ProposalDraft(
        kind="review.daily_plan",
        subject_id=notebook_id,
        title=f"{base_date} 복습 {len(cards)}장",
        payload=payload,
        reasons=[f"기준일까지 복습할 카드 {len(cards)}장(밀린 카드 {overdue}장)"],
        source="agent",
        source_ref=notebook_id,
        dedupe_key=dedupe_key("daily_review", notebook_id, base_date),
    )
