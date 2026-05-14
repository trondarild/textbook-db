"""SQLite schema for textbook_db: CREATE TABLE statements and DB initialisation."""

import sqlite3
from pathlib import Path

_CREATE = [
    """CREATE TABLE IF NOT EXISTS books (
        key       TEXT PRIMARY KEY,
        title     TEXT NOT NULL,
        author    TEXT NOT NULL,
        year      INTEGER NOT NULL,
        pdf_path  TEXT,
        text_path TEXT,
        md_path   TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS terms (
        id      INTEGER PRIMARY KEY,
        term    TEXT NOT NULL UNIQUE,
        n_books INTEGER NOT NULL DEFAULT 0
    )""",
    """CREATE TABLE IF NOT EXISTS occurrences (
        id       INTEGER PRIMARY KEY,
        term_id  INTEGER NOT NULL REFERENCES terms(id),
        book_key TEXT NOT NULL REFERENCES books(key),
        pages    TEXT NOT NULL DEFAULT '[]',
        UNIQUE(term_id, book_key)
    )""",
    """CREATE TABLE IF NOT EXISTS candidates (
        id         INTEGER PRIMARY KEY,
        term1_id   INTEGER NOT NULL REFERENCES terms(id),
        term2_id   INTEGER NOT NULL REFERENCES terms(id),
        match_type TEXT NOT NULL,
        score      REAL NOT NULL,
        CHECK(term1_id != term2_id)
    )""",
    """CREATE TABLE IF NOT EXISTS chapters (
        id              INTEGER PRIMARY KEY,
        book_key        TEXT NOT NULL REFERENCES books(key),
        title           TEXT NOT NULL,
        start_book_page INTEGER,
        end_book_page   INTEGER,
        ref_line        INTEGER
    )""",
    """CREATE TABLE IF NOT EXISTS "references" (
        id         INTEGER PRIMARY KEY,
        chapter_id INTEGER NOT NULL REFERENCES chapters(id),
        authors    TEXT,
        year       INTEGER,
        title      TEXT,
        venue      TEXT,
        raw        TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS term_chapters (
        term_id    INTEGER NOT NULL REFERENCES terms(id),
        chapter_id INTEGER NOT NULL REFERENCES chapters(id),
        PRIMARY KEY(term_id, chapter_id)
    )""",
]

_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_occ_term ON occurrences(term_id)",
    "CREATE INDEX IF NOT EXISTS idx_occ_book ON occurrences(book_key)",
    "CREATE INDEX IF NOT EXISTS idx_cand_t1  ON candidates(term1_id)",
    "CREATE INDEX IF NOT EXISTS idx_cand_t2  ON candidates(term2_id)",
    "CREATE INDEX IF NOT EXISTS idx_ch_book  ON chapters(book_key)",
    "CREATE INDEX IF NOT EXISTS idx_tc_term  ON term_chapters(term_id)",
    "CREATE INDEX IF NOT EXISTS idx_tc_ch    ON term_chapters(chapter_id)",
    'CREATE INDEX IF NOT EXISTS idx_ref_ch   ON "references"(chapter_id)',
]

_DROP_ORDER = [
    "term_chapters", '"references"', "chapters", "candidates",
    "occurrences", "terms", "books",
]


def init_db(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    for stmt in _CREATE + _INDEXES:
        conn.execute(stmt)
    conn.commit()
    return conn


def drop_all(conn: sqlite3.Connection) -> None:
    for tbl in _DROP_ORDER:
        conn.execute(f"DROP TABLE IF EXISTS {tbl}")
    conn.commit()
