#!/usr/bin/env python3
"""Find candidate near-duplicate terms in lookup.json.

Usage:
  python fuzzy_match.py                   # run all strategies
  python fuzzy_match.py --threshold 85    # override token_set threshold (default 80)
  python fuzzy_match.py --show            # print top 30 candidates to stdout

Output: candidates.json
"""

import json
import sys
from pathlib import Path

from src.fuzzy_matcher import find_all_pairs

LOOKUP_PATH = Path("lookup.json")
OUT_PATH = Path("candidates.json")


def main() -> None:
    args = sys.argv[1:]
    show = "--show" in args
    threshold = 80
    for i, a in enumerate(args):
        if a == "--threshold" and i + 1 < len(args):
            threshold = int(args[i + 1])
        elif a.startswith("--threshold="):
            threshold = int(a.split("=")[1])

    lookup = json.loads(LOOKUP_PATH.read_text())
    print(f"Terms: {len(lookup)}")

    results = find_all_pairs(lookup, threshold)
    OUT_PATH.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"{len(results)} candidate pairs → {OUT_PATH}")

    if show:
        print("\nTop 30 candidates:")
        for r in results[:30]:
            books = sorted(set(r["books1"]) | set(r["books2"]))
            print(f"  [{r['match_type']:<12} {r['score']:.2f}] "
                  f"{r['term1']!r}  ↔  {r['term2']!r}  ({', '.join(books)})")


if __name__ == "__main__":
    main()
