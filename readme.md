# textbook-db

Database of index terms across a curated selection of textbooks. By storing overlapping index terms along with page-level lookups, a validated citation resource is built — used to source and ground knowledge-base entries and claims with high-quality references, without broad web searching.

## Books in corpus

| Key | Book | Terms |
|-----|------|-------|
| `kandel2021` | Kandel — Principles of Neural Science, 6th ed. (2021) | 4060 |
| `gazzaniga2014` | Gazzaniga — Cognitive Neuroscience (2014) | 3925 |
| `yudofsky2018` | Yudofsky & Hales — Textbook of Neuropsychiatry (2018) | 1294 |
| `buzaki2011` | Buzaki — Rhythms of the Brain (2011) | 1347 |
| `gosseries2016` | Gosseries — The Neurology of Consciousness, 2nd ed. (2016) | 569 |
| `baars2013` | Baars — Fundamentals of Cognitive Neuroscience (2013) | 209 |

**Total:** ~11k unique terms, ~17k fuzzy-match candidate pairs.

---

## Querying

### Terminal CLI

```bash
# Exact lookup with fuzzy expansion via candidates table
python3 txdb.py lookup "Hippocampus" --expand

# Case-insensitive lookup
python3 txdb.py lookup "hippocampus" --expand

# Fuzzy search when the exact term is unknown
python3 txdb.py search "psychosis"

# Match a claim sentence to relevant terms (token overlap × n_books scoring)
python3 txdb.py claim "theta oscillations coordinate memory consolidation during sleep"

# List all books with term counts
python3 txdb.py books

# DB statistics
python3 txdb.py stats

# JSON output for piping
python3 txdb.py lookup "Hippocampus" --expand --json | jq '.'
```

### Direct SQLite

```bash
sqlite3 textbook_db.sqlite "
  SELECT t.term, GROUP_CONCAT(o.book_key, ', '), COUNT(DISTINCT o.book_key) n
  FROM terms t JOIN occurrences o ON t.id = o.term_id
  WHERE t.term = 'Hippocampus'
  GROUP BY t.term;"
```

---

## Pipeline

### Full rebuild

```bash
python3 build_lookup.py        # indices/*.json → lookup.json
python3 fuzzy_match.py         # lookup.json → candidates.json
python3 load_db.py             # lookup + candidates → textbook_db.sqlite
```

### Adding a PDF book

```bash
# 1. Add entry to registry.json (copy an existing entry as template)
# 2. Convert PDF
python3 pdf_to_text.py <key>
# 3. Preview auto-detected index start
python3 extract_index.py --detect <key>
# 4. Confirm or adjust index_start_line in registry.json, then extract
python3 extract_index.py <key>
# 5. Rebuild
python3 build_lookup.py && python3 fuzzy_match.py && python3 load_db.py
```

### Adding an epub book

```bash
# 1. Add entry to registry.json with epub_path field (instead of pdf)
# 2. Convert — extracts full text and index directly from epub HTML structure
python3 epub_to_text.py <key>
# 3. Rebuild
python3 build_lookup.py && python3 fuzzy_match.py && python3 load_db.py
```

`subentry_strategy` values in `registry.json`:

| Value | When to use |
|-------|-------------|
| `capitalize` | Uppercase at column-0 = main entry; lowercase = subentry (Kandel, Gosseries, Baars) |
| `indent_only` | All column-0 lines are main entries regardless of case (Gazzaniga, Buzaki) |

---

## Setup

```bash
pip install rapidfuzz ebooklib beautifulsoup4 pytest
```

Requires `pdftotext` (poppler) for PDF conversion:

```bash
brew install poppler          # macOS
apt install poppler-utils     # Debian/Ubuntu
```

After cloning, update the file paths in `registry.json` to point to your local copies of the source PDFs/epubs, then run the full rebuild pipeline above.

---

## Tests

```bash
python3 -m pytest tests/ -v
```

103 tests across index parsing, lookup building, fuzzy matching, DB schema, page segmentation, argument-map parsing, and claim matching.

---

## Code structure

```
src/
  index_parser.py     — parse back-of-book indices from plain text
  lookup_builder.py   — merge per-book indices into unified lookup
  fuzzy_matcher.py    — find near-duplicate terms (abbreviation, case, containment, token_set)
  page_segmenter.py   — split pdftotext output on \x0c; detect book page numbers
  schema.py           — SQLite CREATE TABLE statements; init_db / drop_all
  query_engine.py     — DB query API: lookup, expand, search, books, stats
  amap_parser.py      — parse argument-map files; extract priority claims by status
  claim_matcher.py    — match claim text to DB terms (token overlap × n_books)

pdf_to_text.py        — CLI: PDF → texts/*.txt via pdftotext
epub_to_text.py       — CLI: epub → texts/*.txt + indices/*.json (direct HTML extraction)
extract_index.py      — CLI: texts/*.txt → indices/*.json
build_lookup.py       — CLI: indices/*.json → lookup.json
fuzzy_match.py        — CLI: lookup.json → candidates.json
load_db.py            — CLI: lookup + candidates → textbook_db.sqlite
txdb.py               — CLI: query interface (lookup / search / claim / books / stats)

registry.json         — per-book metadata: paths, index_start_line, subentry_strategy
textbook_db.sqlite    — the database (rebuilt by load_db.py; not committed)
lookup.json           — merged lookup table (rebuilt; not committed)
candidates.json       — fuzzy-match pairs (rebuilt; not committed)
```
