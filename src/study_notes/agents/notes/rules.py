"""notes Agent의 규칙. 모델 없이 시험할 수 있는 순수 함수만 둔다."""

from __future__ import annotations

import re

from study_notes.agents.note_ref import resolve_note_id
from study_notes.tools.be_client.protocol import ChunkHit

__all__ = ["MIN_SCORE", "SUMMARY_POINTS", "excerpt", "key_points", "location", "resolve_note_id", "search_query"]

# 이 점수보다 낮은 검색 조각은 관련이 약하다고 본다
MIN_SCORE = 0.15
SUMMARY_POINTS = {"short": 3, "normal": 4, "long": 5}

_FILLER = re.compile(
    r"(요약해\s*줘|요약해|요약|정리해\s*줘|정리해|핵심만|찾아\s*줘|찾아|검색해\s*줘|검색해|보여\s*줘|보여|알려\s*줘|"
    r"설명해\s*줘|설명해|뭐야|뭐지|뭔데|무엇인가요|무엇|어떻게|목록|노트|메모|관련|대해서|대해|있어|에서|좀|다시|"
    r"[?!.,~])"
)
_BULLET = re.compile(r"^\s*[-*]\s*(.+?)\s*[:：]\s*(.+?)\s*$")
_SENTENCE = re.compile(r"(?<=[.!?다])\s+")


def search_query(text: str) -> str:
    """질문에서 요청 말(요약해줘, 뭐야 …)을 빼고 검색어만 남긴다. 다 빠지면 빈 문자열."""
    return re.sub(r"\s+", " ", _FILLER.sub(" ", text)).strip()


def _first_sentence(paragraph: str) -> str:
    line = " ".join(x.strip() for x in paragraph.split("\n") if x.strip() and not _BULLET.match(x))
    return _SENTENCE.split(line, maxsplit=1)[0].strip() if line else ""


def key_points(body: str, count: int) -> list[str]:
    """규칙 요약: 소제목마다 첫 문장, 그다음 ``- 용어: 설명`` 줄. 앞에서부터 count개."""
    overview: list[str] = []
    terms: list[str] = []
    for block in re.split(r"\n\s*\n", body):
        lines = [x for x in block.strip().split("\n") if x.strip()]
        if not lines:
            continue
        if lines[0].lstrip().startswith("#"):
            lines = lines[1:]
        for x in lines:
            m = _BULLET.match(x)
            if m:
                terms.append(f"{m.group(1)}: {m.group(2)}")
        first = _first_sentence("\n".join(lines))
        if first:
            overview.append(first)
    points: list[str] = []
    for p in overview + terms:
        if p not in points:
            points.append(p)
    return points[:count]


def excerpt(hit: ChunkHit, limit: int = 160) -> str:
    """검색 조각에서 맨 앞 맥락 줄("제목 > 소제목")을 빼고 앞부분만."""
    body = hit.text.split("\n", 1)[1] if "\n" in hit.text else hit.text
    flat = re.sub(r"\s+", " ", body).strip()
    return flat if len(flat) <= limit else flat[:limit].rstrip() + "…"


def location(hit: ChunkHit) -> str:
    return f"{hit.note_id} · {hit.title} > {hit.heading}" if hit.heading else f"{hit.note_id} · {hit.title}"
