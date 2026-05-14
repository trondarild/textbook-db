"""Enrich lookup.json with chapter and reference information.

For each term in lookup.json, uses the per-book chapters/<key>.json and
references/<key>.json to add:

  chapters   — {book_key: [chapter_title, ...]}
  references — {book_key: [{authors, year, title, venue, raw}, ...]}

A term is linked to a chapter if any of the term's book pages falls within
[chapter.start_page, chapter.end_page].  For epub books (no page numbers),
the linkage is skipped (chapter/references fields will be absent for that book).
"""

import json
import re
from pathlib import Path

_PAGE_NUM_RE = re.compile(r'^\d+')   # extract leading digits from "45b", "45f"
_RANGE_RE = re.compile(r'^(\d+)[–\-]')  # "10–11" → 10


def _to_int_pages(raw_pages: list[str]) -> list[int]:
    """Convert raw page strings to ints; skip entries with no leading digit."""
    result = []
    for p in raw_pages:
        p = p.strip()
        m = _RANGE_RE.match(p) or _PAGE_NUM_RE.match(p)
        if m:
            result.append(int(m.group(1) if _RANGE_RE.match(p) else m.group(0)))
    return result


def _find_chapters_for_pages(pages: list[int], chapters: list[dict]) -> list[str]:
    """Return titles of chapters whose page range overlaps with pages."""
    titles = []
    for ch in chapters:
        sp = ch.get('start_page')
        ep = ch.get('end_page')
        if sp is None or ep is None:
            continue
        if any(sp <= p <= ep for p in pages):
            t = ch['title'] or f"p. {sp}–{ep}"
            if t not in titles:
                titles.append(t)
    return titles


def link_all(
    lookup: dict,
    chapters_by_book: dict[str, list[dict]],
    refs_by_book: dict[str, dict],
) -> dict:
    """Return a new lookup dict enriched with 'chapters' and 'references' keys.

    Only books present in both chapters_by_book and refs_by_book are processed.
    """
    enriched = {}

    for term, entry in lookup.items():
        new_entry = dict(entry)
        new_entry.setdefault('chapters', {})
        new_entry.setdefault('references', {})

        for book_key, raw_pages in entry.get('pages', {}).items():
            if book_key not in chapters_by_book:
                continue
            chapters = chapters_by_book[book_key]
            refs = refs_by_book.get(book_key, {})

            int_pages = _to_int_pages(raw_pages)
            if not int_pages:
                continue

            chapter_titles = _find_chapters_for_pages(int_pages, chapters)
            if not chapter_titles:
                continue

            new_entry['chapters'][book_key] = chapter_titles

            # Collect references from matched chapters
            book_refs = []
            seen_raw = set()
            for title in chapter_titles:
                for ref in refs.get(title, []):
                    raw = ref.get('raw', '')
                    if raw and raw not in seen_raw:
                        seen_raw.add(raw)
                        book_refs.append(ref)
            if book_refs:
                new_entry['references'][book_key] = book_refs

        enriched[term] = new_entry

    return enriched


def save(lookup: dict, out_path: Path) -> None:
    """Write enriched lookup to out_path."""
    out_path.write_text(
        json.dumps(lookup, ensure_ascii=False, indent=2), encoding='utf-8'
    )
