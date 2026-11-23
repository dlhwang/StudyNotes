"""BE 저장소 (SQLite).

- 노트북·노트·카드·복습 기록·제안·학습자 프로필을 저장한다.
- 숫자 계산(복습 간격, 통계, 약한 노트)은 여기서 한다. Agent는 받은 숫자를 설명만 한다.
- 제안 초안(Agent가 만든 ``ProposalDraft`` dict)은 사용자가 수락하면 ``accept_proposal``이
  ``dedupe_key``로 한 번만 저장하고 종류별로 반영한다.

sqlite3 동기 API다. FastAPI의 동기 엔드포인트(스레드 풀)에서 부르므로 연결을 스레드 사이에 나눠 쓰고
``threading.Lock``으로 한 번에 하나씩만 실행한다.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import threading
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from typing import Any

from notes_api.store import srs
from notes_api.store.models import (
    Card,
    Grade,
    LearnerProfile,
    Note,
    Notebook,
    NoteSummary,
    ProposalRecord,
    QuizDifficulty,
    ReviewStats,
    SummaryLength,
    WeakNote,
)
from notes_api.store.schema import DDL

_SNIPPET = 120
_GRADES = ("again", "hard", "good", "easy")


class NotFoundError(LookupError):
    """없는 대상. API가 404로 바꾼다. 메시지에 고칠 방법을 담는다."""


class InvalidInputError(ValueError):
    """잘못된 입력. API가 400으로 바꾼다."""


def _parse_id(prefix: str, value: str) -> int:
    m = re.fullmatch(rf"{prefix}-(\d+)", value.strip())
    if not m:
        raise NotFoundError(f"ID 형식이 맞지 않습니다: {value} (예: {prefix}-1)")
    return int(m.group(1))


def _check_date(value: str) -> str:
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as e:
        raise InvalidInputError(f"날짜 형식이 맞지 않습니다: {value} (예: 2026-11-23)") from e


def _compact(text: str) -> str:
    return re.sub(r"\s", "", text).lower()


def _tags(raw: str) -> list[str]:
    return [t for t in raw.split(",") if t]


def _days_before(base: str, days: int) -> str:
    return (date.fromisoformat(base) - timedelta(days=days)).isoformat()


class Store:
    def __init__(self, path: str, *, clock: Callable[[], datetime] | None = None) -> None:
        self.path = path
        self._clock = clock or datetime.now
        self._lock = threading.RLock()
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.executescript(DDL)
        self._db.execute("INSERT OR IGNORE INTO profile (id) VALUES (1)")
        self._db.commit()

    def close(self) -> None:
        self._db.close()

    def _now(self) -> str:
        return self._clock().isoformat(timespec="seconds")

    def today(self) -> str:
        return self._clock().date().isoformat()

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            try:
                yield self._db
                self._db.commit()
            except Exception:
                self._db.rollback()
                raise

    def _rows(self, sql: str, params: Sequence[Any] = ()) -> list[sqlite3.Row]:
        with self._lock:
            return list(self._db.execute(sql, params).fetchall())

    def _one(self, sql: str, params: Sequence[Any] = ()) -> sqlite3.Row | None:
        with self._lock:
            row: sqlite3.Row | None = self._db.execute(sql, params).fetchone()
            return row

    # ── 노트북 ───────────────────────────────────────────────────────

    def list_notebooks(self) -> list[Notebook]:
        return [Notebook(id=f"NB-{r['id']}", name=r["name"]) for r in self._rows("SELECT * FROM notebooks ORDER BY id")]

    def create_notebook(self, name: str) -> Notebook:
        if not name.strip():
            raise InvalidInputError("노트북 이름이 비어 있습니다")
        with self._tx() as db:
            cur = db.execute("INSERT INTO notebooks (name) VALUES (?)", (name.strip(),))
        return Notebook(id=f"NB-{cur.lastrowid}", name=name.strip())

    def get_notebook(self, notebook_id: str) -> Notebook:
        row = self._one("SELECT * FROM notebooks WHERE id = ?", (_parse_id("NB", notebook_id),))
        if row is None:
            raise NotFoundError(f"노트북 {notebook_id}를 찾을 수 없습니다. 노트북 목록에서 ID를 확인하세요")
        return Notebook(id=f"NB-{row['id']}", name=row["name"])

    # ── 노트 ─────────────────────────────────────────────────────────

    @staticmethod
    def _note(row: sqlite3.Row) -> Note:
        return Note(
            id=f"N-{row['id']}",
            notebook_id=f"NB-{row['notebook_id']}",
            title=row["title"],
            body=row["body"],
            tags=_tags(row["tags"]),
            source=row["source"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _summary(note: Note) -> NoteSummary:
        snippet = re.sub(r"\s+", " ", note.body).strip()[:_SNIPPET]
        return NoteSummary(
            id=note.id,
            notebook_id=note.notebook_id,
            title=note.title,
            tags=note.tags,
            updated_at=note.updated_at,
            snippet=snippet,
        )

    @staticmethod
    def _clean_note(title: str, body: str, tags: list[str]) -> tuple[str, str, str]:
        if not title.strip():
            raise InvalidInputError("노트 제목이 비어 있습니다")
        if not body.strip():
            raise InvalidInputError("노트 본문이 비어 있습니다")
        clean_tags = ",".join(t.strip().replace(",", " ") for t in tags if t.strip())
        return title.strip(), body.strip(), clean_tags

    def create_note(self, notebook_id: str, title: str, body: str, tags: list[str], source: str = "") -> Note:
        nb = _parse_id("NB", self.get_notebook(notebook_id).id)
        title, body, tag_str = self._clean_note(title, body, tags)
        now = self._now()
        with self._tx() as db:
            cur = db.execute(
                "INSERT INTO notes (notebook_id, title, body, tags, source, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (nb, title, body, tag_str, source.strip(), now, now),
            )
        return self.require_note(f"N-{cur.lastrowid}")

    def update_note(self, note_id: str, *, title: str, body: str, tags: list[str], source: str = "") -> Note:
        self.require_note(note_id)
        title, body, tag_str = self._clean_note(title, body, tags)
        with self._tx() as db:
            db.execute(
                "UPDATE notes SET title = ?, body = ?, tags = ?, source = ?, updated_at = ? WHERE id = ?",
                (title, body, tag_str, source.strip(), self._now(), _parse_id("N", note_id)),
            )
        return self.require_note(note_id)

    def delete_note(self, note_id: str) -> None:
        self.require_note(note_id)
        with self._tx() as db:
            db.execute("DELETE FROM notes WHERE id = ?", (_parse_id("N", note_id),))

    def get_note(self, note_id: str) -> Note | None:
        try:
            nid = _parse_id("N", note_id)
        except NotFoundError:
            return None
        row = self._one("SELECT * FROM notes WHERE id = ?", (nid,))
        return self._note(row) if row else None

    def require_note(self, note_id: str) -> Note:
        note = self.get_note(note_id)
        if note is None:
            raise NotFoundError(f"노트 {note_id}를 찾을 수 없습니다. 노트 목록에서 ID를 확인하세요")
        return note

    def all_notes(self) -> list[Note]:
        return [self._note(r) for r in self._rows("SELECT * FROM notes ORDER BY id")]

    def list_notes(self, notebook_id: str, query: str | None = None, limit: int = 50) -> list[NoteSummary]:
        """노트 목록. query가 있으면 단어마다 제목 3점·태그 2점·본문 1점으로 점수를 매겨 점수순."""
        nb = _parse_id("NB", self.get_notebook(notebook_id).id)
        rows = self._rows("SELECT * FROM notes WHERE notebook_id = ? ORDER BY updated_at DESC, id DESC", (nb,))
        notes = [self._note(r) for r in rows]
        words = [_compact(w) for w in (query or "").split() if len(_compact(w)) >= 2]
        if words:
            scored: list[tuple[int, int, Note]] = []
            for i, n in enumerate(notes):
                title, tags, body = _compact(n.title), _compact(" ".join(n.tags)), _compact(n.body)
                score = sum(3 * (w in title) + 2 * (w in tags) + (w in body) for w in words)
                if score > 0:
                    scored.append((-score, i, n))
            notes = [n for _, _, n in sorted(scored)]
        return [self._summary(n) for n in notes[: max(1, limit)]]

    # ── 카드 ─────────────────────────────────────────────────────────

    _CARD_SQL = (
        "SELECT c.*, n.title AS note_title, n.notebook_id AS notebook_id FROM cards c JOIN notes n ON n.id = c.note_id"
    )

    @staticmethod
    def _card(row: sqlite3.Row) -> Card:
        return Card(
            id=f"C-{row['id']}",
            note_id=f"N-{row['note_id']}",
            note_title=row["note_title"],
            question=row["question"],
            answer=row["answer"],
            ease=row["ease"],
            interval_days=row["interval_days"],
            repetitions=row["repetitions"],
            due_date=row["due_date"],
            lapses=row["lapses"],
        )

    @staticmethod
    def card_key(note_id: str, question: str) -> str:
        return hashlib.sha256(f"{note_id}\x1f{_compact(question)}".encode()).hexdigest()[:40]

    def add_cards(self, note_id: str, cards: list[tuple[str, str]], created_on: str) -> list[Card]:
        """카드를 더한다. 같은 노트에 같은 질문(공백 무시)이 있으면 건너뛴다. 새로 만든 카드만 돌려준다."""
        note = self.require_note(note_id)
        created_on = _check_date(created_on)
        new_ids: list[int] = []
        with self._tx() as db:
            for question, answer in cards:
                if not question.strip() or not answer.strip():
                    raise InvalidInputError("카드 질문과 답은 비울 수 없습니다")
                cur = db.execute(
                    "INSERT OR IGNORE INTO cards (note_id, question, answer, due_date, created_at, dedupe_key)"
                    " VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        _parse_id("N", note.id),
                        question.strip(),
                        answer.strip(),
                        created_on,
                        self._now(),
                        self.card_key(note.id, question),
                    ),
                )
                if cur.rowcount and cur.lastrowid is not None:
                    new_ids.append(cur.lastrowid)
        return [self.require_card(f"C-{i}") for i in new_ids]

    def get_card(self, card_id: str) -> Card | None:
        row = self._one(f"{self._CARD_SQL} WHERE c.id = ?", (_parse_id("C", card_id),))
        return self._card(row) if row else None

    def require_card(self, card_id: str) -> Card:
        card = self.get_card(card_id)
        if card is None:
            raise NotFoundError(f"카드 {card_id}를 찾을 수 없습니다")
        return card

    def list_cards(self, notebook_id: str, note_id: str | None = None) -> list[Card]:
        nb = _parse_id("NB", self.get_notebook(notebook_id).id)
        if note_id:
            rows = self._rows(
                f"{self._CARD_SQL} WHERE n.notebook_id = ? AND c.note_id = ? ORDER BY c.id",
                (nb, _parse_id("N", note_id)),
            )
        else:
            rows = self._rows(f"{self._CARD_SQL} WHERE n.notebook_id = ? ORDER BY c.id", (nb,))
        return [self._card(r) for r in rows]

    def list_due_cards(self, notebook_id: str, base_date: str, limit: int = 20) -> list[Card]:
        nb = _parse_id("NB", self.get_notebook(notebook_id).id)
        rows = self._rows(
            f"{self._CARD_SQL} WHERE n.notebook_id = ? AND c.due_date <= ? ORDER BY c.due_date, c.id LIMIT ?",
            (nb, _check_date(base_date), max(1, limit)),
        )
        return [self._card(r) for r in rows]

    # ── 복습 ─────────────────────────────────────────────────────────

    def record_review(self, card_id: str, grade: Grade, reviewed_on: str) -> Card:
        if grade not in _GRADES:
            raise InvalidInputError(f"등급은 {', '.join(_GRADES)} 중 하나입니다: {grade}")
        card = self.require_card(card_id)
        reviewed_on = _check_date(reviewed_on)
        ease, interval, reps = srs.schedule(card.ease, card.interval_days, card.repetitions, grade)
        cid = _parse_id("C", card.id)
        with self._tx() as db:
            db.execute(
                "UPDATE cards SET ease = ?, interval_days = ?, repetitions = ?, due_date = ?,"
                " lapses = lapses + ? WHERE id = ?",
                (ease, interval, reps, srs.next_due(reviewed_on, interval), 1 if grade == "again" else 0, cid),
            )
            db.execute("INSERT INTO reviews (card_id, grade, reviewed_on) VALUES (?, ?, ?)", (cid, grade, reviewed_on))
        return self.require_card(card_id)

    def review_stats(self, notebook_id: str, base_date: str) -> ReviewStats:
        nb = _parse_id("NB", self.get_notebook(notebook_id).id)
        base = _check_date(base_date)
        cards = self.list_cards(notebook_id)
        week_from = _days_before(base, 6)
        rows = self._rows(
            "SELECT r.grade, r.reviewed_on FROM reviews r JOIN cards c ON c.id = r.card_id"
            " JOIN notes n ON n.id = c.note_id WHERE n.notebook_id = ? AND r.reviewed_on <= ?",
            (nb, base),
        )
        week = [r for r in rows if r["reviewed_on"] >= week_from]
        correct = sum(1 for r in week if r["grade"] != "again")
        days = {r["reviewed_on"] for r in rows}
        streak, cursor = 0, base
        while cursor in days:
            streak += 1
            cursor = _days_before(cursor, 1)
        return ReviewStats(
            notebook_id=notebook_id,
            base_date=base,
            total_cards=len(cards),
            due_today=sum(1 for c in cards if c.due_date <= base),
            overdue=sum(1 for c in cards if c.due_date < base),
            new_cards=sum(1 for c in cards if c.repetitions == 0 and c.lapses == 0),
            reviewed_7d=len(week),
            correct_rate_7d_pct=round(correct * 100 / len(week)) if week else None,
            streak_days=streak,
        )

    # ── 학습자 프로필 (장기 메모리) ──────────────────────────────────

    def get_profile(self, base_date: str | None = None) -> LearnerProfile:
        base = _check_date(base_date) if base_date else self.today()
        row = self._one("SELECT * FROM profile WHERE id = 1")
        assert row is not None
        weak_rows = self._rows(
            "SELECT n.id AS note_id, n.title AS title, COUNT(*) AS cnt FROM reviews r"
            " JOIN cards c ON c.id = r.card_id JOIN notes n ON n.id = c.note_id"
            " WHERE r.grade = 'again' AND r.reviewed_on BETWEEN ? AND ?"
            " GROUP BY n.id HAVING cnt >= 2 ORDER BY cnt DESC, n.id LIMIT 3",
            (_days_before(base, 13), base),
        )
        return LearnerProfile(
            summary_length=row["summary_length"],
            quiz_difficulty=row["quiz_difficulty"],
            weak_notes=[
                WeakNote(note_id=f"N-{r['note_id']}", title=r["title"], again_count_14d=r["cnt"]) for r in weak_rows
            ],
        )

    def set_preferences(
        self, summary_length: SummaryLength | None = None, quiz_difficulty: QuizDifficulty | None = None
    ) -> LearnerProfile:
        if summary_length is not None and summary_length not in ("short", "normal", "long"):
            raise InvalidInputError(f"요약 길이는 short, normal, long 중 하나입니다: {summary_length}")
        if quiz_difficulty is not None and quiz_difficulty not in ("easy", "normal", "hard"):
            raise InvalidInputError(f"퀴즈 난이도는 easy, normal, hard 중 하나입니다: {quiz_difficulty}")
        with self._tx() as db:
            if summary_length is not None:
                db.execute("UPDATE profile SET summary_length = ? WHERE id = 1", (summary_length,))
            if quiz_difficulty is not None:
                db.execute("UPDATE profile SET quiz_difficulty = ? WHERE id = 1", (quiz_difficulty,))
        return self.get_profile()

    # ── 제안 ─────────────────────────────────────────────────────────

    @staticmethod
    def _proposal(row: sqlite3.Row) -> ProposalRecord:
        return ProposalRecord(
            id=row["id"],
            dedupe_key=row["dedupe_key"],
            kind=row["kind"],
            subject_id=row["subject_id"],
            title=row["title"],
            payload=json.loads(row["payload"]),
            reasons=json.loads(row["reasons"]),
            source=row["source"],
            status=row["status"],
            created_at=row["created_at"],
            applied=json.loads(row["applied"]),
        )

    def _apply(self, kind: str, payload: dict[str, Any], accepted_on: str) -> tuple[str, dict[str, Any]]:
        if kind == "quiz.cards_add":
            raw = payload.get("cards") or []
            pairs = [(str(c.get("question", "")), str(c.get("answer", ""))) for c in raw if isinstance(c, dict)]
            if not pairs:
                raise InvalidInputError("quiz.cards_add 제안에 카드가 없습니다")
            created = self.add_cards(str(payload.get("note_id", "")), pairs, accepted_on)
            return "applied", {"card_ids": [c.id for c in created]}
        if kind == "review.daily_plan":
            return "applied", {"card_ids": list(payload.get("card_ids") or [])}
        if kind == "profile.update":
            profile = self.set_preferences(
                summary_length=payload.get("summary_length"), quiz_difficulty=payload.get("quiz_difficulty")
            )
            return "applied", {"summary_length": profile.summary_length, "quiz_difficulty": profile.quiz_difficulty}
        return "saved", {}

    def accept_proposal(self, draft: dict[str, Any], accepted_on: str) -> ProposalRecord:
        """사용자가 수락한 제안을 저장하고 반영한다. 같은 dedupe_key는 한 번만 — 두 번째부터는 기존 기록을 돌려준다."""
        key = str(draft.get("dedupe_key") or "")
        kind = str(draft.get("kind") or "")
        if not key or not kind:
            raise InvalidInputError("제안에 kind와 dedupe_key가 필요합니다")
        with self._lock:
            existing = self._one("SELECT * FROM proposals WHERE dedupe_key = ?", (key,))
            if existing is not None:
                return self._proposal(existing)
            payload = dict(draft.get("payload") or {})
            status, applied = self._apply(kind, payload, _check_date(accepted_on))
            with self._tx() as db:
                cur = db.execute(
                    "INSERT INTO proposals (dedupe_key, kind, subject_id, title, payload, reasons, source, status,"
                    " applied, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        key,
                        kind,
                        str(draft.get("subject_id") or ""),
                        str(draft.get("title") or ""),
                        json.dumps(payload, ensure_ascii=False),
                        json.dumps(list(draft.get("reasons") or []), ensure_ascii=False),
                        str(draft.get("source") or "chat"),
                        status,
                        json.dumps(applied, ensure_ascii=False),
                        self._now(),
                    ),
                )
            row = self._one("SELECT * FROM proposals WHERE id = ?", (cur.lastrowid,))
            assert row is not None
            return self._proposal(row)

    def list_proposals(self, subject_id: str | None = None, kind: str | None = None) -> list[ProposalRecord]:
        sql = "SELECT * FROM proposals WHERE 1 = 1"
        params: list[str] = []
        if subject_id:
            sql, params = sql + " AND subject_id = ?", [*params, subject_id]
        if kind:
            sql, params = sql + " AND kind = ?", [*params, kind]
        return [self._proposal(r) for r in self._rows(sql + " ORDER BY id DESC", params)]

    def get_daily_plan(self, notebook_id: str, base_date: str) -> ProposalRecord | None:
        base = _check_date(base_date)
        for rec in self.list_proposals(subject_id=notebook_id, kind="review.daily_plan"):
            if rec.payload.get("base_date") == base:
                return rec
        return None
