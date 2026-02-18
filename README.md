# paper & search

CLI tools for reading academic papers and searching the web, academic literature, and biomedical databases from the terminal.

- **`paper`** — read, skim, and search PDFs. Inspired by [agent-browser](https://github.com/vercel-labs/agent-browser) — but for PDFs.
- **`search`** — search Google, Google Scholar, Semantic Scholar, PubMed, and extract webpage content. Based on the search APIs from [dr-tulu](https://github.com/rlresearch/dr-tulu).

## Install

```bash
uv pip install -e .
```

Requires Python 3.10+.

## `paper` commands

```bash
paper outline <ref>                    # Show heading tree
paper read <ref> [section]             # Read full paper or specific section
paper skim <ref> --lines N --level L   # Headings + first N sentences
paper search <ref> "query"             # Keyword search with context
paper info <ref>                       # Show metadata
paper goto <ref> <ref_id>              # Jump to a section, link, or citation

# Highlights
paper highlight search <ref> "query"   # Search PDF for text (with coordinates)
paper highlight add <ref> "query"      # Find text and persist a highlight
paper highlight list <ref>             # List stored highlights
paper highlight remove <ref> <id>      # Remove a highlight by ID
```

`<ref>` accepts: `2302.13971`, `arxiv.org/abs/2302.13971`, `arxiv.org/pdf/2302.13971`, or a **local PDF path** like `./paper.pdf`

Arxiv papers are downloaded once and cached in `~/.papers/`. Local PDFs are read directly from disk.

## `search` commands

```bash
# Environment / API keys
search env                             # Show API key status
search env set KEY value               # Save a key to ~/.papers/.env

# Google (requires SERPER_API_KEY)
search google web "query"              # Web search
search google scholar "query"          # Google Scholar search

# Semantic Scholar (S2_API_KEY optional, recommended for rate limits)
search semanticscholar papers "query"  # Paper search
  [--year 2023-2025] [--min-citations 10] [--venue ACL] [--sort citationCount:desc] [--limit N]
search semanticscholar snippets "query"  # Text snippet search
  [--year 2024] [--paper-ids id1,id2]
search semanticscholar citations <id>  # Papers citing this one
search semanticscholar references <id> # Papers this one references
search semanticscholar details <id>    # Full paper metadata

# PubMed (no key needed)
search pubmed "query" [--limit N] [--offset N]

# Browse (requires JINA_API_KEY for jina backend)
search browse <url> [--backend jina|serper] [--timeout 30]
```

### API keys

Set API keys persistently with `search env set`:

```bash
search env set SERPER_API_KEY sk-...   # required for google, browse --backend serper
search env set S2_API_KEY ...          # optional, higher Semantic Scholar rate limits
search env set JINA_API_KEY ...        # required for browse --backend jina
```

Keys are saved to `~/.papers/.env` and loaded automatically. Shell environment variables take precedence. Run `search env` to check what's configured.

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

### Highlight text in a paper

```bash
# Search for text (shows matches with page numbers and coordinates)
paper highlight search 2501.12948 "reinforcement learning"

# Add a highlight (single match is saved directly)
paper highlight add 2501.12948 "reinforcement learning" --color green --note "key concept"

# Multiple matches? Shows a numbered list — use --pick to select
paper highlight add 2501.12948 "model" --pick 3

# Or use --interactive for a prompt, --range to paginate
paper highlight add 2501.12948 "model" --interactive
paper highlight add 2501.12948 "model" --range 21:40

# Output app-compatible JSON (ScaledPosition format, 0-1 normalized)
paper highlight add 2501.12948 "reinforcement learning" --return-json

# List and manage highlights
paper highlight list 2501.12948
paper highlight remove 2501.12948 1
```

Highlights are stored in `~/.papers/<id>/highlights.json` and optionally annotated onto `paper_annotated.pdf`.

## Architecture

```
src/paper/                         # paper CLI
├── cli.py         # Click CLI — all commands defined here
├── fetcher.py     # Downloads PDFs from arxiv, manages cache
├── highlighter.py # PDF text search, coordinate conversion, highlight CRUD, PDF annotation
├── models.py      # Data models: Document, Section, Sentence, Span, Box, Metadata, Link, Highlight
├── parser.py      # PDF → Document: text extraction, heading detection, sentence splitting
├── renderer.py    # Rich terminal output, ref registry, goto rendering
└── storage.py     # ~/.papers/ cache directory management

src/search/                        # search CLI
├── cli.py        # Click CLI — all commands and subgroups
├── config.py     # API key loading (dotenv), persistent storage, env status
├── models.py     # Data models: SearchResult, SnippetResult, CitationResult, BrowseResult
├── renderer.py   # Rich terminal output with reference IDs and suggestive prompts
└── backends/
    ├── google.py           # Serper API (web + scholar)
    ├── semanticscholar.py  # S2 API (papers, snippets, citations, references, details)
    ├── pubmed.py           # NCBI E-utilities (esearch + efetch)
    └── browse.py           # Webpage content extraction (Jina Reader, Serper scrape)
```

### How it works

1. **Fetch**: Downloads the PDF from arxiv (and caches in `~/.papers/<id>/`) or reads a local PDF directly
2. **Parse**: Extracts text with [PyMuPDF](https://pymupdf.readthedocs.io/), detects headings via PDF outline or font-size heuristics, splits sentences with [PySBD](https://github.com/nipunsadvilkar/pySBD), extracts links and citations
3. **Display**: Renders structured output with [Rich](https://rich.readthedocs.io/), annotates with `[ref=...]` jump links

The parsed structure is cached as JSON so subsequent commands are instant.

### Data model

Simplified flat-layer approach inspired by [papermage](https://github.com/allenai/papermage):

- **Document** has a `raw_text` string, list of `Section`s, and list of `Link`s
- Each **Section** has a heading, level, content, and list of `Sentence`s
- Each **Link** has a kind (`external`/`internal`/`citation`), anchor text, URL, and page
- **Highlight** stores persisted highlights with page, bounding rects (absolute PDF coords), color, and note
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
paper highlight search 2501.12948 "reinforcement learning"  # highlight search
```

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PAPER_DOWNLOAD_TIMEOUT` | `120` | Download timeout in seconds |
| `SERPER_API_KEY` | — | Google search and scraping via Serper.dev |
| `S2_API_KEY` | — | Semantic Scholar API (optional, increases rate limits) |
| `JINA_API_KEY` | — | Jina Reader for webpage content extraction |

Search API keys can be set via shell env, `.env` in the working directory, or persistently via `search env set`.

## Agent Skills

This repo includes Claude Code skills for agent-driven research workflows. See [SKILLS.md](SKILLS.md) for details.

| Skill | Command | Description |
|-------|---------|-------------|
| Research Coordinator | `/research-coordinator` | Analyzes the request and dispatches to the right workflow |
| Deep Research | `/deep-research` | Broad-to-deep investigation of a topic |
| Literature Review | `/literature-review` | Systematic survey of academic literature |
| Fact Check | `/fact-check` | Verify claims against web and academic sources |

## Known limitations

- Heading detection is heuristic-based (font size + bold) — works well on standard arxiv but fragile on unusual templates
- PDFs with a built-in outline/ToC get better results (read directly when available)
- Section hierarchy (nesting) is approximate
- Citation detection: numeric citations (`[1]`, `[2, 3]`, `[1-5]`) are detected via regex; author-year citations (`(Kingma & Ba, 2015)`) are detected when hyperlinked in the PDF (via `LINK_NAMED` destinations, common in LaTeX). Non-hyperlinked author-year citations are not detected.
- When a TOC heading doesn't match any line on its page (e.g., TOC says "Proof of thm:foo" but PDF says "A.2. Proof of Thm. 1"), the section may include some extra content from the page header

## Future plans

- [GROBID](https://github.com/kermitt2/grobid) backend for ML-based section detection
- Figure/table refs (`[ref=f...]`) — needs caption detection logic
- Named citation detection for non-hyperlinked author-year citations (hyperlinked ones already work via `LINK_NAMED`)
- Richer document model inspired by [papermage](https://github.com/allenai/papermage)
- Better handling of tables, figures, equations
