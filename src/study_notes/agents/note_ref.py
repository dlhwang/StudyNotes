"""여러 하위 Agent가 함께 쓰는 순수 함수: 질문이 가리키는 노트 고르기.

하위 Agent끼리 서로 부르지 않는다(AGENTS.md §2). 같은 판단이 필요하면 이렇게 순수 함수로 나눠 각자 부른다.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from study_notes.orchestrator.intents import compact
from study_notes.tools.be_client.protocol import NoteSummary

_THIS = re.compile(r"(이노트|지금노트|현재노트|보고있는|이거|여기)")
_THAT = re.compile(r"(그노트|그거|그것|방금|아까|그내용|위노트|다시)")


def resolve_note_id(
    text: str, notes: Sequence[NoteSummary], screen_note_id: str | None, focus_ids: Sequence[str]
) -> str | None:
    """질문이 가리키는 노트.

    ① 질문에 노트 제목이 들어 있음(긴 제목 먼저) ② "이 노트" + 보고 있는 노트 ③ "그 노트"·"방금" + 대화 메모리
    ④ 보고 있는 노트 ⑤ 대화 메모리 ⑥ 없음(None) → 부른 쪽이 검색으로 찾는다
    """
    t = compact(text)
    for n in sorted(notes, key=lambda n: -len(n.title)):
        if compact(n.title) and compact(n.title) in t:
            return n.id
    if screen_note_id and _THIS.search(t):
        return screen_note_id
    if focus_ids and _THAT.search(t):
        return focus_ids[0]
    if screen_note_id:
        return screen_note_id
    return focus_ids[0] if focus_ids else None
