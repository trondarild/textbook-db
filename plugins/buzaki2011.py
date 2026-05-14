"""
Buzaki 2011 — Rhythms of the Brain

post_segment: drop front-matter PDF pages before Cycle 1.

post_chapter_detect: Buzaki has no "## References" heading; the full bibliography
is a single alphabetical list starting at page 373.  This hook adds one synthetic
chapter entry per Cycle (detected from # Cycle N headings) plus a final
bibliography entry for everything from page 373 onward.
"""

import re

_CYCLE_RE = re.compile(r'^# (Cycle \d+)')
_REF_LINE_RE = re.compile(r'^[A-Z][a-z]+ [A-Z]+ \(')  # "Abbott LF (...)"
_PAGE_RE = re.compile(r'^<!-- p\. (\d+) -->')

_BIBLIO_START_PAGE = 373   # first page of Buzaki's bibliography


def post_segment(segments, meta):
    # Locate the pdf_page where Cycle 1 begins.
    cycle1_pdf = None
    for s in segments:
        if s['text'].strip().startswith('Cycle 1'):
            cycle1_pdf = s['pdf_page']
            break

    if cycle1_pdf is None:
        return segments  # can't detect — leave untouched

    return [s for s in segments if s['pdf_page'] >= cycle1_pdf]


def post_chapter_detect(chapters, meta):
    """Build chapter list from # Cycle N headings and bibliography page."""
    import pathlib, json
    base = pathlib.Path(__file__).parent.parent
    md_path = base / meta.get('md_path', 'md/buzaki2011.md')
    if not md_path.exists():
        return chapters

    lines = md_path.read_text(encoding='utf-8').splitlines()

    # Collect (cycle_title, first_page) pairs
    cycles = []
    current_page = None
    for line in lines:
        m = _PAGE_RE.match(line)
        if m:
            current_page = int(m.group(1))
        mc = _CYCLE_RE.match(line)
        if mc and current_page is not None:
            cycles.append({'title': mc.group(1), 'start_page': current_page})

    if not cycles:
        return chapters

    # Fill end_page: each cycle ends one page before the next cycle
    for i in range(len(cycles) - 1):
        cycles[i]['end_page'] = cycles[i + 1]['start_page'] - 1
    cycles[-1]['end_page'] = _BIBLIO_START_PAGE - 1

    # Add empty ref fields (no per-chapter refs in Buzaki)
    for c in cycles:
        c['ref_start_line'] = None
        c['ref_end_line'] = None

    # Find the line index where the bibliography starts (first page ≥ 373)
    biblio_start_line = None
    for i, line in enumerate(lines):
        m = _PAGE_RE.match(line)
        if m and int(m.group(1)) >= _BIBLIO_START_PAGE:
            biblio_start_line = i
            break

    if biblio_start_line is not None:
        cycles.append({
            'title': 'Bibliography',
            'start_page': _BIBLIO_START_PAGE,
            'end_page': None,
            'ref_start_line': biblio_start_line,
            'ref_end_line': len(lines),
        })

    return cycles
