"""가짜 BE. BE 없이 끝까지 돌려 보고 시험하기 위한 것 (AGENTS.md §4.6).

데이터는 모두 합성이다(직접 쓴 짧은 학습 메모). 실데이터를 넣지 않는다.
- 검색은 진짜 임베딩 대신 질의와 청크의 문자 2-gram 겹침 비율을 score로 쓴다.
- 시험에서 바꿔 끼울 수 있게 ``notes``·``cards``·``stats``·``profile`` 속성을 연다.
실제 BE(``notes_api``)와 같은 약속을 지키는지는 계약 시험(tests/contract)이 확인한다.
"""

from __future__ import annotations

import re

from pydantic import SecretStr

from study_notes.core.errors import ToolInputError
from study_notes.tools.be_client.protocol import (
    Card,
    ChunkHit,
    LearnerProfile,
    Note,
    NoteSummary,
    ReviewStats,
    WeakNote,
)

DEMO_SUBJECT = "NB-1"
DEMO_DATE = "2026-11-23"


def _demo_notes() -> list[Note]:
    def note(nid: str, nb: str, title: str, tags: list[str], body: str) -> Note:
        return Note(id=nid, notebook_id=nb, title=title, body=body, tags=tags, updated_at=f"{DEMO_DATE}T09:00:00")

    return [
        note(
            "N-1",
            "NB-1",
            "StateGraph 기초",
            ["langgraph"],
            "## 그래프를 만드는 순서\n"
            "StateGraph는 상태 스키마를 정하고 노드와 엣지를 더한 뒤 compile 해서 실행한다.\n\n"
            "- 노드: 상태를 받아 부분 업데이트를 돌려주는 함수\n"
            "- 엣지: 다음에 어느 노드로 갈지 정하는 연결\n"
            "- 리듀서: 여러 노드가 같은 키를 갱신할 때 값을 합치는 규칙\n\n"
            "## 조건 분기\n"
            "add_conditional_edges로 상태를 보고 다음 노드를 고른다.",
        ),
        note(
            "N-2",
            "NB-1",
            "체크포인터와 메모리",
            ["langgraph", "메모리"],
            "## 체크포인터\n"
            "체크포인터는 노드가 끝날 때마다 그래프 상태를 저장해 대화를 이어 가게 한다.\n\n"
            "- 체크포인터: 단계마다 상태 스냅숏을 저장하는 장치\n"
            "- thread_id: 하나의 대화를 구분하는 키\n\n"
            "## 장기 메모리\n"
            "여러 thread를 넘어 기억할 정보는 따로 저장소에 둔다.\n\n"
            "- 장기 메모리: thread가 바뀌어도 남는 사용자별 정보",
        ),
        note(
            "N-3",
            "NB-1",
            "도구 호출과 ReAct",
            ["agent"],
            "## Function Calling\n"
            "모델에게 도구 이름과 인자 스키마를 알려 주면 어떤 도구를 부를지 JSON으로 돌려준다.\n\n"
            "- Function Calling: 모델이 도구 호출을 구조화된 JSON으로 내놓는 기능\n\n"
            "## ReAct\n"
            "ReAct는 추론하고 행동하고 관찰하는 과정을 반복하는 실행 방식이다.\n\n"
            "- ReAct: 추론과 도구 실행을 번갈아 반복하는 패턴\n"
            "- 관찰: 도구 실행 결과를 모델에게 돌려준 것",
        ),
        note(
            "N-4",
            "NB-2",
            "asyncio 기초",
            ["python"],
            "## 이벤트 루프\nawait를 만나면 제어권을 이벤트 루프에 넘긴다.\n\n"
            "- 코루틴: async def로 정의한 함수\n- 이벤트 루프: 준비된 코루틴을 번갈아 실행하는 스케줄러",
        ),
    ]


def _demo_cards() -> list[Card]:
    def card(
        cid: str, nid: str, title: str, q: str, a: str, due: str, reps: int = 0, ivl: int = 0, lapses: int = 0
    ) -> Card:
        return Card(
            id=cid,
            note_id=nid,
            note_title=title,
            question=q,
            answer=a,
            due_date=due,
            repetitions=reps,
            interval_days=ivl,
            lapses=lapses,
        )

    sg, cp = "StateGraph 기초", "체크포인터와 메모리"
    return [
        card("C-1", "N-1", sg, "리듀서란?", "값을 합치는 규칙", "2026-11-20"),
        card("C-2", "N-1", sg, "노드란?", "부분 업데이트를 돌려주는 함수", "2026-11-23", reps=2, ivl=3),
        card("C-3", "N-2", cp, "체크포인터란?", "상태 스냅숏을 저장하는 장치", "2026-11-23", lapses=3),
        card("C-4", "N-2", cp, "thread_id란?", "대화를 구분하는 키", "2026-11-30", reps=3, ivl=8),
        card("C-5", "N-4", "asyncio 기초", "코루틴이란?", "async def로 정의한 함수", "2026-12-01", reps=1, ivl=3),
    ]


