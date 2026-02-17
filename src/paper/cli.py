"""CLI entry point for the paper tool."""

from __future__ import annotations

import click
from rich.console import Console

from paper.fetcher import fetch_paper
from paper.parser import parse_paper
from paper.renderer import (
    render_full,
    render_header,
    render_highlight_list,
    render_highlight_matches,
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


def _load_with_paths(reference: str):
    """Fetch + parse a paper, returning (Document, arxiv_id, pdf_path)."""
    arxiv_id, pdf_path = fetch_paper(reference)
    doc = parse_paper(arxiv_id, pdf_path)
    return doc, arxiv_id, pdf_path


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
def read(reference: str, section: str | None):
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
            render_section(matched)
        else:
            console.print(f"[red]Section \"{section}\" not found.[/red]")
            console.print("[dim]Available sections:[/dim]")
            for s in doc.sections:
                console.print(f"  {'  ' * (s.level - 1)}{s.heading}")
            raise SystemExit(1)
    else:
        render_full(doc)


@cli.command()
@click.argument("reference")
def outline(reference: str):
    """Show paper outline/table of contents.

    REFERENCE: arxiv ID or URL (e.g., 2301.12345)
    """
    try:
        doc = _load(reference)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)

    render_outline(doc)


@cli.command()
@click.argument("reference")
@click.option("--lines", "-n", default=2, help="Number of sentences per section.")
@click.option("--level", "-l", default=None, type=int, help="Max heading level to show.")
def skim(reference: str, lines: int, level: int | None):
    """Skim a paper (headings + first N sentences).

    REFERENCE: arxiv ID or URL (e.g., 2301.12345)
    """
    try:
        doc = _load(reference)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)

    render_skim(doc, num_lines=lines, max_level=level)


@cli.command()
@click.argument("reference")
@click.argument("query")
@click.option("--context", "-c", default=2, help="Lines of context around matches.")
def search(reference: str, query: str, context: int):
    """Search for keywords in a paper.

    REFERENCE: arxiv ID or URL (e.g., 2301.12345)
    QUERY: text to search for
    """
    try:
        doc = _load(reference)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)

    render_search_results(doc, query, context_lines=context)


@cli.command()
@click.argument("reference")
def info(reference: str):
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


# --- Highlight command group ---

@cli.group()
def highlight():
    """Search, add, list, and remove highlights on a paper."""
    pass


@highlight.command("search")
@click.argument("reference")
@click.argument("query")
@click.option("--context", "-c", default=2, help="Lines of context around matches.")
def highlight_search(reference: str, query: str, context: int):
    """Search for text in a paper's PDF.

    REFERENCE: arxiv ID or URL (e.g., 2301.12345)
    QUERY: text to search for
    """
    from paper.highlighter import search_pdf

    try:
        doc, arxiv_id, pdf = _load_with_paths(reference)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)

    matches = search_pdf(pdf, query)
    render_highlight_matches(matches, query, doc)


@highlight.command("add")
@click.argument("reference")
@click.argument("query")
@click.option("--color", type=click.Choice(["yellow", "green", "blue", "pink"]), default="yellow", help="Highlight color.")
@click.option("--note", default="", help="Note to attach to the highlight.")
@click.option("--return-json", "return_json", is_flag=True, default=False, help="Output app-compatible JSON.")
def highlight_add(reference: str, query: str, color: str, note: str, return_json: bool):
    """Find text and add a highlight.

    REFERENCE: arxiv ID or URL (e.g., 2301.12345)
    QUERY: text to highlight
    """
    import json as json_mod
    import sys
    from paper.highlighter import add_highlight, annotate_pdf, match_to_json, search_pdf
    from paper import storage

    try:
        doc, arxiv_id, pdf = _load_with_paths(reference)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)

    matches = search_pdf(pdf, query)

    if not matches:
        console.print(f"[red]No matches found for \"{query}\"[/red]")
        raise SystemExit(1)

    # Select match
    if len(matches) == 1:
        selected = matches[0]
    else:
        console.print(f"  [bold]{len(matches)} matches found:[/bold]")
        console.print()
        for i, m in enumerate(matches, 1):
            context = m.get("context", "")
            if len(context) > 100:
                context = context[:97] + "..."
            console.print(f"  [bold yellow]{i}.[/bold yellow] page {m['page'] + 1}: {context}")
        console.print()

        if not sys.stdin.isatty():
            selected = matches[0]
        else:
            try:
                choice = click.prompt("Pick a match", type=int, default=1)
                if 1 <= choice <= len(matches):
                    selected = matches[choice - 1]
                else:
                    selected = matches[0]
            except (EOFError, click.Abort):
                selected = matches[0]

    if return_json:
        result = match_to_json(selected, doc)
        result["color"] = color
        if note:
            result["note"] = note
        console.print(json_mod.dumps(result, indent=2))
        return

    # Persist highlight
    hl = add_highlight(
        paper_id=arxiv_id,
        text=query,
        page=selected["page"],
        rects=selected["rects"],
        color=color,
        note=note,
    )

    # Annotate PDF
    annotated = storage.annotated_pdf_path(arxiv_id)
    all_highlights = storage.load_highlights(arxiv_id)
    annotate_pdf(pdf, annotated, all_highlights)

    console.print(f"  [bold green]Highlight #{hl.id} added[/bold green] on page {selected['page'] + 1}")
    if note:
        console.print(f"  [dim]Note: {note}[/dim]")
    console.print(f"  [dim]Annotated PDF: {annotated}[/dim]")
    console.print()


@highlight.command("list")
@click.argument("reference")
def highlight_list(reference: str):
    """List highlights for a paper.

    REFERENCE: arxiv ID or URL (e.g., 2301.12345)
    """
    from paper import storage

    try:
        doc, arxiv_id, _ = _load_with_paths(reference)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)

    highlights = storage.load_highlights(arxiv_id)
    render_highlight_list(highlights, doc)


@highlight.command("remove")
@click.argument("reference")
@click.argument("highlight_id", type=int)
def highlight_remove(reference: str, highlight_id: int):
    """Remove a highlight by ID.

    REFERENCE: arxiv ID or URL (e.g., 2301.12345)
    HIGHLIGHT_ID: numeric ID of the highlight to remove
    """
    from paper.highlighter import annotate_pdf, remove_highlight
    from paper import storage

    try:
        _, arxiv_id, pdf = _load_with_paths(reference)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)

    if remove_highlight(arxiv_id, highlight_id):
        # Re-annotate PDF with remaining highlights
        remaining = storage.load_highlights(arxiv_id)
        annotated = storage.annotated_pdf_path(arxiv_id)
        if remaining:
            annotate_pdf(pdf, annotated, remaining)
        elif annotated.exists():
            annotated.unlink()
        console.print(f"  [bold green]Highlight #{highlight_id} removed.[/bold green]")
    else:
        console.print(f"  [red]Highlight #{highlight_id} not found.[/red]")
        raise SystemExit(1)
