"""Unit tests for src/page_mapper.py"""

import json
import textwrap
from pathlib import Path

import pytest

from src.page_mapper import parse_markers, build


class TestParseMarkers:
    def test_empty_text(self):
        assert parse_markers('') == {}

    def test_single_page_marker(self):
        assert parse_markers('<!-- p. 42 -->') == {'42': 0}

    def test_single_chapter_marker(self):
        assert parse_markers('<!-- ch. 3 -->') == {'3': 0}

    def test_page_and_chapter_markers(self):
        md = '<!-- ch. 1 -->\nsome text\n<!-- p. 10 -->'
        assert parse_markers(md) == {'1': 0, '10': 2}

    def test_first_occurrence_wins(self):
        md = '<!-- p. 5 -->\ntext\n<!-- p. 5 -->'
        assert parse_markers(md) == {'5': 0}

    def test_line_index_is_zero_based(self):
        md = 'line0\nline1\n<!-- p. 7 -->\nline3'
        assert parse_markers(md) == {'7': 2}

    def test_non_marker_lines_ignored(self):
        md = 'normal text\n<-- p. 5 -->\n<!-- q. 5 -->'
        assert parse_markers(md) == {}

    def test_multiple_consecutive_markers(self):
        md = '<!-- p. 1 -->\n<!-- p. 2 -->\n<!-- p. 3 -->'
        assert parse_markers(md) == {'1': 0, '2': 1, '3': 2}

    def test_alpha_chapter_label(self):
        md = '<!-- ch. appendix -->'
        assert parse_markers(md) == {'appendix': 0}


class TestBuild:
    def test_missing_md_path_returns_empty(self, tmp_path):
        meta = {}
        result = build('book', meta, tmp_path, tmp_path / 'pages')
        assert result == {}

    def test_nonexistent_file_returns_empty(self, tmp_path):
        meta = {'md_path': 'missing.md'}
        result = build('book', meta, tmp_path, tmp_path / 'pages')
        assert result == {}

    def test_writes_json_file(self, tmp_path):
        md_path = tmp_path / 'md' / 'testbook.md'
        md_path.parent.mkdir()
        md_path.write_text('<!-- p. 10 -->\ntext\n<!-- p. 11 -->', encoding='utf-8')
        pages_dir = tmp_path / 'pages'
        meta = {'md_path': 'md/testbook.md'}

        result = build('testbook', meta, tmp_path, pages_dir)
        assert result == {'10': 0, '11': 2}

        saved = json.loads((pages_dir / 'testbook.json').read_text())
        assert saved == {'10': 0, '11': 2}

    def test_creates_pages_dir_if_missing(self, tmp_path):
        md_path = tmp_path / 'book.md'
        md_path.write_text('<!-- p. 1 -->', encoding='utf-8')
        pages_dir = tmp_path / 'pages' / 'subdir'
        meta = {'md_path': str(md_path)}

        build('book', meta, tmp_path, pages_dir)
        assert (pages_dir / 'book.json').exists()
