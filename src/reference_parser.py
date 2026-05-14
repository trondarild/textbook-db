"""Parse reference section lines into structured entries.

Handles the six citation formats present in the corpus:

  Gosseries / Baars  (Elsevier/APA)
    LastName, F.N., Year. Title. Journal. Vol, pages.
    LastName, F., & LastName2, F. (Year). Title. Journal, Vol, pages.

  Kandel  (Vancouver-like)
    LastName AB. Year. Title. Journal Vol:Pages.

  Gazzaniga  (APA)
    LastName, F. (Year). Title. Journal, vol, pages.

  Yudofsky  (Am. Psychiatric Press – single-line)
    LastName AB: Title. Journal Vol(No):pages, Year PMID

  Buzaki  (author-year, single-line)
    LastName AB, LastName2 CD (Year) Title. Journal Vol:Pages.

Output entry dict:
  authors  — raw author string (everything before year)
  year     — four-digit year string, or '' if not found
  title    — approximate title (heuristic split)
  venue    — approximate venue/journal string
  raw      — full joined text of the entry
"""

import re

_YEAR_RE = re.compile(r'\b(1[89]\d\d|20[012]\d)[a-z]?\b', re.I)

# A new entry starts with an author-like token: LastName possibly followed by
# initials, comma, or colon.  We accept unicode characters in last names.
_ENTRY_START_RE = re.compile(
    r'^[A-Z][a-záéíóúàèìòùäëïöüñç\w-]+'  # last name
    r'(?:'
    r'(?:,\s+[A-Z])'            # ", F"  (APA/Elsevier)
    r'|(?:\s+[A-Z]{1,4}[,\.\s])' # " AB,"  (Vancouver/Buzaki)
    r'|(?:\s+[A-Z]{1,4}:)'       # " AB:"  (Yudofsky)
    r')'
)

# Lines to skip inside a reference section
_SKIP_LINE_RE = re.compile(
    r'^(?:<!-- p\. \d+ -->|<!-- ch\. \w+ -->|\d{1,4}$|#{1,4} )',
)

_BLANK_THRESHOLD = 3   # consecutive blanks → stop parsing
_BODY_THRESHOLD = 4    # consecutive non-ref lines → stop parsing


def _join_entries(raw_lines: list[str]) -> list[str]:
    """Group multi-line reference entries into single strings.

    A new entry starts when _ENTRY_START_RE matches the line.
    Lines that don't start an entry are continuation lines of the previous.
    Returns a list of joined strings, one per entry.
    """
    entries: list[list[str]] = []
    current: list[str] = []
    consecutive_blanks = 0
    consecutive_nonref = 0

    for line in raw_lines:
        stripped = line.strip()

        # Skip markers and headings
        if _SKIP_LINE_RE.match(line):
            continue

        if not stripped:
            consecutive_blanks += 1
            if consecutive_blanks >= _BLANK_THRESHOLD and current:
                entries.append(current)
                current = []
            continue
        consecutive_blanks = 0

        if _ENTRY_START_RE.match(stripped):
            if current:
                entries.append(current)
            current = [stripped]
            consecutive_nonref = 0
        elif current:
            # Check if this looks like a continuation or body text
            if len(stripped) > 120 and not _YEAR_RE.search(stripped):
                # Long non-year line → likely body text; stop
                consecutive_nonref += 1
                if consecutive_nonref >= _BODY_THRESHOLD:
                    break
                # Still append to keep multi-line entry intact
                current.append(stripped)
            else:
                current.append(stripped)
                consecutive_nonref = 0
        else:
            # Before first entry: skip
            pass

    if current:
        entries.append(current)

    return [' '.join(parts) for parts in entries]


def _parse_entry(raw: str) -> dict:
    """Parse one reference string into {authors, year, title, venue, raw}."""
    m = _YEAR_RE.search(raw)
    if m:
        year = m.group(1)
        year_pos = m.start()
        authors = raw[:year_pos].strip().rstrip('(,').strip()
        after_year = raw[m.end():].strip().lstrip(').').strip()
    else:
        year = ''
        # Try splitting on colon (Yudofsky) or period after initials
        colon = raw.find(':')
        if colon > 0 and colon < 40:
            authors = raw[:colon].strip()
            after_year = raw[colon + 1:].strip()
        else:
            authors = raw
            after_year = ''

    # Split after_year into title and venue at first sentence boundary
    # (period followed by space and capital, or common journal patterns)
    title, venue = _split_title_venue(after_year)

    return {
        'authors': authors,
        'year': year,
        'title': title,
        'venue': venue,
        'raw': raw,
    }


def _split_title_venue(text: str) -> tuple[str, str]:
    """Heuristically split 'Title. Journal vol:pages.' into (title, venue)."""
    # Find first '. ' followed by a pattern that looks like venue (short word,
    # number, or known journal abbreviation abbreviation-like)
    # Simple: split at first '. ' where what follows is ≤ 60 chars
    parts = text.split('. ')
    if len(parts) == 1:
        return text, ''
    if len(parts) == 2:
        return parts[0], parts[1]
    # Multiple periods: title is likely everything up to the penultimate '.'
    # and venue is the last fragment
    title = '. '.join(parts[:-1])
    venue = parts[-1]
    return title, venue


def parse_section(lines: list[str]) -> list[dict]:
    """Parse a list of lines from a reference section into structured entries.

    Stops parsing when it encounters clearly non-reference content
    (long body-text paragraphs without year patterns).
    Returns a list of entry dicts: {authors, year, title, venue, raw}.
    """
    joined = _join_entries(lines)
    return [_parse_entry(raw) for raw in joined if raw.strip()]


def extract_all(md_text: str, chapters: list[dict]) -> dict[str, list[dict]]:
    """Extract references for all chapters.

    Returns {chapter_title: [entry_dict, ...]}
    """
    lines = md_text.splitlines()
    result: dict[str, list[dict]] = {}
    for ch in chapters:
        if ch.get('ref_start_line') is None:
            continue
        ref_lines = lines[ch['ref_start_line']:ch['ref_end_line']]
        entries = parse_section(ref_lines)
        title = ch['title'] or f"p. {ch['start_page']}–{ch['end_page']}"
        result[title] = entries
    return result


def save(refs: dict, key: str, refs_dir) -> 'Path':
    """Write references/<key>.json and return the path."""
    import json
    from pathlib import Path
    refs_dir = Path(refs_dir)
    refs_dir.mkdir(parents=True, exist_ok=True)
    out = refs_dir / f'{key}.json'
    out.write_text(json.dumps(refs, ensure_ascii=False, indent=2), encoding='utf-8')
    return out
