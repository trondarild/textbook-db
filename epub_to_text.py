#!/usr/bin/env python3
"""Convert an epub to plain text and extract its index.

Unlike PDF books, epub structure is hierarchical HTML — the index section
has explicit level1/level2/level3 CSS classes, so we extract it directly
rather than through the pdftotext heuristics in extract_index.py.

Outputs:
  texts/<key>.txt        — full text, chapters separated by \\x0c
  indices/<key>.json     — {term: [pages]} extracted from index HTML
"""

import json
import re
import sys
from pathlib import Path

import ebooklib
from bs4 import BeautifulSoup
from ebooklib import epub

BASE_DIR = Path(__file__).parent
TEXTS_DIR = BASE_DIR / "texts"
INDICES_DIR = BASE_DIR / "indices"
REGISTRY_PATH = BASE_DIR / "registry.json"

# Matches trailing page numbers:  ", 33 , 195–196 , 440"
_PAGES_TAIL_RE = re.compile(r',\s*([\d][,\s\d–\-]*)$')
# Matches individual page numbers or ranges
_PAGE_TOKEN_RE = re.compile(r'\d+(?:[–\-]\d+)?')

INDEX_DOC_NAMES = {'51_Index', 'Index', 'index'}


def _is_index_doc(name: str) -> bool:
    stem = Path(name).stem
    return any(idx in stem for idx in INDEX_DOC_NAMES)


def _parse_entry(text: str) -> tuple[str, list[str]]:
    """Split 'Term text, 123 , 456–789' into (term, [pages])."""
    text = text.strip()
    m = _PAGES_TAIL_RE.search(text)
    if m:
        term = text[:m.start()].strip().rstrip(',').strip()
        pages = _PAGE_TOKEN_RE.findall(m.group(1))
    else:
        term = text
        pages = []
    return term, pages


def extract_index(soup: BeautifulSoup) -> dict[str, list[str]]:
    """Parse level1/level2/level3 index entries into {term: [pages]}."""
    index: dict[str, list[str]] = {}
    current_l1 = ''
    current_l2 = ''

    for el in soup.find_all(class_=re.compile(r'^level[123]$')):
        cls = el['class'][0]
        raw = el.get_text(' ', strip=True)

        # Skip cross-references and empty entries
        if not raw or re.search(r'\bSee\b', raw):
            continue

        term, pages = _parse_entry(raw)
        if not term:
            continue

        if cls == 'level1':
            current_l1 = term
            current_l2 = ''
            if pages:
                index.setdefault(term, []).extend(pages)
            else:
                index.setdefault(term, [])
        elif cls == 'level2':
            current_l2 = term
            full = f"{current_l1} > {term}" if current_l1 else term
            if pages:
                index.setdefault(full, []).extend(pages)
            else:
                index.setdefault(full, [])
        elif cls == 'level3':
            parts = [p for p in [current_l1, current_l2, term] if p]
            full = ' > '.join(parts)
            if pages:
                index.setdefault(full, []).extend(pages)

    return index


def convert(key: str, epub_path: str | Path, force: bool = False) -> None:
    epub_path = Path(epub_path)
    text_path = TEXTS_DIR / f"{key.title().replace('_','')}.txt"
    index_path = INDICES_DIR / f"{key}.json"

    if text_path.exists() and index_path.exists() and not force:
        print(f"already exists: {text_path.name}, {index_path.name} (use --force)")
        return

    print(f"reading {epub_path.name} …")
    book = epub.read_epub(str(epub_path))
    docs = list(book.get_items_of_type(ebooklib.ITEM_DOCUMENT))

    chapters = []
    index_soup = None

    for doc in docs:
        name = doc.get_name()
        soup = BeautifulSoup(doc.get_content(), 'html.parser')
        if _is_index_doc(name):
            index_soup = soup
        else:
            chapters.append(soup.get_text('\n'))

    # Full text
    TEXTS_DIR.mkdir(exist_ok=True)
    full_text = '\x0c'.join(chapters)
    text_path.write_text(full_text, encoding='utf-8')
    print(f"text  → {text_path}  ({len(full_text):,} chars, {len(chapters)} chapters)")

    # Index
    if index_soup is None:
        print("warning: no index document found")
        return
    INDICES_DIR.mkdir(exist_ok=True)
    index = extract_index(index_soup)
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding='utf-8')
    main_terms = sum(1 for k in index if ' > ' not in k)
    print(f"index → {index_path}  ({main_terms} main terms, {len(index)} total entries)")


def _usage() -> None:
    print("usage: python epub_to_text.py <registry_key> [--force]")
    print("       python epub_to_text.py yudofsky2018")
    sys.exit(1)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    force = '--force' in sys.argv

    if not args:
        _usage()

    key = args[0]
    registry = json.loads(REGISTRY_PATH.read_text())
    if key not in registry:
        print(f"key '{key}' not in registry.json")
        sys.exit(1)

    entry = registry[key]
    epub_path = entry.get('pdf') or entry.get('epub_path', '')
    if not epub_path:
        print(f"no epub_path in registry for '{key}'")
        sys.exit(1)

    convert(key, epub_path, force=force)
