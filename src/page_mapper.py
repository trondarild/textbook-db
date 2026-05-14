"""Parse page/chapter markers from a markdown file.

Extracts <!-- p. N --> and <!-- ch. N --> markers to build a
{marker_value: line_idx} map.  Saved as pages/<key>.json and consumed by
chapter_detector to determine which chapter a given page belongs to.
"""

import json
import re
from pathlib import Path

_PAGE_RE = re.compile(r'^<!-- p\. (\d+) -->')
_CH_RE = re.compile(r'^<!-- ch\. (\w+) -->')


def parse_markers(md_text: str) -> dict[str, int]:
    """Return {marker_value: line_idx} for all page/chapter markers.

    Keys are strings: page numbers ("45") or chapter labels ("3").
    """
    result: dict[str, int] = {}
    for i, line in enumerate(md_text.splitlines()):
        m = _PAGE_RE.match(line) or _CH_RE.match(line)
        if m and m.group(1) not in result:
            result[m.group(1)] = i
    return result


def build(key: str, meta: dict, base_dir: Path, pages_dir: Path) -> dict[str, int]:
    """Parse the book's md_path, save markers to pages/<key>.json.

    Returns the markers dict (may be empty if md_path is missing).
    """
    md_rel = meta.get('md_path', '')
    if not md_rel:
        return {}
    md_path = Path(md_rel) if Path(md_rel).is_absolute() else base_dir / md_rel
    if not md_path.exists():
        return {}
    markers = parse_markers(md_path.read_text(encoding='utf-8'))
    pages_dir.mkdir(parents=True, exist_ok=True)
    (pages_dir / f'{key}.json').write_text(
        json.dumps(markers, ensure_ascii=False, indent=2), encoding='utf-8'
    )
    return markers
