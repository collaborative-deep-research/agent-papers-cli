"""Public API for paper fetching and parsing.

Import paper functions and models without pulling in CLI dependencies::

    from paper.api import fetch_paper, parse_paper, Document
"""

from __future__ import annotations

from paper.fetcher import fetch_paper, resolve_arxiv_id
from paper.parser import parse_paper
from paper.models import Document, Metadata, Section
from paper.storage import has_pdf, has_parsed, pdf_path, list_papers

__all__ = [
    # Fetching
    "fetch_paper",
    "resolve_arxiv_id",
    # Parsing
    "parse_paper",
    # Models
    "Document",
    "Metadata",
    "Section",
    # Storage queries
    "has_pdf",
    "has_parsed",
    "pdf_path",
    "list_papers",
]
