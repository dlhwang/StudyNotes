"""전처리: 노트 본문을 검색 단위(청크)로 나눈다.

1. 정규화(줄 끝 공백, 연속 빈 줄, 탭)
2. ``## 소제목`` 단위로 묶음 → 빈 줄(문단) 단위
3. 짧은 문단은 ``max_chars``까지 합치고, 그래도 긴 문단은 ``overlap``만큼 겹쳐 자른다
4. 각 청크 앞에 ``"{제목} > {소제목}"``을 붙여 검색·답변 때 맥락을 준다
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*$")


@dataclass(frozen=True)
class Chunk:
    id: str
    note_id: str
    position: int
    heading: str
    text: str


def normalize(text: str) -> str:
    lines = [line.rstrip().replace("\t", "    ") for line in text.replace("\r\n", "\n").split("\n")]
    out = "\n".join(lines).strip()
    return re.sub(r"\n{3,}", "\n\n", out)


def _sections(body: str) -> list[tuple[str, list[str]]]:
    """(소제목, 문단 목록) 목록. 소제목 앞 내용은 소제목 ''."""
    sections: list[tuple[str, list[str]]] = [("", [])]
    para: list[str] = []

    def flush() -> None:
        if para:
            sections[-1][1].append("\n".join(para).strip())
            para.clear()

    for line in body.split("\n"):
        m = _HEADING.match(line)
        if m:
            flush()
            sections.append((m.group(1), []))
        elif not line.strip():
            flush()
        else:
            para.append(line)
    flush()
    return [(h, ps) for h, ps in sections if ps]


def _windows(text: str, max_chars: int, overlap: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    step = max(1, max_chars - overlap)
    return [text[i : i + max_chars] for i in range(0, len(text) - overlap, step)]


def _pack(paragraphs: list[str], max_chars: int, overlap: int) -> list[str]:
    out: list[str] = []
    buf = ""
    for p in paragraphs:
        if len(p) > max_chars:
            if buf:
                out.append(buf)
                buf = ""
            out += _windows(p, max_chars, overlap)
        elif not buf:
            buf = p
        elif len(buf) + 2 + len(p) <= max_chars:
            buf = f"{buf}\n\n{p}"
        else:
            out.append(buf)
            buf = p
    if buf:
        out.append(buf)
    return out


def split_note(note_id: str, title: str, body: str, max_chars: int = 400, overlap: int = 50) -> list[Chunk]:
    if max_chars <= overlap:
        raise ValueError("max_chars는 overlap보다 커야 합니다")
    chunks: list[Chunk] = []
    for heading, paragraphs in _sections(normalize(body)):
        prefix = f"{title} > {heading}" if heading else title
        for piece in _pack(paragraphs, max_chars, overlap):
            pos = len(chunks)
            chunks.append(
                Chunk(id=f"{note_id}#{pos}", note_id=note_id, position=pos, heading=heading, text=f"{prefix}\n{piece}")
            )
    return chunks
