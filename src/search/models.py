"""Data models for search results."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SearchResult:
    """A single search result from any backend."""

    title: str
    url: str = ""
    snippet: str = ""
    year: Optional[int] = None
    authors: str = ""
    venue: str = ""
    citation_count: Optional[int] = None
    paper_id: str = ""
    arxiv_id: str = ""

    def has_arxiv(self) -> bool:
        return bool(self.arxiv_id) or "arxiv.org" in self.url


@dataclass
class SnippetResult:
    """A snippet search result from Semantic Scholar."""

    text: str
    section: str = ""
    kind: str = ""
    paper_title: str = ""
    paper_id: str = ""
    score: float = 0.0


@dataclass
class CitationResult:
    """A citation or reference entry."""

    title: str
    paper_id: str = ""
    year: Optional[int] = None
    venue: str = ""
    authors: str = ""
    is_influential: bool = False
    contexts: list[str] = field(default_factory=list)


@dataclass
class BrowseResult:
    """Content extracted from a URL."""

    url: str
    title: str = ""
    content: str = ""
    word_count: int = 0
