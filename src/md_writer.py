"""
Assemble cleaned, annotated page segments into a markdown document.

Output format:
  ---
  title: Book Title
  author: Author Name
  year: 2024
  source_pdf: /path/to/book.pdf
  ---

  <!-- p. 1 -->
  ## Chapter Heading

  Body text paragraph...

  <!-- p. 2 -->
  Body continues...
"""

import re

_BLANK_RUN = re.compile(r'\n{3,}')


def _level_prefix(level):
    return '#' * level + ' '


def _render_segment(seg):
    """Return markdown string for a single page segment."""
    lines = seg['text'].split('\n')
    heading_indices = {idx for idx, _lvl, _txt in seg.get('headings', [])}
    heading_levels = {idx: lvl for idx, lvl, _txt in seg.get('headings', [])}

    parts = [f'<!-- p. {seg["book_page"]} -->']
    for i, line in enumerate(lines):
        stripped = line.strip()
        if i in heading_indices:
            parts.append(f'\n{_level_prefix(heading_levels[i])}{stripped}\n')
        else:
            # Escape leading '#' so PDF artifacts don't create accidental headings
            parts.append(re.sub(r'^(#+)', r'\\\1', line) if line.lstrip().startswith('#') else line)

    text = '\n'.join(parts)
    text = _BLANK_RUN.sub('\n\n', text)
    return text.strip()


def _front_matter(meta):
    """Return YAML front-matter block from a registry entry dict."""
    title = meta.get('title', '')
    author = meta.get('author', '')
    year = meta.get('year', '')
    source = meta.get('pdf') or meta.get('epub_path') or ''
    lines = [
        '---',
        f'title: {title}',
        f'author: {author}',
        f'year: {year}',
        f'source_pdf: {source}',
        '---',
    ]
    return '\n'.join(lines)


def write_md(segments, meta, out_path):
    """Write segments to out_path as a markdown file.

    segments must already have 'headings' key (from heading_detector.annotate_segments).
    meta is the registry entry dict for the book.
    """
    import pathlib
    pathlib.Path(out_path).parent.mkdir(parents=True, exist_ok=True)

    parts = [_front_matter(meta)]
    for seg in segments:
        if seg.get('book_page') is None:
            continue
        rendered = _render_segment(seg)
        if rendered:
            parts.append(rendered)

    content = '\n\n'.join(parts) + '\n'
    content = _BLANK_RUN.sub('\n\n', content)

    pathlib.Path(out_path).write_text(content, encoding='utf-8')
    return out_path
