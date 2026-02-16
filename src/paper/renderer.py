"""Rich terminal output for paper content."""

from __future__ import annotations

import re
from dataclasses import dataclass

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.tree import Tree

from paper.models import Document, Section

console = Console()


@dataclass
class RefEntry:
    """A navigable reference shown in output."""
    ref_id: str    # "s3", "e1", "c5"
    kind: str      # "section", "external", "citation"
    label: str     # display label
    target: str    # section heading / URL / citation text


# TODO(v2): Figure/table refs [ref=f...] — needs caption detection
def build_ref_registry(doc: Document) -> list[RefEntry]:
    """Build the ref registry for a document.

    Order: s1..sN (sections), e1..eN (external links), c1..cN (citations).
    """
    registry: list[RefEntry] = []

    # Sections
    for i, section in enumerate(doc.sections, 1):
        registry.append(RefEntry(
            ref_id=f"s{i}",
            kind="section",
            label=section.heading,
            target=section.heading,
        ))

    # External links (unique URLs, in order of first appearance)
    seen_urls: set[str] = set()
    ext_idx = 0
    for link in doc.links:
        if link.kind == "external" and link.url not in seen_urls:
            seen_urls.add(link.url)
            ext_idx += 1
            registry.append(RefEntry(
                ref_id=f"e{ext_idx}",
                kind="external",
                label=link.text or link.url,
                target=link.url,
            ))

    # Citations (unique markers, in order of first appearance)
    seen_cites: set[str] = set()
    cite_idx = 0
    for link in doc.links:
        if link.kind == "citation" and link.text not in seen_cites:
            seen_cites.add(link.text)
            cite_idx += 1
            registry.append(RefEntry(
                ref_id=f"c{cite_idx}",
                kind="citation",
                label=link.text,
                target=link.text,
            ))

    return registry


def _ref_tag(ref_id: str) -> str:
    """Format a ref tag for display."""
    return f"[dim]\\[ref={ref_id}][/dim]"


def _section_ref_map(registry: list[RefEntry]) -> dict[str, str]:
    """Map section headings to their ref IDs."""
    return {
        entry.target: entry.ref_id
        for entry in registry
        if entry.kind == "section"
    }


def _ref_summary(registry: list[RefEntry]) -> str:
    """Build a compact ref summary line."""
    sections = [e for e in registry if e.kind == "section"]
    externals = [e for e in registry if e.kind == "external"]
    citations = [e for e in registry if e.kind == "citation"]

    parts = []
    if sections:
        parts.append(f"s1..s{len(sections)} (sections)")
    if externals:
        parts.append(f"e1..e{len(externals)} (links)")
    if citations:
        parts.append(f"c1..c{len(citations)} (citations)")

    if not parts:
        return ""
    return " · ".join(parts)


def _print_ref_footer(registry: list[RefEntry], paper_id: str = "") -> None:
    """Print the ref summary footer."""
    summary = _ref_summary(registry)
    if not summary:
        return
    console.print(f"[dim]Refs: {summary}[/dim]")
    id_hint = f" {paper_id}" if paper_id else " <id>"
    console.print(f"[dim]Use: paper goto{id_hint} <ref>[/dim]")
    console.print()


def annotate_text(text: str, doc: Document, registry: list[RefEntry]) -> str:
    """Insert [ref=...] annotations inline for citations and external links.

    Annotates the first occurrence of each citation marker and link anchor text.
    """
    # Build lookup maps
    cite_map: dict[str, str] = {}  # "[1]" -> "c1"
    for entry in registry:
        if entry.kind == "citation":
            cite_map[entry.label] = entry.ref_id

    ext_map: dict[str, str] = {}  # anchor text -> "e1"
    for entry in registry:
        if entry.kind == "external" and entry.label:
            ext_map[entry.label] = entry.ref_id

    # Annotate citations: [1] -> [1][ref=c1]
    annotated = text
    for marker, ref_id in cite_map.items():
        tag = f"\\[ref={ref_id}]"
        # Only annotate first occurrence to avoid clutter
        escaped_marker = re.escape(marker)
        annotated = re.sub(escaped_marker, lambda m: f"{m.group(0)}{tag}", annotated, count=1)

    return annotated


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


def render_outline(doc: Document, refs: bool = True) -> None:
    """Print the heading tree."""
    render_header(doc)

    registry = build_ref_registry(doc) if refs else []
    sec_refs = _section_ref_map(registry) if refs else {}

    tree = Tree("[bold]Outline[/bold]", guide_style="dim")
    # Track tree nodes by level for nesting
    level_nodes: dict[int, Tree] = {}

    for section in doc.sections:
        label = f"[bold]{section.heading}[/bold]" if section.level == 1 else section.heading
        if refs and section.heading in sec_refs:
            label += f" {_ref_tag(sec_refs[section.heading])}"
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

    if refs and registry:
        _print_ref_footer(registry, doc.metadata.arxiv_id)


def render_section(section: Section, show_heading: bool = True, refs: bool = True,
                   registry: list[RefEntry] | None = None,
                   sec_refs: dict[str, str] | None = None,
                   doc: Document | None = None) -> None:
    """Print a single section's content."""
    if show_heading:
        indent = "  " * (section.level - 1)
        heading_label = f"{indent}[bold cyan]{section.heading}[/bold cyan]"
        if refs and sec_refs and section.heading in sec_refs:
            heading_label += f" {_ref_tag(sec_refs[section.heading])}"
        console.print(heading_label)
        console.print()

    for sentence in section.sentences:
        text = sentence.text
        if refs and doc and registry:
            text = annotate_text(text, doc, registry)
        console.print(f"  {text}")

    if not section.sentences and section.content:
        # Fall back to raw content if no sentences parsed
        for line in section.content.split("\n"):
            if line.strip():
                text = line.strip()
                if refs and doc and registry:
                    text = annotate_text(text, doc, registry)
                console.print(f"  {text}")

    console.print()


