"""quiz Agent의 규칙. 모델 없이 시험할 수 있는 순수 함수만 둔다."""

from __future__ import annotations

import re
from collections.abc import Iterable

from pydantic import BaseModel, Field

from study_notes.orchestrator.intents import compact

DEFAULT_COUNT = 3
MAX_COUNT = 5
_COUNT = re.compile(r"(\d+)\s*(개|장|문제|문항)")
_BULLET = re.compile(r"^\s*[-*]\s*(.+?)\s*[:：]\s*(.+?)\s*$")


class QuizCard(BaseModel):
    question: str = Field(min_length=2)
    answer: str = Field(min_length=1)
    # 노트에서 그대로 옮긴 근거 문장. 노트 본문에 있어야 통과한다
    evidence: str = ""


def requested_count(text: str) -> int:
    m = _COUNT.search(text)
    n = int(m.group(1)) if m else DEFAULT_COUNT
    return max(1, min(MAX_COUNT, n))


def _has_batchim(word: str) -> bool:
    last = word.strip()[-1:] if word.strip() else ""
    if "가" <= last <= "힣":
        return (ord(last) - ord("가")) % 28 != 0
    return bool(last) and last.lower() in "lmngkpbt"  # 영어는 받침 소리로 읽히는 끝 글자만 '이란' (calling→이란, id→란)


def term_question(term: str) -> str:
    return f"{term}{'이란' if _has_batchim(term) else '란'} 무엇인가?"


def cards_from_note(body: str, count: int, existing: Iterable[str] = ()) -> list[QuizCard]:
    """규칙 카드: ``- 용어: 설명`` 줄 → "용어란 무엇인가?" / 설명. 이미 있는 질문은 뺀다."""
    seen = {compact(q) for q in existing}
    out: list[QuizCard] = []
    for line in body.split("\n"):
        m = _BULLET.match(line)
        if not m:
            continue
        q = term_question(m.group(1))
        if compact(q) in seen:
            continue
        seen.add(compact(q))
        out.append(QuizCard(question=q, answer=m.group(2), evidence=line.strip()))
        if len(out) >= count:
            break
    return out


def grounded(cards: Iterable[QuizCard], body: str, existing: Iterable[str], count: int) -> list[QuizCard]:
    """모델 카드 검증: 근거(evidence)가 노트 본문에 있는 것만, 기존·중복 질문 제외, count개까지."""
    text = compact(body)
    seen = {compact(q) for q in existing}
    out: list[QuizCard] = []
    for c in cards:
        ev = compact(c.evidence.lstrip("-* "))
        if not ev or ev not in text or compact(c.question) in seen:
            continue
        seen.add(compact(c.question))
        out.append(c)
        if len(out) >= count:
            break
    return out
