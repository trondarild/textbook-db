"""
Strip running headers and footers from page-segmented book text.

Algorithm:
1. For each page, collect the first 3 and last 3 non-empty lines (the "header zone").
2. Global pass: lines appearing in the header zone of > GLOBAL_THRESH of all pages → bad.
3. Windowed pass (window=WINDOW_SIZE pages, step=WINDOW_SIZE//2): lines appearing in
   the header zone of > WINDOW_THRESH of pages in the window → bad (catches chapter titles).
4. Pure page-number lines (bare integers) are never added to bad_lines.
5. Strip bad lines only when they appear in the header zone of a page.
"""

import re
from collections import Counter

_PURE_INT = re.compile(r'^\d{1,5}$')

_DEFAULT_GLOBAL_THRESH = 0.35
_DEFAULT_WINDOW_SIZE = 30
_DEFAULT_WINDOW_THRESH = 0.30


def _header_zone_lines(text):
    """Return (list_of_ne_lines, set_of_header_zone_strings) for a page text."""
    lines = text.split('\n')
    ne_indices = [i for i, l in enumerate(lines) if l.strip()]
    zone_indices = set(ne_indices[:3]) | set(ne_indices[-3:])
    zone_strings = {lines[i].strip() for i in zone_indices}
    return lines, ne_indices, zone_indices, zone_strings


def find_bad_lines(
    segments,
    global_thresh=_DEFAULT_GLOBAL_THRESH,
    window_size=_DEFAULT_WINDOW_SIZE,
    window_thresh=_DEFAULT_WINDOW_THRESH,
):
    """Return frozenset of line strings identified as running headers or footers."""
    n = len(segments)
    page_zones = [_header_zone_lines(s['text'])[3] for s in segments]

    global_freq = Counter()
    for zone in page_zones:
        for line in zone:
            global_freq[line] += 1

    bad = set()
    for line, cnt in global_freq.items():
        if _PURE_INT.match(line):
            continue
        if cnt / n >= global_thresh:
            bad.add(line)

    step = max(1, window_size // 2)
    for start in range(0, n, step):
        end = min(start + window_size, n)
        window = page_zones[start:end]
        w = len(window)
        if w < 5:
            continue
        win_freq = Counter()
        for zone in window:
            for line in zone:
                win_freq[line] += 1
        for line, cnt in win_freq.items():
            if _PURE_INT.match(line):
                continue
            if cnt / w >= window_thresh:
                bad.add(line)

    return frozenset(bad)


def strip_headers(segments, bad_lines=None, **kwargs):
    """Strip running headers/footers from segments.

    Returns (new_segments, bad_lines).  Each new segment has the same keys as the
    input segment, with 'text' cleaned of header/footer lines.
    """
    if bad_lines is None:
        bad_lines = find_bad_lines(segments, **kwargs)

    result = []
    for seg in segments:
        lines, ne_indices, zone_indices, _ = _header_zone_lines(seg['text'])
        cleaned = [
            line for i, line in enumerate(lines)
            if not (i in zone_indices and line.strip() in bad_lines)
        ]
        result.append({**seg, 'text': '\n'.join(cleaned)})

    return result, bad_lines
