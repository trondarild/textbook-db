#!/usr/bin/env python3
"""txdb — textbook-db query CLI.

Commands
--------
  lookup TERM [--expand] [--score N] [--json]
      Exact term lookup + optional fuzzy expansion via candidates table.
      Falls back to case-insensitive match when exact term is not found.

  search QUERY [--limit N] [--json]
      Fuzzy search across all terms in the DB.

  claim TEXT [--top N] [--json]
      Match free-text claim to DB terms (token overlap × n_books scoring).

  books [--json]
      List books in the DB with term counts.

  stats
      Print DB statistics.

Composability
-------------
  All commands support --json for machine-readable output.
  Combine with jq, or pipe into other tools:

      python3 txdb.py lookup hippocampus --expand --json | jq '.'
      python3 txdb.py claim "theta oscillations coordinate memory" --json
"""

import argparse
import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

from src import query_engine as qe
from src.claim_matcher import match_claim

DB_PATH = BASE_DIR / "textbook_db.sqlite"


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

def _book_label(conn, key: str) -> str:
    row = conn.execute(
        "SELECT author, year FROM books WHERE key = ?", (key,)
    ).fetchone()
    return f"{row['author']} {row['year']}" if row else key


def _fmt_hit(hit: dict, conn, label: str = "") -> None:
    prefix = f"  [{label}] " if label else "  "
    print(f"{prefix}{hit['term']}  ({hit['n_books']} book{'s' if hit['n_books'] != 1 else ''})")
    for book, pages in hit["pages"].items():
        bl = _book_label(conn, book)
        page_str = ", ".join(pages) if pages else "—"
        print(f"      {bl:<30}  pp. {page_str}")


def _print_lookup(result: dict, conn) -> None:
    if result["exact"]:
        _fmt_hit(result["exact"], conn)
    elif result["icase"]:
        for h in result["icase"]:
            _fmt_hit(h, conn, "case")
    else:
        print("  (not found)")

    if result["variants"]:
        print(f"\n  variants ({len(result['variants'])}):")
        for v in result["variants"]:
            _fmt_hit(v, conn, v.get("match_type", "~"))


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------

def cmd_lookup(args, conn) -> int:
    result = qe.full_lookup(
        args.term, conn,
        expand_results=args.expand,
        min_score=args.score / 100,
    )
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"lookup: {args.term}")
        _print_lookup(result, conn)
    return 0 if (result["exact"] or result["icase"]) else 1


def cmd_search(args, conn) -> int:
    hits = qe.search(args.query, conn, limit=args.limit)
    if args.json:
        print(json.dumps(hits, indent=2))
    else:
        print(f"search: {args.query!r}")
        if not hits:
            print("  (no results)")
        for h in hits:
            _fmt_hit(h, conn, f"{int(h['score']):3d}")
    return 0 if hits else 1


def cmd_claim(args, conn) -> int:
    lookup_data = json.loads((BASE_DIR / "lookup.json").read_text())
    matches = match_claim(args.text, lookup_data, top_n=args.top)
    if args.json:
        print(json.dumps(matches, indent=2))
    else:
        print(f"claim: {args.text!r}")
        if not matches:
            print("  (no matches)")
        for m in matches:
            bl = _book_label(conn, m["books"][0]) if m["books"] else "—"
            others = f" + {len(m['books'])-1} more" if len(m["books"]) > 1 else ""
            print(f"  [{m['score']:.2f}]  {m['term']:<45}  {bl}{others}")
    return 0 if matches else 1


def cmd_books(args, conn) -> int:
    rows = qe.books(conn)
    if args.json:
        print(json.dumps(rows, indent=2))
    else:
        print(f"{'key':<18} {'year':>4}  {'author':<22}  {'terms':>6}  title")
        print("-" * 80)
        for b in rows:
            print(f"{b['key']:<18} {b['year']:>4}  {b['author']:<22}  "
                  f"{b['term_count']:>6}  {b['title']}")
    return 0


def cmd_stats(args, conn) -> int:
    s = qe.stats(conn)
    if args.json:
        print(json.dumps(s, indent=2))
    else:
        for k, v in s.items():
            print(f"  {k:<22} {v:>8,}")
    return 0


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="txdb",
        description="textbook-db query CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--db", default=str(DB_PATH), help="path to textbook_db.sqlite")

    sub = p.add_subparsers(dest="cmd", required=True)

    lo = sub.add_parser("lookup", help="exact term lookup")
    lo.add_argument("term")
    lo.add_argument("--expand", action="store_true", help="include fuzzy variants")
    lo.add_argument("--score", type=int, default=60,
                    help="minimum candidate score 0–100 (default 60)")
    lo.add_argument("--json", action="store_true")

    se = sub.add_parser("search", help="fuzzy search across all terms")
    se.add_argument("query")
    se.add_argument("--limit", type=int, default=20)
    se.add_argument("--json", action="store_true")

    cl = sub.add_parser("claim", help="match claim text to DB terms")
    cl.add_argument("text")
    cl.add_argument("--top", type=int, default=10)
    cl.add_argument("--json", action="store_true")

    bk = sub.add_parser("books", help="list books in DB")
    bk.add_argument("--json", action="store_true")

    st = sub.add_parser("stats", help="DB statistics")
    st.add_argument("--json", action="store_true")

    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    conn = qe.connect(Path(args.db))
    try:
        dispatch = {
            "lookup": cmd_lookup,
            "search": cmd_search,
            "claim":  cmd_claim,
            "books":  cmd_books,
            "stats":  cmd_stats,
        }
        return dispatch[args.cmd](args, conn)
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
