#!/usr/bin/env python3
"""Populate textbook_db.sqlite from registry + lookup + candidates.

Re-runnable: deletes and recreates the database on each run.
Chapters and references are populated by extract_refs.py once that pipeline runs.
"""

import json
import sys
from pathlib import Path

from src.schema import init_db

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "textbook_db.sqlite"


def load(db_path: Path = DB_PATH, verbose: bool = True) -> None:
    registry   = json.loads((BASE_DIR / "registry.json").read_text())
    lookup     = json.loads((BASE_DIR / "lookup.json").read_text())
    candidates = json.loads((BASE_DIR / "candidates.json").read_text())

    if db_path.exists():
        db_path.unlink()
    conn = init_db(db_path)

    # books — normalise pdf/epub_path → pdf_path
    book_rows = []
    for k, v in registry.items():
        book_rows.append({
            "key":   k,
            "title": v["title"],
            "author": v["author"],
            "year":  v["year"],
            "pdf":   v.get("pdf") or v.get("epub_path"),
            "text":  v.get("text"),
        })
    conn.executemany(
        "INSERT INTO books(key, title, author, year, pdf_path, text_path) "
        "VALUES (:key, :title, :author, :year, :pdf, :text)",
        book_rows,
    )
    if verbose:
        print(f"books:      {len(registry)}")

    # terms + occurrences
    term_id: dict[str, int] = {}
    for term, entry in lookup.items():
        cur = conn.execute(
            "INSERT INTO terms(term, n_books) VALUES (?, ?)",
            (term, len(entry["books"])),
        )
        term_id[term] = cur.lastrowid
        for book_key, pages in entry["pages"].items():
            conn.execute(
                "INSERT INTO occurrences(term_id, book_key, pages) VALUES (?, ?, ?)",
                (term_id[term], book_key, json.dumps(pages)),
            )
    if verbose:
        print(f"terms:      {len(term_id)}")

    # candidates — normalise term order so term1_id < term2_id
    rows = []
    for c in candidates:
        t1, t2 = c["term1"], c["term2"]
        if t1 not in term_id or t2 not in term_id:
            continue
        id1, id2 = term_id[t1], term_id[t2]
        if id1 > id2:
            id1, id2 = id2, id1
        rows.append((id1, id2, c["match_type"], c["score"]))
    conn.executemany(
        "INSERT INTO candidates(term1_id, term2_id, match_type, score) "
        "VALUES (?, ?, ?, ?)",
        rows,
    )
    if verbose:
        print(f"candidates: {len(rows)}")

    conn.commit()
    conn.close()
    if verbose:
        print(f"written  →  {db_path}")


if __name__ == "__main__":
    load()
