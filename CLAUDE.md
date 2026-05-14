# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Purpose

Build a database of index terms across a curated selection of textbooks. Source PDFs are transformed to text, their indices are extracted with page lookups, and overlapping terms are deduplicated into a unified lookup table. The result serves two goals:

1. Source and ground Memex wiki entries with validated references (Memex = the user's personal wiki, managed via the `/mmxentry` and `/mmx*` family of skills).
2. Provide high-quality, page-level citations without broad web searching.

## Running the Pipeline

Each stage is an independent script; run them in order for a full rebuild:

```bash
python pdf_to_text.py          # PDF → texts/*.txt
python extract_index.py        # texts/*.txt → indices/*.json
python build_lookup.py         # indices/*.json → lookup.json
python fuzzy_match.py          # lookup.json → candidates.json
```

Single-book operations:
```bash
python pdf_to_text.py kandel2021
python extract_index.py --detect kandel2021   # preview auto-detected index start
python extract_index.py kandel2021
```

## Running Tests

```bash
python -m pytest tests/ -v
```

50 unit tests across `tests/test_index_parser.py`, `tests/test_lookup_builder.py`, `tests/test_fuzzy_matcher.py`.

## Code Structure

```
src/
  index_parser.py    — parse_index, join_continuations, extract_pages, detect_index_start
  lookup_builder.py  — build_lookup, load_indices
  fuzzy_matcher.py   — find_abbreviation_pairs, find_case_pairs, find_containment_pairs,
                       find_token_set_pairs, find_all_pairs
tests/               — pytest unit tests for each src/ module
pdf_to_text.py       — CLI: convert PDFs via pdftotext
extract_index.py     — CLI: extract book indices
build_lookup.py      — CLI: merge indices into lookup.json
fuzzy_match.py       — CLI: find near-duplicate terms → candidates.json
registry.json        — per-book metadata: pdf path, text path, index_start_line, subentry_strategy
```

Top-level scripts are thin CLI wrappers; all logic lives in `src/`.

## Adding a New Book

1. Add an entry to `registry.json` (copy an existing entry as template).
2. `python pdf_to_text.py <key>` — convert the PDF.
3. `python extract_index.py --detect <key>` — preview the auto-detected index start.
4. Confirm or override `index_start_line` and `subentry_strategy` in `registry.json`.
5. `python extract_index.py <key>` — extract the index.
6. `python build_lookup.py && python fuzzy_match.py` — rebuild lookup and candidates.

### subentry_strategy values
- `"capitalize"` — uppercase at column-0 = main entry; lowercase = subentry (Kandel, Gosseries, Baars).
- `"indent_only"` — all column-0 lines are main entries regardless of case (Gazzaniga, Buzaki).

Use `"indent_only"` when the book's index uses all-lowercase terms, or when pdftotext preserved indentation.

## Key Paths

- Source PDFs: `/Users/trond/books/Bøker/textbooks/cognitive science/`
- Gosseries text (pre-existing): `/Users/trond/Documents/consciousness-rhythms-and-tubes/texts/Gosseries2016-NeurologyOfConsciousness.txt`
- Database choice (Kuzu vs SQL) is still open — see `todo.md`.
