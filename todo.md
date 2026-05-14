# Todo


## New books

- [x] Add Yudofsky & Hales 2018 — Neuropsychiatry (epub)
  - epub_to_text.py: extracts full text + index directly from HTML (level1/2/3 CSS classes)
  - 1294 main terms, 7080 total entries; texts/Yudofsky2018.txt (1.8M)
  - DB now: 6 books, 10950 terms, 17411 candidates
  Note: CHM book (Synopsis of Psychiatry 2007) also present at same path if needed later —
        convert via archmage/7-zip → html2text then same pipeline

## Text enrichment (texts → readable/searchable markdown)
- [x] src/page_segmenter.py — split text on \x0c; detect printed Arabic page number from
      first/last 3 non-empty lines per PDF page; output [{pdf_page, book_page, text}]
      (skip roman-numeral front matter; build_page_map helper included)
- [ ] src/header_stripper.py — remove running headers/footers via frequency analysis:
      lines appearing on >40% of pages in a window are header/footer candidates; strip them
- [ ] src/heading_detector.py — detect chapter/section titles and return their markdown level;
      heuristics: short (<60 chars), title-case or all-caps, blank lines before/after,
      no terminal punctuation
- [ ] src/md_writer.py — assemble cleaned page segments into md/<book_key>.md:
      YAML front matter (title, author, year, source_pdf), <!-- p. N --> page markers,
      ## headings, preserved paragraph breaks
