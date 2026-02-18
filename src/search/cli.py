"""CLI entry point for the search tool."""

from __future__ import annotations

from typing import Optional

import click
from rich.console import Console

console = Console()


@click.group()
@click.version_option(package_name="paper-cli")
def cli():
    """search - Search the web, academic papers, and medical literature."""
    pass


# ---------------------------------------------------------------------------
# search env
# ---------------------------------------------------------------------------


@cli.group(invoke_without_command=True)
@click.pass_context
def env(ctx):
    """Show or configure API keys.

    Run without arguments to see current status.
    Use `search env set KEY value` to save a key to ~/.papers/.env.
    """
    if ctx.invoked_subcommand is not None:
        return

    from search.config import PERSISTENT_ENV, check_env

    statuses = check_env()
    console.print("API Key Status:")
    console.print()
    for var, is_set, info in statuses:
        status = "[green]set[/green]" if is_set else "[red]not set[/red]"
        console.print(f"  {var}: {status}")
        console.print(f"    {info['description']}")
        console.print(f"    Used by: {', '.join(info['required_by'])}", style="dim")
        console.print()

    console.print(f"Config file: {PERSISTENT_ENV}", style="dim")

    if not all(is_set for _, is_set, _ in statuses):
        console.print(
            "Tip: Run `search env set KEY value` to save a key persistently.",
            style="dim",
        )


@env.command("set")
@click.argument("key")
@click.argument("value")
def env_set(key: str, value: str):
    """Save an API key to ~/.papers/.env.

    KEY: one of SERPER_API_KEY, S2_API_KEY, JINA_API_KEY
    VALUE: your API key value
    """
    from search.config import VALID_KEYS, save_key

    key = key.upper()
    if key not in VALID_KEYS:
        console.print(f"[red]Unknown key: {key}[/red]")
        console.print(f"Valid keys: {', '.join(sorted(VALID_KEYS))}")
        raise SystemExit(1)

    path = save_key(key, value)
    console.print(f"Saved {key} to {path}")


# ---------------------------------------------------------------------------
# search google
# ---------------------------------------------------------------------------


@cli.group()
def google():
    """Search the web via Google (Serper API)."""
    pass


@google.command("web")
@click.argument("query")
@click.option("--num", "-n", default=10, help="Number of results.")
@click.option("--gl", default="us", help="Country code (default: us).")
@click.option("--hl", default="en", help="Language (default: en).")
def google_web(query: str, num: int, gl: str, hl: str):
    """Web search.

    QUERY: the search query string
    """
    from search.backends.google import search_web
    from search.renderer import render_search_results

    try:
        results = search_web(query, num_results=num, gl=gl, hl=hl)
        render_search_results(results, source="Google")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)


@google.command("scholar")
@click.argument("query")
@click.option("--num", "-n", default=10, help="Number of results.")
def google_scholar(query: str, num: int):
    """Google Scholar search.

    QUERY: the search query string
    """
    from search.backends.google import search_scholar
    from search.renderer import render_search_results

    try:
        results = search_scholar(query, num_results=num)
        render_search_results(results, source="Google Scholar")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)


# ---------------------------------------------------------------------------
# search semanticscholar
# ---------------------------------------------------------------------------


@cli.group()
def semanticscholar():
    """Search academic papers via Semantic Scholar."""
    pass


@semanticscholar.command("papers")
@click.argument("query")
@click.option("--year", default=None, help="Year range (e.g., '2020-2024', '2023-').")
@click.option("--min-citations", default=None, type=int, help="Minimum citation count.")
@click.option("--venue", default=None, help="Venue filter (e.g., 'ACL', 'NeurIPS').")
@click.option("--sort", default=None, help="Sort order (e.g., 'citationCount:desc').")
@click.option("--limit", "-n", default=10, help="Number of results.")
@click.option("--offset", default=0, help="Pagination offset.")
def s2_papers(
    query: str,
    year: Optional[str],
    min_citations: Optional[int],
    venue: Optional[str],
    sort: Optional[str],
    limit: int,
    offset: int,
):
    """Search for papers by keyword.

    QUERY: the search query string
    """
    from search.backends.semanticscholar import search_papers
    from search.renderer import render_search_results

    try:
        results = search_papers(
            query, year=year, min_citations=min_citations,
            venue=venue, sort=sort, limit=limit, offset=offset,
        )
        render_search_results(results, source="Semantic Scholar")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)


