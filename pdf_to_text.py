#!/usr/bin/env python3
"""Convert PDFs to text files using pdftotext (poppler).

Usage:
  python pdf_to_text.py                  # convert all books in registry
  python pdf_to_text.py kandel2021       # convert one book by key
  python pdf_to_text.py --force          # re-convert even if text exists

Writes output paths back to registry.json if they were auto-generated.
"""

import json
import subprocess
import sys
from pathlib import Path

REGISTRY = Path("registry.json")
PROJECT_ROOT = Path(__file__).parent


def text_path_for(key: str, pdf: Path) -> Path:
    return PROJECT_ROOT / "texts" / f"{pdf.stem.replace(' ', '_')}.txt"


def convert(key: str, entry: dict, force: bool = False) -> bool:
    pdf = Path(entry["pdf"])
    if not pdf.exists():
        print(f"  [{key}] PDF not found: {pdf}")
        return False

    out = Path(entry.get("text", "")) if entry.get("text") else text_path_for(key, pdf)
    if not out.is_absolute():
        out = PROJECT_ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)

    if out.exists() and not force:
        print(f"  [{key}] already exists: {out.name} — skip (use --force to redo)")
        return True

    print(f"  [{key}] converting {pdf.name} → {out.name} ...", end=" ", flush=True)
    result = subprocess.run(["pdftotext", str(pdf), str(out)], capture_output=True)
    if result.returncode != 0:
        print(f"FAILED\n{result.stderr.decode()}")
        return False
    print(f"done ({out.stat().st_size // 1024} KB)")
    return True


def main() -> None:
    args = sys.argv[1:]
    force = "--force" in args
    keys = [a for a in args if not a.startswith("--")]

    registry = json.loads(REGISTRY.read_text())
    targets = {k: v for k, v in registry.items() if not keys or k in keys}

    if not targets:
        print(f"No matching keys: {keys}")
        sys.exit(1)

    for key, entry in targets.items():
        convert(key, entry, force)


if __name__ == "__main__":
    main()
