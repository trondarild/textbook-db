import pathlib
import pytest
from src.md_writer import write_md, _front_matter, _render_segment


class TestFrontMatter:
    def test_contains_title(self):
        meta = {'title': 'Test Book', 'author': 'Author', 'year': 2024, 'pdf': '/path/to/book.pdf'}
        fm = _front_matter(meta)
        assert 'title: Test Book' in fm
        assert '---' in fm

    def test_epub_path_used_when_no_pdf(self):
        meta = {'title': 'Epub Book', 'author': 'A', 'year': 2020, 'epub_path': '/e.epub'}
        fm = _front_matter(meta)
        assert '/e.epub' in fm

    def test_missing_fields_dont_crash(self):
        fm = _front_matter({})
        assert '---' in fm


class TestRenderSegment:
    def test_page_marker_present(self):
        seg = {'book_page': 42, 'text': 'Some text.', 'headings': []}
        out = _render_segment(seg)
        assert '<!-- p. 42 -->' in out

    def test_heading_rendered_with_hashes(self):
        seg = {
            'book_page': 5,
            'text': '\nCycle 1\n\nBody text.',
            'headings': [(1, 1, 'Cycle 1')],
        }
        out = _render_segment(seg)
        assert '# Cycle 1' in out

    def test_body_text_preserved(self):
        seg = {'book_page': 3, 'text': 'Body paragraph here.', 'headings': []}
        out = _render_segment(seg)
        assert 'Body paragraph here.' in out


class TestWriteMd:
    def test_creates_file(self, tmp_path):
        segs = [
            {
                'book_page': 1,
                'text': '\nCycle 1\n\nIntroductory text.',
                'headings': [(1, 1, 'Cycle 1')],
            },
            {
                'book_page': 2,
                'text': 'More text on page two.',
                'headings': [],
            },
        ]
        meta = {'title': 'Brain Rhythms', 'author': 'Buzaki', 'year': 2011, 'pdf': '/x.pdf'}
        out = write_md(segs, meta, tmp_path / 'out.md')
        assert pathlib.Path(out).exists()

    def test_front_matter_in_output(self, tmp_path):
        segs = [{'book_page': 1, 'text': 'Text.', 'headings': []}]
        meta = {'title': 'My Book', 'author': 'Auth', 'year': 2000, 'pdf': '/b.pdf'}
        out = write_md(segs, meta, tmp_path / 'b.md')
        content = pathlib.Path(out).read_text()
        assert 'title: My Book' in content

    def test_skips_none_book_page(self, tmp_path):
        segs = [
            {'book_page': None, 'text': 'Front matter page.', 'headings': []},
            {'book_page': 1, 'text': 'Real page.', 'headings': []},
        ]
        meta = {'title': 'T', 'author': 'A', 'year': 2000}
        out = write_md(segs, meta, tmp_path / 'c.md')
        content = pathlib.Path(out).read_text()
        assert 'Front matter page.' not in content
        assert 'Real page.' in content

    def test_creates_parent_dirs(self, tmp_path):
        segs = [{'book_page': 1, 'text': 'Text.', 'headings': []}]
        meta = {'title': 'T', 'author': 'A', 'year': 2000}
        out_path = tmp_path / 'subdir' / 'nested' / 'out.md'
        write_md(segs, meta, out_path)
        assert out_path.exists()
