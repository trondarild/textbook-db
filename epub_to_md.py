#!/usr/bin/env python3
"""Convert a textbook epub → md/<key>.md.

Unlike the PDF pipeline (text_to_md.py), epub documents have explicit HTML
structure (h2/h3 headings, p paragraphs) — no form-feeds, no page numbers.

Chapter markers use document sequence: <!-- ch. N -->
Heading mapping:
  h2 class='Chap-no'    → label for <!-- ch. N --> marker only (not output inline)
  h2 class='chap-title' → # Title  (H1)
  h2 class=''           → # Title  (H1, e.g. Preface)
  h3                    → ## Heading

Usage:
  python epub_to_md.py <registry_key> [--force]
  python epub_to_md.py yudofsky2018
"""

import json
import re
import sys
from pathlib import Path

import ebooklib
from bs4 import BeautifulSoup
from ebooklib import epub

BASE_DIR = Path(__file__).parent
REGISTRY_PATH = BASE_DIR / "registry.json"
MD_DIR = BASE_DIR / "md"

_SKIP_STEMS = {
    'nav', '01_Cover', '02_Halftitle', '03_Title', '04_Copyright',
    '05_Tableofcontent', '51_Index', '51_Plate',
}

_BLANK_RUN = re.compile(r'\n{3,}')


def _is_skip(name: str) -> bool:
    stem = Path(name).stem
    return stem in _SKIP_STEMS or stem.lower() == 'nav'


def _front_matter(meta: dict) -> str:
    lines = [
        '---',
        f'title: {meta.get("title", "")}',
        f'author: {meta.get("author", "")}',
        f'year: {meta.get("year", "")}',
        f'source_pdf: {meta.get("epub_path", "")}',
        '---',
    ]
    return '\n'.join(lines)


def _convert_doc(soup: BeautifulSoup, ch_label: str) -> str:
    """Return markdown for one epub document."""
    lines = [f'<!-- ch. {ch_label} -->']

    body = soup.find('body') or soup
    for el in body.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'p']):
        tag = el.name
        cls = el.get('class') or []
        text = el.get_text(' ', strip=True)
        if not text:
            continue

        if tag == 'p':
            if any(c.startswith('chap-auth') for c in cls):
                continue
            lines.append(text)

        elif tag == 'h2':
            if 'Chap-no' in cls:
                continue  # label already in <!-- ch. N -->
            lines.append(f'\n# {text}\n')

        elif tag == 'h3':
            lines.append(f'\n## {text}\n')

        elif tag == 'h4':
            lines.append(f'\n### {text}\n')

        elif tag == 'h5':
            lines.append(f'\n#### {text}\n')

    return '\n'.join(lines)


def convert(key: str, epub_path: Path, force: bool = False) -> None:
    out_path = MD_DIR / f'{key}.md'
    if out_path.exists() and not force:
        print(f'already exists: {out_path} (use --force)')
        return

    print(f'reading {epub_path.name} …')
    book = epub.read_epub(str(epub_path))
    docs = list(book.get_items_of_type(ebooklib.ITEM_DOCUMENT))

    registry = json.loads(REGISTRY_PATH.read_text())
    meta = registry[key]

    sections = []
    seq = 0
    for doc in docs:
        name = doc.get_name()
        if _is_skip(name):
            continue
        seq += 1
        soup = BeautifulSoup(doc.get_content(), 'html.parser')
        sections.append(_convert_doc(soup, str(seq)))

    MD_DIR.mkdir(exist_ok=True)
    content = _front_matter(meta) + '\n\n' + '\n\n'.join(sections) + '\n'
    content = _BLANK_RUN.sub('\n\n', content)
    out_path.write_text(content, encoding='utf-8')

    size_kb = out_path.stat().st_size // 1024
    print(f'md    → {out_path}  ({size_kb}K, {seq} sections)')


def _usage() -> None:
    print('usage: python epub_to_md.py <registry_key> [--force]')
    print('       python epub_to_md.py yudofsky2018')
    sys.exit(1)


if __name__ == '__main__':
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
    epub_path = entry.get('epub_path') or entry.get('pdf', '')
    if not epub_path:
        print(f"no epub_path in registry for '{key}'")
        sys.exit(1)

    convert(key, Path(epub_path), force=force)
