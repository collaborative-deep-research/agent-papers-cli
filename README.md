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
```

`<ref>` accepts: `2302.13971`, `arxiv.org/abs/2302.13971`, `arxiv.org/pdf/2302.13971`

Papers are downloaded once and cached in `~/.papers/`.

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
├── Abstract
├── Introduction
├── Approach
│   ├── Pre-training Data
│   ├── Architecture
│   ├── Optimizer
│   └── Efficient implementation
├── Main results
...
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
  Match 1 in Architecture (p.3)
   our network is based on the transformer architec-
   ture (Vaswani et al., 2017). We leverage various
```

## Architecture

```
src/paper/
├── cli.py        # Click CLI — all commands defined here
├── fetcher.py    # Downloads PDFs from arxiv, manages cache
├── parser.py     # PDF → Document: text extraction, heading detection, sentence splitting
├── models.py     # Data models: Document, Section, Sentence, Span, Box, Metadata
├── renderer.py   # Rich terminal output for all commands
└── storage.py    # ~/.papers/ cache directory management
```

### How it works

1. **Fetch**: Downloads the PDF from arxiv and caches it in `~/.papers/<id>/`
2. **Parse**: Extracts text with [PyMuPDF](https://pymupdf.readthedocs.io/), detects headings via font-size heuristics, splits sentences with [PySBD](https://github.com/nipunsadvilkar/pySBD)
3. **Display**: Renders structured output with [Rich](https://rich.readthedocs.io/)

The parsed structure is cached as JSON so subsequent commands are instant.

### Data model

Simplified flat-layer approach inspired by [papermage](https://github.com/allenai/papermage):

- **Document** has a `raw_text` string + list of `Section`s
- Each **Section** has a heading, level, content, and list of `Sentence`s
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

These papers cover different PDF structures:

| Paper | ID | Notes |
|-------|-----|-------|
| LLaMA (Touvron et al.) | `2302.13971` | No built-in ToC, standard two-column arxiv format |
| Completion ≠ Collaboration (Shen et al.) | `2510.25744` | Has built-in PDF outline with proper hierarchy |
| Attention Is All You Need (Vaswani et al.) | `1706.03762` | Classic paper, older arxiv format |
| DeepSeek-R1 | `2501.12948` | Very long paper (86 pages), stress test for parsing |

```bash
# Quick smoke test across formats
paper outline 2302.13971        # font-size heuristic path
paper outline 2510.25744        # PDF outline path
paper skim 2302.13971 --lines 1
paper search 2302.13971 "transformer"
paper read 2510.25744 "introduction"
```

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PAPER_DOWNLOAD_TIMEOUT` | `120` | Download timeout in seconds |

## Known limitations

- Heading detection is heuristic-based (font size + bold) — works well on standard arxiv but fragile on unusual templates
- PDFs with a built-in outline/ToC get better results (read directly when available)
- Section hierarchy (nesting) is approximate
- `paper annotate` command is not yet implemented

## Future plans

- [GROBID](https://github.com/kermitt2/grobid) backend for ML-based section detection
- `paper annotate` command for highlighting text in PDFs
- Richer document model inspired by [papermage](https://github.com/allenai/papermage)
- Better handling of tables, figures, equations
