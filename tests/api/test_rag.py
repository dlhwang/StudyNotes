from __future__ import annotations

import math
import uuid
from datetime import datetime

import pytest

from notes_api.rag import HashEmbedder, NoteIndex, make_client, reindex_all, split_note
from notes_api.store import Store, seed_demo

TODAY = "2026-11-23"


@pytest.fixture
def store() -> Store:
    s = Store(":memory:", clock=lambda: datetime(2026, 11, 23, 9, 0, 0))
    seed_demo(s, TODAY)
    return s


@pytest.fixture
def index(store: Store) -> NoteIndex:
    idx = NoteIndex(make_client(None), HashEmbedder(), collection=f"t-{uuid.uuid4().hex[:8]}")
    reindex_all(idx, store.all_notes())
    return idx


def test_split_note_by_heading_and_length() -> None:
    body = "머리말 문단\n\n## 첫째\n짧은 문단\n\n또 짧은 문단\n\n## 둘째\n" + "가" * 900
    chunks = split_note("N-1", "제목", body, max_chars=400, overlap=50)
    assert [c.id for c in chunks][:2] == ["N-1#0", "N-1#1"]
    assert chunks[0].heading == "" and chunks[0].text.startswith("제목\n")
    assert chunks[1].heading == "첫째" and "짧은 문단\n\n또 짧은 문단" in chunks[1].text  # 짧은 문단은 합친다
    long = [c for c in chunks if c.heading == "둘째"]
    assert len(long) == 3 and all(len(c.text.split("\n", 1)[1]) <= 400 for c in long)


def test_split_overlap() -> None:
    body = "".join(str(i % 10) for i in range(500))
    a, b = split_note("N-2", "t", body, max_chars=200, overlap=50)[:2]
    assert a.text.split("\n", 1)[1][-50:] == b.text.split("\n", 1)[1][:50]


def test_hash_embedder_deterministic_and_normalized() -> None:
    e = HashEmbedder()
    v1, v2 = e.embed(["체크포인터는 상태를 저장한다", "체크포인터는 상태를 저장한다"])
    assert v1 == v2 and math.isclose(sum(x * x for x in v1), 1.0, rel_tol=1e-6)


@pytest.mark.parametrize(
    ("notebook", "query", "title"),
    [
        ("NB-1", "체크포인터가 뭐야", "체크포인터와 메모리"),
        ("NB-1", "ReAct 패턴", "도구 호출과 ReAct"),
        ("NB-2", "이벤트 루프", "asyncio 기초"),
    ],
)
def test_search_finds_right_note(index: NoteIndex, notebook: str, query: str, title: str) -> None:
    hits = index.search(notebook, query, k=3)
    assert hits and hits[0].title == title
    assert all(h.notebook_id == notebook for h in hits)
    assert hits[0].score >= hits[-1].score


def test_upsert_delete_and_metadata(store: Store, index: NoteIndex) -> None:
    note = store.require_note("N-2")
    before = index.count("NB-1")
    meta = index.metadata(f"{note.id}#0")
    assert meta["embedder"] == "hash-ngram" and meta["embedder_version"] == "1"
    changed = store.update_note(note.id, title=note.title, body="짧은 새 본문 무지개", tags=note.tags)
    assert index.upsert_note(changed) == 1
    assert index.count("NB-1") < before
    assert index.search("NB-1", "무지개", k=1)[0].note_id == note.id
    index.delete_note(note.id)
    assert all(h.note_id != note.id for h in index.search("NB-1", "무지개", k=5))
    assert index.search("NB-1", "  ") == []
