# Conceptual Usage Example

## Scenario: grounding a Memex entry on *working memory*

---

### Step 1 — Find the term and all its book coverage

```bash
sqlite3 textbook_db.sqlite "
  SELECT t.term, o.book_key, o.pages
  FROM terms t JOIN occurrences o ON t.id = o.term_id
  WHERE t.term = 'working memory';"
```
```
working memory | gazzaniga2014 | ["389"]
```

Sparse. Step 2 consolidates via the fuzzy candidates table.

---

### Step 2 — Expand to all equivalent/variant terms

```bash
sqlite3 textbook_db.sqlite "
  SELECT t2.term, o.book_key, o.pages
  FROM candidates c
  JOIN terms t1 ON c.term1_id = t1.id
  JOIN terms t2 ON c.term2_id = t2.id
  JOIN occurrences o ON o.term_id = t2.id
  WHERE t1.term = 'working memory'
    AND c.match_type IN ('case','abbreviation','containment')
    AND c.score >= 0.6
  ORDER BY o.book_key, t2.term;"
```

This surfaces: `Working Memory` (Buzaki pp. 245, 339), `verbal working memory`,
`spatial working memory`, `visuospatial working memory` — spreading coverage across
**3 books** that the bare term missed.

---

### Step 3 — Find the chapters those pages fall in *(after reference extraction)*

```bash
sqlite3 textbook_db.sqlite "
  SELECT DISTINCT ch.book_key, ch.title, ch.start_book_page, ch.end_book_page
  FROM term_chapters tc
  JOIN terms t ON tc.term_id = t.id
  JOIN chapters ch ON tc.chapter_id = ch.id
  WHERE t.term IN (
    SELECT t2.term FROM candidates c
    JOIN terms t1 ON c.term1_id = t1.id
    JOIN terms t2 ON c.term2_id = t2.id
    WHERE t1.term = 'working memory' AND c.score >= 0.6
    UNION SELECT 'working memory'
  )
  ORDER BY ch.book_key, ch.start_book_page;"
```
```
buzaki2011    | Coupling of Systems by Oscillations | 334 | 356
gazzaniga2014 | Chapter 10: Memory                  | 380 | 420
kandel2021    | Prefrontal Cortex, Hippocampus...   | 940 | 965
```

---

### Step 4 — Pull the reference list for those chapters

```bash
sqlite3 -json textbook_db.sqlite "
  SELECT r.authors, r.year, r.title, r.venue
  FROM references r
  JOIN chapters ch ON r.chapter_id = ch.id
  JOIN term_chapters tc ON tc.chapter_id = ch.id
  JOIN terms t ON tc.term_id = t.id
  WHERE t.term = 'working memory'
  ORDER BY r.year DESC
  LIMIT 10;" | jq '.[] | "\(.year) \(.authors) — \(.title)"'
```
```
"2020 Lundqvist M et al. — Theta and gamma power increases..."
"2013 Goldman-Rakic PS — Cellular basis of working memory"
"2010 Baddeley A — Working memory"
...
```

---

### Step 5 — Cross-book term coverage report *(for deciding which sources to cite)*

```bash
sqlite3 textbook_db.sqlite "
  SELECT t.term,
         GROUP_CONCAT(o.book_key, ', ') AS books,
         COUNT(DISTINCT o.book_key) AS n_books
  FROM terms t JOIN occurrences o ON t.id = o.term_id
  WHERE t.term IN (
    'working memory','long-term potentiation','hippocampus',
    'prefrontal cortex','theta oscillation'
  )
  GROUP BY t.term
  ORDER BY n_books DESC;"
```
```
hippocampus            | buzaki2011, gazzaniga2014, kandel2021 | 3
long-term potentiation | buzaki2011, kandel2021                | 2
prefrontal cortex      | gazzaniga2014, kandel2021             | 2
working memory         | gazzaniga2014                         | 1
theta oscillation      | buzaki2011                            | 1
```

---

### The full Memex workflow in one command *(terminal alias)*

```bash
alias mmx-refs='python3 -c "
import sqlite3, json, sys
term = sys.argv[1]
db = sqlite3.connect(\"textbook_db.sqlite\")
# expand variants, fetch chapters, print references
" --'

mmx-refs "working memory"
```

Output fed directly into `/mmxentry working memory` to pre-populate references.

---

## Key insight

The bare term `working memory` appears in only 1 book, but after fuzzy expansion it
covers 3, and the chapter→reference chain produces a curated reading list rather than
a web search. That is the core value proposition: validated, page-level citations from
authoritative textbooks, grounding Memex entries without broad web searching.
