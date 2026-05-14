"""
Baars 2013 — Fundamentals of Cognitive Neuroscience

post_segment : drop front-matter pages before the first chapter opener.
post_strip   : on chapter-opener pages (contain 'C H A P T E R' and 'O U T L I N E'),
               trim everything from 'O U T L I N E' onward.  This removes the per-chapter
               section outline and the trailing copyright line (which pdftotext renders
               as '# 2013 Elsevier Inc. All rights reserved.').
post_chapter_detect : rebuild chapter list from ## C H A P T E R markers.  Baars has a
               single global ## References section at the end; all chapters get
               ref_start_line=None except the last, which gets the global ref line.
"""

import re
from pathlib import Path

_PAGE_RE = re.compile(r'^<!-- p\. (\d+) -->')
_CHAP_RE = re.compile(r'^## C H A P T E R')
_REF_HEADING_RE = re.compile(r'^## References\s*$')


def post_segment(segments, meta):
    # Drop everything before the first page that contains 'C H A P T E R'
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
                (i for i, l in enumerate(lines) if l.strip() == 'O U T L I N E'),
                None,
            )
            if cut is not None:
                text = '\n'.join(lines[:cut])
        result.append({**s, 'text': text})
    return result


def post_chapter_detect(chapters, meta):
    base = Path(__file__).parent.parent
    md_rel = meta.get('md_path', 'md/baars2013.md')
    md_path = base / md_rel
    if not md_path.exists():
        return chapters

    lines = md_path.read_text(encoding='utf-8').splitlines()

    page_to_line: dict[int, int] = {}
    for i, l in enumerate(lines):
        m = _PAGE_RE.match(l)
        if m:
            p = int(m.group(1))
            if p not in page_to_line:
                page_to_line[p] = i

    chap_marker_lines = [i for i, l in enumerate(lines) if _CHAP_RE.match(l)]

    global_ref_line = next(
        (i for i, l in enumerate(lines) if _REF_HEADING_RE.match(l)), None
    )

    entries = []
    for cl in chap_marker_lines:
        title = ''
        start_p = None
        for j in range(cl + 1, min(cl + 15, len(lines))):
            l2 = lines[j].strip()
            if l2.startswith('### ') and len(l2) > 6:
                title = l2[4:]
                break
        for j in range(cl + 1, min(cl + 20, len(lines))):
            m2 = _PAGE_RE.match(lines[j])
            if m2:
                start_p = int(m2.group(1))
                break
        if start_p is not None:
            entries.append({'title': title, 'start_page': start_p})

    result = []
    for k, e in enumerate(entries):
        next_start = entries[k + 1]['start_page'] if k + 1 < len(entries) else None
        end_p = (next_start - 1) if next_start else None
        end_line = (
            page_to_line.get(next_start, len(lines))
            if next_start
            else (global_ref_line or len(lines))
        )
        result.append({
            'title': e['title'],
            'start_page': e['start_page'],
            'end_page': end_p,
            'ref_start_line': None,
            'ref_end_line': end_line,
        })

    # Attach global reference list to the last chapter
    if result and global_ref_line is not None:
        result[-1]['ref_start_line'] = global_ref_line
        result[-1]['ref_end_line'] = len(lines)

    return result
