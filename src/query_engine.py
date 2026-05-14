"""High-level query API over textbook_db.sqlite."""

import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "textbook_db.sqlite"


def connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ---------------------------------------------------------------------------
# Core lookups
# ---------------------------------------------------------------------------

def lookup(term: str, conn: sqlite3.Connection) -> dict:
    """Exact lookup (case-sensitive). Returns hit or {found: False}."""
    row = conn.execute(
        "SELECT id, term, n_books FROM terms WHERE term = ?", (term,)
    ).fetchone()
    if not row:
        return {"term": term, "found": False, "n_books": 0, "books": [], "pages": {}}

    occs = conn.execute(
        "SELECT book_key, pages FROM occurrences WHERE term_id = ?",
        (row["id"],),
    ).fetchall()
    books = [o["book_key"] for o in occs]
    pages = {o["book_key"]: json.loads(o["pages"]) for o in occs}
    return {"term": term, "found": True, "n_books": row["n_books"],
            "books": books, "pages": pages}


def lookup_icase(term: str, conn: sqlite3.Connection) -> list[dict]:
    """Case-insensitive lookup — may return multiple hits."""
    rows = conn.execute(
        "SELECT term FROM terms WHERE lower(term) = lower(?)", (term,)
    ).fetchall()
    return [lookup(r["term"], conn) for r in rows]


def expand(term: str, conn: sqlite3.Connection, min_score: float = 0.6) -> list[dict]:
    """Return fuzzy variants of *term* via the candidates table."""
    row = conn.execute("SELECT id FROM terms WHERE term = ?", (term,)).fetchone()
    if not row:
        return []
    tid = row["id"]

    rows = conn.execute("""
        SELECT t2.term, c.match_type, c.score
        FROM candidates c
        JOIN terms t2 ON t2.id = CASE
            WHEN c.term1_id = :tid THEN c.term2_id
            ELSE c.term1_id END
        WHERE (c.term1_id = :tid OR c.term2_id = :tid)
          AND t2.id != :tid
          AND c.score >= :min_score
        ORDER BY c.score DESC, t2.term
    """, {"tid": tid, "min_score": min_score}).fetchall()

    variants = []
    for r in rows:
        hit = lookup(r["term"], conn)
        hit["match_type"] = r["match_type"]
        hit["match_score"] = r["score"]
        variants.append(hit)
    return variants


def search(query: str, conn: sqlite3.Connection, limit: int = 20) -> list[dict]:
    """Fuzzy search across all term names; returns ranked hits."""
    from rapidfuzz import fuzz, process

    all_terms = [r[0] for r in conn.execute("SELECT term FROM terms").fetchall()]
    matches = process.extract(
        query, all_terms, scorer=fuzz.token_set_ratio, limit=limit * 2
    )
    results = []
    for term, score, _ in matches:
        if score < 50:
            continue
        hit = lookup(term, conn)
        hit["score"] = score
        results.append(hit)
        if len(results) == limit:
            break
    return results


# ---------------------------------------------------------------------------
# Aggregated / formatted lookups
# ---------------------------------------------------------------------------

def full_lookup(term: str, conn: sqlite3.Connection,
                expand_results: bool = True,
                min_score: float = 0.6) -> dict:
    """Lookup + optional expansion + case-insensitive fallback.

    Returns:
        exact      — direct hit (or None)
        icase      — case-insensitive hits when exact misses
        variants   — fuzzy candidates (if expand=True)
    """
    exact = lookup(term, conn)
    icase = [] if exact["found"] else lookup_icase(term, conn)
    variants = expand(term, conn, min_score) if expand_results and exact["found"] else []

    # Also expand icase hits
    if not exact["found"] and icase and expand_results:
        seen = {h["term"] for h in icase}
        for hit in icase:
            for v in expand(hit["term"], conn, min_score):
                if v["term"] not in seen:
                    seen.add(v["term"])
                    variants.append(v)

    return {"exact": exact if exact["found"] else None,
            "icase": icase,
            "variants": variants}


def books(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("""
        SELECT b.key, b.title, b.author, b.year,
               COUNT(DISTINCT o.id) AS term_count
        FROM books b LEFT JOIN occurrences o ON o.book_key = b.key
        GROUP BY b.key ORDER BY b.year
    """).fetchall()
    return [dict(r) for r in rows]


def stats(conn: sqlite3.Connection) -> dict:
    def n(sql):
        return conn.execute(sql).fetchone()[0]
    return {
        "books":            n("SELECT COUNT(*) FROM books"),
        "terms":            n("SELECT COUNT(*) FROM terms"),
        "occurrences":      n("SELECT COUNT(*) FROM occurrences"),
        "candidates":       n("SELECT COUNT(*) FROM candidates"),
        "cross_book_terms": n("SELECT COUNT(*) FROM terms WHERE n_books > 1"),
    }
