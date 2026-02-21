"""Rich terminal renderer for search results with reference IDs and suggestive prompts."""

from __future__ import annotations

import os
import re
import uuid

from rich.console import Console
from rich.text import Text

from search.models import BrowseResult, CitationResult, SearchResult, SnippetResult

console = Console()

# Set PAPER_SEARCH_HASH_IDS=1 to use deterministic hash-based reference IDs
# (8-char UUID5 from URL) instead of sequential r1, s1, etc.  Hash IDs are
# unique across multiple searches, which is required for citation tracing in
# the eval harness.
_USE_HASH_IDS = os.environ.get("PAPER_SEARCH_HASH_IDS", "") == "1"


def _url_to_snippet_id(url: str) -> str:
    """Deterministic short snippet ID from a URL (8-char UUID5 prefix)."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, url))[:8]


def _make_ref_id(url: str, fallback_index: int, prefix: str = "r") -> str:
    """Generate a reference ID for a search result.

    When ``PAPER_SEARCH_HASH_IDS=1``, uses a deterministic hash of the URL
    so the same source always gets the same ID across searches.  Otherwise
    returns the classic sequential ``{prefix}{index}`` format.
    """
    if _USE_HASH_IDS and url:
        return _url_to_snippet_id(url)
    return f"{prefix}{fallback_index}"


def _detect_arxiv_id(url: str) -> str:
    """Try to extract an arxiv ID from a URL."""
    m = re.search(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5})", url)
    return m.group(1) if m else ""


def _suggestion_lines(result: SearchResult) -> list[str]:
    """Generate suggestive prompt lines for a search result."""
    lines = []
    arxiv_id = result.arxiv_id or _detect_arxiv_id(result.url)
    if arxiv_id:
        lines.append(f"  > Use `paper read {arxiv_id}` to read this paper")
        lines.append(f"  > Use `paper outline {arxiv_id}` to see its structure")
    elif result.url:
        lines.append(f"  > Use `paper-search browse {result.url}` to read full content")
    return lines


def render_search_results(
    results: list[SearchResult],
    *,
    source: str = "",
) -> None:
    """Render a list of search results with reference IDs."""
    if not results:
        console.print("[yellow]No results found.[/yellow]")
        return

    header = f"Found {len(results)} results"
    if source:
        header += f" from {source}"
    console.print(header)
    console.print()

    seen_ids: dict[str, int] = {}
    for i, r in enumerate(results, 1):
        ref = _make_ref_id(r.url, i, prefix="r")
        # De-duplicate within a single call
        count = seen_ids.get(ref, 0)
        seen_ids[ref] = count + 1
        if count > 0:
            ref = f"{ref}-{count}"
        # Title line
        title_line = Text()
        title_line.append(f"[{ref}] ", style="bold cyan")
        title_line.append(r.title, style="bold")
        console.print(title_line)

        # URL
        if r.url:
            console.print(f"     {r.url}", style="dim")

        # Metadata line
        meta_parts = []
        if r.authors:
            meta_parts.append(r.authors)
        if r.year:
            meta_parts.append(str(r.year))
        if r.venue:
            meta_parts.append(r.venue)
        if r.citation_count is not None:
            meta_parts.append(f"cited by {r.citation_count}")
        if meta_parts:
            console.print(f"     {' | '.join(meta_parts)}", style="dim")

        # Snippet
        if r.snippet:
            # Truncate long snippets
            snippet = r.snippet[:300]
            if len(r.snippet) > 300:
                snippet += "..."
            console.print(f"     {snippet}")

        # Suggestive prompts
        for line in _suggestion_lines(r):
            console.print(line, style="dim italic")

        console.print()


def render_snippet_results(results: list[SnippetResult]) -> None:
    """Render snippet search results."""
    if not results:
        console.print("[yellow]No snippets found.[/yellow]")
        return

    console.print(f"Found {len(results)} snippets")
    console.print()

    seen_ids: dict[str, int] = {}
    for i, s in enumerate(results, 1):
        if _USE_HASH_IDS and s.paper_id:
            ref = _url_to_snippet_id(s.paper_id)
        else:
            ref = f"s{i}"
        # De-duplicate within a single call
        count = seen_ids.get(ref, 0)
        seen_ids[ref] = count + 1
        if count > 0:
            ref = f"{ref}-{count}"
        title_line = Text()
        title_line.append(f"[{ref}] ", style="bold cyan")
        title_line.append(s.paper_title or "(untitled)", style="bold")
        console.print(title_line)

        meta_parts = []
        if s.section:
            meta_parts.append(f"section: {s.section}")
        if s.kind:
            meta_parts.append(f"type: {s.kind}")
        if s.score:
            meta_parts.append(f"score: {s.score:.2f}")
        if meta_parts:
            console.print(f"     {' | '.join(meta_parts)}", style="dim")

        console.print(f"     {s.text}")
        console.print()


def render_citation_results(
    results: list[CitationResult],
    *,
    direction: str = "citations",
) -> None:
    """Render citation/reference results."""
    if not results:
        console.print(f"[yellow]No {direction} found.[/yellow]")
        return

    console.print(f"Found {len(results)} {direction}")
    console.print()

    seen_ids: dict[str, int] = {}
    for i, c in enumerate(results, 1):
        if _USE_HASH_IDS and c.paper_id:
            ref = _url_to_snippet_id(c.paper_id)
        else:
            ref = f"c{i}"
        # De-duplicate within a single call
        count = seen_ids.get(ref, 0)
        seen_ids[ref] = count + 1
        if count > 0:
            ref = f"{ref}-{count}"
        title_line = Text()
        title_line.append(f"[{ref}] ", style="bold cyan")
        title_line.append(c.title or "(untitled)", style="bold")
        if c.is_influential:
            title_line.append(" *", style="bold yellow")
        console.print(title_line)

        meta_parts = []
        if c.authors:
            meta_parts.append(c.authors)
        if c.year:
            meta_parts.append(str(c.year))
        if c.venue:
            meta_parts.append(c.venue)
        if meta_parts:
            console.print(f"     {' | '.join(meta_parts)}", style="dim")

        if c.paper_id:
            console.print(
                f"  > Use `paper-search semanticscholar details {c.paper_id}` for more info",
                style="dim italic",
            )

        if c.contexts:
            ctx = c.contexts[0][:200]
            if len(c.contexts[0]) > 200:
                ctx += "..."
            console.print(f'     Context: "{ctx}"', style="dim")

        console.print()


def render_paper_details(result: SearchResult) -> None:
    """Render detailed info for a single paper."""
    console.print(result.title, style="bold")
    if result.url:
        console.print(result.url, style="dim")

    meta_parts = []
    if result.authors:
        meta_parts.append(result.authors)
    if result.year:
        meta_parts.append(str(result.year))
    if result.venue:
        meta_parts.append(result.venue)
    if result.citation_count is not None:
        meta_parts.append(f"cited by {result.citation_count}")
    if meta_parts:
        console.print(" | ".join(meta_parts), style="dim")

    if result.snippet:
        console.print()
        console.print(result.snippet)

    # Suggestions
    arxiv_id = result.arxiv_id or _detect_arxiv_id(result.url)
    if arxiv_id:
        console.print()
        console.print(f"> Use `paper read {arxiv_id}` to read this paper", style="dim italic")
        console.print(f"> Use `paper outline {arxiv_id}` to see its structure", style="dim italic")
    if result.paper_id:
        console.print(
            f"> Use `paper-search semanticscholar citations {result.paper_id}` to see who cites this",
            style="dim italic",
        )
        console.print(
            f"> Use `paper-search semanticscholar references {result.paper_id}` to see its references",
            style="dim italic",
        )
    console.print()


def render_browse_result(result: BrowseResult) -> None:
    """Render browsed webpage content."""
    console.print(f"Fetched content from {result.url} ({result.word_count:,} words)", style="bold")
    if result.title:
        console.print(result.title, style="bold")
    console.print()
    console.print(result.content)
