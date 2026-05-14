import pytest
from src.header_stripper import find_bad_lines, strip_headers


def _seg(book_page, text):
    return {'pdf_page': book_page, 'book_page': book_page, 'text': text}


def _make_segments(header='BOOK TITLE', n=20, body='Body text here.\n\nMore body.'):
    """Build n segments long enough that body text is NOT in the first/last 3 ne lines.

    Structure per page:
      line 1: page number (unique)
      line 2: header (repeated — target for detection)
      lines 3-10: unique middle paragraphs
      body text (what tests inspect)
      lines N-4..N: unique footer lines
    """
    segs = []
    for i in range(n):
        middle = '\n'.join(f'Middle content {i}-{j}.' for j in range(8))
        footer = '\n'.join(f'Footer line {i}-{j}.' for j in range(5))
        text = f'{i + 1}\n{header}\n\n{middle}\n\n{body}\n\n{footer}'
        segs.append(_seg(i + 1, text))
    return segs


class TestFindBadLines:
    def test_global_header_detected(self):
        segs = _make_segments('RUNNING TITLE', n=30)
        bad = find_bad_lines(segs)
        assert 'RUNNING TITLE' in bad

    def test_page_numbers_not_in_bad_lines(self):
        segs = _make_segments('TITLE', n=30)
        bad = find_bad_lines(segs)
        for item in bad:
            assert not item.isdigit(), f'Page number {item!r} should not be in bad_lines'

    def test_body_text_not_stripped(self):
        segs = _make_segments('TITLE', n=30, body='Regular paragraph text.\n\nMore.')
        bad = find_bad_lines(segs)
        assert 'Regular paragraph text.' not in bad

    def test_windowed_chapter_title(self):
        # Chapter title appears in header zone for 12 out of 20 pages in a window
        segs = []
        for i in range(40):
            if i < 20:
                hdr = 'Chapter One Title'
            else:
                hdr = 'Chapter Two Title'
            text = f'{hdr}\n{i + 1}\n\nBody text.\n\nMore body.'
            segs.append(_seg(i + 1, text))
        bad = find_bad_lines(segs, window_size=20, window_thresh=0.40)
        assert 'Chapter One Title' in bad
        assert 'Chapter Two Title' in bad

    def test_rare_line_not_flagged(self):
        segs = _make_segments('TITLE', n=50)
        # Insert a unique line in header zone of one page
        segs[10] = _seg(11, 'Unique Special Line\n11\n\nBody.')
        bad = find_bad_lines(segs)
        assert 'Unique Special Line' not in bad

    def test_returns_frozenset(self):
        segs = _make_segments('TITLE', n=20)
        bad = find_bad_lines(segs)
        assert isinstance(bad, frozenset)


class TestStripHeaders:
    def test_header_removed_from_header_zone(self):
        segs = _make_segments('BOOK HEADER', n=30)
        cleaned, bad = strip_headers(segs)
        assert 'BOOK HEADER' in bad
        for seg in cleaned:
            lines = [l.strip() for l in seg['text'].split('\n') if l.strip()]
            assert 'BOOK HEADER' not in lines

    def test_body_text_preserved(self):
        body = 'Important body content.\n\nMore paragraphs here.'
        segs = _make_segments('HEADER', n=30, body=body)
        cleaned, _ = strip_headers(segs)
        for seg in cleaned:
            assert 'Important body content.' in seg['text']

    def test_accepts_precomputed_bad_lines(self):
        segs = _make_segments('TITLE', n=20)
        bad = frozenset({'TITLE'})
        cleaned, returned_bad = strip_headers(segs, bad_lines=bad)
        assert returned_bad is bad
        for seg in cleaned:
            lines = [l.strip() for l in seg['text'].split('\n') if l.strip()]
            assert 'TITLE' not in lines

    def test_segment_keys_preserved(self):
        segs = _make_segments('TITLE', n=10)
        cleaned, _ = strip_headers(segs)
        for orig, clean in zip(segs, cleaned):
            assert clean['pdf_page'] == orig['pdf_page']
            assert clean['book_page'] == orig['book_page']

    def test_body_occurrence_of_header_text_preserved(self):
        # "TITLE" appears in header zone; body text also contains "TITLE" but is not
        # in the header zone — that body line must survive stripping.
        segs = []
        for i in range(30):
            middle = '\n'.join(f'Middle {i}-{j}.' for j in range(8))
            footer = '\n'.join(f'Footer {i}-{j}.' for j in range(5))
            text = f'TITLE\n{i + 1}\n\n{middle}\n\nBody containing TITLE text.\n\n{footer}'
            segs.append(_seg(i + 1, text))
        cleaned, _ = strip_headers(segs)
        for seg in cleaned:
            assert 'Body containing TITLE text.' in seg['text']
