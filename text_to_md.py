#!/usr/bin/env python3
"""
Convert texts/*.txt to md/<key>.md for one or all books in registry.json.

Usage:
    python3 text_to_md.py                 # convert all books
    python3 text_to_md.py buzaki2011      # convert one book
    python3 text_to_md.py --list          # list books and their text/md status

## Customisation

### Registry parameters (tuning)
Add config dicts to the registry entry; they are passed as kwargs to pipeline stages:

    "header_stripper": {"global_thresh": 0.30, "window_size": 20, "window_thresh": 0.25}

Supported keys: "header_stripper" (kwargs for strip_headers).

### Plugin hooks (logic overrides)
Create plugins/<key>.py.  Any defined hook is called at the corresponding stage.
Missing hooks are silently skipped — books with no quirks need no plugin file.

Hook signatures (all optional):

    def post_segment(segments, meta):   -> segments
        # After segmentation, BEFORE body-page filtering (book_page is not None).
        # Receives ALL segments including those with book_page=None.
        # Use to assign missing page numbers, drop front-matter, fix split pages.

    def post_strip(segments, meta):     -> segments
        # After header/footer stripping.

    def post_annotate(segments, meta):  -> segments
        # After heading detection.
        # Use to add, remove, or re-level specific headings.
"""

import argparse
import importlib.util
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))

from src.page_segmenter import segment
from src.header_stripper import strip_headers
from src.heading_detector import annotate_segments
from src.md_writer import write_md

REGISTRY = pathlib.Path(__file__).parent / 'registry.json'
MD_DIR = pathlib.Path(__file__).parent / 'md'
PLUGINS_DIR = pathlib.Path(__file__).parent / 'plugins'


# ---------------------------------------------------------------------------
# Plugin loader
# ---------------------------------------------------------------------------

def load_plugin(key):
    """Return the plugin module for *key*, or None if no plugin file exists."""
    path = PLUGINS_DIR / f'{key}.py'
    if not path.exists():
        return None
    spec = importlib.util.spec_from_file_location(key, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def apply_hook(plugin, hook_name, segments, meta):
    """Call plugin.<hook_name>(segments, meta) if defined; otherwise return segments."""
    if plugin is None:
        return segments
    fn = getattr(plugin, hook_name, None)
    if fn is None:
        return segments
    return fn(segments, meta)


# ---------------------------------------------------------------------------
# Conversion
# ---------------------------------------------------------------------------

def load_registry():
    with open(REGISTRY) as f:
        return json.load(f)


def convert_book(key, meta, force=False):
    text_path = pathlib.Path(meta.get('text', ''))
    if not text_path.exists():
        print(f'  [{key}] SKIP — text not found: {text_path}')
        return False

    out_path = MD_DIR / f'{key}.md'
    if out_path.exists() and not force:
        print(f'  [{key}] SKIP — already exists (use --force to overwrite)')
        return False

    plugin = load_plugin(key)

    print(f'  [{key}] segmenting...', end=' ', flush=True)
    text = text_path.read_text(encoding='utf-8', errors='replace')
    segs = segment(text)
    # post_segment receives ALL segments so plugins can assign missing page numbers
    segs = apply_hook(plugin, 'post_segment', segs, meta)
    body_segs = [s for s in segs if s['book_page'] is not None]
    print(f'{len(body_segs)} pages', end=' ', flush=True)

    print('stripping headers...', end=' ', flush=True)
    hs_opts = meta.get('header_stripper', {})
    cleaned, bad = strip_headers(body_segs, **hs_opts)
    cleaned = apply_hook(plugin, 'post_strip', cleaned, meta)
    print(f'({len(bad)} bad lines)', end=' ', flush=True)

    print('detecting headings...', end=' ', flush=True)
    annotated = annotate_segments(cleaned)
    annotated = apply_hook(plugin, 'post_annotate', annotated, meta)

    print('writing...', end=' ', flush=True)
    write_md(annotated, meta, out_path)
    size = out_path.stat().st_size
    print(f'done ({size // 1024}K → {out_path})')
    return True


def list_books(registry):
    print(f'{"key":<20} {"text":>8} {"md":>8}')
    print('-' * 40)
    for key, meta in registry.items():
        text_path = pathlib.Path(meta.get('text', ''))
        md_path = MD_DIR / f'{key}.md'
        text_size = f'{text_path.stat().st_size // 1024}K' if text_path.exists() else '-'
        md_size = f'{md_path.stat().st_size // 1024}K' if md_path.exists() else '-'
        print(f'{key:<20} {text_size:>8} {md_size:>8}')


def main():
    parser = argparse.ArgumentParser(description='Convert book texts to markdown')
    parser.add_argument('key', nargs='?', help='Book key (omit for all books)')
    parser.add_argument('--force', action='store_true', help='Overwrite existing .md files')
    parser.add_argument('--list', action='store_true', help='List books and status')
    args = parser.parse_args()

    registry = load_registry()

    if args.list:
        list_books(registry)
        return

    if args.key:
        if args.key not in registry:
            print(f'Error: key "{args.key}" not in registry.json', file=sys.stderr)
            sys.exit(1)
        books = {args.key: registry[args.key]}
    else:
        books = registry

    for key, meta in books.items():
        convert_book(key, meta, force=args.force)


if __name__ == '__main__':
    main()
