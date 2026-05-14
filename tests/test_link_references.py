"""Unit tests for src/link_references.py"""

import pytest

from src.link_references import _to_int_pages, _find_chapters_for_pages, link_all


class TestToIntPages:
    def test_plain_integers(self):
        assert _to_int_pages(['5', '10', '20']) == [5, 10, 20]

    def test_page_with_suffix(self):
        assert _to_int_pages(['45b', '45f']) == [45, 45]

    def test_range_takes_first(self):
        assert _to_int_pages(['10–11']) == [10]
        assert _to_int_pages(['10-20']) == [10]

    def test_skips_non_numeric(self):
        assert _to_int_pages(['abc', 'xiv']) == []

    def test_empty_list(self):
        assert _to_int_pages([]) == []

    def test_mixed(self):
        result = _to_int_pages(['5', 'abc', '10b', '20–25'])
        assert result == [5, 10, 20]


class TestFindChaptersForPages:
    def _ch(self, title, start, end):
        return {'title': title, 'start_page': start, 'end_page': end}

    def test_page_within_range(self):
        chapters = [self._ch('Ch1', 1, 50)]
        assert _find_chapters_for_pages([25], chapters) == ['Ch1']

    def test_page_at_boundary(self):
        chapters = [self._ch('Ch1', 1, 50)]
        assert _find_chapters_for_pages([1], chapters) == ['Ch1']
        assert _find_chapters_for_pages([50], chapters) == ['Ch1']

    def test_page_outside_range(self):
        chapters = [self._ch('Ch1', 1, 50)]
        assert _find_chapters_for_pages([51], chapters) == []

    def test_multiple_chapters_matched(self):
        chapters = [self._ch('Ch1', 1, 50), self._ch('Ch2', 51, 100)]
        result = _find_chapters_for_pages([25, 75], chapters)
        assert 'Ch1' in result
        assert 'Ch2' in result

    def test_no_duplicate_titles(self):
        chapters = [self._ch('Ch1', 1, 50)]
        result = _find_chapters_for_pages([10, 20, 30], chapters)
        assert result.count('Ch1') == 1

    def test_none_pages_skipped(self):
        chapters = [{'title': 'Ch1', 'start_page': None, 'end_page': None}]
        assert _find_chapters_for_pages([10], chapters) == []

    def test_fallback_title(self):
        chapters = [{'title': '', 'start_page': 1, 'end_page': 10}]
        result = _find_chapters_for_pages([5], chapters)
        assert result == ['p. 1–10']


class TestLinkAll:
    def _chapters(self):
        return [
            {'title': 'Memory', 'start_page': 1, 'end_page': 50,
             'ref_start_line': 40, 'ref_end_line': 50},
            {'title': 'Emotion', 'start_page': 51, 'end_page': 100,
             'ref_start_line': 90, 'ref_end_line': 100},
        ]

    def _refs(self):
        return {
            'Memory': [{'authors': 'Smith', 'year': '2001', 'title': 'Memory',
                         'venue': 'J', 'raw': 'Smith 2001'}],
            'Emotion': [{'authors': 'Jones', 'year': '2002', 'title': 'Emotion',
                          'venue': 'J', 'raw': 'Jones 2002'}],
        }

    def test_basic_linking(self):
        lookup = {'synapse': {'pages': {'testbook': ['25']}, 'books': ['testbook']}}
        chapters_by_book = {'testbook': self._chapters()}
        refs_by_book = {'testbook': self._refs()}

        result = link_all(lookup, chapters_by_book, refs_by_book)
        assert result['synapse']['chapters']['testbook'] == ['Memory']

    def test_references_attached(self):
        lookup = {'synapse': {'pages': {'testbook': ['25']}, 'books': ['testbook']}}
        chapters_by_book = {'testbook': self._chapters()}
        refs_by_book = {'testbook': self._refs()}

        result = link_all(lookup, chapters_by_book, refs_by_book)
        refs = result['synapse']['references']['testbook']
        assert len(refs) == 1
        assert refs[0]['authors'] == 'Smith'

    def test_term_in_multiple_books(self):
        lookup = {
            'memory': {
                'pages': {'book1': ['10'], 'book2': ['60']},
                'books': ['book1', 'book2'],
            }
        }
        chapters_by_book = {
            'book1': [{'title': 'Ch1', 'start_page': 1, 'end_page': 50,
                        'ref_start_line': 40, 'ref_end_line': 50}],
            'book2': [{'title': 'Ch2', 'start_page': 51, 'end_page': 100,
                        'ref_start_line': 90, 'ref_end_line': 100}],
        }
        refs_by_book = {
            'book1': {'Ch1': [{'authors': 'A', 'year': '2000', 'title': 'T',
                                'venue': 'J', 'raw': 'A 2000'}]},
            'book2': {'Ch2': [{'authors': 'B', 'year': '2001', 'title': 'T',
                                'venue': 'J', 'raw': 'B 2001'}]},
        }

        result = link_all(lookup, chapters_by_book, refs_by_book)
        assert 'book1' in result['memory']['chapters']
        assert 'book2' in result['memory']['chapters']

    def test_book_not_in_chapters_skipped(self):
        lookup = {'term': {'pages': {'unknown': ['5']}, 'books': ['unknown']}}
        result = link_all(lookup, {}, {})
        assert result['term']['chapters'] == {}

    def test_no_pages_match_gives_no_chapter(self):
        lookup = {'term': {'pages': {'testbook': ['200']}, 'books': ['testbook']}}
        chapters_by_book = {'testbook': self._chapters()}
        refs_by_book = {'testbook': self._refs()}

        result = link_all(lookup, chapters_by_book, refs_by_book)
        assert 'testbook' not in result['term']['chapters']

    def test_duplicate_references_deduplicated(self):
        lookup = {'term': {'pages': {'b': ['5', '10']}, 'books': ['b']}}
        ch = [{'title': 'Ch1', 'start_page': 1, 'end_page': 20,
                'ref_start_line': 15, 'ref_end_line': 20}]
        ref_entry = {'authors': 'X', 'year': '2000', 'title': 'T', 'venue': 'J', 'raw': 'X 2000'}
        refs = {'Ch1': [ref_entry]}

        result = link_all(lookup, {'b': ch}, {'b': refs})
        assert len(result['term']['references']['b']) == 1

    def test_existing_chapters_field_preserved(self):
        lookup = {'term': {'pages': {}, 'books': [], 'chapters': {'existing': ['X']}}}
        result = link_all(lookup, {}, {})
        assert result['term']['chapters']['existing'] == ['X']
