"""CLI entry point for the paper tool."""

from __future__ import annotations

import click
from rich.console import Console

from paper.fetcher import fetch_paper
from paper.parser import parse_paper
from paper import renderer as _renderer
from paper.renderer import (
    build_ref_registry,
    render_full,
    render_goto,
    render_header,
    render_highlight_list,
    render_highlight_matches,
    render_layout_list,
    render_outline,
    render_search_results,
    render_section,
    render_skim,
    _print_ref_footer,
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
@click.version_option(package_name="agent-papers-cli")
@click.option("--no-header", is_flag=True, default=False, hidden=True,
              help="Suppress the title header (useful for consecutive commands on the same paper).")
@click.option("--include-header", is_flag=True, default=False, hidden=True,
              help="Force the title header even when auto-suppression would hide it.")
@click.pass_context
def cli(ctx, no_header: bool, include_header: bool):
    """paper - A CLI for reading, skimming, and searching academic papers."""
    ctx.ensure_object(dict)
    if no_header and include_header:
        raise click.UsageError("Options --no-header and --include-header are mutually exclusive.")
    ctx.obj["no_header"] = no_header
    if include_header:
        _renderer._force_header = True
        ctx.call_on_close(lambda: setattr(_renderer, "_force_header", False))


DEFAULT_MAX_LINES = 50


@cli.command()
@click.argument("reference")
@click.argument("section", required=False, default=None)
@click.option("--no-refs", is_flag=True, default=False, help="Hide [ref=...] annotations.")
@click.option("--max-lines", default=None, type=int,
              help=f"Max sentences to show for a section (default: {DEFAULT_MAX_LINES}). Use 0 for unlimited.")
@click.pass_context
def read(ctx, reference: str, section: str | None, no_refs: bool, max_lines: int | None):
    """Read a paper (full or specific section).

    REFERENCE: arxiv ID or URL (e.g., 2301.12345)
    SECTION: optional section name to read (e.g., "method")
    """
    show_header = not ctx.obj.get("no_header", False)
    try:
        doc = _load(reference)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)

    if section:
        matched = _find_section(doc, section)
        if matched:
            refs = not no_refs
            registry = build_ref_registry(doc) if refs else []
            if show_header:
                render_header(doc)

            # Determine max lines: explicit flag > default for sections
            limit = max_lines if max_lines is not None else DEFAULT_MAX_LINES
            if limit == 0:
                limit = None  # unlimited

            render_section(matched, refs=refs, registry=registry, doc=doc,
                           max_lines=limit, paper_id=doc.metadata.arxiv_id)
            if refs and registry:
                _print_ref_footer(registry, doc.metadata.arxiv_id)
        else:
            console.print(f"[red]Section \"{section}\" not found.[/red]")
            console.print("[dim]Available sections:[/dim]")
            for s in doc.sections:
                console.print(f"  {'  ' * (s.level - 1)}{s.heading}")
            raise SystemExit(1)
    else:
        render_full(doc, refs=not no_refs, show_header=show_header)


@cli.command()
@click.argument("reference")
@click.option("--no-refs", is_flag=True, default=False, help="Hide [ref=...] annotations.")
@click.pass_context
def outline(ctx, reference: str, no_refs: bool):
    """Show paper outline/table of contents.

    REFERENCE: arxiv ID or URL (e.g., 2301.12345)
    """
    try:
        doc = _load(reference)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)

    show_header = not ctx.obj.get("no_header", False)
    render_outline(doc, refs=not no_refs, show_header=show_header)


@cli.command()
@click.argument("reference")
@click.option("--lines", "-n", default=2, help="Number of sentences per section.")
@click.option("--level", "-l", default=None, type=int, help="Max heading level to show.")
@click.option("--no-refs", is_flag=True, default=False, help="Hide [ref=...] annotations.")
@click.pass_context
def skim(ctx, reference: str, lines: int, level: int | None, no_refs: bool):
    """Skim a paper (headings + first N sentences).

    REFERENCE: arxiv ID or URL (e.g., 2301.12345)
    """
    try:
        doc = _load(reference)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)

    show_header = not ctx.obj.get("no_header", False)
    render_skim(doc, num_lines=lines, max_level=level, refs=not no_refs, show_header=show_header)


