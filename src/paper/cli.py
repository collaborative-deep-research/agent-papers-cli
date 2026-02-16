"""CLI entry point for the paper tool."""

from __future__ import annotations

import click
from rich.console import Console

from paper.fetcher import fetch_paper
from paper.parser import parse_paper
from paper.renderer import (
    render_full,
    render_goto,
    render_header,
    render_outline,
    render_search_results,
    render_section,
    render_skim,
)

console = Console()


def _load(reference: str):
    """Fetch + parse a paper, returning the Document."""
    arxiv_id, pdf_path = fetch_paper(reference)
    return parse_paper(arxiv_id, pdf_path)


def _find_section(doc, section_name: str):
    """Fuzzy-find a section by name."""
    name_lower = section_name.lower()

    # Exact match first
    for s in doc.sections:
        if s.heading.lower() == name_lower:
            return s

    # Substring match
    candidates = [s for s in doc.sections if name_lower in s.heading.lower()]
    if len(candidates) == 1:
        return candidates[0]

    if len(candidates) > 1:
        console.print("[yellow]Multiple sections match:[/yellow]")
        for i, c in enumerate(candidates, 1):
            console.print(f"  {i}. {c.heading}")
        console.print()
        # In non-interactive mode (piped stdin), default to first match
        import sys
        if not sys.stdin.isatty():
            return candidates[0]
        try:
            choice = click.prompt("Pick a section", type=int, default=1)
            if 1 <= choice <= len(candidates):
                return candidates[choice - 1]
        except (EOFError, click.Abort):
            return candidates[0]

    # Fallback: word overlap
    query_words = set(name_lower.split())
    best = None
    best_score = 0
    for s in doc.sections:
        heading_words = set(s.heading.lower().split())
        score = len(query_words & heading_words)
        if score > best_score:
            best_score = score
            best = s
    if best and best_score > 0:
        return best

    return None


@click.group()
@click.version_option(package_name="paper-cli")
def cli():
    """paper - A CLI for reading, skimming, and searching academic papers."""
    pass


@cli.command()
@click.argument("reference")
@click.argument("section", required=False, default=None)
@click.option("--no-refs", is_flag=True, default=False, help="Hide [ref=...] annotations.")
def read(reference: str, section: str | None, no_refs: bool):
    """Read a paper (full or specific section).

    REFERENCE: arxiv ID or URL (e.g., 2301.12345)
    SECTION: optional section name to read (e.g., "method")
    """
    try:
        doc = _load(reference)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)

    if section:
        matched = _find_section(doc, section)
        if matched:
            render_header(doc)
            render_section(matched, refs=not no_refs)
        else:
            console.print(f"[red]Section \"{section}\" not found.[/red]")
            console.print("[dim]Available sections:[/dim]")
            for s in doc.sections:
                console.print(f"  {'  ' * (s.level - 1)}{s.heading}")
            raise SystemExit(1)
    else:
        render_full(doc, refs=not no_refs)


@cli.command()
@click.argument("reference")
@click.option("--no-refs", is_flag=True, default=False, help="Hide [ref=...] annotations.")
def outline(reference: str, no_refs: bool):
    """Show paper outline/table of contents.

    REFERENCE: arxiv ID or URL (e.g., 2301.12345)
    """
    try:
        doc = _load(reference)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)

    render_outline(doc, refs=not no_refs)


@cli.command()
@click.argument("reference")
@click.option("--lines", "-n", default=2, help="Number of sentences per section.")
@click.option("--level", "-l", default=None, type=int, help="Max heading level to show.")
@click.option("--no-refs", is_flag=True, default=False, help="Hide [ref=...] annotations.")
def skim(reference: str, lines: int, level: int | None, no_refs: bool):
    """Skim a paper (headings + first N sentences).

    REFERENCE: arxiv ID or URL (e.g., 2301.12345)
    """
    try:
        doc = _load(reference)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)

    render_skim(doc, num_lines=lines, max_level=level, refs=not no_refs)


@cli.command()
@click.argument("reference")
@click.argument("query")
@click.option("--context", "-c", default=2, help="Lines of context around matches.")
@click.option("--no-refs", is_flag=True, default=False, help="Hide [ref=...] annotations.")
def search(reference: str, query: str, context: int, no_refs: bool):
    """Search for keywords in a paper.

    REFERENCE: arxiv ID or URL (e.g., 2301.12345)
    QUERY: text to search for
    """
    try:
        doc = _load(reference)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)

    render_search_results(doc, query, context_lines=context, refs=not no_refs)


@cli.command()
@click.argument("reference")
@click.option("--no-refs", is_flag=True, default=False, help="Hide [ref=...] annotations.")
def info(reference: str, no_refs: bool):
    """Show paper metadata.

    REFERENCE: arxiv ID or URL (e.g., 2301.12345)
    """
    try:
        doc = _load(reference)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)

    render_header(doc)
    console.print(f"  Sections: {len(doc.sections)}")
    console.print(f"  Pages: {len(doc.pages)}")
    total_sentences = sum(len(s.sentences) for s in doc.sections)
    console.print(f"  Sentences: {total_sentences}")
    console.print(f"  Characters: {len(doc.raw_text)}")
    console.print()


@cli.command()
@click.argument("reference")
@click.argument("ref_id")
def goto(reference: str, ref_id: str):
    """Jump to a reference shown in paper output.

    REFERENCE: arxiv ID or URL (e.g., 2301.12345)
    REF_ID: a reference like s3, e1, c5
    """
    try:
        doc = _load(reference)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)

    if not render_goto(doc, ref_id):
        raise SystemExit(1)
