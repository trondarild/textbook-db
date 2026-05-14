"""Find candidate near-duplicate terms across a lookup table.

Four strategies:
  1. abbreviation – ALL-CAPS term appears as "(ABBREV)" inside a longer term
  2. case         – terms identical after lowercasing
  3. containment  – one term is a significant substring of another
  4. token_set    – rapidfuzz token_set_ratio >= threshold, blocked by first token
"""

import re
from collections import defaultdict

from rapidfuzz import fuzz

ABBREV_IN_TERM_RE = re.compile(r"\(([A-Z][A-Z0-9\-]{1,7})\)")

STOP_WORDS = {
    "a", "an", "the", "of", "in", "and", "or", "for", "with",
    "to", "by", "on", "at", "as", "is", "its", "from",
}


def _normalise(term: str) -> str:
    return term.lower().strip(" ,;:()")


def _significant_tokens(term: str) -> list[str]:
    tokens = re.split(r"[\s\-/,;:()\[\]]+", term.lower())
    return [t for t in tokens if t and t not in STOP_WORDS and len(t) > 2]


def _first_token(term: str) -> str:
    toks = _significant_tokens(term)
    return toks[0] if toks else _normalise(term)[:4]


def find_abbreviation_pairs(terms: list[str]) -> list[dict]:
    """Match bare ALL-CAPS terms to longer terms containing them in parentheses."""
    abbrev_hosts: dict[str, list[str]] = defaultdict(list)
    for t in terms:
        for abbrev in ABBREV_IN_TERM_RE.findall(t):
            abbrev_hosts[abbrev].append(t)

    bare_abbrevs = {t for t in terms if re.match(r"^[A-Z][A-Z0-9\-]{1,6}$", t)}

    results = []
    for abbrev in bare_abbrevs:
        for host in abbrev_hosts.get(abbrev, []):
            if host != abbrev:
                results.append({"term1": abbrev, "term2": host,
                                 "match_type": "abbreviation", "score": 1.0})
    return results


def find_case_pairs(terms: list[str]) -> list[dict]:
    """Terms identical after lowercasing."""
    by_lower: dict[str, list[str]] = defaultdict(list)
    for t in terms:
        by_lower[_normalise(t)].append(t)

    results = []
    for group in by_lower.values():
        if len(group) > 1:
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    results.append({"term1": group[i], "term2": group[j],
                                     "match_type": "case", "score": 1.0})
    return results


def _by_all_tokens(terms: list[str]) -> dict[str, list[str]]:
    """Index each term under every one of its significant tokens."""
    index: dict[str, list[str]] = defaultdict(list)
    for t in terms:
        for tok in _significant_tokens(t) or [_first_token(t)]:
            index[tok].append(t)
    return index


def find_containment_pairs(terms: list[str], min_len: int = 6) -> list[dict]:
    """One term is a significant substring of another (blocked by shared tokens)."""
    by_token = _by_all_tokens(terms)

    results = []
    seen: set[tuple] = set()
    for group in by_token.values():
        if len(group) < 2:
            continue
        for i, t1 in enumerate(group):
            n1 = _normalise(t1)
            if len(n1) < min_len:
                continue
            for t2 in group[i + 1:]:
                n2 = _normalise(t2)
                if n1 == n2:
                    continue
                pair = tuple(sorted([t1, t2]))
                if pair in seen:
                    continue
                if n1 in n2 or n2 in n1:
                    shorter, longer = (t1, t2) if len(n1) < len(n2) else (t2, t1)
                    score = round(len(_normalise(shorter)) / len(_normalise(longer)), 3)
                    if score < 0.95:
                        seen.add(pair)
                        results.append({"term1": shorter, "term2": longer,
                                         "match_type": "containment", "score": score})
    return results


def find_token_set_pairs(terms: list[str], threshold: int = 80) -> list[dict]:
    """rapidfuzz token_set_ratio >= threshold, blocked by shared tokens."""
    by_token = _by_all_tokens(terms)

    results = []
    seen: set[tuple] = set()
    for group in by_token.values():
        if len(group) < 2:
            continue
        for i, t1 in enumerate(group):
            for t2 in group[i + 1:]:
                pair = tuple(sorted([t1, t2]))
                if pair in seen:
                    continue
                score = fuzz.token_set_ratio(t1, t2)
                if score >= threshold and _normalise(t1) != _normalise(t2):
                    seen.add(pair)
                    results.append({"term1": t1, "term2": t2,
                                     "match_type": "token_set",
                                     "score": round(score / 100, 3)})
    return results


def find_all_pairs(
    lookup: dict[str, dict],
    threshold: int = 80,
) -> list[dict]:
    """Run all strategies, deduplicate, attach book lists, sort by coverage then score."""
    terms = list(lookup.keys())
    results: list[dict] = []
    seen: set[tuple] = set()

    def add(new: list[dict]) -> None:
        for r in new:
            pair = tuple(sorted([r["term1"], r["term2"]]))
            if pair not in seen:
                seen.add(pair)
                r["books1"] = lookup[r["term1"]]["books"]
                r["books2"] = lookup[r["term2"]]["books"]
                results.append(r)

    add(find_abbreviation_pairs(terms))
    add(find_case_pairs(terms))
    add(find_containment_pairs(terms))
    add(find_token_set_pairs(terms, threshold))

    results.sort(key=lambda r: (
        -(len(set(r["books1"]) | set(r["books2"]))),
        -r["score"],
    ))
    return results
