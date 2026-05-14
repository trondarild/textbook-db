import pytest
from src.claim_matcher import match_claim, match_claims

_LOOKUP = {
    "hippocampus": {
        "books": ["b1", "b2", "b3"],
        "pages": {"b1": ["10"], "b2": ["20"], "b3": ["30"]},
    },
    "working memory": {
        "books": ["b1", "b2"],
        "pages": {"b1": ["5"], "b2": ["15"]},
    },
    "long-term potentiation": {
        "books": ["b1"],
        "pages": {"b1": ["100"]},
    },
    "theta oscillation": {
        "books": ["b2"],
        "pages": {"b2": ["50"]},
    },
    "cortex": {
        "books": ["b1", "b2"],
        "pages": {"b1": ["1"], "b2": ["2"]},
    },
}


class TestMatchClaim:
    def test_finds_relevant_term(self):
        matches = match_claim("The hippocampus plays a role in memory", _LOOKUP)
        assert any(m['term'] == 'hippocampus' for m in matches)

    def test_sorted_by_score_descending(self):
        matches = match_claim("hippocampus working memory", _LOOKUP)
        scores = [m['score'] for m in matches]
        assert scores == sorted(scores, reverse=True)

    def test_n_books_in_result(self):
        matches = match_claim("hippocampus", _LOOKUP)
        hipp = next(m for m in matches if m['term'] == 'hippocampus')
        assert hipp['n_books'] == 3

    def test_high_coverage_ranks_above_rare(self):
        matches = match_claim("hippocampus", _LOOKUP)
        terms = [m['term'] for m in matches]
        hipp_idx = terms.index('hippocampus')
        ltp_idx = terms.index('long-term potentiation') if 'long-term potentiation' in terms else 999
        assert hipp_idx < ltp_idx

    def test_empty_claim_returns_empty(self):
        assert match_claim("", _LOOKUP) == []

    def test_stopword_only_returns_empty(self):
        assert match_claim("the and of in", _LOOKUP) == []

    def test_top_n_respected(self):
        matches = match_claim("hippocampus memory cortex oscillation", _LOOKUP, top_n=2)
        assert len(matches) <= 2

    def test_result_has_required_keys(self):
        matches = match_claim("hippocampus", _LOOKUP)
        assert matches
        for key in ('term', 'books', 'pages', 'n_books', 'token_overlap', 'score'):
            assert key in matches[0]


class TestMatchClaims:
    def test_adds_matches_key(self):
        claims = [{'label': 'c1', 'text': 'hippocampus and memory'}]
        result = match_claims(claims, _LOOKUP)
        assert 'matches' in result[0]

    def test_preserves_other_fields(self):
        claims = [{'label': 'c1', 'type': 'T', 'text': 'hippocampus'}]
        result = match_claims(claims, _LOOKUP)
        assert result[0]['label'] == 'c1'
        assert result[0]['type'] == 'T'

    def test_batch_length_matches_input(self):
        claims = [
            {'label': 'a', 'text': 'hippocampus'},
            {'label': 'b', 'text': 'theta oscillation'},
        ]
        result = match_claims(claims, _LOOKUP)
        assert len(result) == 2
