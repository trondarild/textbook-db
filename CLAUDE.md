# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Purpose

Build a database of index terms across a curated selection of neuroscience/psychiatry textbooks. Source PDFs are transformed to markdown, their indices are extracted, overlapping terms are deduplicated, and per-chapter reference lists are linked to each term. The result serves two goals:

1. Source and ground Memex wiki entries with validated references (Memex = the user's personal wiki, managed via the `/mmxentry` and `/mmx*` family of skills).
2. Provide high-quality, page-level citations without broad web searching.

## Running the Pipeline

Full rebuild — run stages in order:

```bash
python pdf_to_text.py          # PDF → texts/*.txt
python extract_index.py        # texts/*.txt → indices/*.json
python build_lookup.py         # indices/*.json → lookup.json
python fuzzy_match.py          # lookup.json → candidates.json
python text_to_md.py           # texts/*.txt → md/*.md  (PDF books)
python epub_to_md.py yudofsky2018  # epub → md/yudofsky2018.md
python extract_refs.py         # md/*.md → pages/ + chapters/ + references/ → enriched lookup.json
```

Single-book operations:
```bash
python pdf_to_text.py kandel2021
python extract_index.py --detect kandel2021   # preview auto-detected index start
python extract_index.py kandel2021
python text_to_md.py kandel2021
python extract_refs.py kandel2021 --no-link   # skip lookup enrichment
```

## Running Tests

```bash
python3 -m pytest tests/ -v
```

234 tests across 11 test files. To run a single module: `python3 -m pytest tests/test_chapter_detector.py -v`.

## Code Structure

```
src/
  index_parser.py      — parse_index, join_continuations, extract_pages, detect_index_start
  lookup_builder.py    — build_lookup, load_indices
  fuzzy_matcher.py     — find_*_pairs, find_all_pairs
  page_segmenter.py    — split text on \x0c; detect book page numbers
  header_stripper.py   — frequency-based running header removal
  heading_detector.py  — classify lines as H1/H2 headings
  md_writer.py         — write YAML front matter + <!-- p. N --> markers + headings
  page_mapper.py       — parse <!-- p. N --> / <!-- ch. N --> markers → pages/<key>.json
  chapter_detector.py  — locate reference headings as chapter boundaries → chapters/<key>.json
  reference_parser.py  — parse 6 citation formats → references/<key>.json
  link_references.py   — enrich lookup.json with chapter + ref data per term
plugins/               — per-book hooks loaded by text_to_md.py and extract_refs.py
  <key>.py             — hooks: post_segment, post_strip, post_annotate,
                         post_chapter_detect, post_page_map, post_ref_parse
toc/                   — jpdfbm-extracted TOC data (gazzaniga2014.json)
tests/                 — pytest unit tests; one file per src/ module
registry.json          — per-book metadata (local, not committed)
```

Top-level scripts are thin CLI wrappers; all logic lives in `src/`.

## Adding a New Book

### Copyright policy
Only **code, plugins, TOC metadata, and tests** are committed. All book-derived content
(`texts/`, `indices/`, `md/`, `pages/`, `chapters/`, `references/`, `lookup.json`,
`candidates.json`, `textbook_db.sqlite`) is gitignored and rebuilt locally from the source PDFs.
`toc/<key>.json` files (chapter titles + page numbers only) are safe to commit — structural
metadata is not copyrightable. Do not commit PDFs, extracted text, or any other reproduction
of book content.

### PDF book
1. Add entry to `registry.json` (see existing entries as template).
2. `python pdf_to_text.py <key>` — convert PDF.
3. `python extract_index.py --detect <key>` → confirm/set `index_start_line` and `subentry_strategy`.
4. `python extract_index.py <key>` — extract index.
5. `python text_to_md.py <key>` — generate md file; add `md_path` to registry.
6. Extract TOC via `echo "path.pdf" | jpdfbm` → `toc/<key>.json`; wire into plugin if needed.
7. `python extract_refs.py <key> --no-link` — verify chapter/ref detection; add plugin if needed.
8. `python build_lookup.py && python fuzzy_match.py && python extract_refs.py` — full rebuild.

### subentry_strategy values
- `"capitalize"` — uppercase column-0 = main entry; lowercase = subentry (Kandel, Gosseries, Baars).
- `"indent_only"` — all column-0 lines are main entries (Gazzaniga, Buzaki).

### registry.json optional fields
- `ref_heading_pattern` — regex for per-book reference section headings (default: `## References|Bibliography`)
- `md_path` — relative path to generated markdown file

### Plugin hooks
Plugins in `plugins/<key>.py` can define any subset of these functions:
- `post_segment(segments, meta)` — filter/patch segments before stripping
- `post_strip(segments, meta)` — additional header removal passes
- `post_annotate(segments, meta)` — filter false-positive headings
- `post_chapter_detect(chapters, meta)` — rebuild chapter list (e.g. from TOC JSON)
- `post_page_map(markers, meta)` — patch the page marker map
- `post_ref_parse(refs, meta)` — patch extracted references

## chapter_detector.py notes

- Uses reference section headings (`## References`, `## Suggested Reading`, etc.) as chapter boundaries.
- `_find_ref_end()` scans forward from a ref heading to find where the ref section ends: stops at H1 headings, non-ref `##` headings (no year and no author-initials pattern), or 3 consecutive long body-text lines.
- `_REF_LINE_RE` matches author-name patterns (`Smith AB,` or `Jones, F.`) to distinguish ref entries formatted as headings from real section headings. Requires initials after surname.
- `_YEAR_RE` matches years including suffixed forms (`2013a`, `1999b`) used in Yudofsky citations.

## Key Paths

- Source PDFs: `/Users/trond/books/Bøker/textbooks/cognitive science/`
- Gosseries text (pre-existing): `/Users/trond/Documents/consciousness-rhythms-and-tubes/texts/Gosseries2016-NeurologyOfConsciousness.txt`
