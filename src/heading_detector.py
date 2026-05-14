"""
Detect chapter/section headings in page-segmented text and return markdown levels.

Heuristics (all must pass for a line to be a heading candidate):
  - Short: <= MAX_HEADING_LEN characters
  - No terminal punctuation (. , ; : ? !)
  - Preceded and followed by a blank line within the page (or at page boundary)
  - Not a bare integer

Level assignment (first matching rule wins):
  1  — matches CYCLE_RE  (e.g. "Cycle 1", "CYCLE 1")
  2  — all-caps or title-case, len >= MIN_H2_LEN chars
  3  — mixed case, len < MIN_H2_LEN chars (short subheadings)
"""

import re

MAX_HEADING_LEN = 79
MIN_H2_LEN = 10
_TERMINAL_PUNCT = re.compile(r'[.,;:?!]$')
_PURE_INT = re.compile(r'^\d+$')
_CYCLE_RE = re.compile(r'^cycle\s+\d+\s*$', re.I)  # full line must be "Cycle N"
_ALL_CAPS = re.compile(r'^[A-Z][A-Z0-9 \-:,\']+$')

# Words excluded when measuring title-case ratio
_FUNC_WORDS = frozenset({
    'a', 'an', 'the', 'of', 'in', 'on', 'at', 'to', 'for', 'and', 'or',
    'but', 'with', 'by', 'from', 'as', 'is', 'no', 'not', 'that', 'than',
    'this', 'its', 'it', 'are', 'was', 'be', 'been', 'have', 'has',
})


def _is_heading_candidate(line, prev_blank, next_blank):
    s = line.strip()
    if not s:
        return False
    if len(s) > MAX_HEADING_LEN:
        return False
    if _TERMINAL_PUNCT.search(s):
        return False
    if _PURE_INT.match(s):
        return False
    if not (prev_blank or next_blank):
        return False
    return True


def _is_title_case(text):
    """True if >= 60% of content words start with a capital letter."""
    words = text.split()
    if not words or not words[0][:1].isupper():
        return False
    content = [w for w in words if w.rstrip('.,;:!?').lower() not in _FUNC_WORDS]
    if len(content) < 2:
        return bool(content) and content[0][:1].isupper()
    cap = sum(1 for w in content if w[:1].isupper())
    return cap / len(content) >= 0.6


def _heading_level(line):
    s = line.strip()
    if _CYCLE_RE.match(s):
        return 1
    if (_ALL_CAPS.match(s) or _is_title_case(s)) and len(s) >= MIN_H2_LEN:
        return 2
    return 3


def detect_headings(text):
    """Return list of (line_index, heading_level, heading_text) for a single page text."""
    lines = text.split('\n')
    results = []
    for i, line in enumerate(lines):
        prev_blank = (i == 0) or (not lines[i - 1].strip())
        next_blank = (i == len(lines) - 1) or (not lines[i + 1].strip())
        if _is_heading_candidate(line, prev_blank, next_blank):
            results.append((i, _heading_level(line), line.strip()))
    return results


def annotate_segments(segments):
    """Add 'headings' key to each segment: list of (line_idx, level, text)."""
    return [{**seg, 'headings': detect_headings(seg['text'])} for seg in segments]
