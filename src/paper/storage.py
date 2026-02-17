"""Manage the ~/.papers/ cache directory."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

PAPERS_DIR = Path.home() / ".papers"


def _sanitize_paper_id(paper_id: str) -> str:
    """Sanitize a paper ID for safe use as a directory name."""
    paper_id = paper_id.strip()
    paper_id = paper_id.replace("/", "_").replace("\\", "_")
    while paper_id.startswith("."):
        paper_id = paper_id[1:]
    if not paper_id:
        raise ValueError("paper_id must not be empty")
    return paper_id


def _safe_json_load(path: Path, fallback=None):
    """Load JSON from a file, returning fallback if corrupted."""
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, ValueError):
        logger.warning("Corrupted JSON file: %s — ignoring", path)
        return fallback


def ensure_dirs() -> None:
    PAPERS_DIR.mkdir(parents=True, exist_ok=True)


def paper_dir(paper_id: str) -> Path:
    safe_id = _sanitize_paper_id(paper_id)
    d = PAPERS_DIR / safe_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def pdf_path(paper_id: str) -> Path:
    return paper_dir(paper_id) / "paper.pdf"


def parsed_path(paper_id: str) -> Path:
    return paper_dir(paper_id) / "parsed.json"


def metadata_path(paper_id: str) -> Path:
    return paper_dir(paper_id) / "metadata.json"


def annotated_pdf_path(paper_id: str) -> Path:
    return paper_dir(paper_id) / "paper_annotated.pdf"


def has_pdf(paper_id: str) -> bool:
    return pdf_path(paper_id).exists()


def has_parsed(paper_id: str) -> bool:
    return parsed_path(paper_id).exists()


def save_metadata(paper_id: str, meta: dict) -> None:
    metadata_path(paper_id).write_text(json.dumps(meta, indent=2, ensure_ascii=False))


def load_metadata(paper_id: str) -> Optional[dict]:
    p = metadata_path(paper_id)
    if p.exists():
        return _safe_json_load(p, fallback=None)
    return None


def index_path() -> Path:
    return PAPERS_DIR / "index.json"


def update_index(paper_id: str, title: str) -> None:
    ensure_dirs()
    p = index_path()
    index = {}
    if p.exists():
        index = _safe_json_load(p, fallback={}) or {}
    index[paper_id] = title
    # Atomic write: write to temp file, then rename
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(index, indent=2, ensure_ascii=False))
    tmp.rename(p)


def list_papers() -> dict[str, str]:
    p = index_path()
    if p.exists():
        return _safe_json_load(p, fallback={}) or {}
    return {}


def highlights_path(paper_id: str) -> Path:
    return paper_dir(paper_id) / "highlights.json"


def load_highlights(paper_id: str) -> list[dict]:
    p = highlights_path(paper_id)
    if p.exists():
        return _safe_json_load(p, fallback=[]) or []
    return []


def save_highlights(paper_id: str, highlights: list[dict]) -> None:
    p = highlights_path(paper_id)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(highlights, indent=2, ensure_ascii=False))
    tmp.rename(p)
