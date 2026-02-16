# paper

A command-line tool for reading, skimming, and searching academic papers from the terminal. Inspired by [agent-browser](https://github.com/vercel-labs/agent-browser) — but for PDFs.

## Install

```bash
uv pip install -e .
```

Requires Python 3.10+.

## Usage

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

Or read the full paper:

```bash
paper read 2302.13971
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

### Paper metadata

```bash
paper info 2302.13971
```

## Input formats

All commands accept arxiv references in multiple formats:

- Arxiv ID: `2302.13971`
- Abstract URL: `arxiv.org/abs/2302.13971`
- PDF URL: `arxiv.org/pdf/2302.13971`

Papers are downloaded once and cached in `~/.papers/`.

## How it works

1. **Fetch**: Downloads the PDF from arxiv and caches it in `~/.papers/<id>/`
2. **Parse**: Extracts text with [PyMuPDF](https://pymupdf.readthedocs.io/), detects headings via font-size heuristics, splits sentences with [PySBD](https://github.com/nipunsadvilkar/pySBD)
3. **Display**: Renders structured output with [Rich](https://rich.readthedocs.io/)

The parsed structure is cached as JSON so subsequent commands are instant.

## Development

### Run tests

```bash
uv pip install -e ".[dev]"
pytest
```

### Test papers

These papers are useful for manual testing since they cover different PDF structures:

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

## Known limitations

- Heading detection uses font-size heuristics — works well on standard arxiv papers but may be fragile on unusual templates
- PDFs with a built-in outline/ToC get better results (the tool reads it directly when available)
- Section hierarchy (nesting) is approximate

## Future plans

- [GROBID](https://github.com/kermitt2/grobid) backend for ML-based section detection
- `paper annotate` command for highlighting text in PDFs
- Richer document model inspired by [papermage](https://github.com/allenai/papermage)