def render_full(doc: Document, refs: bool = True) -> None:
    """Print the full paper."""
    render_header(doc)

    registry = build_ref_registry(doc) if refs else []
    sec_refs = _section_ref_map(registry) if refs else {}

    for section in doc.sections:
        render_section(section, refs=refs, registry=registry, sec_refs=sec_refs, doc=doc)

    if refs and registry:
        _print_ref_footer(registry, doc.metadata.arxiv_id)


def render_skim(doc: Document, num_lines: int = 2, max_level: int | None = None,
                refs: bool = True) -> None:
    """Print headings with first N sentences per section."""
    render_header(doc)

    registry = build_ref_registry(doc) if refs else []
    sec_refs = _section_ref_map(registry) if refs else {}

    for section in doc.sections:
        if max_level is not None and section.level > max_level:
            continue

        indent = "  " * (section.level - 1)
        heading_label = f"{indent}[bold cyan]{section.heading}[/bold cyan]"
        if refs and section.heading in sec_refs:
            heading_label += f" {_ref_tag(sec_refs[section.heading])}"
        console.print(heading_label)

        sentences = section.sentences[:num_lines]
        if sentences:
            for sent in sentences:
                text = sent.text
                if refs and registry:
                    text = annotate_text(text, doc, registry)
                console.print(f"{indent}  [dim]{text}[/dim]")
        elif section.content:
            # Fall back to first lines of raw content
            lines = [l.strip() for l in section.content.split("\n") if l.strip()]
            for line in lines[:num_lines]:
                text = line
                if refs and registry:
                    text = annotate_text(text, doc, registry)
                console.print(f"{indent}  [dim]{text}[/dim]")

        console.print()

    if refs and registry:
        _print_ref_footer(registry, doc.metadata.arxiv_id)


def render_search_results(
    doc: Document, query: str, context_lines: int = 2, refs: bool = True
) -> int:
    """Search and display matches with context. Returns match count."""
    render_header(doc)

    registry = build_ref_registry(doc) if refs else []
    sec_refs = _section_ref_map(registry) if refs else {}

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

            # Section heading with ref
            heading_label = section.heading
            if refs and section.heading in sec_refs:
                heading_label += f" {_ref_tag(sec_refs[section.heading])}"

            console.print(f"  [bold yellow]Match {match_count}[/bold yellow] in [cyan]{heading_label}[/cyan] (p.{section.page_start + 1})")

            # Highlight the match
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

    if refs and registry:
        _print_ref_footer(registry, doc.metadata.arxiv_id)

    return match_count


def render_goto(doc: Document, ref_id: str) -> bool:
    """Jump to a reference. Returns True if found, False otherwise."""
    registry = build_ref_registry(doc)
    sec_refs = _section_ref_map(registry)

    # Find the entry
    entry = None
    for e in registry:
        if e.ref_id == ref_id:
            entry = e
            break

    if entry is None:
        console.print(f"[red]Unknown ref: {ref_id}[/red]")
        console.print("[dim]Use paper outline or paper skim to see available refs.[/dim]")
        return False

    if entry.kind == "section":
        # Find and render the section
        for section in doc.sections:
            if section.heading == entry.target:
                render_header(doc)
                render_section(section, refs=True, registry=registry, sec_refs=sec_refs, doc=doc)
                _print_ref_footer(registry, doc.metadata.arxiv_id)
                return True
        console.print(f"[red]Section not found: {entry.target}[/red]")
        return False

    elif entry.kind == "external":
        render_header(doc)
        console.print(f"  [bold]Link {entry.ref_id}:[/bold] {entry.target}")
        # Find context: which page/section this link appeared in
        for link in doc.links:
            if link.kind == "external" and link.url == entry.target:
                # Find containing section
                for section in doc.sections:
                    if section.spans:
                        sec_start = section.spans[0].start
                        sec_end = section.spans[0].end
                        if sec_start <= link.span.start < sec_end:
                            console.print(f"  [dim]Found in: {section.heading} (p.{link.page + 1})[/dim]")
                            break
                break
        console.print()
        return True

    elif entry.kind == "citation":
        render_header(doc)
        console.print(f"  [bold]Citation {entry.ref_id}:[/bold] {entry.label}")
        console.print()

        # Try to find the matching entry in a References section
        ref_section = None
        for section in doc.sections:
            heading_lower = section.heading.lower()
            if "reference" in heading_lower or "bibliography" in heading_lower:
                ref_section = section
                break

        if ref_section:
            # Extract the number from the citation marker, e.g. "[1]" -> "1"
            nums = re.findall(r"\d+", entry.label)
            if nums:
                # Search for the reference entry in the section content
                for num in nums:
                    # Look for patterns like "[1]" or "1." at start of line in references
                    pattern = re.compile(
                        rf"(?:^|\n)\s*\[?{re.escape(num)}\]?[\.\)]\s*(.+?)(?=\n\s*\[?\d+\]?[\.\)]|\Z)",
                        re.DOTALL,
                    )
                    match = pattern.search(ref_section.content)
                    if match:
                        ref_text = match.group(0).strip()
                        # Clean up and limit length
                        ref_text = re.sub(r"\s+", " ", ref_text)
                        console.print(f"  [dim]{ref_text}[/dim]")
                        console.print()
        else:
            console.print("  [dim]No References section found in this paper.[/dim]")
            console.print()

        return True

    return False
