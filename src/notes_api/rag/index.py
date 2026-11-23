"""Vector DB(Chroma) 색인. 적재는 노트 저장 때 BE가 하고, 검색은 Agent가 내부 API로 부른다.

- 컬렉션 하나(``note_chunks``), 코사인 거리. 임베딩은 ``Embedder``로 직접 계산해 넘긴다.
- 메타데이터: note_id, notebook_id, title, heading, position, embedder, embedder_version
- 검색은 노트북으로 거르고, score = 1 - 코사인 거리.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import chromadb
from chromadb.config import Settings
from pydantic import BaseModel

from notes_api.rag.chunking import split_note
from notes_api.rag.embedder import Embedder
from notes_api.store.models import Note


class ChunkHit(BaseModel):
    note_id: str
    chunk_id: str
    notebook_id: str
    title: str
    heading: str
    text: str
    position: int
    score: float


def make_client(path: str | None) -> Any:
    """path가 None이면 메모리(시험용), 있으면 디스크에 저장."""
    settings = Settings(anonymized_telemetry=False, allow_reset=True)
    if path is None:
        return chromadb.EphemeralClient(settings=settings)
    return chromadb.PersistentClient(path=path, settings=settings)


class NoteIndex:
    def __init__(self, client: Any, embedder: Embedder, collection: str = "note_chunks") -> None:
        self.embedder = embedder
        self.col = client.get_or_create_collection(
            name=collection, metadata={"hnsw:space": "cosine"}, embedding_function=None
        )

    def upsert_note(self, note: Note) -> int:
        """그 노트의 청크를 모두 지우고 새로 적재한다. 청크 수를 돌려준다."""
        self.delete_note(note.id)
        chunks = split_note(note.id, note.title, note.body)
        if not chunks:
            return 0
        self.col.add(
            ids=[c.id for c in chunks],
            embeddings=self.embedder.embed([c.text for c in chunks]),
            documents=[c.text for c in chunks],
            metadatas=[
                {
                    "note_id": note.id,
                    "notebook_id": note.notebook_id,
                    "title": note.title,
                    "heading": c.heading,
                    "position": c.position,
                    "embedder": self.embedder.name,
                    "embedder_version": self.embedder.version,
                }
                for c in chunks
            ],
        )
        return len(chunks)

    def delete_note(self, note_id: str) -> None:
        self.col.delete(where={"note_id": note_id})

    def search(self, notebook_id: str, query: str, k: int = 5) -> list[ChunkHit]:
        if not query.strip() or self.count(notebook_id) == 0:
            return []
        res = self.col.query(
            query_embeddings=self.embedder.embed([query]),
            n_results=max(1, min(k, 20)),
            where={"notebook_id": notebook_id},
            include=["documents", "metadatas", "distances"],
        )
        hits: list[ChunkHit] = []
        for cid, doc, meta, dist in zip(
            res["ids"][0], res["documents"][0], res["metadatas"][0], res["distances"][0], strict=True
        ):
            hits.append(
                ChunkHit(
                    note_id=str(meta["note_id"]),
                    chunk_id=str(cid),
                    notebook_id=str(meta["notebook_id"]),
                    title=str(meta["title"]),
                    heading=str(meta.get("heading") or ""),
                    text=str(doc),
                    position=int(meta["position"]),
                    score=round(1.0 - float(dist), 4),
                )
            )
        return sorted(hits, key=lambda h: -h.score)

    def count(self, notebook_id: str | None = None) -> int:
        if notebook_id is None:
            return int(self.col.count())
        got = self.col.get(where={"notebook_id": notebook_id}, include=[])
        return len(got["ids"])

    def metadata(self, chunk_id: str) -> dict[str, Any]:
        got = self.col.get(ids=[chunk_id], include=["metadatas"])
        return dict(got["metadatas"][0]) if got["metadatas"] else {}


def reindex_all(index: NoteIndex, notes: Iterable[Note]) -> int:
    return sum(index.upsert_note(n) for n in notes)
