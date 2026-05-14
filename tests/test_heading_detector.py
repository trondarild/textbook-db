import pytest
from src.heading_detector import detect_headings, annotate_segments, _heading_level


class TestDetectHeadings:
    def test_cycle_heading_level_1(self):
        text = '\nCycle 1\n\nBody text here.'
        headings = detect_headings(text)
        assert any(lvl == 1 and txt == 'Cycle 1' for _, lvl, txt in headings)

    def test_cycle_case_insensitive(self):
        text = '\nCYCLE 3\n\nSome text.'
        headings = detect_headings(text)
        assert any(lvl == 1 for _, lvl, _ in headings)

    def test_title_case_h2(self):
        text = '\nNavigation in Real Space\n\nParagraph.'
        headings = detect_headings(text)
        assert any(lvl == 2 and txt == 'Navigation in Real Space' for _, lvl, txt in headings)

    def test_all_caps_h2(self):
        text = '\nRHYTHMS OF THE BRAIN\n\nParagraph.'
        headings = detect_headings(text)
        assert any(lvl == 2 for _, lvl, _ in headings)

    def test_interior_lines_without_blanks_not_heading(self):
        # Lines that are interior (not at page boundary) with no blank neighbours
        # should never be detected as headings.
        text = 'First line\nLine two\nLine three\nLine four\nLast line'
        headings = detect_headings(text)
        interior = [h for h in headings if h[2] in ('Line two', 'Line three', 'Line four')]
        assert len(interior) == 0

    def test_terminal_punctuation_excluded(self):
        text = '\nThis ends with a period.\n\nBody.'
        headings = detect_headings(text)
        assert len(headings) == 0

    def test_pure_integer_excluded(self):
        text = '\n42\n\nBody text.'
        headings = detect_headings(text)
        assert len(headings) == 0

    def test_long_line_excluded(self):
        long_line = 'A' * 85
        text = f'\n{long_line}\n\nBody.'
        headings = detect_headings(text)
        assert len(headings) == 0

    def test_page_boundary_counts_as_blank(self):
        # First line of page has no preceding line — counts as prev_blank=True
        text = 'Introduction\n\nBody text.'
        headings = detect_headings(text)
        assert any(txt == 'Introduction' for _, _, txt in headings)

    def test_returns_list_of_tuples(self):
        text = '\nCycle 5\n\nText.'
        headings = detect_headings(text)
        assert isinstance(headings, list)
        for item in headings:
            assert len(item) == 3

    def test_short_subheading_h3(self):
        # Short mixed-case with blanks around it → level 3
        text = '\nA note\n\nBody.'
        headings = detect_headings(text)
        # 'A note' is 6 chars < MIN_H2_LEN=10
        assert any(lvl == 3 for _, lvl, _ in headings)


class TestAnnotateSegments:
    def test_adds_headings_key(self):
        segs = [{'pdf_page': 1, 'book_page': 1, 'text': '\nCycle 1\n\nText.'}]
        result = annotate_segments(segs)
        assert 'headings' in result[0]

    def test_other_keys_preserved(self):
        segs = [{'pdf_page': 5, 'book_page': 3, 'text': '\nCycle 2\n\nText.'}]
        result = annotate_segments(segs)
        assert result[0]['pdf_page'] == 5
        assert result[0]['book_page'] == 3
