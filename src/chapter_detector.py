"""Detect chapter boundaries and reference sections from a markdown file.

Algorithm: reference section headings (## References, ## Suggested Reading,
etc.) act as chapter separators.  Everything between consecutive ref headings
is treated as a chapter body; the chapter's page range is derived from the
<!-- p. N --> markers in that span.

Outputs chapters/<key>.json as a list of dicts:
  {title, start_page, end_page, ref_start_line, ref_end_line}

start_page/end_page are the min/max book pages seen in the chapter body.
ref_start_line/ref_end_line are line indices (0-based) of the reference text,
half-open interval [ref_start_line, ref_end_line).
"""

import json
import re
from pathlib import Path

_DEFAULT_REF_RE = re.compile(r'^## (?:References|Bibliography)\s*$', re.I)
_PAGE_MARKER_RE = re.compile(r'^<!-- p\. (\d+) -->')
_HEADING_RE = re.compile(r'^(#{1,4}) (.+)')
_SKIP_TITLE_RE = re.compile(
    r'^(?:references|bibliography|suggested reading|further reading|'
    r'recommended reading|highlights?|key concepts?|summary|introduction|'
    r'c h a p t e r)',
    re.I,
)
# Reference-entry-like: surname followed by initials (" AB,") or comma+initial (", F")
# Stricter than just Cap+lowercase so "Chapter Two" / "Introduction" don't match.
_REF_LINE_RE = re.compile(
    r'^[A-Z][a-záéíóúàèìòùäëïöüñç\w-]+'
    r'(?:\s+[A-Z]{1,4}[,:.\s]|,\s*[A-Z])',
    re.U,
)
_YEAR_RE = re.compile(r'\b(1[89]\d\d|20[012]\d)[a-z]?\b', re.I)
_PAGE_ONLY_RE = re.compile(r'^\d{1,4}$')


def _extract_title(lines: list[str]) -> str:
    """Return first non-trivial heading text from a list of lines."""
    for line in lines:
        m = _HEADING_RE.match(line)
        if m:
            text = m.group(2).strip()
            if len(text) >= 5 and not _SKIP_TITLE_RE.match(text):
                return text
    return ''


def _find_ref_end(lines: list[str], start: int, limit: int) -> int:
    """Find the exclusive end of a reference section within [start, limit).

    Stops at:
    - An H1 heading (# Title) — unambiguous new chapter start
    - Three or more consecutive lines that are clearly body text
      (long lines without year patterns, not starting with author-like tokens)

    Returns the line index where non-reference content begins, or `limit`.
    """
    consecutive_body = 0
    body_start = limit

    for j in range(start, limit):
        raw = lines[j]
        stripped = raw.strip()
        if not stripped:
            continue

        # H1 heading → definite chapter start
        if re.match(r'^# [^#]', raw):
            return j

        # Page marker → neutral, skip
        if _PAGE_MARKER_RE.match(raw):
            continue

        # Bare page-number artifact from header stripping
        if _PAGE_ONLY_RE.match(stripped):
            continue

        # ## heading — treat as chapter boundary unless it looks like a
        # reference entry mis-classified as a heading by heading_detector
        # (e.g. "## Alberts B, Johnson A ... 2002 ..." or "## Smith, J. (1997)...")
        if raw.startswith('## '):
            heading_text = raw[3:].strip()
            is_ref_entry = bool(
                _YEAR_RE.search(heading_text) or _REF_LINE_RE.match(heading_text)
            )
            if not is_ref_entry:
                # Chapter boundary: scan backward past blanks and page markers so
                # page markers immediately before a chapter heading belong to that
                # chapter's body rather than the current ref section.
                boundary = j
                for back in range(j - 1, start - 1, -1):
                    bl = lines[back].strip()
                    if not bl:
                        continue
                    if _PAGE_MARKER_RE.match(lines[back]):
                        boundary = back
                        continue
                    break
                return boundary
            consecutive_body = 0
            continue

        # If line has a year it's likely a reference (any format)
        if _YEAR_RE.search(stripped):
            consecutive_body = 0
            continue

        # Line starts like an author name
        if _REF_LINE_RE.match(stripped):
            consecutive_body = 0
            continue

        # Continuation of a previous multi-line entry (short-ish, no year)
        if len(stripped) <= 90:
            consecutive_body = 0
            continue

        # Long line without year → probable body text
        consecutive_body += 1
        if consecutive_body == 1:
            body_start = j
        if consecutive_body >= 3:
            return body_start

    return limit


def detect(md_text: str, ref_heading_re=None) -> list[dict]:
    """Return chapter list derived from reference section headings.

    Each dict has:
      title          — str (first meaningful heading in the chapter body)
      start_page     — int | None  (min book page in chapter body span)
      end_page       — int | None  (max book page in chapter body span)
      ref_start_line — int  (line index of the ## References heading)
      ref_end_line   — int  (exclusive end of reference section lines)
    """
    if ref_heading_re is None:
        ref_heading_re = _DEFAULT_REF_RE

    lines = md_text.splitlines()
    ref_positions = [i for i, l in enumerate(lines) if ref_heading_re.match(l)]
    if not ref_positions:
        return []

    chapters = []
    prev_end = 0  # start of current chapter body (updated after each ref section)

    for k, ref_pos in enumerate(ref_positions):
        body_lines = lines[prev_end:ref_pos]

        pages = [
            int(m.group(1))
            for l in body_lines
            if (m := _PAGE_MARKER_RE.match(l))
        ]

        title = _extract_title(body_lines)

        # Determine where this ref section ends
        limit = ref_positions[k + 1] if k + 1 < len(ref_positions) else len(lines)
        ref_end = _find_ref_end(lines, ref_pos + 1, limit)

        chapters.append({
            'title': title,
            'start_page': min(pages) if pages else None,
            'end_page': max(pages) if pages else None,
            'ref_start_line': ref_pos,
            'ref_end_line': ref_end,
        })

        prev_end = ref_end

    return chapters


def save(chapters: list[dict], key: str, chapters_dir: Path) -> Path:
    """Write chapters/<key>.json and return the path."""
    chapters_dir.mkdir(parents=True, exist_ok=True)
    out = chapters_dir / f'{key}.json'
    out.write_text(json.dumps(chapters, ensure_ascii=False, indent=2), encoding='utf-8')
    return out
