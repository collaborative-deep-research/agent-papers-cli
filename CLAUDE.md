# Project: paper & search CLI

Two CLI tools in one repo: `paper` (read academic PDFs) and `search` (web + academic search). See README.md for full docs and SKILLS.md for agent workflows.

## Quick reference

- **Entry points**: `paper = paper.cli:cli`, `search = search.cli:cli` (Click)
- **paper modules**: `cli.py`, `parser.py`, `fetcher.py`, `storage.py`, `renderer.py`, `models.py`, `highlighter.py`, `layout.py`
- **search modules**: `cli.py`, `config.py`, `models.py`, `renderer.py`, `backends/{google,semanticscholar,pubmed,browse}.py`
- **Cache**: `~/.papers/<paper_id>/` (papers: `paper.pdf`, `parsed.json`, `metadata.json`, `highlights.json`, `layout.json`, `paper_annotated.pdf`), `~/.papers/.models/` (YOLO weights), `~/.papers/.env` (persistent API keys)
- **Tests**: `pytest` — paper tests in `tests/` (124 tests), search tests in `tests/search/` (69 tests)
- **Agent skills**: `.claude/skills/` — research-coordinator, deep-research, literature-review, fact-check

## Architecture notes

### paper
- Parser tries PDF built-in outline first, falls back to font-size heuristics
- GROBID backend planned for future (noted in `parser.py`)
- Data model inspired by papermage: flat `raw_text` + `Section` list with character-offset `Span`s
- Downloads use atomic temp-file-then-rename pattern
- Storage sanitizes paper IDs to prevent path traversal
- Layout detection (optional `[layout]` extra) uses DocLayout-YOLO via ultralytics
- Layout detection is lazy: runs on first `paper figures`/`tables`/`equations` call, cached in `layout.json`
- Supports MPS (Apple Metal), CUDA, and CPU backends for inference
- Model weights auto-downloaded to `~/.papers/.models/` on first use

### search
- Thin httpx wrappers over external APIs (Serper, Semantic Scholar, PubMed, Jina)
- API keys loaded via python-dotenv in priority order: shell env > `.env` in cwd > `~/.papers/.env`
- `search env set` saves keys persistently to `~/.papers/.env`
- Semantic Scholar backend uses tenacity for retry on 429 rate limits
- Renderer outputs reference IDs (`[r1]`, `[s1]`, `[c1]`) and suggestive next-action prompts
