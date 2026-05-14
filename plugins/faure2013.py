"""
Faure 2013 — Pediatric Neurogastroenterology. Springer handbook format.

Layout:
  Left-hand pages  (even book pages): bare book_page, then short author
                   "C. Faure et al." or "A. Author and B. Author", then body.
  Right-hand pages (odd book pages):  chapter_num (1–50), then chapter title,
                   then sometimes the book_page; book_page may be absent.
  Chapter openers: chapter title first (no leading bare number), then chapter num,
                   then author names.

Refs: Springer numbered format — "1. Author AB. Title. Journal. Year;vol:pages."
  Standard parser doesn't recognise lines starting with "N. " as entry boundaries.

post_segment       : fix book_page detection; interpolate where not detectable.
post_index_parse   : remove Springer copyright/DOI artifacts from index entries.
post_chapter_detect: map 50 TOC titles to detected chapters by page range.
post_ref_parse     : re-parse numbered refs from raw markdown.
"""

import json
import re
from pathlib import Path

_NUM_RE = re.compile(r"^\d{1,4}$")
_MAX_CHAPTER = 50
_MAX_PAGE = 540

_PROJECT_ROOT = Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# Page detection helpers
# ---------------------------------------------------------------------------

def _is_short_author(line: str) -> bool:
    """Left-hand running header: short line with initials and 'et al.' or 'and'."""
    return len(line) < 55 and "." in line and ("et al." in line or " and " in line)


def _extract_page(text: str) -> int | None:
    ne = [l.strip() for l in text.split("\n") if l.strip()]
    if not ne:
        return None

    first = ne[0]

    # Chapter opener or Part separator: title text as first line.
    if not _NUM_RE.match(first):
        for line in ne[1:6]:
            if _NUM_RE.match(line):
                pg = int(line)
                if _MAX_CHAPTER < pg <= _MAX_PAGE:
                    return pg
        return None

    pg1 = int(first)

    # Large number: unambiguously a book page.
    if pg1 > _MAX_CHAPTER:
        return pg1 if pg1 <= _MAX_PAGE else None

    # Small number (1–50): could be book page (early chapters) or chapter number.
    if len(ne) >= 2:
        second = ne[1]

        # Left-hand page: short author running header → first = book page.
        if _is_short_author(second):
            return pg1

        # Right-hand page: bare number on line 2 → first = chapter num, second = book page.
        if _NUM_RE.match(second):
            pg2 = int(second)
            return pg2 if pg2 <= _MAX_PAGE else None

        # Left-hand page: body text starts lowercase (sentence continuation).
        if second and second[0].islower():
            return pg1

        # Right-hand page: second line is chapter title (uppercase start).
        # Book page may appear a few lines later.
        for line in ne[2:7]:
            if _NUM_RE.match(line):
                pg = int(line)
                if pg <= _MAX_PAGE:
                    return pg
        return None

    return None


# ---------------------------------------------------------------------------
# Hooks
# ---------------------------------------------------------------------------

def post_segment(segments, meta):
    # Pass 1: detect what we can; right-hand pages often have no visible page number.
    pass1 = [{**s, "book_page": _extract_page(s["text"])} for s in segments]

    # Pass 2: fill None pages by interpolating from the previous known page + 1.
    result = []
    last_page = None
    for s in pass1:
        if s["book_page"] is not None:
            last_page = s["book_page"]
            result.append(s)
        elif last_page is not None:
            last_page += 1
            result.append({**s, "book_page": last_page})
        else:
            result.append(s)  # front matter; keep as None
    return result


def post_index_parse(entries: dict, meta: dict) -> dict:
    """Remove Springer copyright/DOI artifacts picked up as index entries."""
    def _is_noise(key: str) -> bool:
        return "© Springer" in key or "DOI" in key or "Faure et al" in key

    return {k: v for k, v in entries.items() if not _is_noise(k)}


def post_chapter_detect(chapters, meta):
    """Map detected chapters to TOC titles by page range.

    50 TOC entries; chapter count may differ from detected. Use last TOC entry
    whose start_page falls within the detected chapter's page range.
    Drops chapters that precede the first TOC entry (false positives from
    figure captions / table headings in the early pages).
    """
    toc_path = _PROJECT_ROOT / "toc" / "faure2013.json"
    if not toc_path.exists():
        return chapters

    toc = json.loads(toc_path.read_text(encoding="utf-8"))

    def strip_num(title: str) -> str:
        m = re.match(r"^\d+\s+(.+)", title)
        return m.group(1) if m else title

    toc_clean = [{"title": strip_num(e["title"]), "start_page": e["start_page"]} for e in toc]

    result = []
    for ch in chapters:
        sp = ch.get("start_page")
        ep = ch.get("end_page", 999999)
        if sp is None:
            result.append(ch)
            continue
        in_range = [t for t in toc_clean if sp <= t["start_page"] <= ep]
        if in_range:
            title = in_range[-1]["title"]
        else:
            before = [t for t in toc_clean if t["start_page"] <= sp]
            if not before:
                continue  # before first TOC entry → false positive, drop
            title = before[-1]["title"]
        result.append({**ch, "title": title})
    return result


def post_ref_parse(refs: dict, meta: dict) -> dict:
    """Re-parse Springer numbered references.

    Standard parser doesn't split at '1. Author AB.' boundaries.
    Re-read markdown and re-parse each chapter's ref section.
    """
    from src.reference_parser import _parse_entry

    key = Path(__file__).stem
    md_rel = meta.get("md_path")
    if not md_rel:
        return refs

    md_path = Path(md_rel) if Path(md_rel).is_absolute() else _PROJECT_ROOT / md_rel
    chapters_path = _PROJECT_ROOT / "chapters" / f"{key}.json"

    if not md_path.exists() or not chapters_path.exists():
        return refs

    chapters = json.loads(chapters_path.read_text())
    md_lines = md_path.read_text(encoding="utf-8").splitlines()

    _SKIP_RE = re.compile(r"^(?:<!-- |#|\d{1,4}$)")

    result = {}
    for ch in chapters:
        title = ch["title"]
        start = ch.get("ref_start_line", 0)
        end = ch.get("ref_end_line", start)

        lines = [l for l in md_lines[start:end] if not _SKIP_RE.match(l) and l.strip()]
        text = "\n".join(lines)

        # Split at numbered ref boundaries: each ref starts with "N. " at line start.
        blocks = re.split(r"\n(?=\d+\. )", text)
        entries = []
        for block in blocks:
            cleaned = re.sub(r"^\d+\.\s+", "", block.replace("\n", " ").strip())
            if len(cleaned) < 15:
                continue
            entry = _parse_entry(cleaned)
            if entry.get("year"):
                entries.append(entry)

        result[title] = entries

    return result
