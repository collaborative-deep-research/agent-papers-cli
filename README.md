# paper

A command-line tool for reading, skimming, and searching academic papers from the terminal. Inspired by [agent-browser](https://github.com/vercel-labs/agent-browser) — but for PDFs.

## Install

```bash
uv pip install -e .
```

Requires Python 3.10+.

## Commands

```bash
paper outline <ref>                    # Show heading tree
paper read <ref> [section]             # Read full paper or specific section
paper skim <ref> --lines N --level L   # Headings + first N sentences
paper search <ref> "query"             # Keyword search with context
paper info <ref>                       # Show metadata
paper goto <ref> <ref_id>              # Jump to a section, link, or citation
```

`<ref>` accepts: `2302.13971`, `arxiv.org/abs/2302.13971`, `arxiv.org/pdf/2302.13971`

Papers are downloaded once and cached in `~/.papers/`.

### Jump links

All output is annotated with `[ref=...]` markers that agents (or humans) can follow up on:

- `[ref=s3]` — section (jump to section 3)
- `[ref=e1]` — external link (show URL and context)
- `[ref=c5]` — citation (look up reference [5] in the bibliography)

Use `paper goto <ref> <ref_id>` to follow any marker. A summary footer shows the available ref ranges:

```
Refs: s1..s12 (sections) · e1..e8 (links) · c1..c24 (citations)
Use: paper goto 2302.13971 <ref>
```

Add `--no-refs` to any command to hide the annotations.

## Examples

### Browse a paper's structure

```bash
paper outline 2302.13971
```
```
╭──────────────────────────────────────────────────────╮
│  LLaMA: Open and Efficient Foundation Language Models │
│  arxiv.org/abs/2302.13971                             │
╰──────────────────────────────────────────────────────╯

Outline
├── Abstract [ref=s1]
├── Introduction [ref=s2]
├── Approach [ref=s3]
│   ├── Pre-training Data [ref=s4]
│   ├── Architecture [ref=s5]
│   ├── Optimizer [ref=s6]
│   └── Efficient implementation [ref=s7]
├── Main results [ref=s8]
...

Refs: s1..s12 (sections) · e1..e8 (links) · c1..c24 (citations)
Use: paper goto 2302.13971 <ref>
```

### Jump to a section, link, or citation

```bash
paper goto 2302.13971 s3     # read the "Approach" section
paper goto 2302.13971 e1     # show URL and context for the first external link
paper goto 2302.13971 c5     # look up citation [5] in the bibliography
```

### Read a specific section

```bash
paper read 2302.13971 "abstract"
```

### Skim headings with first N sentences

```bash
paper skim 2302.13971 --lines 2
paper skim 2302.13971 --lines 1 --level 1   # top-level headings only
```

### Search for keywords

```bash
paper search 2302.13971 "transformer"
```
```
  Match 1 in Architecture [ref=s5] (p.3)
   our network is based on the transformer architec-
   ture (Vaswani et al., 2017). We leverage various
```

### Hide ref annotations

```bash
paper outline 2302.13971 --no-refs
```

## Architecture

```
src/paper/
├── cli.py        # Click CLI — all commands defined here
├── fetcher.py    # Downloads PDFs from arxiv, manages cache
├── parser.py     # PDF → Document: text extraction, heading detection, sentence splitting
├── models.py     # Data models: Document, Section, Sentence, Span, Box, Metadata, Link
├── renderer.py   # Rich terminal output, ref registry, goto rendering
└── storage.py    # ~/.papers/ cache directory management
```

### How it works

1. **Fetch**: Downloads the PDF from arxiv and caches it in `~/.papers/<id>/`
2. **Parse**: Extracts text with [PyMuPDF](https://pymupdf.readthedocs.io/), detects headings via PDF outline or font-size heuristics, splits sentences with [PySBD](https://github.com/nipunsadvilkar/pySBD), extracts links and citations
3. **Display**: Renders structured output with [Rich](https://rich.readthedocs.io/), annotates with `[ref=...]` jump links

The parsed structure is cached as JSON so subsequent commands are instant.

### Data model

Simplified flat-layer approach inspired by [papermage](https://github.com/allenai/papermage):

- **Document** has a `raw_text` string, list of `Section`s, and list of `Link`s
- Each **Section** has a heading, level, content, and list of `Sentence`s
- Each **Link** has a kind (`external`/`internal`/`citation`), anchor text, URL, and page
- **Span** objects store character offsets into `raw_text`, enabling text-to-PDF coordinate mapping
- Everything serializes to JSON for caching

### PDF heading detection

Two strategies, tried in order:

1. **PDF outline** — if the PDF has a built-in table of contents, use it directly (most reliable)
2. **Font-size heuristic** — detect body text size (most common), treat larger/bold text as headings, merge section number fragments ("1" + "Introduction" → "1 Introduction"), filter false positives (author names, table data, captions)

## Development

### Run tests

```bash
uv pip install -e ".[dev]"
pytest
```

### Test papers

These papers cover different PDF structures and parsing paths:

| Paper | ID | Parsing path | Notes |
|-------|-----|---|-------|
| LLaMA (Touvron et al.) | `2302.13971` | Font-size heuristic | No built-in ToC, standard two-column arxiv format |
| Gradient ↔ Adapters (Torroba-Hennigen et al.) | `2502.13811` | PDF outline | 20 TOC entries, caught outline offset bug |
| Words Like Knives (Shen et al.) | `2505.21451` | Font-size heuristic | Tricky formatting: author names at heading size, multi-line headings, small-caps |
| Completion ≠ Collaboration (Shen et al.) | `2510.25744` | PDF outline | Proper hierarchy |
| DeepSeek-R1 | `2501.12948` | PDF outline | Very long paper (86 pages), stress test |

See `tests/README.md` for detailed notes on why each paper is included and known edge cases.

```bash
# Quick smoke test across formats
paper outline 2302.13971            # font-size heuristic path
paper outline 2502.13811            # PDF outline path
paper skim 2302.13971 --lines 1
paper search 2302.13971 "transformer"
paper goto 2302.13971 s2            # jump to section
paper goto 2502.13811 e1            # jump to external link
paper outline 2302.13971 --no-refs  # clean output without refs
```

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PAPER_DOWNLOAD_TIMEOUT` | `120` | Download timeout in seconds |

## Known limitations

- Heading detection is heuristic-based (font size + bold) — works well on standard arxiv but fragile on unusual templates
- PDFs with a built-in outline/ToC get better results (read directly when available)
- Section hierarchy (nesting) is approximate
- Citation detection: numeric citations (`[1]`, `[2, 3]`, `[1-5]`) are detected via regex; author-year citations (`(Kingma & Ba, 2015)`) are detected when hyperlinked in the PDF (via `LINK_NAMED` destinations, common in LaTeX). Non-hyperlinked author-year citations are not detected.
- When a TOC heading doesn't match any line on its page (e.g., TOC says "Proof of thm:foo" but PDF says "A.2. Proof of Thm. 1"), the section may include some extra content from the page header

## Future plans

- [GROBID](https://github.com/kermitt2/grobid) backend for ML-based section detection
- `paper annotate` command for highlighting text in PDFs
- Figure/table refs (`[ref=f...]`) — needs caption detection logic
- Named citation detection for non-hyperlinked author-year citations (hyperlinked ones already work via `LINK_NAMED`)
- Richer document model inspired by [papermage](https://github.com/allenai/papermage)
- Better handling of tables, figures, equations
