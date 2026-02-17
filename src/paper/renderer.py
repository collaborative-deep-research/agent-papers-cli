"""Rich terminal output for paper content."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.tree import Tree

from paper.models import Document, Highlight, Section

console = Console()


def render_header(doc: Document) -> None:
    """Print paper title and metadata."""
    meta = doc.metadata
    title_text = Text(meta.title or "(Untitled)", style="bold white")
    subtitle_parts = []
    if meta.authors:
        subtitle_parts.append(", ".join(meta.authors))
    if meta.arxiv_id:
        subtitle_parts.append(f"arxiv.org/abs/{meta.arxiv_id}")
    subtitle = Text(" · ".join(subtitle_parts), style="dim")

    console.print()
    console.print(Panel(
        Text.assemble(title_text, "\n", subtitle),
        border_style="blue",
        padding=(0, 2),
    ))
    console.print()


def render_outline(doc: Document) -> None:
    """Print the heading tree."""
    render_header(doc)

    tree = Tree("[bold]Outline[/bold]", guide_style="dim")
    # Track tree nodes by level for nesting
    level_nodes: dict[int, Tree] = {}

    for section in doc.sections:
        label = f"[bold]{section.heading}[/bold]" if section.level == 1 else section.heading
        # Find parent node
        parent = tree
        for lvl in range(1, section.level):
            if lvl in level_nodes:
                parent = level_nodes[lvl]

        node = parent.add(label)
        level_nodes[section.level] = node
        # Clear deeper levels
        for lvl in list(level_nodes):
            if lvl > section.level:
                del level_nodes[lvl]

    console.print(tree)
    console.print()


def render_section(section: Section, show_heading: bool = True) -> None:
    """Print a single section's content."""
    if show_heading:
        indent = "  " * (section.level - 1)
        console.print(f"{indent}[bold cyan]{section.heading}[/bold cyan]")
        console.print()

    for sentence in section.sentences:
        console.print(f"  {sentence.text}")

    if not section.sentences and section.content:
        # Fall back to raw content if no sentences parsed
        for line in section.content.split("\n"):
            if line.strip():
                console.print(f"  {line.strip()}")

    console.print()


def render_full(doc: Document) -> None:
    """Print the full paper."""
    render_header(doc)
    for section in doc.sections:
        render_section(section)


def render_skim(doc: Document, num_lines: int = 2, max_level: int | None = None) -> None:
    """Print headings with first N sentences per section."""
    render_header(doc)

    for section in doc.sections:
        if max_level is not None and section.level > max_level:
            continue

        indent = "  " * (section.level - 1)
        console.print(f"{indent}[bold cyan]{section.heading}[/bold cyan]")

        sentences = section.sentences[:num_lines]
        if sentences:
            for sent in sentences:
                console.print(f"{indent}  [dim]{sent.text}[/dim]")
        elif section.content:
            # Fall back to first lines of raw content
            lines = [l.strip() for l in section.content.split("\n") if l.strip()]
            for line in lines[:num_lines]:
                console.print(f"{indent}  [dim]{line}[/dim]")

        console.print()


def render_search_results(
    doc: Document, query: str, context_lines: int = 2
) -> int:
    """Search and display matches with context. Returns match count."""
    render_header(doc)
    query_lower = query.lower()
    match_count = 0

    for section in doc.sections:
        text = section.content
        text_lower = text.lower()
        pos = 0

        while True:
            idx = text_lower.find(query_lower, pos)
            if idx == -1:
                break
            match_count += 1

            # Get context around the match
            line_start = text.rfind("\n", 0, idx)
            line_start = 0 if line_start == -1 else line_start + 1

            # Get a few lines of context
            context_end = idx + len(query)
            for _ in range(context_lines):
                next_nl = text.find("\n", context_end)
                if next_nl == -1:
                    context_end = len(text)
                    break
                context_end = next_nl + 1

            context = text[line_start:context_end].strip()

            # Highlight the match
            console.print(f"  [bold yellow]Match {match_count}[/bold yellow] in [cyan]{section.heading}[/cyan] (p.{section.page_start + 1})")

            # Highlight query in context
            highlighted = Text(context)
            ctx_lower = context.lower()
            search_pos = 0
            while True:
                hi = ctx_lower.find(query_lower, search_pos)
                if hi == -1:
                    break
                highlighted.stylize("bold red", hi, hi + len(query))
                search_pos = hi + len(query)

            console.print(Text("  "), highlighted)
            console.print()

            pos = idx + len(query)

    if match_count == 0:
        console.print(f"  [dim]No matches found for \"{query}\"[/dim]")
    else:
        console.print(f"  [dim]{match_count} match(es) found[/dim]")

    console.print()
    return match_count


def render_highlight_matches(
    matches: list[dict], query: str, doc: Document
) -> None:
    """Render highlight search matches with context."""
    render_header(doc)
    query_lower = query.lower()

    if not matches:
        console.print(f"  [dim]No matches found for \"{query}\"[/dim]")
        console.print()
        return

    for i, match in enumerate(matches, 1):
        page = match["page"]
        context = match.get("context", "")

        console.print(f"  [bold yellow]Match {i}[/bold yellow] on page {page + 1}")

        # Highlight the query in context
        highlighted = Text(context)
        ctx_lower = context.lower()
        search_pos = 0
        while True:
            hi = ctx_lower.find(query_lower, search_pos)
            if hi == -1:
                break
            highlighted.stylize("bold red", hi, hi + len(query))
            search_pos = hi + len(query)

        console.print(Text("  "), highlighted)
        console.print()

    console.print(f"  [dim]{len(matches)} match(es) found[/dim]")
    console.print()


def render_highlight_list(highlights: list[dict], doc: Document) -> None:
    """Render stored highlights for a paper."""
    render_header(doc)

    if not highlights:
        console.print("  [dim]No highlights saved.[/dim]")
        console.print()
        return

    COLOR_STYLES = {
        "yellow": "bold yellow",
        "green": "bold green",
        "blue": "bold blue",
        "pink": "bold magenta",
    }

    for hl in highlights:
        color_style = COLOR_STYLES.get(hl.get("color", "yellow"), "bold yellow")
        hl_id = hl["id"]
        page = hl.get("page", 0)
        text = hl.get("text", "")
        note = hl.get("note", "")
        color = hl.get("color", "yellow")

        # Truncate long text
        display_text = text if len(text) <= 80 else text[:77] + "..."

        console.print(f"  [{color_style}]#{hl_id}[/{color_style}] [dim](p.{page + 1}, {color})[/dim]")
        console.print(f"    {display_text}")
        if note:
            console.print(f"    [dim italic]Note: {note}[/dim italic]")
        console.print()

    console.print(f"  [dim]{len(highlights)} highlight(s)[/dim]")
    console.print()
