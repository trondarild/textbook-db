import pytest
from src.lookup_builder import build_lookup


INDICES = {
    "book_a": {
        "Hippocampus": ["12", "34"],
        "Thalamus": ["56"],
        "Hippocampus > in memory": ["12"],
    },
    "book_b": {
        "Hippocampus": ["99"],
        "Cortex": ["1", "2"],
    },
}


class TestBuildLookup:
    def test_unique_term_has_one_book(self):
        result = build_lookup(INDICES)
        assert result["Thalamus"]["books"] == ["book_a"]
        assert result["Thalamus"]["pages"] == {"book_a": ["56"]}

    def test_shared_term_has_both_books(self):
        result = build_lookup(INDICES)
        assert set(result["Hippocampus"]["books"]) == {"book_a", "book_b"}

    def test_pages_per_book_stored_separately(self):
        result = build_lookup(INDICES)
        assert result["Hippocampus"]["pages"]["book_a"] == ["12", "34"]
        assert result["Hippocampus"]["pages"]["book_b"] == ["99"]

    def test_subentries_excluded_by_default(self):
        result = build_lookup(INDICES)
        assert not any(">" in t for t in result)

    def test_subentries_included_when_requested(self):
        result = build_lookup(INDICES, with_subentries=True)
        assert "Hippocampus > in memory" in result

    def test_sorted_by_book_count_then_alpha(self):
        result = build_lookup(INDICES)
        keys = list(result.keys())
        # Hippocampus (2 books) should come before Cortex and Thalamus (1 book each)
        assert keys.index("Hippocampus") < keys.index("Cortex")
        assert keys.index("Hippocampus") < keys.index("Thalamus")

    def test_empty_indices(self):
        assert build_lookup({}) == {}

    def test_no_duplicate_book_entries(self):
        # If a book appears twice in the loop it should still only be listed once
        result = build_lookup(INDICES)
        for v in result.values():
            assert len(v["books"]) == len(set(v["books"]))
