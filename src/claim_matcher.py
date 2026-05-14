"""Match .amap claim text to terms in the textbook lookup table.

Strategy: extract significant tokens from the claim text, find lookup terms
that share those tokens, score by token overlap × cross-book coverage, rank.
Pure lexical — no embeddings required for a first pass.
"""

from collections import defaultdict

from src.fuzzy_matcher import _significant_tokens, _by_all_tokens


def match_claim(
    claim_text: str,
    lookup: dict[str, dict],
    top_n: int = 10,
) -> list[dict]:
    """Return ranked term matches for a single claim text.

    lookup: {term: {books: [...], pages: {book_key: [page_str]}}}

    Each result dict:
        term          — matched lookup term
        books         — list of book keys containing the term
        pages         — {book_key: [pages]} dict
        n_books       — number of books
        token_overlap — fraction of claim tokens shared with term (recall-oriented)
        score         — token_overlap × n_books  (penalises rare terms)
    """
    claim_tokens = set(_significant_tokens(claim_text))
    if not claim_tokens:
        return []

    term_index = _by_all_tokens(list(lookup.keys()))

    best_overlap: dict[str, float] = defaultdict(float)
    for token in claim_tokens:
        for term in term_index.get(token, []):
            term_tokens = set(_significant_tokens(term))
            if not term_tokens:
                continue
            overlap = len(claim_tokens & term_tokens) / len(claim_tokens)
            if overlap > best_overlap[term]:
                best_overlap[term] = overlap

    if not best_overlap:
        return []

    results = []
    for term, overlap in best_overlap.items():
        entry = lookup[term]
        n_books = len(entry['books'])
        results.append({
            'term':          term,
            'books':         entry['books'],
            'pages':         entry['pages'],
            'n_books':       n_books,
            'token_overlap': round(overlap, 3),
            'score':         round(overlap * n_books, 3),
        })

    results.sort(key=lambda r: (-r['score'], -r['n_books'], r['term']))
    return results[:top_n]


def match_claims(
    claims: list[dict],
    lookup: dict[str, dict],
    top_n: int = 10,
) -> list[dict]:
    """Batch version: add a 'matches' key to each claim dict (must have 'text')."""
    return [
        {**c, 'matches': match_claim(c['text'], lookup, top_n)}
        for c in claims
    ]
