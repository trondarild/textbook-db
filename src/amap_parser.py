"""Parse .amap argument-map files into structured claim dicts.

Canonical claim line format (manual-notation.md):
    ↓ STATUS label (TYPE) "one-line note or source"

    STATUS : ?  stub (not yet formulated — primary grounding target)
             ~  drafted (prose exists, no citation yet — secondary target)
             *  cited (citation present, not verified)
             ✓  complete (verified, fits in chain)
             (absent = unset)
    TYPE   : T (theoretical)  E (empirical)  R (review)  ! (naked assertion)

Inline citations in square brackets are an extension used in practice:
    ↓ * label (T) "text" [Author Year; Author Year]

Gap report section (inside a ``` fence after ## Gap report) lists structural
gaps, naked assertions needing citation, and stubs.
"""

import re
from pathlib import Path

# Handles canonical single-char status + legacy *? from older files
_CLAIM_RE = re.compile(
    r'^↓\s+'
    r'(?P<status>[?~*✓]|\*\?)?\s*'
    r'(?P<label>\w+)\s+'
    r'\((?P<type>[TER!])\)\s+'
    r'"(?P<text>[^"]+)"'
    r'(?:\s+\[(?P<citations>[^\]]*)\])?'
)

_CITATIONS_ENTRY_RE = re.compile(r'^\s+(\w+)\s+\([^)]+\):\s*(.+)$')
_GAP_LABEL_RE = re.compile(r'^(\w+)\s+\([^)]+\)\s+[—\-]\s+(.+)')


def parse_claims(text: str) -> list[dict]:
    """Parse all claim lines from .amap text."""
    claims = []
    for line in text.splitlines():
        m = _CLAIM_RE.match(line.strip())
        if not m:
            continue
        citations = []
        if m.group('citations'):
            citations = [c.strip() for c in m.group('citations').split(';')
                         if c.strip()]
        claims.append({
            'label':     m.group('label'),
            'status':    m.group('status') or '',
            'type':      m.group('type'),
            'text':      m.group('text'),
            'citations': citations,
        })
    return claims


def priority_claims(claims: list[dict]) -> list[dict]:
    """Return claims that are highest-priority for textbook grounding.

    Primary:   status='?' — stubs not yet formulated; need evidence to develop
    Secondary: status='~' — drafted but no citation yet
    """
    stubs   = [c for c in claims if c['status'] == '?']
    drafted = [c for c in claims if c['status'] == '~']
    return stubs + drafted


def parse_citations_block(text: str) -> dict[str, list[str]]:
    """Parse canonical CITATIONS block → {label: [ref_str]}.

    Format:
        CITATIONS
          claim_one  (R): Nagel1974, Chalmers1995
          claim_two  (E): CrickKoch1998
    """
    result: dict[str, list[str]] = {}
    in_block = False
    for line in text.splitlines():
        if line.strip() == 'CITATIONS':
            in_block = True
            continue
        if in_block:
            if line and not line[0].isspace():
                break  # end of block
            m = _CITATIONS_ENTRY_RE.match(line)
            if m:
                refs = [r.strip() for r in m.group(2).split(',') if r.strip()]
                result[m.group(1)] = refs
    return result


def _extract_fence_content(text: str, heading: str = '## Gap report') -> list[str]:
    """Return lines inside the first ``` fence following *heading*."""
    lines = text.splitlines()
    in_section = False
    in_fence = False
    content: list[str] = []
    for line in lines:
        if line.strip() == heading:
            in_section = True
            continue
        if in_section:
            if line.strip() == '```':
                if not in_fence:
                    in_fence = True
                else:
                    break
                continue
            if in_fence:
                content.append(line)
    return content


def parse_gap_report(text: str) -> dict:
    """Extract structural gaps, naked assertions, and stubs from the gap report."""
    gaps: dict = {'structural': [], 'naked_assertions': [], 'stubs': []}
    section = None

    for line in _extract_fence_content(text):
        stripped = line.strip()
        if not stripped or stripped.startswith('─'):
            continue
        if stripped.startswith('STRUCTURAL GAPS'):
            section = 'structural'
        elif 'NAKED ASSERTIONS' in stripped:
            section = 'naked'
        elif stripped.startswith('STUBS'):
            section = 'stubs'
        elif section == 'structural' and re.match(r'^G\d', stripped):
            gaps['structural'].append(stripped)
        elif section in ('naked', 'stubs'):
            m = _GAP_LABEL_RE.match(stripped)
            if m:
                key = 'naked_assertions' if section == 'naked' else 'stubs'
                gaps[key].append({'label': m.group(1), 'note': m.group(2)})

    return gaps


def load(amap_path: str | Path) -> dict:
    """Parse a .amap file.

    Returns:
        claims           — all parsed claim dicts
        priority_claims  — status=? then status=~, highest grounding priority first
        citations_block  — {label: [refs]} from canonical CITATIONS section if present
        gap_report       — {structural, naked_assertions, stubs}
    """
    text = Path(amap_path).read_text(encoding='utf-8')
    claims = parse_claims(text)
    return {
        'claims':          claims,
        'priority_claims': priority_claims(claims),
        'citations_block': parse_citations_block(text),
        'gap_report':      parse_gap_report(text),
    }
