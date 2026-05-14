"""Split a pdftotext output into per-PDF-page segments with book page detection.

pdftotext preserves \x0c (form feed) between PDF pages and prints the book's
page numbers in headers or footers.  This module locates those numbers so
downstream modules can map book_page → pdf_page.
"""

import re

# Matches a line that is just an Arabic number (1–4 digits)
_ARABIC_ONLY = re.compile(r'^\d{1,4}$')

# Standard roman numeral pattern (front-matter pages)
_ROMAN = re.compile(
    r'^m{0,4}(cm|cd|d?c{0,3})(xc|xl|l?x{0,3})(ix|iv|v?i{0,3})$',
    re.IGNORECASE,
)


def _candidate_lines(page_text: str) -> list[str]:
    """First 3 + last 3 non-empty stripped lines of a page."""
    lines = [ln.strip() for ln in page_text.split('\n') if ln.strip()]
    return (lines[:3] + lines[-3:]) if len(lines) >= 6 else lines


def _detect_number(lines: list[str]) -> tuple[int | None, bool]:
    """Scan candidate lines for a printed page number.

    Returns (arabic_number, is_roman).
    is_roman=True means the page carries only a roman-numeral marker (front matter).
    """
    for line in lines:
        if _ARABIC_ONLY.match(line):
            return int(line), False
        if _ROMAN.match(line) and line:
            return None, True
    return None, False


def segment(text: str) -> list[dict]:
    """Split on form-feed chars; detect book page number per PDF page.

    Returns a list of dicts:
        pdf_page  — 0-based index of the PDF page (form-feed counter)
        book_page — printed page number (int), or None if not detectable
        text      — raw text content of that PDF page

    Pages with a roman-numeral marker (front matter) are excluded.
    Empty pages (whitespace only) are excluded.
    """
    segments = []
    for pdf_page, page_text in enumerate(text.split('\x0c')):
        if not page_text.strip():
            continue
        lines = _candidate_lines(page_text)
        arabic, is_roman = _detect_number(lines)
        if is_roman:
            continue
        segments.append({
            'pdf_page': pdf_page,
            'book_page': arabic,
            'text': page_text,
        })
    return segments


def build_page_map(segments: list[dict]) -> dict[int, int]:
    """Build {book_page: pdf_page} from segment output.

    Only includes segments where book_page was successfully detected.
    """
    return {
        s['book_page']: s['pdf_page']
        for s in segments
        if s['book_page'] is not None
    }
