"""
Franks 2013 — Handbook of Neurosociology (Springer).

Springer handbook running-header layout:
  even PDF pages: <book_page>\n<Author et al.>\n<content>
  odd  PDF pages: <chapter_num>\n<chapter_title>\n<book_page>\n<content>

post_segment      : detect both patterns to assign the correct book_page; drop front matter.
post_strip        : pattern-based strip of bare page numbers, author-abbrev lines, and
                    chapter-number lines from the header zone; second frequency pass to
                    catch exposed chapter titles.
post_annotate     : drop headings that are author-abbreviation lines (e.g. "G. Lakoff ()").
post_chapter_detect: override chapter titles from toc/franks2013.json by matching
                    ### Chapter N headings found in each chapter body.
"""

import json
import re
from pathlib import Path
from src.header_stripper import _header_zone_lines, strip_headers

# Matches a bare integer on a line (page or chapter number)
_PAGE_ONLY_RE = re.compile(r'^\d{1,4}$')
# Matches an author abbreviation: starts with Capital initial + dot (e.g. "G. Lakoff")
_AUTHOR_ABBREV_RE = re.compile(r'^[A-Z]\.[A-Z]?\.')
# Matches a chapter opener first line: "Chapter N"
_CHAPTER_OPENER_RE = re.compile(r'^Chapter\s+\d+$', re.I)
# Chapter numbers in this book are 1–25
_MAX_CHAPTER = 25


def _extract_page(text: str) -> int | None:
    """Return printed book page for a PDF page using Springer header patterns."""
    ne = [l.strip() for l in text.split('\n') if l.strip()]
    if not ne:
        return None

    first = ne[0]
    if not _PAGE_ONLY_RE.match(first):
        return None

    # Even page: <page>\n<Author abbrev.>\n...
    if len(ne) >= 2 and _AUTHOR_ABBREV_RE.match(ne[1]):
        return int(first)

    # Odd page: <chapter_num>\n<chapter_title>\n<page>\n...
    if len(ne) >= 3 and _PAGE_ONLY_RE.match(ne[2]):
        chapter_num = int(first)
        if 1 <= chapter_num <= _MAX_CHAPTER:
            return int(ne[2])

    return None


def _is_header_line(line: str, ne_lines: list[str]) -> bool:
    """True if line is a running-header artifact (page num, author abbrev, or chapter num)."""
    s = line.strip()
    if not s:
        return False
    # Bare integer (page number or chapter number line)
    if _PAGE_ONLY_RE.match(s):
        return True
    # Author abbreviation line
    if _AUTHOR_ABBREV_RE.match(s):
        return True
    return False


def post_segment(segments, meta):
    patched = []
    for s in segments:
        # Always re-detect: the default segmenter grabs chapter numbers (1-25) as
        # page numbers on odd pages; our pattern-aware extractor overrides that.
        page = _extract_page(s['text'])
        patched.append({**s, 'book_page': page if page is not None else s['book_page']})

    # Drop front matter: keep from the first "Chapter N" opener page.
    # Without this, TOC/Contributors pages get spurious page numbers from the
    # table-of-contents entry numbers (e.g. the "1" in "Chapter 1 ..... 15").
    for i, s in enumerate(patched):
        first = next((l.strip() for l in s['text'].split('\n') if l.strip()), '')
        if _CHAPTER_OPENER_RE.match(first):
            return patched[i:]
    return patched


def post_strip(segments, meta):
    # Pass 1: remove header-zone lines matching the running-header patterns
    pass1 = []
    for s in segments:
        lines, ne_indices, zone_indices, _ = _header_zone_lines(s['text'])
        ne_in_zone = [lines[i].strip() for i in sorted(zone_indices)]
        cleaned = [
            l for i, l in enumerate(lines)
            if not (i in zone_indices and _is_header_line(l, ne_in_zone))
        ]
        pass1.append({**s, 'text': '\n'.join(cleaned)})

    # Pass 2: frequency analysis to catch chapter titles used as running headers
    pass2, _ = strip_headers(pass1, window_thresh=0.20)
    return pass2


def post_annotate(segments, meta):
    """Remove headings that are author-abbreviation lines leaked into the body."""
    result = []
    for s in segments:
        lines = s['text'].split('\n')
        cleaned = []
        for line in lines:
            # Drop ## headings that look like "## G. Lakoff ()" or "## D.D. Franks"
            if line.startswith('## ') and _AUTHOR_ABBREV_RE.match(line[3:].strip()):
                continue
            cleaned.append(line)
        result.append({**s, 'text': '\n'.join(cleaned)})
    return result


def post_chapter_detect(chapters, meta):
    """Override chapter titles from toc/franks2013.json.

    Each detected chapter body contains a '### Chapter N' heading; use N to
    look up the authoritative title from the TOC and replace any heuristic title
    (which may be an author byline rather than the real chapter title).
    """
    toc_path = Path(__file__).parent.parent / 'toc' / 'franks2013.json'
    if not toc_path.exists():
        return chapters

    toc = json.loads(toc_path.read_text(encoding='utf-8'))
    # Build {chapter_number: clean_title} — strip the leading "N " prefix
    toc_titles = {}
    for entry in toc:
        m = re.match(r'^(\d+)\s+(.+)', entry['title'])
        if m:
            toc_titles[int(m.group(1))] = m.group(2).strip()

    md_rel = meta.get('md_path', 'md/franks2013.md')
    md_path = Path(__file__).parent.parent / md_rel
    if not md_path.exists():
        return chapters

    lines = md_path.read_text(encoding='utf-8').splitlines()
    _chap_heading_re = re.compile(r'^### Chapter\s+(\d+)', re.I)

    result = []
    for ch in chapters:
        rsl = ch.get('ref_start_line', 0)
        # Scan backward from ref_start_line to find the ### Chapter N heading.
        # Chapters can span 700+ lines; use a wide window.
        ch_num = None
        scan_start = max(0, rsl - 2000)
        for j in range(rsl - 1, scan_start, -1):
            m = _chap_heading_re.match(lines[j])
            if m:
                ch_num = int(m.group(1))
                break
        if ch_num is not None and ch_num in toc_titles:
            result.append({**ch, 'title': toc_titles[ch_num]})
        else:
            result.append(ch)
    return result
