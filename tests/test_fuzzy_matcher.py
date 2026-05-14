import pytest
from src.fuzzy_matcher import (
    find_abbreviation_pairs,
    find_case_pairs,
    find_containment_pairs,
    find_token_set_pairs,
    find_all_pairs,
)


def terms_from_pairs(pairs, match_type=None):
    if match_type:
        pairs = [p for p in pairs if p["match_type"] == match_type]
    return {(p["term1"], p["term2"]) for p in pairs}


class TestAbbreviationPairs:
    def test_finds_known_pair(self):
        terms = ["EEG", "Electroencephalogram (EEG)", "Thalamus"]
        pairs = find_abbreviation_pairs(terms)
        found = terms_from_pairs(pairs)
        assert ("EEG", "Electroencephalogram (EEG)") in found

    def test_no_self_match(self):
        terms = ["EEG", "Thalamus"]
        pairs = find_abbreviation_pairs(terms)
        assert all(p["term1"] != p["term2"] for p in pairs)

    def test_multiple_expansions(self):
        terms = ["TMS", "Transcranial magnetic stimulation (TMS)",
                 "TMS in depression (TMS)", "Cortex"]
        pairs = find_abbreviation_pairs(terms)
        tms_pairs = [p for p in pairs if p["term1"] == "TMS"]
        assert len(tms_pairs) == 2

    def test_score_is_1(self):
        terms = ["PET", "Positron emission tomography (PET)"]
        pairs = find_abbreviation_pairs(terms)
        assert all(p["score"] == 1.0 for p in pairs)

    def test_no_pairs_when_no_abbrevs(self):
        terms = ["hippocampus", "thalamus", "cortex"]
        assert find_abbreviation_pairs(terms) == []


class TestCasePairs:
    def test_finds_case_variant(self):
        terms = ["Thalamus", "thalamus", "Cortex"]
        pairs = find_case_pairs(terms)
        found = terms_from_pairs(pairs)
        assert ("Thalamus", "thalamus") in found or ("thalamus", "Thalamus") in found

    def test_no_false_positives(self):
        terms = ["Hippocampus", "Thalamus", "Cortex"]
        assert find_case_pairs(terms) == []

    def test_parenthetical_case(self):
        terms = ["(fMRI)", "fMRI"]
        pairs = find_case_pairs(terms)
        assert len(pairs) == 1


class TestContainmentPairs:
    def test_substring_found(self):
        terms = ["working memory", "visual working memory"]
        pairs = find_containment_pairs(terms)
        found = terms_from_pairs(pairs)
        assert ("working memory", "visual working memory") in found

    def test_score_is_length_ratio(self):
        terms = ["memory", "working memory"]
        pairs = find_containment_pairs(terms, min_len=4)
        assert pairs[0]["score"] == pytest.approx(len("memory") / len("working memory"), abs=0.01)

    def test_no_near_identical(self):
        # Terms differing only by trailing 's' have score ~0.95+ — should be excluded
        terms = ["hippocampus", "hippocampuss"]
        pairs = find_containment_pairs(terms)
        assert pairs == []

    def test_min_len_respected(self):
        terms = ["go", "go away"]
        pairs = find_containment_pairs(terms, min_len=6)
        assert pairs == []


class TestTokenSetPairs:
    def test_finds_similar_terms(self):
        terms = ["long-term potentiation", "potentiation long-term", "hippocampus"]
        pairs = find_token_set_pairs(terms, threshold=80)
        found = terms_from_pairs(pairs)
        assert len(found) >= 1

    def test_threshold_respected(self):
        terms = ["working memory", "working memory capacity"]
        high = find_token_set_pairs(terms, threshold=95)
        low = find_token_set_pairs(terms, threshold=60)
        assert len(low) >= len(high)

    def test_no_self_match(self):
        terms = ["hippocampus", "hippocampus"]
        pairs = find_token_set_pairs(terms)
        assert all(p["term1"] != p["term2"] for p in pairs)


class TestFindAllPairs:
    def test_deduplicates_across_strategies(self):
        lookup = {
            "EEG": {"books": ["a"], "pages": {"a": ["1"]}},
            "Electroencephalogram (EEG)": {"books": ["b"], "pages": {"b": ["2"]}},
        }
        results = find_all_pairs(lookup)
        pairs = terms_from_pairs(results)
        # Should appear exactly once despite multiple strategies potentially matching
        matching = [r for r in results
                    if set([r["term1"], r["term2"]]) == {"EEG", "Electroencephalogram (EEG)"}]
        assert len(matching) == 1

    def test_books_attached(self):
        lookup = {
            "Thalamus": {"books": ["book_a"], "pages": {}},
            "thalamus": {"books": ["book_b"], "pages": {}},
        }
        results = find_all_pairs(lookup)
        assert len(results) >= 1
        assert "books1" in results[0]
        assert "books2" in results[0]

    def test_sorted_by_coverage(self):
        lookup = {
            "EEG": {"books": ["a", "b", "c"], "pages": {}},
            "Electroencephalogram (EEG)": {"books": ["a", "b", "c"], "pages": {}},
            "Thalamus": {"books": ["a"], "pages": {}},
            "thalamus": {"books": ["b"], "pages": {}},
        }
        results = find_all_pairs(lookup)
        # EEG pair covers 3 books, Thalamus pair covers 2 — EEG should come first
        eeg_idx = next(i for i, r in enumerate(results)
                       if "EEG" in [r["term1"], r["term2"]] and
                       "Electroencephalogram" in (r["term1"] + r["term2"]))
        thal_idx = next(i for i, r in enumerate(results)
                        if set([r["term1"], r["term2"]]) == {"Thalamus", "thalamus"})
        assert eeg_idx < thal_idx
