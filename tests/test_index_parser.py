import pytest
from src.index_parser import extract_pages, normalize_term, join_continuations, parse_index


class TestExtractPages:
    def test_plain_numbers(self):
        assert extract_pages("term, 12, 34, 56") == ["12", "34", "56"]

    def test_figure_suffix(self):
        assert extract_pages("term, 12f, 34b, 56t") == ["12f", "34b", "56t"]

    def test_range(self):
        assert extract_pages("term, 12–15") == ["12–15"]

    def test_range_hyphen(self):
        assert extract_pages("term, 12-15") == ["12-15"]

    def test_mixed(self):
        assert extract_pages("term, 1, 23f, 100–105, 200b") == ["1", "23f", "100–105", "200b"]

    def test_no_pages(self):
        assert extract_pages("term with no numbers here") == []

    def test_ignores_long_numbers(self):
        # 5-digit numbers are not page refs
        assert extract_pages("ISBN 12345") == []


class TestNormalizeTerm:
    def test_strips_trailing_punctuation(self):
        assert normalize_term("term, ") == "term"

    def test_strips_see_also(self):
        assert normalize_term("working memory, see also long-term memory") == "working memory"

    def test_strips_see(self):
        assert normalize_term("fMRI, see functional MRI") == "fMRI"

    def test_preserves_parenthetical(self):
        assert normalize_term("EEG (electroencephalogram)") == "EEG (electroencephalogram)"

    def test_empty_string(self):
        assert normalize_term("") == ""


class TestJoinContinuations:
    def test_only_pages_continuation(self):
        lines = ["Term, 12, 34,\n", "56, 78\n"]
        result = join_continuations(lines)
        assert result == ["Term, 12, 34, 56, 78"]

    def test_comma_plus_lowercase_continuation(self):
        lines = ["Brain-computer interface,\n", "invasive methods, 45\n"]
        result = join_continuations(lines)
        assert result == ["Brain-computer interface, invasive methods, 45"]

    def test_no_join_for_uppercase_next(self):
        lines = ["Term A, 12\n", "Term B, 34\n"]
        result = join_continuations(lines)
        assert len(result) == 2

    def test_blank_line_not_joined(self):
        lines = ["Term A, 12\n", "\n", "Term B, 34\n"]
        result = join_continuations(lines)
        assert len(result) == 3


class TestParseIndex:
    def test_capitalize_strategy_main_entry(self):
        lines = ["Hippocampus, 12, 34\n"]
        result = parse_index(lines, "capitalize")
        assert "Hippocampus" in result
        assert result["Hippocampus"] == ["12", "34"]

    def test_capitalize_strategy_subentry(self):
        lines = ["Hippocampus\n", "in memory formation, 12\n"]
        result = parse_index(lines, "capitalize")
        assert "Hippocampus > in memory formation" in result
        assert "in memory formation" not in result

    def test_indent_only_lowercase_as_main(self):
        lines = ["hippocampus, 12, 34\n", "thalamus, 56\n"]
        result = parse_index(lines, "indent_only")
        assert "hippocampus" in result
        assert "thalamus" in result

    def test_indented_subentry_both_strategies(self):
        lines = ["Cortex, 10\n", "  visual, 20\n"]
        for strategy in ("capitalize", "indent_only"):
            result = parse_index(lines, strategy)
            assert "Cortex > visual" in result

    def test_skip_lines(self):
        lines = ["Index\n", "\n", "A\n", "Amygdala, 5\n"]
        result = parse_index(lines, "capitalize")
        assert "Amygdala" in result
        assert "Index" not in result

    def test_see_also_stripped(self):
        lines = ["Thalamus, see also Basal ganglia\n"]
        result = parse_index(lines, "capitalize")
        assert "Thalamus" in result
        assert "Basal ganglia" not in str(list(result.keys()))

    def test_page_deduplication_not_enforced(self):
        # Pages are stored as-is; deduplication is left to consumers
        lines = ["Term, 10, 10\n"]
        result = parse_index(lines, "capitalize")
        assert result["Term"].count("10") == 2

    def test_empty_input(self):
        assert parse_index([], "capitalize") == {}