- [ ] text_to_md.py — CLI script: registry → texts/*.txt → md/*.md using the four modules above
- [ ] add md_path field to each registry.json entry after generation
- [ ] add unit tests for page_segmenter, header_stripper, heading_detector, md_writer

## Reference extraction (terms → chapters → bibliography)
- [ ] src/page_mapper.py — build {book_page: pdf_page} from page_segmenter output;
      store as pages/<key>.json (shared with text enrichment pipeline)
- [ ] src/chapter_detector.py — locate "References" headings as chapter boundaries;
      extract chapter title from opening lines of each span;
      output chapters/<key>.json [{title, start_book_page, end_book_page, ref_line}]
      (heading-agnostic: works for Buzaki "Cycles", Gosseries edited chapters, etc.;
      add registry field chapter_heading_pattern per book if needed)
- [ ] src/reference_parser.py — parse each chapter's reference section into structured
      entries; format: Author(s) (Year) Title. Venue Vol:pages
      output references/<key>.json {chapter_title: [{authors, year, title, venue, raw}]}
- [ ] src/link_references.py — for each term in lookup.json, use page_map + chapter
      boundaries to identify which chapters the term appears in; enrich lookup.json with
      {chapters: {book: [titles]}, references: {book: [ref_entries]}}
- [ ] extract_refs.py — CLI script: registry → pages/ + chapters/ + references/ using
      the four modules above
- [ ] add unit tests for page_mapper, chapter_detector, reference_parser, link_references

## Argmap integration

### .amap format (full spec in ~/code/argument-notation/manual-notation.md)
Each claim line: `↓ ?/*/~/✓ claim_label (E/T/R/!) "Claim text" [Author Year; Author Year]`
- Status: `?` stub, `~` developed, `*` cited, `✓` finished prose written
- Type: `(T)` theoretical, `(E)` empirical, `(R)` review — source type of the claim, `(!)` naked/original claim,
- Inline citations already present; textbook-db supplements/validates them
- Gap report section is outcome of status-update process;  lists uncited claims explicitly
- Full APA 7th bibliography block at end of file

### Tasks
- [x] src/amap_parser.py — parse .amap lines into structured dicts:
      {label, strength, claim_type, text, citations: [str]}; extract `(?)` claims as
      priority targets (speculative — need grounding); `(!)` = original contributions/
      syntheses, not necessarily needing refs; also parse gap-report section
- [x] src/claim_matcher.py — given claim text, retrieve candidate db terms:
      token overlap × n_books scoring; match_claims batch version included
- [ ] src/coverage_reporter.py — for a set of claims, report which have no db match
      (coverage gap); output: {covered: [...], uncovered: [...], partial: [...]}
- [ ] enrich_argmap.py — CLI: reads .amap file → for each `(?)` claim (then `*?`)
      runs claim_matcher → appends textbook references to existing citation list;
      outputs annotated .amap and a JSON side-car with full reference details per claim
      (format compatible with the existing citation block structure in .amap files)
- [x] unit tests for amap_parser (test_amap_parser.py — 17 tests), claim_matcher (test_claim_matcher.py — 11 tests)
- [ ] add unit tests for coverage_reporter
- [ ] decide embedding vs lexical-only: start with pure lexical (noun-phrase extraction
      + fuzzy_matcher); if recall is poor on (!) claims, add sentence-transformers
      or Claude embeddings as a second-pass retrieval stage

## User interface
- [x] txdb.py — composable CLI: lookup TERM [--expand], search QUERY, claim TEXT, books, stats
      All subcommands support --json for piping; src/query_engine.py is the DB query API
- [x] ~/.claude/commands/textbook-db.md — /textbook-db skill; composes with /mmxentry and /argmap
      Takes term or claim as $ARGUMENTS; formats output as reference list or .amap citation block

## Database
- [x] src/schema.py — CREATE TABLE statements and DB initialisation for textbook_db.sqlite
      Tables: books, terms, occurrences, candidates, chapters, references, term_chapters
- [x] load_db.py — CLI script: reads registry + lookup.json + candidates.json
      → populates textbook_db.sqlite; re-runnable (deletes + recreates)
- [x] unit tests for schema creation (test_schema.py — 7 tests)


## Done
- [x] find paths to initial source textbooks: Kandel 2021; Gosseries 2016;/Users/trond/books/Bøker/textbooks/cognitive science/ 
- [x] use tree command on /Users/trond/books/Bøker/textbooks/cognitive science/ to get list of books; propose three additional core texts to process;
  - Gazzaniga 2014: cognitive science/Cognitive neuroscience/Gazzaniga 2014 - Cognitive Neuroscience - The Biology of the Mind.pdf
  - Buzaki 2011: cognitive science/Buzaki 2011 - Rhythms of the brain.pdf
  - Baars 2013: cognitive science/Cognitive neuroscience/Baars 2013 - Fundamentals of cognitive neuroscience.pdf
- [x] transform Kandel and the three other books into text (Gosseries already exists);
  - texts/ in project root: Kandel2021 (6.0M), Gazzaniga2014 (2.9M), Buzaki2011 (1.3M), Baars2013 (1.1M)
  - Gosseries TXT: /Users/trond/Documents/consciousness-rhythms-and-tubes/texts/Gosseries2016-NeurologyOfConsciousness.txt
- [x] extract indeces with lookups from selected texts;
  - Script: extract_index.py → indices/<book>.json ({term: [pages]})
  - Counts: Kandel 4060 main terms, Gazzaniga 3925, Gosseries 569, Buzaki 1347, Baars 209; 10110 total
- [x] refactor: create registry.json with per-book metadata (path, index_start_line, subentry_strategy)
- [x] refactor: add auto-detect helper for index start line (search last 30% of text file)
- [x] refactor: split pipeline into composable scripts (pdf_to_text.py, extract_index.py, build_lookup.py, fuzzy_match.py)
- [x] build lookup table of unique terms
  - Script: build_lookup.py → lookup.json ({term: {books, pages}})
  - 9798 unique terms; 278 in 2+ books (1 in all 5, 4 in 4, 23 in 3, 250 in 2)
  - Sorted by cross-book frequency; subentries excluded by default (--with-subentries flag available)
- [x] build list of candidates for overlapping terms that are not exactly the same;
  - Script: fuzzy_match.py → candidates.json, sorted by cross-book coverage then score
  - 15702 pairs: abbreviation, case, containment, token_set (>=80) strategies
  - Strategies: abbreviation expansion, case normalisation, substring containment, token-set ratio (rapidfuzz)
