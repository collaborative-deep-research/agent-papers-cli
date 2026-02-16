# Tests

## Structure

| File | What it tests |
|---|---|
| `test_models.py` | Data model serialization (Document save/load roundtrip, links) |
| `test_parser.py` | Heading detection heuristics, sentence splitting, fragment merging |
| `test_cli.py` | CLI smoke tests (help output, flag presence, error handling) |
| `test_links.py` | Citation detection, ref registry building, `goto` rendering |
| `test_fetcher.py` | ArXiv ID resolution from various URL formats |
| `test_storage.py` | Cache directory management, JSON corruption recovery |
| `test_integration.py` | End-to-end parsing of real papers (see below) |

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

### Known edge cases

- **Parent sections with no body text**: When an outline heading (e.g.,
  "Empirical Study") is immediately followed by a subsection (e.g.,
  "Study 1: ..."), the parent section will have 0 sentences. This is
  expected — the parent is a structural grouping, not a content section.

- **Heading text mismatch**: The PDF outline may say "Introduction" while
  the actual line text is "1. Introduction". `_resolve_outline_offsets`
  handles this via substring matching, but the heading text in the section
  content may not get stripped cleanly. This is cosmetic.

- **Citation detection is numeric-only**: Named citations like
  `[Smith et al., 2023]` are not detected by the v1 regex. This is
  intentional — numeric citations (`[1]`, `[2, 3]`, `[1-5]`) cover
  the majority of ML papers.