@cli.command()
@click.argument("reference")
@click.argument("query")
@click.option("--context", "-c", default=2, help="Lines of context around matches.")
@click.option("--no-refs", is_flag=True, default=False, help="Hide [ref=...] annotations.")
@click.pass_context
def search(ctx, reference: str, query: str, context: int, no_refs: bool):
    """Search for keywords in a paper.

    REFERENCE: arxiv ID or URL (e.g., 2301.12345)
    QUERY: text to search for
    """
    try:
        doc = _load(reference)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)

    show_header = not ctx.obj.get("no_header", False)
    render_search_results(doc, query, context_lines=context, refs=not no_refs, show_header=show_header)


@cli.command()
@click.argument("reference")
@click.option("--no-refs", is_flag=True, default=False, help="Hide [ref=...] annotations.")
@click.pass_context
def info(ctx, reference: str, no_refs: bool):
    """Show paper metadata.

    REFERENCE: arxiv ID or URL (e.g., 2301.12345)
    """
    try:
        doc = _load(reference)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)

    if not ctx.obj.get("no_header", False):
        render_header(doc)
    console.print(f"  Sections: {len(doc.sections)}")
    console.print(f"  Pages: {len(doc.pages)}")
    total_sentences = sum(len(s.sentences) for s in doc.sections)
    console.print(f"  Sentences: {total_sentences}")
    console.print(f"  Characters: {len(doc.raw_text)}")
    console.print()


@cli.command()
@click.argument("reference")
@click.option("--force", is_flag=True, default=False, help="Re-fetch from APIs (ignore cache).")
@click.pass_context
def bibtex(ctx, reference: str, force: bool):
    """Generate a BibTeX entry for a paper.

    REFERENCE: arxiv ID, URL, or local PDF path (e.g., 2301.12345)

    Fetches metadata from arxiv, Semantic Scholar, and Crossref to produce
    a complete BibTeX entry. If the paper was published at a venue, uses
    that instead of the arxiv preprint (rebiber-like normalization).

    Results are cached. Use --force to re-fetch.
    """
    from paper import storage
    from paper.bibtex import generate_bibtex

    try:
        doc, arxiv_id, _ = _load_with_paths(reference)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)

    show_header = not ctx.obj.get("no_header", False)
    if show_header:
        render_header(doc)

    try:
        bib = generate_bibtex(arxiv_id, doc, force=force)
    except Exception as e:
        console.print(f"[red]Error generating BibTeX: {e}[/red]")
        raise SystemExit(1)

    console.print(bib)
    console.print()
    console.print(f"  [dim]Cached to {storage.bibtex_path(arxiv_id)}[/dim]")
    console.print()


@cli.command()
@click.argument("reference")
@click.argument("ref_id")
@click.pass_context
def goto(ctx, reference: str, ref_id: str):
    """Jump to a reference shown in paper output.

    REFERENCE: arxiv ID or URL (e.g., 2301.12345)
    REF_ID: a reference like s3, e1, c5, f1, t2, eq3
    """
    try:
        # For layout refs (f/t/eq), load with layout detection
        if ref_id.startswith(("f", "t", "eq")):
            doc, _, _ = _load_with_layout(reference)
        else:
            doc = _load(reference)
    except ImportError as e:
        console.print(f"[red]{e}[/red]")
        raise SystemExit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)

    show_header = not ctx.obj.get("no_header", False)
    if not render_goto(doc, ref_id, show_header=show_header):
        raise SystemExit(1)


# --- Layout detection commands ---

