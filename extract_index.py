#!/usr/bin/env python3
"""Extract back-of-book indices from textbook text files.

Usage:
  python extract_index.py                  # extract all books in registry
  python extract_index.py kandel2021       # extract one book by key
  python extract_index.py --detect         # show auto-detected index start lines

Output: indices/<book_key>.json  — {term: [page_numbers_as_strings]}
"""

import importlib
import importlib.util
import json
import sys
from pathlib import Path

from src.index_parser import detect_index_start, parse_index

REGISTRY = Path("registry.json")
PROJECT_ROOT = Path(__file__).parent


def _load_plugin(key: str):
    plugin_path = PROJECT_ROOT / "plugins" / f"{key}.py"
    if not plugin_path.exists():
        return None
    spec = importlib.util.spec_from_file_location(f"plugins.{key}", plugin_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def resolve_text_path(entry: dict) -> Path:
    p = Path(entry["text"])
    return p if p.is_absolute() else PROJECT_ROOT / p


def run_extract(key: str, entry: dict) -> None:
    text_path = resolve_text_path(entry)
    if not text_path.exists():
        print(f"  [{key}] text file not found: {text_path} — run pdf_to_text.py first")
        return

    with open(text_path, encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    start = entry.get("index_start_line")
    if not start:
        print(f"  [{key}] no index_start_line — auto-detecting...")
        start = detect_index_start(lines)
        if not start:
            print(f"  [{key}] detection failed — set index_start_line in registry.json")
            return

    strategy = entry.get("subentry_strategy", "capitalize")
    entries = parse_index(lines[start - 1:], strategy)

    plugin = _load_plugin(key)
    if plugin and hasattr(plugin, "post_index_parse"):
        meta = {"key": key, "entry": entry}
        entries = plugin.post_index_parse(entries, meta)

    out_dir = PROJECT_ROOT / "indices"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"{key}.json"
    out_path.write_text(json.dumps(entries, indent=2, ensure_ascii=False))

    main_count = sum(1 for k in entries if ">" not in k)
    print(f"  [{key}] {len(entries)} terms ({main_count} main) → {out_path.name}")


def run_detect(key: str, entry: dict) -> None:
    text_path = resolve_text_path(entry)
    if not text_path.exists():
        print(f"  [{key}] text file not found")
        return
    print(f"\n[{key}] detecting in {text_path.name}:")
    with open(text_path, encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    start = detect_index_start(lines)
    if start:
        print(f"  line {start} — first 10 entries:")
        for ln in lines[start - 1: start + 9]:
            print(f"    {ln.rstrip()}")
    else:
        print("  not found — set index_start_line manually in registry.json")


def main() -> None:
    args = sys.argv[1:]
    detect_mode = "--detect" in args
    keys = [a for a in args if not a.startswith("--")]

    registry = json.loads(REGISTRY.read_text())
    targets = {k: v for k, v in registry.items() if not keys or k in keys}

    if not targets:
        print(f"No matching keys: {keys}")
        sys.exit(1)

    for key, entry in targets.items():
        if detect_mode:
            run_detect(key, entry)
        else:
            run_extract(key, entry)


if __name__ == "__main__":
    main()
