"""Public API for programmatic use by other packages.

Import search functions and models without pulling in CLI dependencies::

    from search.api import search_papers, get_citations, SearchResult
"""

from __future__ import annotations

# Search backends
from search.backends.semanticscholar import (
    get_citations,
    get_paper_details,
    get_references,
    search_papers,
    search_snippets,
)
from search.backends.google import search_scholar, search_web
from search.backends.pubmed import search_pubmed
from search.backends.browse import browse

# Data models
from search.models import BrowseResult, CitationResult, SearchResult, SnippetResult

__all__ = [
    # Semantic Scholar
    "search_papers",
    "search_snippets",
    "get_citations",
    "get_references",
    "get_paper_details",
    # Google
    "search_web",
    "search_scholar",
    # PubMed
    "search_pubmed",
    # Browse
    "browse",
    # Models
    "SearchResult",
    "SnippetResult",
    "CitationResult",
    "BrowseResult",
]
