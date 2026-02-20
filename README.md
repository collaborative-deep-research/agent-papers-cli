# agent-papers-cli

Read academic papers, search the literature, and run multi-step research workflows — all from the terminal.

**agent-papers-cli** gives your AI agents (and you) the ability to read academic papers, search Google, Google Scholar, Semantic Scholar, PubMed, and browse webpages — all from the command line. Two CLI tools work together: `paper` for reading and navigating PDFs, and `paper-search` for querying search engines and academic databases.

Designed as building blocks for agentic research workflows, these tools let agents autonomously discover papers, read them in depth, follow citation graphs, and verify claims. The repo includes four [Claude Code skills](#agent-skills) that orchestrate multi-step research tasks like deep-dive investigations, systematic literature reviews, and fact-checking.

- **`paper`** — read, skim, and search PDFs. Inspired by [agent-browser](https://github.com/vercel-labs/agent-browser) — but for PDFs.
- **`paper-search`** — search Google, Google Scholar, Semantic Scholar, PubMed, and extract webpage content. Based on the search APIs from [dr-tulu](https://github.com/rlresearch/dr-tulu).

## Install

```bash
pip install agent-papers-cli

# Optional: enable figure/table/equation detection (requires ~40MB for model)
pip install agent-papers-cli[layout]
```

Requires Python 3.10+. Also works with `uv pip install agent-papers-cli`.

To install the [agent skills](#agent-skills) for Claude Code: `npx skills add collaborative-deep-research/agent-papers-cli`

## `paper` commands

```bash
paper outline <ref>                    # Show heading tree
paper read <ref> [section]             # Read full paper or specific section (default: 50 sentences)
  [--max-lines N]                      # Limit sentences shown (0 = unlimited)
paper skim <ref> --lines N --level L   # Headings + first N sentences
paper search <ref> "query"             # Keyword search with context
paper info <ref>                       # Show metadata
paper goto <ref> <ref_id>              # Jump to a section, link, or citation

# Layout detection (requires `pip install paper-cli[layout]`)
paper detect <ref>                     # Run figure/table/equation detection
paper figures <ref>                    # List detected figures with captions
paper tables <ref>                     # List detected tables
paper equations <ref>                  # List detected equations
paper goto <ref> f1                    # Jump to figure 1
paper goto <ref> t2                    # Jump to table 2
paper goto <ref> eq3                   # Jump to equation 3

# Highlights
paper highlight search <ref> "query"   # Search PDF for text (with coordinates)
paper highlight add <ref> "query"      # Find text and persist a highlight
paper highlight list <ref>             # List stored highlights
paper highlight remove <ref> <id>      # Remove a highlight by ID
```

`<ref>` accepts: `2302.13971`, `arxiv.org/abs/2302.13971`, `arxiv.org/pdf/2302.13971`, or a **local PDF path** like `./paper.pdf`

Arxiv papers are downloaded once and cached in `~/.papers/`. Local PDFs are read directly from disk — each gets a unique cache directory based on its absolute path (`{stem}-{hash8}`), so two different `paper.pdf` files in different directories won't collide. If you modify a local PDF after it's been parsed, the stale cache is automatically detected and re-parsed.

## `paper-search` commands

```bash
# Environment / API keys
paper-search env                             # Show API key status
paper-search env set KEY value               # Save a key to ~/.papers/.env

# Google (requires SERPER_API_KEY)
paper-search google web "query"              # Web search
paper-search google scholar "query"          # Google Scholar search

# Semantic Scholar (S2_API_KEY optional, recommended for rate limits)
paper-search semanticscholar papers "query"  # Paper search
  [--year 2023-2025] [--min-citations 10] [--venue ACL] [--sort citationCount:desc] [--limit N]
paper-search semanticscholar snippets "query"  # Text snippet search
  [--year 2024] [--paper-ids id1,id2]
paper-search semanticscholar citations <id>  # Papers citing this one
paper-search semanticscholar references <id> # Papers this one references
paper-search semanticscholar details <id>    # Full paper metadata

# PubMed (no key needed)
paper-search pubmed "query" [--limit N] [--offset N]

# Browse (requires JINA_API_KEY for jina backend)
paper-search browse <url> [--backend jina|serper] [--timeout 30]
```

### API keys

Set API keys persistently with `paper-search env set`:

```bash
paper-search env set SERPER_API_KEY sk-...   # required for google, browse --backend serper
paper-search env set S2_API_KEY ...          # optional, higher Semantic Scholar rate limits
paper-search env set JINA_API_KEY ...        # required for browse --backend jina
```

Keys are saved to `~/.papers/.env` and loaded automatically. Shell environment variables take precedence. Run `paper-search env` to check what's configured.

### Jump links

All output is annotated with `[ref=...]` markers that agents (or humans) can follow up on:

- `[ref=s3]` — section (jump to section 3)
- `[ref=f1]` — figure (show bounding box and caption)
- `[ref=t2]` — table (show bounding box and caption)
- `[ref=eq1]` — equation (show bounding box)
- `[ref=e1]` — external link (show URL and context)
- `[ref=c5]` — citation (look up reference [5] in the bibliography)

Use `paper goto <ref> <ref_id>` to follow any marker. A summary footer shows the available ref ranges:

```
Refs: s1..s12 (sections) · f1..f5 (figures) · t1..t3 (tables) · eq1..eq8 (equations) · e1..e8 (links) · c1..c24 (citations)
Use: paper goto 2302.13971 <ref>
```

Add `--no-refs` to any command to hide the annotations.

### Header auto-suppression

When you run consecutive `paper` commands on the same paper, the title header is automatically suppressed after the first call (within a 5-minute window). This keeps agent context windows lean and avoids redundant output.

```bash
paper outline 2302.13971          # header shown
paper read 2302.13971 "abstract"  # header auto-suppressed
paper read 2302.13971 "method"    # still suppressed
paper outline 2502.13811          # different paper — header shown
```

Use `--include-header` to force the header, or `--no-header` to always suppress it:

```bash
paper --include-header read 2302.13971 "abstract"   # force header
paper --no-header outline 2302.13971                 # always suppress
```

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

### Detect figures, tables, and equations

Requires `pip install paper-cli[layout]` (installs `doclayout_yolo`). Model weights (~40MB) are downloaded automatically on first use to `~/.papers/.models/`.

```bash
# Run detection (results cached in ~/.papers/<id>/layout.json)
paper detect 2302.13971

# List detected elements
paper figures 2302.13971
paper tables 2302.13971
paper equations 2302.13971

# Jump to a specific element
paper goto 2302.13971 f1    # figure 1
paper goto 2302.13971 t2    # table 2
paper goto 2302.13971 eq3   # equation 3
```

Detection uses [DocLayout-YOLO](https://github.com/opendatalab/DocLayout-YOLO) trained on DocStructBench (10 categories including figures, tables, and formulas). Model weights are from our [pinned fork](https://huggingface.co/collab-dr/DocLayout-YOLO-DocStructBench). Supports CUDA, MPS (Apple Silicon), and CPU. Running `paper figures` etc. triggers detection lazily on first use — subsequent calls use the cached result. Each detected element is cropped as a PNG screenshot to `~/.papers/<id>/layout/` (e.g., `f1.png`, `t2.png`, `eq3.png`).

## Architecture

```
src/paper/                         # paper CLI
├── cli.py         # Click CLI — all commands defined here
├── fetcher.py     # Downloads PDFs from arxiv, manages cache
├── highlighter.py # PDF text search, coordinate conversion, highlight CRUD, PDF annotation
├── layout.py      # Figure/table/equation detection via DocLayout-YOLO (optional)
├── models.py      # Data models: Document, Section, Sentence, Span, Box, Metadata, Link, LayoutElement, Highlight
├── parser.py      # PDF → Document: text extraction, heading detection, sentence splitting
├── renderer.py    # Rich terminal output, ref registry, goto rendering
└── storage.py     # ~/.papers/ cache directory management

src/search/                        # paper-search CLI
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
3. **Detect** (optional, lazy): Detects figures, tables, and equations using [DocLayout-YOLO](https://github.com/opendatalab/DocLayout-YOLO) pre-trained on [DocStructBench](https://github.com/opendatalab/DocLayout-YOLO). Renders pages to images, runs YOLO detection, maps bounding boxes back to PDF coordinates. Supports MPS (Apple Metal), CUDA, and CPU. Runs on first `paper figures`/`tables`/`equations` call and is cached.
4. **Display**: Renders structured output with [Rich](https://rich.readthedocs.io/), annotates with `[ref=...]` jump links

The parsed structure is cached as JSON so subsequent commands are instant. Layout detection results are cached separately in `layout.json`.

### Data model

Simplified flat-layer approach inspired by [papermage](https://github.com/allenai/papermage):

- **Document** has a `raw_text` string, list of `Section`s, `Link`s, and `LayoutElement`s
- Each **Section** has a heading, level, content, and list of `Sentence`s
- Each **Link** has a kind (`external`/`internal`/`citation`), anchor text, URL, and page
- **LayoutElement** stores a detected figure, table, or equation with bounding `Box`, confidence, caption, label, and `image_path` (cropped PNG)
- **Highlight** stores persisted highlights with page, bounding rects (absolute PDF coords), color, and note
- **Span** objects store character offsets into `raw_text`, enabling text-to-PDF coordinate mapping
- Everything serializes to JSON for caching

### PDF heading detection

Two strategies, tried in order:

1. **PDF outline** — if the PDF has a built-in table of contents, use it directly (most reliable)
2. **Font-size heuristic** — detect body text size (most common), treat larger/bold text as headings, merge section number fragments ("1" + "Introduction" → "1 Introduction"), filter false positives (author names, table data, captions)

## Development

### Setup

```bash
git clone https://github.com/collaborative-deep-research/agent-papers-cli.git
cd agent-papers-cli
uv pip install -e ".[dev]"
```

### Run tests

```bash
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

# Layout detection (requires paper-cli[layout])
paper detect 2302.13971              # run figure/table/equation detection
paper figures 2302.13971             # list detected figures
paper goto 2302.13971 f1             # jump to figure 1
```

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PAPER_DOWNLOAD_TIMEOUT` | `120` | Download timeout in seconds |
| `SERPER_API_KEY` | — | Google search and scraping via Serper.dev |
| `S2_API_KEY` | — | Semantic Scholar API (optional, increases rate limits) |
| `JINA_API_KEY` | — | Jina Reader for webpage content extraction |

Search API keys can be set via shell env, `.env` in the working directory, or persistently via `paper-search env set`.

## Agent Skills

This repo includes [Claude Code skills](https://agentskills.io) for agent-driven research workflows. Install them into any project with:

```bash
npx skills add collaborative-deep-research/agent-papers-cli
```

Or see [SKILLS.md](SKILLS.md) for manual setup and details.

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
- Named citation detection for non-hyperlinked author-year citations (hyperlinked ones already work via `LINK_NAMED`)
- Richer document model inspired by [papermage](https://github.com/allenai/papermage)
- Equation recognition to LaTeX (via [UniMERNet](https://github.com/opendatalab/UniMERNet) or [LaTeX-OCR](https://github.com/lukas-blecher/LaTeX-OCR))
- Table structure recognition (cell-level extraction)
- Fine-tuning DocLayout-YOLO on custom academic paper datasets
