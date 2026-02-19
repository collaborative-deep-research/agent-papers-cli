# Tests

## Structure

### paper tests (`tests/`)

| File | What it tests |
|---|---|
| `test_models.py` | Data model serialization (Document save/load roundtrip, links) |
| `test_parser.py` | Heading detection heuristics, sentence splitting, fragment merging |
| `test_cli.py` | CLI smoke tests (help output, flag presence, error handling) |
| `test_links.py` | Citation detection, ref registry building, `goto` rendering |
| `test_fetcher.py` | ArXiv ID resolution, local PDF ID generation (`{stem}-{hash8}`), local metadata saving |
| `test_highlighter.py` | Highlight search, coordinate conversion, CRUD, storage |
| `test_storage.py` | Cache directory management, JSON corruption recovery, local PDF cache staleness detection |
| `test_integration.py` | End-to-end parsing of real papers (see below) |

### search tests (`tests/search/`)

| File | What it tests |
|---|---|
| `test_cli.py` | CLI help text, command registration, env set, missing key errors |
| `test_backends.py` | Backend HTTP calls with mocked responses (Google, S2, PubMed, Jina, Serper) |
| `test_config.py` | Env var detection, key accessors, persistent `save_key` to `~/.papers/.env` |
| `test_models.py` | Dataclass defaults and field values |
| `test_renderer.py` | Rich output formatting, reference IDs, suggestive prompts |

## Integration tests (`test_integration.py`)

These tests parse **real PDFs** cached in `~/.papers/` and verify that the
parsing pipeline produces correct results. They are skipped automatically
when papers aren't cached (e.g., in CI).

Run locally after fetching papers:

```bash
uv run paper outline 2502.13811   # fetches + caches PDF
uv run pytest tests/test_integration.py -v
```

### Test papers and why each is included

| ArXiv ID | Paper | Parsing path | Why it's here |
|---|---|---|---|
| `2502.13811` | *On the Duality between Gradient Transformations and Adapters* | **Outline-based** (20 TOC entries) | Caught a critical bug: outline headings from `get_toc()` had no `char_start` offsets, so `_segment_sections` defaulted every section to offset 0 → all sections contained the entire document text. Fixed by `_resolve_outline_offsets()`. |
| `2302.13971` | *LLaMA: Open and Efficient Foundation Language Models* | **Font-based** (no TOC) | Exercises the font-size heuristic path. Used during initial development as the primary test paper. No TOC in the PDF, so headings are detected by comparing font sizes to body text. |
| `2505.21451` | *Words Like Knives: Backstory-Personalized Modeling and Detection of Violent Communication* | **Font-based** (no TOC) | Stress-tests heading detection robustness: author names at heading font size (♣ ♢ ♠ symbols), bold body text containing heading keywords, arXiv header at larger font than title, multi-line wrapped headings, and small-caps section titles. |

### Known edge cases

- **Parent sections with no body text**: When an outline heading (e.g.,
  "Empirical Study") is immediately followed by a subsection (e.g.,
  "Study 1: ..."), the parent section will have 0 sentences. This is
  expected — the parent is a structural grouping, not a content section.

- **Heading text mismatch**: The PDF outline may say "Introduction" while
  the actual line text is "1. Introduction". `_resolve_outline_offsets`
  handles this via substring matching, but the heading text in the section
  content may not get stripped cleanly. This is cosmetic.

- **Citation detection**: Numeric citations (`[1]`, `[2, 3]`, `[1-5]`)
  are detected via regex in `_detect_citations`. Author-year citations
  like `(Kingma & Ba, 2015)` are detected from PDF link annotations
  (`LINK_NAMED` with `cite.*` destinations), which covers most LaTeX
  papers. Non-hyperlinked author-year citations are not detected.

- **Small-caps section titles**: Some papers use small caps at a smaller
  font size for section titles (e.g., 2505.21451 section 4 "PERSONA
  CONFLICTS CORPUS" at 9.6pt vs 11pt body). These are currently not
  detected, leaving the section number alone ("4") without its title.