def _load_with_layout(reference: str):
    """Fetch + parse + detect layout, returning (Document, arxiv_id, pdf_path).

    Layout detection is lazy: runs on first call, then cached.
    """
    from paper.layout import detect_layout

    arxiv_id, pdf_path = fetch_paper(reference)
    doc = parse_paper(arxiv_id, pdf_path)

    if not doc.layout_elements:
        doc.layout_elements = detect_layout(arxiv_id, pdf_path)

    return doc, arxiv_id, pdf_path


@cli.command()
@click.argument("reference")
@click.option("--force", is_flag=True, default=False, help="Re-run detection even if cached.")
@click.pass_context
def detect(ctx, reference: str, force: bool):
    """Run layout detection (figures, tables, equations) on a paper.

    REFERENCE: arxiv ID or URL (e.g., 2301.12345)

    Detection results are cached. Use --force to re-detect.
    """
    from paper.layout import detect_layout

    try:
        arxiv_id, pdf_path = fetch_paper(reference)
        doc = parse_paper(arxiv_id, pdf_path)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)

    console.print("[dim]Running layout detection...[/dim]")
    elements = detect_layout(arxiv_id, pdf_path, force=force)
    doc.layout_elements = elements

    if not ctx.obj.get("no_header", False):
        render_header(doc)
    figs = sum(1 for e in elements if e.kind == "figure")
    tabs = sum(1 for e in elements if e.kind == "table")
    eqs = sum(1 for e in elements if e.kind == "equation")
    console.print(f"  Detected: {figs} figure(s), {tabs} table(s), {eqs} equation(s)")
    console.print(f"  [dim]Cached to ~/.papers/{arxiv_id}/layout.json[/dim]")
    console.print()


@cli.command()
@click.argument("reference")
@click.pass_context
def figures(ctx, reference: str):
    """List detected figures in a paper.

    REFERENCE: arxiv ID or URL (e.g., 2301.12345)

    Triggers layout detection on first use (cached afterward).
    """
    try:
        doc, _, _ = _load_with_layout(reference)
    except ImportError as e:
        console.print(f"[red]{e}[/red]")
        raise SystemExit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)

    show_header = not ctx.obj.get("no_header", False)
    render_layout_list(doc, kind="figure", show_header=show_header)


@cli.command()
@click.argument("reference")
@click.pass_context
def tables(ctx, reference: str):
    """List detected tables in a paper.

    REFERENCE: arxiv ID or URL (e.g., 2301.12345)

    Triggers layout detection on first use (cached afterward).
    """
    try:
        doc, _, _ = _load_with_layout(reference)
    except ImportError as e:
        console.print(f"[red]{e}[/red]")
        raise SystemExit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)

    show_header = not ctx.obj.get("no_header", False)
    render_layout_list(doc, kind="table", show_header=show_header)


@cli.command()
@click.argument("reference")
@click.pass_context
def equations(ctx, reference: str):
    """List detected equations in a paper.

    REFERENCE: arxiv ID or URL (e.g., 2301.12345)

    Triggers layout detection on first use (cached afterward).
    """
    try:
        doc, _, _ = _load_with_layout(reference)
    except ImportError as e:
        console.print(f"[red]{e}[/red]")
        raise SystemExit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)

    show_header = not ctx.obj.get("no_header", False)
    render_layout_list(doc, kind="equation", show_header=show_header)


# --- Highlight helpers ---

def _print_match_list(matches: list[dict], match_range: str | None, total: int) -> None:
    """Print a slice of matches. Uses --range if given, else first DEFAULT_MATCH_RANGE."""
    if match_range:
        start, end = _parse_range(match_range, total)
    else:
        start, end = 0, min(total, DEFAULT_MATCH_RANGE)

    for i, m in enumerate(matches[start:end], start + 1):
        context = m.get("context", "")
        if len(context) > 100:
            context = context[:97] + "..."
        console.print(f"  [bold yellow]{i}.[/bold yellow] page {m['page'] + 1}: {context}")

    remaining_before = start
    remaining_after = total - end
    hints = []
    if remaining_before > 0:
        hints.append(f"{remaining_before} before")
    if remaining_after > 0:
        hints.append(f"{remaining_after} after")
    if hints:
        console.print(f"  [dim]... {' / '.join(hints)} (use --range START:END to paginate, e.g., --range {end + 1}:{end + DEFAULT_MATCH_RANGE})[/dim]")
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
@click.pass_context
def highlight_search(ctx, reference: str, query: str, context: int):
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
    show_header = not ctx.obj.get("no_header", False)
    render_highlight_matches(matches, query, doc, show_header=show_header)


