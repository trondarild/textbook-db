"""Unit tests for src/chapter_detector.py"""

import json
import textwrap
from pathlib import Path

import pytest

from src.chapter_detector import detect, save, _extract_title, _find_ref_end


class TestExtractTitle:
    def test_returns_first_heading(self):
        lines = ['', '## My Chapter', 'body text']
        assert _extract_title(lines) == 'My Chapter'

    def test_skips_references_heading(self):
        lines = ['## References', '## Real Title']
        assert _extract_title(lines) == 'Real Title'

    def test_skips_summary_heading(self):
        lines = ['## Summary', '## Actual Content']
        assert _extract_title(lines) == 'Actual Content'

    def test_skips_c_h_a_p_t_e_r(self):
        lines = ['## C H A P T E R', '## The Nerve Cell']
        assert _extract_title(lines) == 'The Nerve Cell'

    def test_skips_short_headings(self):
        lines = ['## Hi', '## Long Enough Title']
        assert _extract_title(lines) == 'Long Enough Title'

    def test_empty_lines(self):
        assert _extract_title([]) == ''

    def test_no_heading(self):
        assert _extract_title(['body text', 'more text']) == ''


class TestFindRefEnd:
    def test_stops_at_h1(self):
        lines = ['ref entry', '# New Chapter', 'more']
        assert _find_ref_end(lines, 0, len(lines)) == 1

    def test_stops_at_non_ref_h2(self):
        lines = ['ref entry', '## Introduction']
        assert _find_ref_end(lines, 0, len(lines)) == 1

    def test_ref_like_h2_is_not_a_stop(self):
        lines = ['## Smith, J. (2001). A title. Journal.', 'next line']
        result = _find_ref_end(lines, 0, len(lines))
        assert result == len(lines)

    def test_stops_after_three_long_body_lines(self):
        body_line = 'x' * 100
        lines = ['Smith 2001 title', body_line, body_line, body_line, 'trailing']
        result = _find_ref_end(lines, 0, len(lines))
        assert result == 1

    def test_year_line_resets_body_counter(self):
        body_line = 'x' * 100
        lines = [body_line, body_line, 'entry (2001). Title.', body_line, body_line, body_line]
        result = _find_ref_end(lines, 0, len(lines))
        assert result == 3

    def test_returns_limit_when_all_ref_lines(self):
        lines = ['Smith AB. 2001. Title. Journal 1:1.', 'Jones CD. 1999. Other. J 2:3.']
        assert _find_ref_end(lines, 0, len(lines)) == len(lines)

    def test_blank_lines_ignored(self):
        lines = ['Smith 2001', '', 'Jones 2002', '']
        assert _find_ref_end(lines, 0, len(lines)) == len(lines)


class TestDetect:
    def _make_md(self, chapters):
        """Build a minimal md string from list of (title, pages, refs) tuples."""
        parts = []
        for title, pages, refs in chapters:
            for p in pages:
                parts.append(f'<!-- p. {p} -->')
            parts.append(f'## {title}')
            parts.append('body text body text body text')
            parts.append('')
            parts.append('## References')
            parts.extend(refs)
            parts.append('')
        return '\n'.join(parts)

    def test_empty_md(self):
        assert detect('') == []

    def test_no_ref_headings(self):
        assert detect('## Chapter One\nbody text\n') == []

    def test_single_chapter(self):
        md = '<!-- p. 5 -->\n## My Chapter\nbody\n\n## References\nSmith 2001\n'
        result = detect(md)
        assert len(result) == 1
        ch = result[0]
        assert ch['title'] == 'My Chapter'
        assert ch['start_page'] == 5
        assert ch['end_page'] == 5
        assert ch['ref_start_line'] is not None

    def test_two_chapters(self):
        md = textwrap.dedent("""\
            <!-- p. 1 -->
            ## Chapter One
            body

            ## References
            Smith 2001

            <!-- p. 10 -->
            ## Chapter Two
            body

            ## References
            Jones 2002
        """)
        result = detect(md)
        assert len(result) == 2
        assert result[0]['title'] == 'Chapter One'
        assert result[1]['title'] == 'Chapter Two'
        assert result[0]['start_page'] == 1
        assert result[1]['start_page'] == 10

    def test_custom_ref_heading_pattern(self):
        import re
        md = '<!-- p. 3 -->\n## Topic\nbody\n\n## Suggested Reading\nentry\n'
        result = detect(md, ref_heading_re=re.compile(r'^## Suggested Reading'))
        assert len(result) == 1
        assert result[0]['title'] == 'Topic'

    def test_no_pages_gives_none(self):
        md = '## Chapter\nbody\n\n## References\nSmith 2001\n'
        result = detect(md)
        assert result[0]['start_page'] is None
        assert result[0]['end_page'] is None

    def test_ref_end_line_before_next_chapter(self):
        md = textwrap.dedent("""\
            ## Ch1
            ## References
            Smith AB. 2001. Title. J.

            ## Ch2
            ## References
            Jones CD. 2002. Other. J.
        """)
        result = detect(md)
        assert result[0]['ref_end_line'] <= result[1]['ref_start_line']


class TestSave:
    def test_writes_json(self, tmp_path):
        chapters = [{'title': 'Ch1', 'start_page': 1, 'end_page': 10,
                     'ref_start_line': 5, 'ref_end_line': 8}]
        path = save(chapters, 'mybook', tmp_path)
        assert path == tmp_path / 'mybook.json'
        loaded = json.loads(path.read_text())
        assert loaded == chapters

    def test_creates_dir(self, tmp_path):
        d = tmp_path / 'chapters' / 'sub'
        save([], 'book', d)
        assert d.exists()
