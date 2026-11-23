"""SQLite 스키마. 토이 프로젝트라 마이그레이션 도구 없이 ``CREATE TABLE IF NOT EXISTS``로 둔다."""

DDL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS notebooks (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    notebook_id INTEGER NOT NULL REFERENCES notebooks(id) ON DELETE CASCADE,
    title       TEXT NOT NULL,
    body        TEXT NOT NULL,
    tags        TEXT NOT NULL DEFAULT '',
    source      TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cards (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    note_id       INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
    question      TEXT NOT NULL,
    answer        TEXT NOT NULL,
    ease          REAL NOT NULL DEFAULT 2.5,
    interval_days INTEGER NOT NULL DEFAULT 0,
    repetitions   INTEGER NOT NULL DEFAULT 0,
    lapses        INTEGER NOT NULL DEFAULT 0,
    due_date      TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    dedupe_key    TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS reviews (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id     INTEGER NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
    grade       TEXT NOT NULL CHECK (grade IN ('again', 'hard', 'good', 'easy')),
    reviewed_on TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS proposals (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    dedupe_key  TEXT NOT NULL UNIQUE,
    kind        TEXT NOT NULL,
    subject_id  TEXT NOT NULL,
    title       TEXT NOT NULL,
    payload     TEXT NOT NULL,
    reasons     TEXT NOT NULL,
    source      TEXT NOT NULL,
    status      TEXT NOT NULL,
    applied     TEXT NOT NULL DEFAULT '{}',
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS profile (
    id              INTEGER PRIMARY KEY CHECK (id = 1),
    summary_length  TEXT NOT NULL DEFAULT 'normal',
    quiz_difficulty TEXT NOT NULL DEFAULT 'normal'
);

CREATE INDEX IF NOT EXISTS ix_notes_notebook ON notes(notebook_id);
CREATE INDEX IF NOT EXISTS ix_cards_note ON cards(note_id);
CREATE INDEX IF NOT EXISTS ix_reviews_card ON reviews(card_id);
"""
