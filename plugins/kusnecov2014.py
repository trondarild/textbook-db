"""
Kusnecov 2014 — The Wiley-Blackwell Handbook of Psychoneuroimmunology.

Wiley-Blackwell handbook layout (same even/odd running-header structure as Springer):
  Chapter openers: chapter_num (1–26), chapter title (1–2 lines), author names,
                   affiliations, © copyright line.
  Even content pages: book_page, then author full names (all authors, comma-separated,
                      ending with "and Lastname"), then body.
  Odd content pages: chapter title, then book_page (may be displaced if figure on page).

post_segment: re-detect book_page using layout-aware logic; drop chapter openers and
              front matter (everything before chapter 1 content).
post_strip  : pattern-based strip of page numbers and author-name lines from header zone;
              frequency pass to catch chapter title running headers.
post_annotate: remove author-name lines promoted to headings.
post_chapter_detect: 26 chapters = 26 TOC entries → positional 1:1 override.
"""

import json
import re
from pathlib import Path
from src.header_stripper import _header_zone_lines, strip_headers

_PAGE_ONLY_RE = re.compile(r'^\d{1,4}$')
_MAX_CHAPTER = 26
_MAX_PAGE = 560  # book has ~543 content pages; cap to avoid year-numbers (e.g. 2010)


def _is_chapter_opener(text: str) -> bool:
    return '©' in text and 'Wiley' in text


def _is_author_line(line: str) -> bool:
    """Even-page running header: full author names, e.g. 'A. Smith, B. Jones, and C. Lee'."""
    return ' and ' in line and ',' in line and bool(line) and line[0].isupper()


def _extract_page(text: str) -> int | None:
    """Return printed book page using Wiley-Blackwell handbook header patterns."""
    if _is_chapter_opener(text):
        return None

    ne = [l.strip() for l in text.split('\n') if l.strip()]
    if not ne:
        return None

    first = ne[0]

    # Even page: bare page number, followed by author full-names line
    if _PAGE_ONLY_RE.match(first):
        pg = int(first)
        if pg > _MAX_PAGE:
            return None  # year or other spurious number
        if pg > _MAX_CHAPTER:
            return pg
        # For pages 1–26 check second line to rule out chapter-number misread
        if len(ne) >= 2 and _is_author_line(ne[1]):
            return pg
        return None  # chapter number on opener page or ambiguous

    # Odd page: chapter title first; page number in next 1–5 non-empty lines
    for token in ne[1:6]:
        if _PAGE_ONLY_RE.match(token):
            pg = int(token)
            if pg <= _MAX_PAGE:
                return pg

    return None


def post_segment(segments, meta):
    patched = []
    for s in segments:
        if _is_chapter_opener(s['text']):
            patched.append({**s, 'book_page': None, '_opener': True})
            continue
        page = _extract_page(s['text'])
        # Always use our detection; never fall back to default (default misreads years/chapter-nums)
        patched.append({**s, 'book_page': page})

    # Drop front matter and chapter openers; keep from first non-opener content page.
    result = []
    in_front = True
    for s in patched:
        if in_front:
            if s.get('_opener'):
                in_front = False  # found first opener; next non-opener = chapter 1 content
            continue
        if s.get('_opener'):
            continue  # skip all subsequent openers too
        result.append({k: v for k, v in s.items() if k != '_opener'})

    return result if result else patched


def _is_header_artifact(line: str) -> bool:
    s = line.strip()
    if not s:
        return False
    if _PAGE_ONLY_RE.match(s):
        return True
    if _is_author_line(s):
        return True
    return False


def post_strip(segments, meta):
    # Pass 1: pattern-based strip of page numbers and author-name lines from header zone
    pass1 = []
    for s in segments:
        lines, ne_indices, zone_indices, _ = _header_zone_lines(s['text'])
        cleaned = [
            l for i, l in enumerate(lines)
            if not (i in zone_indices and _is_header_artifact(l))
        ]
        pass1.append({**s, 'text': '\n'.join(cleaned)})

    # Pass 2: frequency analysis to catch chapter-title running headers
    pass2, _ = strip_headers(pass1, window_thresh=0.20)
    return pass2


def post_annotate(segments, meta):
    """Remove author-name lines promoted to ## headings."""
    result = []
    for s in segments:
        filtered = [
            h for h in s.get('headings', [])
            if not _is_author_line(h[2])
        ]
        result.append({**s, 'headings': filtered})
    return result


def post_chapter_detect(chapters, meta):
    """Override chapter titles from toc/kusnecov2014.json.

    26 detected chapters match 26 TOC entries exactly — use positional mapping.
    Strip the leading 'N ' chapter-number prefix from each TOC title.
    """
    toc_path = Path(__file__).parent.parent / 'toc' / 'kusnecov2014.json'
    if not toc_path.exists():
        return chapters

    toc = json.loads(toc_path.read_text(encoding='utf-8'))

    def strip_num(title: str) -> str:
        m = re.match(r'^\d+\s+(.+)', title)
        return m.group(1) if m else title

    toc_titles = [strip_num(e['title']) for e in toc]

    if len(chapters) == len(toc_titles):
        return [{**ch, 'title': toc_titles[i]} for i, ch in enumerate(chapters)]

    # Fallback: title-substring matching
    result = []
    for ch in chapters:
        detected = ch.get('title', '')
        best = next(
            (t for t in toc_titles if detected and detected[:25] in t),
            None,
        )
        result.append({**ch, 'title': best} if best else ch)
    return result
