#!/usr/bin/env python3
"""Extract chapter boundaries, reference sections, and enrich lookup.json.

Pipeline per book:
  1. page_mapper   — parse md file → pages/<key>.json
  2. chapter_detector — detect chapters via ref headings → chapters/<key>.json
  3. reference_parser — parse each chapter's refs → references/<key>.json

After all books are processed:
  4. link_references — enrich lookup.json with chapter + ref data

Plugin hooks (plugins/<key>.py):
  post_page_map(markers, meta)         → adjusted markers dict
  post_chapter_detect(chapters, meta)  → adjusted chapter list
  post_ref_parse(refs, meta)           → adjusted refs dict  ({title: [entries]})

Registry fields:
  ref_heading_pattern — regex string for matching ref section headings
                        (default: "^## (?:References|Bibliography)\\s*$")

Usage:
  python extract_refs.py                  # all books
  python extract_refs.py gosseries2016    # single book
  python extract_refs.py --no-link        # skip lookup enrichment
"""

import importlib.util
import json
import re
import sys
from pathlib import Path

from src.page_mapper import build as build_page_map
from src.chapter_detector import detect as detect_chapters, save as save_chapters
from src.reference_parser import extract_all, save as save_refs
from src.link_references import link_all, save as save_lookup

BASE_DIR = Path(__file__).parent
REGISTRY_PATH = BASE_DIR / 'registry.json'
LOOKUP_PATH = BASE_DIR / 'lookup.json'
PAGES_DIR = BASE_DIR / 'pages'
CHAPTERS_DIR = BASE_DIR / 'chapters'
REFS_DIR = BASE_DIR / 'references'
PLUGINS_DIR = BASE_DIR / 'plugins'


def _load_plugin(key: str):
    path = PLUGINS_DIR / f'{key}.py'
    if not path.exists():
        return None
    spec = importlib.util.spec_from_file_location(key, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _apply_hook(plugin, hook: str, data, meta: dict):
    if plugin is None:
        return data
    fn = getattr(plugin, hook, None)
    if fn is None:
        return data
    return fn(data, meta)


def _ref_heading_re(meta: dict):
    pattern = meta.get('ref_heading_pattern')
    if pattern:
        return re.compile(pattern)
    return None   # chapter_detector uses its default


def run_book(key: str, meta: dict, force: bool = False) -> tuple[list, dict]:
    """Run all extraction stages for one book.

    Returns (chapters, refs) for use in link_references.
    """
    md_rel = meta.get('md_path', '')
    if not md_rel:
        print(f'  {key}: no md_path in registry, skipping')
        return [], {}

    md_path = Path(md_rel) if Path(md_rel).is_absolute() else BASE_DIR / md_rel
    if not md_path.exists():
        print(f'  {key}: md file not found at {md_path}, skipping')
        return [], {}

    plugin = _load_plugin(key)
    md_text = md_path.read_text(encoding='utf-8')

    # Stage 1: page markers
    markers = build_page_map(key, meta, BASE_DIR, PAGES_DIR)
    markers = _apply_hook(plugin, 'post_page_map', markers, meta)

    # Stage 2: chapter detection
    chapters = detect_chapters(md_text, _ref_heading_re(meta))
    chapters = _apply_hook(plugin, 'post_chapter_detect', chapters, meta)
    save_chapters(chapters, key, CHAPTERS_DIR)

    # Stage 3: reference parsing
    refs = extract_all(md_text, chapters)
    refs = _apply_hook(plugin, 'post_ref_parse', refs, meta)
    save_refs(refs, key, REFS_DIR)

    total_refs = sum(len(v) for v in refs.values())
    print(
        f'  {key}: {len(chapters)} chapters, {total_refs} references'
    )
    return chapters, refs


def _usage():
    print(__doc__)
    sys.exit(1)


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    no_link = '--no-link' in sys.argv

    registry = json.loads(REGISTRY_PATH.read_text())

    keys = args if args else list(registry.keys())
    invalid = [k for k in keys if k not in registry]
    if invalid:
        print(f"Unknown keys: {', '.join(invalid)}")
        _usage()

    chapters_by_book: dict[str, list] = {}
    refs_by_book: dict[str, dict] = {}

    for key in keys:
        meta = registry[key]
        print(f'{key}:')
        chs, refs = run_book(key, meta)
        if chs:
            chapters_by_book[key] = chs
        if refs:
            refs_by_book[key] = refs

    if not no_link and chapters_by_book:
        print('\nenriching lookup.json …')
        lookup = json.loads(LOOKUP_PATH.read_text())
        enriched = link_all(lookup, chapters_by_book, refs_by_book)
        save_lookup(enriched, LOOKUP_PATH)
        linked = sum(
            1 for e in enriched.values() if e.get('chapters')
        )
        print(f'linked {linked}/{len(enriched)} terms to at least one chapter')
