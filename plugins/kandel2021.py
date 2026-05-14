"""
Kandel 2021 — Principles of Neural Science, 6th ed.

Page numbers are embedded in running headers using em-space (U+2003) as separator:
  even pages:  "N  Part / Section"   → book_page = N
  odd pages:   "Chapter N / Title  M" → book_page = M

post_segment: parse these patterns to assign book_page, then drop front matter.
post_strip  : two-pass strip — pattern-based (remove header lines by regex), then
              re-run frequency analysis to catch exposed chapter subtitles.
post_chapter_detect: extend each chapter's ref_start_line to include the preceding
              ## Selected Reading section when it immediately precedes ## References.
"""

import re
from pathlib import Path
from src.header_stripper import _header_zone_lines, strip_headers

_SEL_READ_RE = re.compile(r'^## Selected Reading\s*$')
_PAGE_RE = re.compile(r'^<!-- p\. (\d+) -->')

_EVEN_RE = re.compile(r'^(\d{1,4}) ')          # "8  Part I..."
_ODD_RE  = re.compile(r' (\d{1,4})\s*$')        # "Chapter 1 / Title  9"
# Chapter opener format: "Part I\nChapter 1\nTitle"
_PART_RE = re.compile(r'^Part\s+\w+', re.I)
_CHAP_RE = re.compile(r'^Chapter\s+\d+', re.I)


def _extract_page(text):
    first = next((l.strip() for l in text.split('\n') if l.strip()), '')
    m = _EVEN_RE.match(first) or _ODD_RE.search(first)
    return int(m.group(1)) if m else None


def _is_header_pattern(line):
    s = line.strip()
    return bool(_EVEN_RE.match(s) or _ODD_RE.search(s))


def post_segment(segments, meta):
    # Assign book_page from header pattern
    patched = []
    for s in segments:
        if s['book_page'] is None:
            page = _extract_page(s['text'])
            patched.append({**s, 'book_page': page} if page is not None else s)
        else:
            patched.append(s)

    # Drop front matter: keep from first page where first line matches header pattern
    for i, s in enumerate(patched):
        if s['book_page'] is not None:
            first = next((l.strip() for l in s['text'].split('\n') if l.strip()), '')
            if _EVEN_RE.match(first) or _ODD_RE.search(first):
                return patched[i:]

    return patched


def post_strip(segments, meta):
    # Pass 1: strip pattern-based header lines from header zone
    pass1 = []
    for s in segments:
        lines, ne_indices, zone_indices, _ = _header_zone_lines(s['text'])
        cleaned = [
            l for i, l in enumerate(lines)
            if not (i in zone_indices and _is_header_pattern(l))
        ]
        pass1.append({**s, 'text': '\n'.join(cleaned)})

    # Pass 2: frequency analysis with lower threshold to catch exposed subtitles
    pass2, _ = strip_headers(pass1, window_thresh=0.20)
    return pass2


def post_chapter_detect(chapters, meta):
    """Extend each chapter's ref section to include any preceding ## Selected Reading."""
    base = Path(__file__).parent.parent
    md_rel = meta.get('md_path', 'md/kandel2021.md')
    md_path = base / md_rel
    if not md_path.exists():
        return chapters

    lines = md_path.read_text(encoding='utf-8').splitlines()

    result = []
    for ch in chapters:
        rsl = ch.get('ref_start_line')
        if rsl is None:
            result.append(ch)
            continue

        # Scan backward from ref_start_line looking for a ## Selected Reading
        # heading.  Stop if we hit any other non-ref ## heading (chapter body).
        new_rsl = rsl
        for j in range(rsl - 1, max(0, rsl - 120), -1):
            raw = lines[j]
            if _SEL_READ_RE.match(raw):
                new_rsl = j
                break
            # Stop at any other ## heading that looks like a chapter body heading
            if raw.startswith('## ') and not _SEL_READ_RE.match(raw):
                break

        result.append({**ch, 'ref_start_line': new_rsl})
    return result
