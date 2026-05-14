# textbook-db

Build a searchable database of index terms from your own textbook collection. Each book contributes a term→pages index; overlapping terms are merged and fuzzy-matched across books, producing a unified lookup table backed by SQLite.

Use cases: grounding knowledge-base entries with validated page-level citations, finding which books cover a given concept, matching free-text claims to relevant source material.

---

## How it works

1. **Convert** — PDFs or epubs are converted to plain text
2. **Extract** — the back-of-book index is parsed into `{term: [pages]}` per book
3. **Merge** — indices are merged into a unified lookup table; cross-book coverage is tracked
4. **Match** — near-duplicate terms are identified (abbreviations, case variants, substrings, token-set similarity)
5. **Load** — everything goes into SQLite for querying

---

## Setup

```bash
pip install rapidfuzz ebooklib beautifulsoup4 pytest
```

For PDF conversion, install `pdftotext` (poppler):

```bash
brew install poppler          # macOS
apt install poppler-utils     # Debian/Ubuntu
```

---

## Adding books

After cloning, copy the example registry and fill in your paths:

```bash
cp registry.example.json registry.json
# edit registry.json with your book paths
```

`registry.json` is gitignored — your local paths stay local.

### PDF book

```bash
# 1. Add an entry to registry.json (copy an existing entry as template)
# 2. Convert PDF to text
python3 pdf_to_text.py <key>
# 3. Preview auto-detected index start line
python3 extract_index.py --detect <key>
# 4. Confirm or adjust index_start_line in registry.json, then extract
python3 extract_index.py <key>
# 5. Rebuild lookup, candidates, and database
python3 build_lookup.py && python3 fuzzy_match.py && python3 load_db.py
```

### epub book

```bash
# 1. Add an entry to registry.json with epub_path field (instead of pdf)
# 2. Convert — extracts text and index directly from epub HTML structure
python3 epub_to_text.py <key>
# 3. Rebuild
python3 build_lookup.py && python3 fuzzy_match.py && python3 load_db.py
```

### registry.json entry format

```json
{
  "mybook2024": {
    "title": "Book Title",
    "author": "Author Name",
    "year": 2024,
    "pdf": "/path/to/book.pdf",
    "text": "texts/MyBook2024.txt",
    "index_start_line": 12345,
    "subentry_strategy": "capitalize"
  }
}
```

`subentry_strategy` values:

| Value | When to use |
|-------|-------------|
| `capitalize` | Uppercase at column-0 = main entry; lowercase = subentry |
| `indent_only` | All column-0 lines are main entries regardless of case |

Use `python3 extract_index.py --detect <key>` to find `index_start_line` automatically.

---

## Querying

### Shell commands

Add `bin/` to your PATH once:

```bash
export PATH="$PATH:/path/to/textbook-db/bin"   # add to ~/.zshrc or ~/.bashrc
```

Then use the short commands from anywhere:

```bash
tl "Hippocampus"                                    # lookup + fuzzy expansion
ts "psychosis"                                      # fuzzy search across all terms
tc "oscillations coordinate memory during sleep"    # match a claim to terms
txdb books                                          # list books with term counts
txdb stats                                          # DB statistics
txdb lookup "Hippocampus" --expand --json | jq '.'  # JSON output for piping
```

| Command | Expands to |
|---------|-----------|
| `tl TERM` | `txdb lookup TERM --expand` |
| `ts QUERY` | `txdb search QUERY` |
| `tc TEXT` | `txdb claim TEXT` |
| `txdb …` | full CLI with all subcommands and flags |

### Direct SQLite

```bash
# Term coverage across books
sqlite3 textbook_db.sqlite "
  SELECT t.term, GROUP_CONCAT(o.book_key, ', '), COUNT(DISTINCT o.book_key) n
  FROM terms t JOIN occurrences o ON t.id = o.term_id
  WHERE t.term = 'Hippocampus'
  GROUP BY t.term;"

# Find fuzzy variants of a term
sqlite3 textbook_db.sqlite "
  SELECT t2.term, c.match_type, c.score
  FROM candidates c
  JOIN terms t1 ON t1.id = CASE WHEN c.term1_id = (SELECT id FROM terms WHERE term='Memory')
                               THEN c.term1_id ELSE c.term2_id END
  JOIN terms t2 ON t2.id = CASE WHEN c.term1_id = t1.id THEN c.term2_id ELSE c.term1_id END
  WHERE t1.term = 'Memory' ORDER BY c.score DESC LIMIT 20;"
```

---

## Tests

```bash
python3 -m pytest tests/ -v
```

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
  amap_parser.py      — parse argument-map (.amap) files; extract priority claims by status
  claim_matcher.py    — match claim text to DB terms (token overlap × n_books)

pdf_to_text.py        — CLI: PDF → texts/*.txt via pdftotext
epub_to_text.py       — CLI: epub → texts/*.txt + indices/*.json
extract_index.py      — CLI: texts/*.txt → indices/*.json
build_lookup.py       — CLI: indices/*.json → lookup.json
fuzzy_match.py        — CLI: lookup.json → candidates.json
load_db.py            — CLI: lookup + candidates → textbook_db.sqlite
txdb.py               — CLI: query interface (lookup / search / claim / books / stats)

registry.json         — per-book metadata: paths, index_start_line, subentry_strategy
```

Generated files (`texts/`, `indices/`, `lookup.json`, `candidates.json`, `textbook_db.sqlite`) are not committed — they are built locally from your own book collection.