@semanticscholar.command("snippets")
@click.argument("query")
@click.option("--year", default=None, help="Year range filter.")
@click.option("--paper-ids", default=None, help="Comma-separated paper IDs to search within.")
@click.option("--venue", default=None, help="Venue filter.")
@click.option("--limit", "-n", default=10, help="Number of snippets.")
def s2_snippets(
    query: str,
    year: Optional[str],
    paper_ids: Optional[str],
    venue: Optional[str],
    limit: int,
):
    """Search for relevant text snippets across papers.

    QUERY: the search query string
    """
    from search.backends.semanticscholar import search_snippets
    from search.renderer import render_snippet_results

    try:
        results = search_snippets(query, year=year, paper_ids=paper_ids, venue=venue, limit=limit)
        render_snippet_results(results)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)


@semanticscholar.command("citations")
@click.argument("paper_id")
@click.option("--limit", "-n", default=20, help="Number of citations.")
@click.option("--offset", default=0, help="Pagination offset.")
def s2_citations(paper_id: str, limit: int, offset: int):
    """Show papers that cite the given paper.

    PAPER_ID: Semantic Scholar paper ID, DOI, or arxiv ID (e.g., 'arxiv:2302.13971')
    """
    from search.backends.semanticscholar import get_citations
    from search.renderer import render_citation_results

    try:
        results = get_citations(paper_id, limit=limit, offset=offset)
        render_citation_results(results, direction="citations")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)


@semanticscholar.command("references")
@click.argument("paper_id")
@click.option("--limit", "-n", default=20, help="Number of references.")
@click.option("--offset", default=0, help="Pagination offset.")
def s2_references(paper_id: str, limit: int, offset: int):
    """Show papers referenced by the given paper.

    PAPER_ID: Semantic Scholar paper ID, DOI, or arxiv ID (e.g., 'arxiv:2302.13971')
    """
    from search.backends.semanticscholar import get_references
    from search.renderer import render_citation_results

    try:
        results = get_references(paper_id, limit=limit, offset=offset)
        render_citation_results(results, direction="references")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)


@semanticscholar.command("details")
@click.argument("paper_id")
def s2_details(paper_id: str):
    """Show details for a specific paper.

    PAPER_ID: Semantic Scholar paper ID, DOI, or arxiv ID (e.g., 'arxiv:2302.13971')
    """
    from search.backends.semanticscholar import get_paper_details
    from search.renderer import render_paper_details

    try:
        result = get_paper_details(paper_id)
        render_paper_details(result)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)


# ---------------------------------------------------------------------------
# search pubmed
# ---------------------------------------------------------------------------


@cli.command()
@click.argument("query")
@click.option("--limit", "-n", default=10, help="Number of results.")
@click.option("--offset", default=0, help="Pagination offset.")
def pubmed(query: str, limit: int, offset: int):
    """Search PubMed for biomedical literature.

    QUERY: the search query string
    """
    from search.backends.pubmed import search_pubmed
    from search.renderer import render_search_results

    try:
        results = search_pubmed(query, limit=limit, offset=offset)
        render_search_results(results, source="PubMed")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)


# ---------------------------------------------------------------------------
# search browse
# ---------------------------------------------------------------------------


@cli.command()
@click.argument("url")
@click.option(
    "--backend",
    "-b",
    default="jina",
    type=click.Choice(["jina", "serper"]),
    help="Content extraction backend (default: jina).",
)
@click.option("--timeout", "-t", default=30, help="Request timeout in seconds.")
def browse(url: str, backend: str, timeout: int):
    """Fetch and display webpage content.

    URL: the webpage URL to browse
    """
    from search.backends.browse import browse as do_browse
    from search.renderer import render_browse_result

    try:
        result = do_browse(url, backend=backend, timeout=timeout)
        render_browse_result(result)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)