def _grams(text: str) -> set[str]:
    s = re.sub(r"\s+", "", text).lower()
    return {s[i : i + 2] for i in range(len(s) - 1)}


class FakeBeClient:
    def __init__(self) -> None:
        self.notebooks: list[str] = ["NB-1", "NB-2"]
        self.notes: list[Note] = _demo_notes()
        self.cards: list[Card] = _demo_cards()
        self.stats: dict[str, ReviewStats] = {
            "NB-1": ReviewStats(
                notebook_id="NB-1",
                base_date=DEMO_DATE,
                total_cards=4,
                due_today=3,
                overdue=1,
                new_cards=1,
                reviewed_7d=9,
                correct_rate_7d_pct=56,
                streak_days=4,
            ),
            "NB-2": ReviewStats(
                notebook_id="NB-2",
                base_date=DEMO_DATE,
                total_cards=1,
                due_today=0,
                overdue=0,
                new_cards=0,
                reviewed_7d=0,
                correct_rate_7d_pct=None,
                streak_days=0,
            ),
        }
        self.profile = LearnerProfile(
            weak_notes=[WeakNote(note_id="N-2", title="체크포인터와 메모리", again_count_14d=3)]
        )

    def _notebook(self, notebook_id: str) -> None:
        if notebook_id not in self.notebooks:
            raise ToolInputError(f"노트북 {notebook_id}를 찾을 수 없습니다", hint="노트북 목록에서 ID를 확인하세요")

    async def list_subjects(self, *, token: SecretStr | None) -> list[str]:
        return list(self.notebooks)

    async def list_notes(
        self, notebook_id: str, *, query: str | None = None, limit: int = 10, token: SecretStr | None
    ) -> list[NoteSummary]:
        self._notebook(notebook_id)
        notes = [n for n in self.notes if n.notebook_id == notebook_id]
        words = [w for w in (query or "").lower().split() if len(w) >= 2]
        if words:
            notes = [
                n for n in notes if any(w in (n.title + " " + n.body + " " + " ".join(n.tags)).lower() for w in words)
            ]
        return [
            NoteSummary(
                **n.model_dump(include={"id", "notebook_id", "title", "tags", "updated_at"}), snippet=n.body[:120]
            )
            for n in notes[:limit]
        ]

    async def get_note(self, note_id: str, *, token: SecretStr | None) -> Note:
        for n in self.notes:
            if n.id == note_id:
                return n.model_copy()
        raise ToolInputError(f"노트 {note_id}를 찾을 수 없습니다", hint="노트 목록에서 ID를 확인하세요")

    async def search_chunks(
        self, notebook_id: str, query: str, *, k: int = 5, token: SecretStr | None
    ) -> list[ChunkHit]:
        self._notebook(notebook_id)
        q = _grams(query)
        if not q:
            return []
        hits: list[ChunkHit] = []
        for n in self.notes:
            if n.notebook_id != notebook_id:
                continue
            heading = ""
            for pos, para in enumerate(p for p in n.body.split("\n\n") if p.strip()):
                first = para.split("\n", 1)[0]
                if first.startswith("## "):
                    heading = first[3:].strip()
                text = f"{n.title} > {heading}\n{para}" if heading else f"{n.title}\n{para}"
                score = round(len(q & _grams(text)) / len(q), 4)
                hits.append(
                    ChunkHit(
                        note_id=n.id,
                        chunk_id=f"{n.id}#{pos}",
                        notebook_id=notebook_id,
                        title=n.title,
                        heading=heading,
                        text=text,
                        position=pos,
                        score=score,
                    )
                )
        return sorted(hits, key=lambda h: (-h.score, h.chunk_id))[:k]

    async def list_cards(self, notebook_id: str, *, note_id: str | None = None, token: SecretStr | None) -> list[Card]:
        self._notebook(notebook_id)
        ids = {n.id for n in self.notes if n.notebook_id == notebook_id}
        return [c.model_copy() for c in self.cards if c.note_id in ids and (note_id is None or c.note_id == note_id)]

    async def list_due_cards(
        self, notebook_id: str, base_date: str, *, limit: int = 20, token: SecretStr | None
    ) -> list[Card]:
        cards = await self.list_cards(notebook_id, token=token)
        return sorted((c for c in cards if c.due_date <= base_date), key=lambda c: (c.due_date, c.id))[:limit]

    async def get_review_stats(self, notebook_id: str, base_date: str, *, token: SecretStr | None) -> ReviewStats:
        self._notebook(notebook_id)
        return self.stats[notebook_id].model_copy(update={"base_date": base_date})

    async def get_learner_profile(self, *, token: SecretStr | None, base_date: str | None = None) -> LearnerProfile:
        return self.profile.model_copy(deep=True)