DEFAULT_MATCH_RANGE = 20


def _parse_range(range_str: str, total: int) -> tuple[int, int]:
    """Parse a range string like '5:10', ':10', '5:' into (start, end) 0-indexed.

    Input indices are 1-indexed. Returns 0-indexed (start, end) for slicing.
    """
    parts = range_str.split(":")
    if len(parts) != 2:
        raise click.BadParameter(f"Invalid range '{range_str}'. Use START:END (e.g., 1:20, 21:40).")
    start_str, end_str = parts
    start = int(start_str) - 1 if start_str.strip() else 0
    end = int(end_str) if end_str.strip() else total
    if start < 0:
        start = 0
    if end > total:
        end = total
    if start >= end:
        raise click.BadParameter(f"Empty range {start + 1}:{end} (total matches: {total}).")
    return start, end


@highlight.command("add")
@click.argument("reference")
@click.argument("query")
@click.option("--color", type=click.Choice(["yellow", "green", "blue", "pink"]), default="yellow", help="Highlight color.")
@click.option("--note", default="", help="Note to attach to the highlight.")
@click.option("--return-json", "return_json", is_flag=True, default=False, help="Output app-compatible JSON.")
@click.option("--pick", type=int, default=None, help="Select match N directly (1-indexed). Use with highlight search to find the right index.")
@click.option("--interactive", "-i", is_flag=True, default=False, help="Interactively pick a match when multiple are found.")
@click.option("--range", "match_range", default=None, help="Range of matches to display, e.g., 1:20, 21:40 (1-indexed).")
def highlight_add(reference: str, query: str, color: str, note: str, return_json: bool, pick: int | None, interactive: bool, match_range: str | None):
    """Find text and add a highlight.

    REFERENCE: arxiv ID or URL (e.g., 2301.12345)
    QUERY: text to highlight

    With multiple matches, shows candidates and exits. Use --pick N to select
    one, or --interactive for a prompt. Designed for non-interactive/agent use
    by default.
    """
    import json as json_mod
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
    elif pick is not None:
        if pick < 1 or pick > len(matches):
            console.print(f"[red]--pick {pick} is out of range (1-{len(matches)})[/red]")
            raise SystemExit(1)
        selected = matches[pick - 1]
    elif interactive:
        _print_match_list(matches, match_range, len(matches))
        try:
            choice = click.prompt("Pick a match", type=int, default=1)
            if 1 <= choice <= len(matches):
                selected = matches[choice - 1]
            else:
                console.print(f"[red]Choice {choice} is out of range (1-{len(matches)})[/red]")
                raise SystemExit(1)
        except (EOFError, click.Abort):
            raise SystemExit(1)
    else:
        # Default: non-interactive — list matches and exit
        console.print(f"  [bold]{len(matches)} matches found.[/bold] Use [cyan]--pick N[/cyan] to select one:")
        console.print()
        _print_match_list(matches, match_range, len(matches))
        console.print(f"  [dim]Example: paper highlight add {reference} \"{query}\" --pick 1[/dim]")
        console.print(f"  [dim]Or use --interactive for a prompt.[/dim]")
        raise SystemExit(0)

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
@click.pass_context
def highlight_list(ctx, reference: str):
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
    show_header = not ctx.obj.get("no_header", False)
    render_highlight_list(highlights, doc, show_header=show_header)


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
