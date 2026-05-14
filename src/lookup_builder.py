"""Build a unified term lookup table from per-book index JSONs."""

import json
from pathlib import Path


def build_lookup(
    indices: dict[str, dict[str, list[str]]],
    with_subentries: bool = False,
) -> dict[str, dict]:
    """Merge per-book indices into a single lookup table.

    Args:
        indices: {book_key: {term: [pages]}} — pre-loaded index dicts.
        with_subentries: include "parent > sub" terms when True.

    Returns:
        {term: {"books": [book_key, ...], "pages": {book_key: [pages]}}}
        Sorted by number of books desc, then alphabetically.
    """
    lookup: dict[str, dict] = {}

    for key, index in indices.items():
        for term, pages in index.items():
            if not with_subentries and ">" in term:
                continue
            if term not in lookup:
                lookup[term] = {"books": [], "pages": {}}
            if key not in lookup[term]["books"]:
                lookup[term]["books"].append(key)
            lookup[term]["pages"][key] = pages

    # Second pass: fill empty page lists from subentries.
    # e.g. 'hippocampus' pages=[] in Gazzaniga, but 'hippocampus and' has pages —
    # aggregate all subentry pages whose key starts with term + " ".
    for key, index in indices.items():
        for term, entry in lookup.items():
            if entry["pages"].get(key) != []:
                continue
            prefix = term + " "
            seen: set[str] = set()
            agg: list[str] = []
            for idx_term, idx_pages in index.items():
                if idx_term.startswith(prefix) and idx_pages:
                    for p in idx_pages:
                        if p not in seen:
                            seen.add(p)
                            agg.append(p)
            if agg:
                entry["pages"][key] = agg

    return dict(
        sorted(lookup.items(), key=lambda kv: (-len(kv[1]["books"]), kv[0].lower()))
    )


def load_indices(book_keys: list[str], indices_dir: Path) -> dict[str, dict[str, list[str]]]:
    result = {}
    for key in book_keys:
        path = indices_dir / f"{key}.json"
        if path.exists():
            result[key] = json.loads(path.read_text())
        else:
            print(f"  [{key}] index not found at {path} — run extract_index.py first")
    return result
