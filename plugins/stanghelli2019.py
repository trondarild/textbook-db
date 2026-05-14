"""
Stanghelli 2019 — The Oxford Handbook of Phenomenological Psychopathology (OUP).

OUP online-format PDF layout:
  - No printed page numbers in running headers or footers.
  - Printed page numbers are embedded inline as '(p. N)' in the body text.
  - Chapter title repeated as running header (first line) on every PDF page.
  - 'Page N of M' appears at the bottom (chapter-relative, not used for page mapping).
  - Chapter openers contain: title (×2), author name, book title, editor list, DOI/dates,
    abstract, keywords — these are online-only and should be stripped.

post_segment: assign book_page from first inline '(p. N)' marker per PDF page;
              drop front matter before the first chapter opener.
post_strip  : remove chapter-title running headers from the header zone;
              second frequency pass to catch remaining repeating lines.
post_annotate: remove author-affiliation headings that leak from chapter openers.
post_chapter_detect: override chapter titles from toc/stanghelli2019.json.
"""

import json
import re
from pathlib import Path
from src.header_stripper import _header_zone_lines, strip_headers

_PAGE_MARKER_RE = re.compile(r'\(p\.\s*(\d+)\)')
_CHAPTER_OPENER_RE = re.compile(
    r'^(?:Section\s+\w+|Introduction|List of Contributors)',
    re.I,
)
# Chapter openers start with the chapter title repeated on two consecutive non-empty lines
_DOI_RE = re.compile(r'DOI:\s*10\.')
_ABSTRACT_LINE_RE = re.compile(r'^Abstract and Keywords$', re.I)


def _is_chapter_opener(text: str) -> bool:
    """True if this PDF page is a chapter opener (has DOI or Abstract block)."""
    return bool(_DOI_RE.search(text) or _ABSTRACT_LINE_RE.search(text))


def post_segment(segments, meta):
    patched = []
    for s in segments:
        text = s['text']
        m = _PAGE_MARKER_RE.search(text)
        page = int(m.group(1)) if m else None
        patched.append({**s, 'book_page': page})

    # Drop everything before the first chapter opener.
    # Chapter openers have DOI lines and "Abstract and Keywords" — strip those
    # pages entirely, then keep from the next PDF page onward.
    in_front_matter = True
    result = []
    for s in patched:
        if in_front_matter:
            if _is_chapter_opener(s['text']):
                in_front_matter = False
                # Skip the opener page itself (abstract/keywords only)
                continue
        else:
            result.append(s)

    # If we never left front matter, return everything (shouldn't happen)
    return result if result else patched


def post_strip(segments, meta):
    # Pass 1: strip the chapter-title running header from the header zone.
    # On every regular page, the first non-empty line is the chapter title.
    pass1 = []
    for s in segments:
        lines = s['text'].split('\n')
        ne = [l for l in lines if l.strip()]
        if not ne:
            pass1.append(s)
            continue
        chapter_title = ne[0].strip()
        cleaned = []
        removed_first = False
        for line in lines:
            if not removed_first and line.strip() == chapter_title:
                removed_first = True
                continue
            cleaned.append(line)
        pass1.append({**s, 'text': '\n'.join(cleaned)})

    # Pass 2: frequency analysis to catch any remaining repetitive lines
    pass2, _ = strip_headers(pass1, window_thresh=0.20)
    return pass2


_PAGE_N_OF_M_RE = re.compile(r'^Page \d+ of \d+$')


def post_annotate(segments, meta):
    """Drop headings that are running artifacts: 'Page N of M', DOI lines."""
    result = []
    for s in segments:
        filtered = [
            h for h in s.get('headings', [])
            if not _PAGE_N_OF_M_RE.match(h[2])
            and not _DOI_RE.search(h[2])
        ]
        result.append({**s, 'headings': filtered})
    return result


def post_chapter_detect(chapters, meta):
    """Override chapter titles from toc/stanghelli2019.json.

    Each detected chapter spans the content between two Bibliography sections.
    Multiple TOC chapters may share a single bibliography (OUP handbook structure).
    Use the last TOC entry within each detected chapter's page range; fall back
    to the last TOC entry before the detected chapter's start page.
    """
    toc_path = Path(__file__).parent.parent / 'toc' / 'stanghelli2019.json'
    if not toc_path.exists():
        return chapters

    toc = json.loads(toc_path.read_text(encoding='utf-8'))
    # Exclude the standalone 'Bibliography' TOC entry
    toc_clean = [e for e in toc if e['title'] != 'Bibliography']

    result = []
    for ch in chapters:
        sp = ch.get('start_page')
        ep = ch.get('end_page', 999999)
        if sp is None:
            result.append(ch)
            continue

        # Prefer last TOC entry whose start_page falls within this chapter's range
        in_range = [t for t in toc_clean if sp <= t['start_page'] <= ep]
        if in_range:
            title = in_range[-1]['title']
        else:
            # Fallback: last TOC entry with start_page <= this chapter's start
            before = [t for t in toc_clean if t['start_page'] <= sp]
            title = before[-1]['title'] if before else ch.get('title', '')

        result.append({**ch, 'title': title})

    return result
