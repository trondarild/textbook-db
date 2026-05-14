"""Parse back-of-book index sections from plain-text book files."""

import re

PAGE_RE = re.compile(r"\b(\d{1,4}(?:[fbte])?(?:[–\-]\d{1,4}[fbte]?)?)\b")

SKIP_RE = re.compile(
    r"^\s*(Index|INDEX|Author Index|Name Index|Subject Index"
    r"|See also|see also|See|see)\s*$"
    r"|^\s*[A-Z]\s*$"
    r"|^\s*$"
)

ONLY_PAGES_RE = re.compile(r"^[\d,\s\-–fbte./]+$")

INDEX_HEADING_RE = re.compile(
    r"^(Index|INDEX|Subject Index|Author Index|Name Index)\s*$"
)
INDEX_ENTRY_RE = re.compile(r"^.{2,60},\s*\d{1,4}[fbte]?")


def extract_pages(text: str) -> list[str]:
    return [m.group(1) for m in PAGE_RE.finditer(text)]


def normalize_term(t: str) -> str:
    t = re.sub(r",?\s*(See also|see also|See|see)\b.*$", "", t)
    t = re.sub(r"[\s,;.:]+$", "", t)
    return t.strip()


def join_continuations(raw_lines: list[str]) -> list[str]:
    """Merge wrapped index lines into single logical lines.

    A line is merged into the previous when it:
    - consists only of page references, OR
    - starts with lowercase AND the previous line ended with a comma.
    """
    out: list[str] = []
    for raw in raw_lines:
        line = raw.rstrip("\n")
        stripped = line.strip()

        if not out:
            out.append(line)
            continue

        prev_stripped = out[-1].strip()

        if not stripped or SKIP_RE.match(stripped):
            out.append(line)
            continue

        only_pages = bool(ONLY_PAGES_RE.match(stripped))
        prev_ends_comma = prev_stripped.endswith(",")
        next_lower = stripped[0].islower()

        if only_pages or (prev_ends_comma and next_lower):
            out[-1] = out[-1].rstrip() + " " + stripped
        else:
            out.append(line)

    return out


def parse_index(lines: list[str], subentry_strategy: str = "capitalize") -> dict[str, list[str]]:
    """Parse index lines into {term: [pages]}.

    subentry_strategy:
      "capitalize"  – uppercase at indent-0 = main entry; lowercase = subentry.
                      For books where pdftotext stripped indentation but capitalisation
                      still distinguishes levels (Kandel, Gosseries, Baars).
      "indent_only" – every indent-0 line is a main entry regardless of case.
                      For all-lowercase indices or books with preserved indentation
                      (Gazzaniga, Buzaki).
    """
    entries: dict[str, list[str]] = {}
    current_parent = ""

    def add(term: str, pages: list[str]) -> None:
        key = normalize_term(term)
        if key and len(key) > 1:
            entries.setdefault(key, [])
            entries[key].extend(p for p in pages if p)

    for raw in join_continuations(lines):
        stripped = raw.strip()
        if not stripped or SKIP_RE.match(stripped):
            continue

        indent = len(raw) - len(raw.lstrip())
        pages = extract_pages(stripped)
        term_text = normalize_term(PAGE_RE.sub("", stripped).strip(" ,;:–-"))

        if not term_text:
            continue

        first = stripped[0]
        is_upper_start = first.isupper() or first.isdigit() or first in "αβγδεζ('\"["

        if indent > 0:
            if current_parent:
                add(f"{current_parent} > {term_text}", pages)
            else:
                add(term_text, pages)
        elif subentry_strategy == "indent_only":
            current_parent = term_text
            add(term_text, pages)
        elif is_upper_start:
            current_parent = term_text
            add(term_text, pages)
        else:
            if current_parent:
                add(f"{current_parent} > {term_text}", pages)
            else:
                add(term_text, pages)

    return entries


def detect_index_start(lines: list[str], preview: int = 10) -> int | None:
    """Search the last 35% of file lines for the index section start.

    Returns the 1-based line number of the first real entry (after the heading),
    or None if detection failed.
    """
    total = len(lines)
    search_from = int(total * 0.65)
    candidate_start = None

    for i, line in enumerate(lines[search_from:], search_from):
        if INDEX_HEADING_RE.match(line.strip()):
            for j in range(i + 1, min(i + 30, total)):
                if INDEX_ENTRY_RE.match(lines[j].strip()):
                    candidate_start = j + 1
                    break
            if candidate_start:
                break

    if candidate_start is None:
        for i, line in enumerate(lines[search_from:], search_from):
            if INDEX_ENTRY_RE.match(line.strip()):
                candidate_start = i + 1
                break

    return candidate_start
