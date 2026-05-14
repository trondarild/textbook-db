"""
Gosseries 2016 — The Neurology of Consciousness, 2nd ed. (edited volume)

Each chapter opener has:  C H A P T E R / number / title / author(s) / affiliations / O U T L I N E / ...

post_segment       : drop front-matter pages before the first chapter.
post_strip         : trim from O U T L I N E onwards on chapter-opener pages.
post_annotate      : remove false-positive headings.
post_chapter_detect: rebuild chapter list from C H A P T E R markers because the
                     default detect() cannot find chapter starts from generic signals.
"""

import re
from pathlib import Path

_GEO_SUFFIX    = re.compile(
    r',\s*(USA|UK|France|Germany|Belgium|Netherlands|Italy|Spain|Switzerland|'
    r'Canada|Australia|Norway|Sweden|Denmark|Finland)\s*$', re.I
)
_EDITORIAL     = re.compile(r'\(Eds?\.\)', re.I)
_SPACED_WORD   = re.compile(r'^[A-Z](\s[A-Z])+$')    # "O U T L I N E"
_CAPTION       = re.compile(r'^(FIGURE|TABLE|BOX|PLATE)\s+\d', re.I)


def post_segment(segments, meta):
    for i, s in enumerate(segments):
        if 'C H A P T E R' in s['text']:
            return segments[i:]
    return segments


def post_strip(segments, meta):
    result = []
    for s in segments:
        text = s['text']
        if 'C H A P T E R' in text and 'O U T L I N E' in text:
            lines = text.split('\n')
            cut = next(
                (i for i, l in enumerate(lines) if l.strip() == 'O U T L I N E'), None
            )
            if cut is not None:
                text = '\n'.join(lines[:cut])
        result.append({**s, 'text': text})
    return result


_PAGE_RE = re.compile(r'^<!-- p\. (\d+) -->')
_REF_HEADING_RE = re.compile(r'^## References\s*$')


def post_chapter_detect(chapters, meta):
    """Rebuild chapter list from C H A P T E R openers and ## References headings."""
    base = Path(__file__).parent.parent
    md_path = base / meta.get('md_path', 'md/gosseries2016.md')
    if not md_path.exists():
        return chapters

    lines = md_path.read_text(encoding='utf-8').splitlines()

    # Locate all C H A P T E R opener positions and extract title + first page
    chapter_starts = []
    i = 0
    while i < len(lines):
        if lines[i].strip() == 'C H A P T E R':
            # Next non-empty lines: chapter number, then title, then authors
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            # chapter number line
            j += 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            title_line = lines[j].strip() if j < len(lines) else ''

            # Find first <!-- p. N --> after this opener (the first content page)
            first_page = None
            for k in range(i, min(i + 30, len(lines))):
                m = _PAGE_RE.match(lines[k])
                if m and int(m.group(1)) > 10:   # skip small "chapter number" pages
                    first_page = int(m.group(1))
                    break

            chapter_starts.append({
                'title': title_line,
                'opener_line': i,
                'first_page': first_page,
            })
        i += 1

    if not chapter_starts:
        return chapters

    # Locate all ## References headings
    ref_positions = [i for i, l in enumerate(lines) if _REF_HEADING_RE.match(l)]

    # Pair each chapter with its ref section (the first ref heading after the opener)
    result = []
    for k, cs in enumerate(chapter_starts):
        next_opener = chapter_starts[k + 1]['opener_line'] if k + 1 < len(chapter_starts) else len(lines)

        # Collect pages between chapter opener and next opener (= this chapter's pages)
        pages = [
            int(m.group(1))
            for l in lines[cs['opener_line']:next_opener]
            if (m := _PAGE_RE.match(l))
        ]

        # Find ref section within this chapter's span
        ref_start = next(
            (r for r in ref_positions if cs['opener_line'] < r < next_opener), None
        )
        if ref_start is None:
            ref_end = next_opener
        else:
            # Ref section ends at next C H A P T E R opener
            ref_end = next_opener

        body_pages = [p for p in pages if p > 10]
        result.append({
            'title': cs['title'],
            'start_page': min(body_pages) if body_pages else None,
            'end_page': max(body_pages) if body_pages else None,
            'ref_start_line': ref_start,
            'ref_end_line': ref_end,
        })

    return result


def post_annotate(segments, meta):
    result = []
    for s in segments:
        filtered = [
            h for h in s.get('headings', [])
            if not _GEO_SUFFIX.search(h[2])
            and not _EDITORIAL.search(h[2])
            and not _SPACED_WORD.match(h[2])     # removes "O U T L I N E"
            and not _CAPTION.match(h[2])
        ]
        result.append({**s, 'headings': filtered})
    return result
