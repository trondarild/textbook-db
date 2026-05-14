#!/usr/bin/env python3
"""Build a unified lookup table of unique terms across all extracted indices.

Usage:
  python build_lookup.py                        # merge all books in registry
  python build_lookup.py kandel2021 buzaki2011  # merge specific books
  python build_lookup.py --with-subentries      # include subentry terms

Output: lookup.json
"""

import json
import sys
from pathlib import Path

from src.lookup_builder import build_lookup, load_indices

REGISTRY = Path("registry.json")
PROJECT_ROOT = Path(__file__).parent


def main() -> None:
    args = sys.argv[1:]
    with_subentries = "--with-subentries" in args
    keys = [a for a in args if not a.startswith("--")]

    registry = json.loads(REGISTRY.read_text())
    book_keys = keys if keys else list(registry.keys())
    missing = [k for k in book_keys if k not in registry]
    if missing:
        print(f"Unknown keys: {missing}")
        sys.exit(1)

    print(f"Merging {len(book_keys)} books: {', '.join(book_keys)}")
    indices = load_indices(book_keys, PROJECT_ROOT / "indices")
    lookup = build_lookup(indices, with_subentries)

    out = PROJECT_ROOT / "lookup.json"
    out.write_text(json.dumps(lookup, indent=2, ensure_ascii=False))

    cross = sum(1 for v in lookup.values() if len(v["books"]) > 1)
    print(f"  {len(lookup)} unique terms, {cross} in 2+ books → {out.name}")

    print("\nCross-book term counts:")
    for n in range(len(book_keys), 1, -1):
        count = sum(1 for v in lookup.values() if len(v["books"]) == n)
        if count:
            print(f"  in {n} books: {count}")


if __name__ == "__main__":
    main()
