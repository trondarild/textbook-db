"""
Gazzaniga 2014 — Cognitive Neuroscience: The Biology of the Mind

Page numbers are embedded in running headers rather than as standalone lines:
  even pages:  "N | CHAPTER M"            → book_page = N
  odd pages:   "Section Title | N"         → book_page = N

Because each even-page header is unique (N changes every page), frequency analysis
cannot catch them.  The post_strip hook removes them with pattern matching, then
runs a second frequency pass to catch the chapter subtitle that becomes exposed.

post_chapter_detect: rebuilds chapter list from toc/gazzaniga2014.json (extracted
via jpdfbm) instead of inferring boundaries from ref-heading spacing.
"""

import json
import re
from pathlib import Path

from src.header_stripper import _header_zone_lines, strip_headers

_PAGE_MARKER_RE = re.compile(r'^<!-- p\. (\d+) -->')
_CHAP_PREFIX_RE = re.compile(r'^Chapter\s+\d+:\s+', re.I)

_EVEN_RE = re.compile(r'^(\d{1,4})\s*\|')          # "64 | CHAPTER 2"
_ODD_RE  = re.compile(r'\|\s*(\d{1,4})\s*$')        # "The Brain Story | 5"


def _extract_page(text):
    """Return page number from a Gazzaniga header line, or None."""
    first = next((l.strip() for l in text.split('\n') if l.strip()), '')
    m = _EVEN_RE.match(first) or _ODD_RE.search(first)
    return int(m.group(1)) if m else None


def _is_header_pattern(line):
    s = line.strip()
    return bool(_EVEN_RE.match(s) or _ODD_RE.search(s))


def post_segment(segments, meta):
    # Assign book_page from header pattern where missing
    patched = []
    for s in segments:
        if s['book_page'] is None:
            page = _extract_page(s['text'])
            patched.append({**s, 'book_page': page} if page is not None else s)
        else:
            patched.append(s)

    # Drop front matter: keep from first page whose first line matches the header pattern
    for i, s in enumerate(patched):
        if s['book_page'] is not None:
            first = next((l.strip() for l in s['text'].split('\n') if l.strip()), '')
            if _EVEN_RE.match(first) or _ODD_RE.search(first) or first.lower() == 'chapter':
                return patched[i:]

    return patched


_TRAILING_FUNC = re.compile(
    r'\b(a|an|the|in|of|by|for|and|or|to|from|with|on|at|as|into)\s*$', re.I
)
_CAPTION_PREFIX = re.compile(r'^(FIGURE|TABLE|BOX)\s+\d', re.I)


def post_chapter_detect(chapters, meta):
    """Rebuild chapter list from toc/gazzaniga2014.json and the md file."""
    base = Path(__file__).parent.parent
    toc_path = base / 'toc' / 'gazzaniga2014.json'
    md_rel = meta.get('md_path', 'md/gazzaniga2014.md')
    md_path = base / md_rel

    if not toc_path.exists() or not md_path.exists():
        return chapters

    toc = json.loads(toc_path.read_text())
    lines = md_path.read_text(encoding='utf-8').splitlines()

    # {book_page: first line index} from <!-- p. N --> markers
    page_to_line: dict[int, int] = {}
    for i, line in enumerate(lines):
        m = _PAGE_MARKER_RE.match(line)
        if m:
            p = int(m.group(1))
            if p not in page_to_line:
                page_to_line[p] = i

    # Chapter-level TOC entries only
    chap_entries = [e for e in toc if e['level'] == 0 and re.match(r'^Chapter\s+\d+', e['title'], re.I)]

    # Also capture next top-level entry after last chapter (Glossary/References) for end_page
    last_chap_idx = toc.index(chap_entries[-1]) if chap_entries else -1
    after_chapters = [e for e in toc[last_chap_idx + 1:] if e['level'] == 0]
    post_chapter_page = after_chapters[0]['pdf_page'] if after_chapters else len(lines)

    sorted_pages = sorted(page_to_line)

    def _nearest_line(page, default):
        """Line index for the nearest available page marker >= page."""
        for p in sorted_pages:
            if p >= page:
                return page_to_line[p]
        return default

    result = []
    for k, entry in enumerate(chap_entries):
        title = _CHAP_PREFIX_RE.sub('', entry['title']).strip()
        start_page = entry['pdf_page']
        next_page = chap_entries[k + 1]['pdf_page'] if k + 1 < len(chap_entries) else post_chapter_page
        end_page = next_page - 1

        # Line boundaries: use exact marker if present, else nearest page >= target
        start_line = page_to_line.get(start_page) or _nearest_line(start_page, 0)
        end_line = page_to_line.get(next_page) or _nearest_line(next_page, len(lines))

        # Find ## Suggested Reading(s) within this chapter's line span
        ref_start_line = next(
            (i for i, l in enumerate(lines[start_line:end_line], start=start_line)
             if l.startswith('## Suggested Reading')),
            None,
        )

        result.append({
            'title': title,
            'start_page': start_page,
            'end_page': end_page,
            'ref_start_line': ref_start_line,
            'ref_end_line': end_line,
        })

    return result


def post_annotate(segments, meta):
    """Remove false-positive headings: figure/table captions and truncated lines."""
    result = []
    for s in segments:
        filtered = [
            h for h in s.get('headings', [])
            if not _CAPTION_PREFIX.match(h[2])      # drop FIGURE/TABLE captions
            and not _TRAILING_FUNC.search(h[2])      # drop lines ending mid-phrase
        ]
        result.append({**s, 'headings': filtered})
    return result


def post_strip(segments, meta):
    # Pass 1: strip lines matching the "N | CHAPTER M" / "Title | N" patterns
    #         from the header zone of every page (frequency analysis can't catch
    #         these because N is unique per page).
    pass1 = []
    for s in segments:
        lines, ne_indices, zone_indices, _ = _header_zone_lines(s['text'])
        cleaned = [
            l for i, l in enumerate(lines)
            if not (i in zone_indices and _is_header_pattern(l))
        ]
        pass1.append({**s, 'text': '\n'.join(cleaned)})

    # Pass 2: re-run frequency analysis with a lower window threshold to catch
    #         chapter subtitle lines now exposed at the top of pages.
    pass2, _ = strip_headers(pass1, window_thresh=0.20)
    return pass2
