# Project: paper CLI

A CLI tool for reading, skimming, and searching academic papers from the terminal. See README.md for full docs.

## Quick reference

- **Entry point**: `paper = paper.cli:cli` (Click)
- **Key modules**: `cli.py` (commands), `parser.py` (PDF parsing), `fetcher.py` (arxiv download), `storage.py` (cache), `renderer.py` (Rich output), `models.py` (data types)
- **Cache**: `~/.papers/<arxiv_id>/` with `paper.pdf`, `parsed.json`, `metadata.json`
- **Tests**: `pytest` (63 tests)

## Architecture notes

- Parser tries PDF built-in outline first, falls back to font-size heuristics
- GROBID backend planned for future (noted in `parser.py`)
- Data model inspired by papermage: flat `raw_text` + `Section` list with character-offset `Span`s
- Downloads use atomic temp-file-then-rename pattern
- Storage sanitizes paper IDs to prevent path traversal
