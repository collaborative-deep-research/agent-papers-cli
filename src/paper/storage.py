"""Manage the ~/.papers/ cache directory."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

PAPERS_DIR = Path.home() / ".papers"


def ensure_dirs() -> None:
    PAPERS_DIR.mkdir(parents=True, exist_ok=True)


def paper_dir(paper_id: str) -> Path:
    d = PAPERS_DIR / paper_id
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
        return json.loads(p.read_text())
    return None


def index_path() -> Path:
    return PAPERS_DIR / "index.json"


def update_index(paper_id: str, title: str) -> None:
    ensure_dirs()
    p = index_path()
    index = {}
    if p.exists():
        index = json.loads(p.read_text())
    index[paper_id] = title
    p.write_text(json.dumps(index, indent=2, ensure_ascii=False))


def list_papers() -> dict[str, str]:
    p = index_path()
    if p.exists():
        return json.loads(p.read_text())
    return {}
