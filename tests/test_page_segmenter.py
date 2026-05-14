import pytest
from src.page_segmenter import segment, build_page_map, _candidate_lines, _detect_number


class TestCandidateLines:
    def test_returns_first_and_last_lines(self):
        text = '\n'.join(f'line{i}' for i in range(10))
        lines = _candidate_lines(text)
        assert 'line0' in lines
        assert 'line9' in lines

    def test_ignores_empty_lines(self):
        text = '\n\nfoo\n\nbar\n\n'
        lines = _candidate_lines(text)
        assert '' not in lines

    def test_small_page_returns_all_lines(self):
        text = 'a\nb\nc'
        lines = _candidate_lines(text)
        assert lines == ['a', 'b', 'c']


class TestDetectNumber:
    def test_arabic_number_found(self):
        num, is_roman = _detect_number(['Chapter Title', '123', 'Some text'])
        assert num == 123
        assert not is_roman

    def test_roman_numeral_detected(self):
        num, is_roman = _detect_number(['iv'])
        assert num is None
        assert is_roman

    def test_roman_uppercase(self):
        num, is_roman = _detect_number(['XIV'])
        assert is_roman

    def test_no_number_returns_none(self):
        num, is_roman = _detect_number(['Just text here', 'More text'])
        assert num is None
        assert not is_roman

    def test_arabic_wins_over_later_roman(self):
        num, is_roman = _detect_number(['42', 'iv'])
        assert num == 42
        assert not is_roman


class TestSegment:
    def test_splits_on_form_feed(self):
        text = 'Page one\n42\n\x0cPage two\n43\n'
        segs = segment(text)
        assert len(segs) == 2

    def test_pdf_page_counter(self):
        text = 'first\n10\n\x0csecond\n11\n'
        segs = segment(text)
        assert segs[0]['pdf_page'] == 0
        assert segs[1]['pdf_page'] == 1

    def test_book_page_extracted(self):
        segs = segment('Heading\n\n42\n\nContent.\n')
        assert segs[0]['book_page'] == 42

    def test_roman_page_excluded(self):
        text = 'Preface\niv\n\x0cChapter 1\n1\n'
        segs = segment(text)
        assert len(segs) == 1
        assert segs[0]['book_page'] == 1

    def test_empty_pages_excluded(self):
        text = '\x0c\x0cContent\n5\n\x0c'
        segs = segment(text)
        assert all(s['text'].strip() for s in segs)

    def test_no_number_gives_none_book_page(self):
        segs = segment('Just plain text with no number\n')
        assert segs[0]['book_page'] is None

    def test_text_preserved(self):
        segs = segment('Hello world\n7\n')
        assert 'Hello world' in segs[0]['text']


class TestBuildPageMap:
    def test_maps_book_to_pdf_page(self):
        segs = [
            {'pdf_page': 0, 'book_page': 10, 'text': 'a'},
            {'pdf_page': 1, 'book_page': 11, 'text': 'b'},
        ]
        pm = build_page_map(segs)
        assert pm == {10: 0, 11: 1}

    def test_excludes_none_book_pages(self):
        segs = [
            {'pdf_page': 0, 'book_page': None, 'text': 'a'},
            {'pdf_page': 1, 'book_page': 5,    'text': 'b'},
        ]
        pm = build_page_map(segs)
        assert None not in pm
        assert pm == {5: 1}

    def test_empty_input(self):
        assert build_page_map([]) == {}
