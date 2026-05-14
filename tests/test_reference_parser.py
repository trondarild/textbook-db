"""Unit tests for src/reference_parser.py"""

import pytest

from src.reference_parser import parse_section, extract_all, _join_entries, _parse_entry


class TestJoinEntries:
    def test_single_entry(self):
        lines = ['Smith, J. (2001). Title. Journal.']
        result = _join_entries(lines)
        assert result == ['Smith, J. (2001). Title. Journal.']

    def test_multiline_entry_joined(self):
        lines = ['Smith, J. (2001). A very long title that', 'continues on the next line. Journal.']
        result = _join_entries(lines)
        assert len(result) == 1
        assert 'Smith' in result[0]
        assert 'continues' in result[0]

    def test_two_entries_split(self):
        lines = [
            'Smith, J. (2001). Title A. Journal.',
            'Jones, K. (2002). Title B. Journal.',
        ]
        result = _join_entries(lines)
        assert len(result) == 2

    def test_skips_page_markers(self):
        lines = ['<!-- p. 45 -->', 'Smith, J. (2001). Title. Journal.']
        result = _join_entries(lines)
        assert len(result) == 1
        assert 'Smith' in result[0]

    def test_skips_heading_lines(self):
        lines = ['## References', 'Smith, J. (2001). Title. Journal.']
        result = _join_entries(lines)
        assert len(result) == 1

    def test_three_consecutive_blanks_flush_entry(self):
        # 3 blanks flush the current multi-line entry as a unit; new entries
        # starting after the blanks are still parsed as separate entries
        lines = [
            'Smith, J. (2001). Title that',
            'continues here. Journal.',
            '',
            '',
            '',
            'Jones, K. (2002). Title. Journal.',
        ]
        result = _join_entries(lines)
        assert len(result) == 2
        assert 'Smith' in result[0]
        assert 'continues here' in result[0]   # continuation was kept
        assert 'Jones' in result[1]

    def test_empty_input(self):
        assert _join_entries([]) == []


class TestParseEntry:
    def test_apa_format(self):
        raw = 'Smith, J. (2001). A title. Journal Name, 10, 1–20.'
        e = _parse_entry(raw)
        assert e['year'] == '2001'
        assert 'Smith' in e['authors']
        assert e['raw'] == raw

    def test_vancouver_format(self):
        raw = 'Smith AB. 2001. A title. Journal 10:1–20.'
        e = _parse_entry(raw)
        assert e['year'] == '2001'
        assert 'Smith' in e['authors']

    def test_no_year(self):
        raw = 'Smith, J. Title without year. Journal.'
        e = _parse_entry(raw)
        assert e['year'] == ''
        assert e['raw'] == raw

    def test_year_in_result(self):
        raw = 'Jones CD. 1999. Memory consolidation. Neuron 5:100.'
        e = _parse_entry(raw)
        assert e['year'] == '1999'

    def test_title_and_venue_split(self):
        raw = 'Smith AB. 2001. My title. Nature 1:1.'
        e = _parse_entry(raw)
        assert 'My title' in e['title']
        assert e['venue'] != ''

    def test_all_keys_present(self):
        e = _parse_entry('Smith J. 2001. Title. J.')
        assert set(e.keys()) >= {'authors', 'year', 'title', 'venue', 'raw'}


class TestParseSection:
    def test_empty(self):
        assert parse_section([]) == []

    def test_single_apa_entry(self):
        lines = ['Smith, J. (2001). Title. Journal, 10, 1–20.']
        result = parse_section(lines)
        assert len(result) == 1
        assert result[0]['year'] == '2001'

    def test_multiple_entries(self):
        lines = [
            'Adolphs, R. (2003). Cognitive neuroscience. Annual Review, 26, 27–57.',
            'Baron-Cohen, S. (2005). Autism. Current Biology, 15, 786–790.',
        ]
        result = parse_section(lines)
        assert len(result) == 2

    def test_multiline_entries(self):
        lines = [
            'Smith, J., & Jones, K. (2001). A long title that wraps',
            'across multiple lines. Journal of Cognition, 10, 1–20.',
            'Doe, J. (2002). Short entry. Nature.',
        ]
        result = parse_section(lines)
        assert len(result) == 2

    def test_skips_markers_and_headings(self):
        lines = [
            '## References',
            '<!-- p. 100 -->',
            'Smith, J. (2001). Title. Journal.',
        ]
        result = parse_section(lines)
        assert len(result) == 1

    def test_buzaki_format(self):
        lines = ['Buzsaki G, Draguhn A (2004) Neuronal oscillations. Science 304:1926–1929.']
        result = parse_section(lines)
        assert len(result) == 1
        assert result[0]['year'] == '2004'

    def test_yudofsky_format(self):
        lines = ['Andreasen NC: Symptoms, signs, and diagnosis of schizophrenia. Lancet 346:477, 1995']
        result = parse_section(lines)
        assert len(result) == 1
        assert result[0]['year'] == '1995'


class TestExtractAll:
    def test_skips_chapters_without_ref_start_line(self):
        md_text = '## Ch1\nbody\n\n## References\nSmith 2001'
        chapters = [{'title': 'Ch1', 'ref_start_line': None, 'ref_end_line': 5}]
        result = extract_all(md_text, chapters)
        assert result == {}

    def test_extracts_from_chapter_with_ref_start(self):
        lines = [
            '## Ch1',         # 0
            'body',           # 1
            '',               # 2
            '## References',  # 3
            'Smith, J. (2001). Title. Journal.',  # 4
        ]
        md_text = '\n'.join(lines)
        chapters = [{'title': 'Ch1', 'ref_start_line': 3, 'ref_end_line': 5}]
        result = extract_all(md_text, chapters)
        assert 'Ch1' in result
        assert len(result['Ch1']) == 1

    def test_uses_page_range_as_fallback_title(self):
        lines = ['## References', 'Smith 2001']
        chapters = [{'title': '', 'start_page': 5, 'end_page': 10,
                     'ref_start_line': 0, 'ref_end_line': 2}]
        result = extract_all('\n'.join(lines), chapters)
        assert 'p. 5–10' in result
