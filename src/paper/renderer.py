"""Rich terminal output for paper content."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.tree import Tree

from paper.models import Document, Highlight, LayoutElement, Link, Section
from paper import storage

console = Console()


@dataclass
class RefEntry:
    """A navigable reference shown in output."""
    ref_id: str    # "s3", "e1", "c5", "f1", "t1", "eq1"
    kind: str      # "section", "external", "citation", "figure", "table", "equation"
    label: str     # display label
    target: str    # section heading / URL / citation text / element label


def build_ref_registry(doc: Document) -> list[RefEntry]:
    """Build the ref registry for a document.

    Order: s1..sN (sections), f1..fN (figures), t1..tN (tables),
    eq1..eqN (equations), e1..eN (external links), c1..cN (citations).
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

    # Layout elements: figures, tables, equations
    _REF_PREFIX = {"figure": "f", "table": "t", "equation": "eq"}
    counters: dict[str, int] = {"figure": 0, "table": 0, "equation": 0}
    for elem in doc.layout_elements:
        counters[elem.kind] += 1
        prefix = _REF_PREFIX[elem.kind]
        ref_id = f"{prefix}{counters[elem.kind]}"
        registry.append(RefEntry(
            ref_id=ref_id,
            kind=elem.kind,
            label=elem.label or f"{elem.kind.title()} {counters[elem.kind]}",
            target=elem.label,
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
    figures = [e for e in registry if e.kind == "figure"]
    tables = [e for e in registry if e.kind == "table"]
    equations = [e for e in registry if e.kind == "equation"]
    externals = [e for e in registry if e.kind == "external"]
    citations = [e for e in registry if e.kind == "citation"]

    parts = []
    if sections:
        parts.append(f"s1..s{len(sections)} (sections)")
    if figures:
        parts.append(f"f1..f{len(figures)} (figures)")
    if tables:
        parts.append(f"t1..t{len(tables)} (tables)")
    if equations:
        parts.append(f"eq1..eq{len(equations)} (equations)")
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


def _build_cite_span_index(doc: Document, registry: list[RefEntry]) -> list[tuple[int, int, str]]:
    """Build a list of (start, end, ref_id) for citation links, sorted by start."""
    # Map citation labels to ref IDs
    label_to_ref: dict[str, str] = {}
    for entry in registry:
        if entry.kind == "citation":
            label_to_ref[entry.label] = entry.ref_id

    spans = []
    for link in doc.links:
        if link.kind == "citation" and link.text in label_to_ref:
            spans.append((link.span.start, link.span.end, label_to_ref[link.text]))
    spans.sort()
    return spans


def _find_cite_end_in_text(text: str, link: Link) -> int | None:
    """Find the end position of a citation within sentence text.

    Searches by author surname + year, falling back to year-only
    or bracket pattern for numeric citations.
    """
    author = re.match(r"\(?\s*([A-Z][a-z]+)", link.text)
    year_m = re.search(r"\d{4}", link.text)
    surname = author.group(1) if author else None
    year = year_m.group(0) if year_m else None

    def _skip_close(pos: int) -> int:
        """Advance past trailing whitespace and closing paren/bracket."""
        while pos < len(text) and text[pos] in " \t":
            pos += 1
        if pos < len(text) and text[pos] in ")]":
            pos += 1
        return pos

    # Strategy 1: surname + year (most precise)
    surname_found = False
    if surname and year:
        pos = 0
        while pos < len(text):
            name_idx = text.find(surname, pos)
            if name_idx == -1:
                break
            # Word boundary check — avoid "Hu" matching "Huh", etc.
            if name_idx > 0 and text[name_idx - 1].isalpha():
                pos = name_idx + 1
                continue
            end_of_name = name_idx + len(surname)
            if end_of_name < len(text) and text[end_of_name].isalpha():
                pos = name_idx + 1
                continue
            surname_found = True
            window = text[name_idx : name_idx + 150]
            yr_idx = window.find(year)
            if yr_idx >= 0:
                return _skip_close(name_idx + yr_idx + len(year))
            pos = name_idx + 1

    # Strategy 2: year only — when surname wasn't found in text (cross-line
    # citations) or doesn't exist.  Skipped when surname WAS found to avoid
    # placing "Hao, 2024" at "Huh, 2024" when only one year in text.
    if year and not surname_found:
        positions = [m.start() for m in re.finditer(re.escape(year), text)]
        if len(positions) == 1:
            return _skip_close(positions[0] + len(year))

    # Strategy 3: numeric citation bracket pattern
    if link.text.startswith("[") and link.text.endswith("]"):
        idx = text.find(link.text)
        if idx >= 0:
            return idx + len(link.text)

    return None


def annotate_text(
    text: str, doc: Document, registry: list[RefEntry],
    span_start: int = -1, span_end: int = -1,
    seen_refs: set[str] | None = None,
) -> str:
    """Insert [ref=...] tags inline at citation positions.

    Uses character-offset overlap to find which citations are in this text,
    then searches the text for each citation to place the ref tag right
    after it (rather than appending at end).
    """
    if not registry:
        return text

    cite_spans = _build_cite_span_index(doc, registry)

    if span_start >= 0 and span_end >= 0:
        # Find overlapping citations (skip already-seen refs)
        overlapping: list[tuple[int, int, str]] = []
        for cs, ce, ref_id in cite_spans:
            if cs >= span_end:
                break
            if ce > span_start:
                if seen_refs is None or ref_id not in seen_refs:
                    overlapping.append((cs, ce, ref_id))

        if not overlapping:
            return text

        # Build ref_id -> Link lookup
        label_to_ref = {e.label: e.ref_id for e in registry if e.kind == "citation"}
        ref_to_link: dict[str, Link] = {}
        for link in doc.links:
            if link.kind == "citation" and link.text in label_to_ref:
                rid = label_to_ref[link.text]
                if rid not in ref_to_link:
                    ref_to_link[rid] = link

        # Find inline insertion positions — only place refs we can locate;
        # skip unfound refs so the next sentence can claim them.
        insertions: list[tuple[int, str]] = []  # (position, ref_id)

        for _, _, ref_id in overlapping:
            link = ref_to_link.get(ref_id)
            pos = _find_cite_end_in_text(text, link) if link else None
            if pos is not None:
                insertions.append((pos, ref_id))
                if seen_refs is not None:
                    seen_refs.add(ref_id)

        if not insertions:
            return text

        # Sort rightmost first for safe insertion (avoids offset shifting)
        insertions.sort(key=lambda x: -x[0])

        result = text
        for pos, ref_id in insertions:
            tag = f" [dim]\\[ref={ref_id}][/dim]"
            result = result[:pos] + tag + result[pos:]

        return result

    # Fallback: text-based matching for raw content lines without spans
    label_to_ref_fb: dict[str, str] = {}
    for entry in registry:
        if entry.kind == "citation":
            if seen_refs is None or entry.ref_id not in seen_refs:
                label_to_ref_fb[entry.label] = entry.ref_id

    annotated = text
    for marker, ref_id in label_to_ref_fb.items():
        tag = f" [dim]\\[ref={ref_id}][/dim]"
        escaped_marker = re.escape(marker)
        match = re.search(escaped_marker, annotated)
        if match:
            annotated = annotated[:match.end()] + tag + annotated[match.end():]
            if seen_refs is not None:
                seen_refs.add(ref_id)

    return annotated


def render_header(doc: Document) -> None:
    """Print paper title and metadata.

    Auto-suppresses if the same paper's header was shown recently
    (within the TTL window). Keeps the TTL alive on each call so
    consecutive commands on the same paper never repeat the header.
    """
    paper_id = doc.metadata.arxiv_id or ""

    if paper_id and storage.was_header_shown_recently(paper_id):
        storage.mark_header_shown(paper_id)  # refresh TTL
        return

    if paper_id:
        storage.mark_header_shown(paper_id)

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


def render_outline(doc: Document, refs: bool = True, show_header: bool = True) -> None:
    """Print the heading tree."""
    if show_header:
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
                   doc: Document | None = None,
                   max_lines: int | None = None,
                   paper_id: str = "") -> None:
    """Print a single section's content.

    Refs annotate inline citations/links (navigation targets), not the
    section heading itself — the heading is where you already are.
    If max_lines is set, truncate and show a "show more" hint.
    """
    if show_heading:
        indent = "  " * (section.level - 1)
        heading_label = f"{indent}[bold cyan]{section.heading}[/bold cyan]"
        console.print(heading_label)
        console.print()

    seen_refs: set[str] = set()

    sentences = section.sentences
    total = len(sentences)
    truncated = False

    if max_lines and total > max_lines:
        sentences = sentences[:max_lines]
        truncated = True

    for sentence in sentences:
        text = sentence.text
        if refs and doc and registry:
            text = annotate_text(text, doc, registry,
                                 span_start=sentence.span.start, span_end=sentence.span.end,
                                 seen_refs=seen_refs)
        console.print(f"  {text}")

    if not section.sentences and section.content:
        # Fall back to raw content if no sentences parsed
        lines = [l.strip() for l in section.content.split("\n") if l.strip()]
        total = len(lines)
        if max_lines and total > max_lines:
            lines = lines[:max_lines]
            truncated = True
        for line in lines:
            text = line
            if refs and doc and registry:
                text = annotate_text(text, doc, registry, seen_refs=seen_refs)
            console.print(f"  {text}")

    console.print()

    if truncated:
        id_hint = f" {paper_id}" if paper_id else ""
        console.print(f"[dim]Showing {max_lines} of {total} sentences. "
                      f"Use: paper read{id_hint} \"{section.heading}\" --max-lines 0[/dim]")
        console.print()


def render_full(doc: Document, refs: bool = True, show_header: bool = True) -> None:
    """Print the full paper."""
    if show_header:
        render_header(doc)

    registry = build_ref_registry(doc) if refs else []

    for section in doc.sections:
        render_section(section, refs=refs, registry=registry, doc=doc)

    if refs and registry:
        _print_ref_footer(registry, doc.metadata.arxiv_id)


def render_skim(doc: Document, num_lines: int = 2, max_level: int | None = None,
                refs: bool = True, show_header: bool = True) -> None:
    """Print headings with first N sentences per section."""
    if show_header:
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
        seen_refs: set[str] = set()
        if sentences:
            for sent in sentences:
                text = sent.text
                if refs and registry:
                    text = annotate_text(text, doc, registry,
                                         span_start=sent.span.start, span_end=sent.span.end,
                                         seen_refs=seen_refs)
                console.print(f"{indent}  [dim]{text}[/dim]")
        elif section.content:
            # Fall back to first lines of raw content
            lines = [l.strip() for l in section.content.split("\n") if l.strip()]
            for line in lines[:num_lines]:
                text = line
                if refs and registry:
                    text = annotate_text(text, doc, registry, seen_refs=seen_refs)
                console.print(f"{indent}  [dim]{text}[/dim]")

        console.print()

    if refs and registry:
        _print_ref_footer(registry, doc.metadata.arxiv_id)


def render_search_results(
    doc: Document, query: str, context_lines: int = 2, refs: bool = True,
    show_header: bool = True,
) -> int:
    """Search and display matches with context. Returns match count."""
    if show_header:
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


def render_highlight_matches(
    matches: list[dict], query: str, doc: Document, show_header: bool = True,
) -> None:
    """Render highlight search matches with context."""
    if show_header:
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


def render_highlight_list(highlights: list[dict], doc: Document, show_header: bool = True) -> None:
    """Render stored highlights for a paper."""
    if show_header:
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


def _resolve_citation_text(
    doc: Document, cite_link: Link | None, entry: RefEntry
) -> str | None:
    """Resolve citation to its full reference text.

    Strategy 1: If the link has a target page, open the cached PDF, search
    for the author name on that page, and extract the reference entry.
    Strategy 2: Search for the citation in a References/Bibliography section
    using text matching (for numeric citations).
    """
    # Strategy 1: Search the target page in the PDF for the author name
    if cite_link and cite_link.target_page >= 0:
        pdf_path = storage.pdf_path(doc.metadata.arxiv_id)
        if pdf_path.exists():
            ref_text = _extract_ref_from_pdf(pdf_path, cite_link)
            if ref_text:
                return ref_text

    # Strategy 2: Search in References/Bibliography section (numeric citations)
    ref_section = None
    for section in doc.sections:
        heading_lower = section.heading.lower()
        if "reference" in heading_lower or "bibliography" in heading_lower:
            ref_section = section
            break

    if ref_section:
        nums = re.findall(r"\d+", entry.label)
        if nums:
            for num in nums:
                pattern = re.compile(
                    rf"(?:^|\n)\s*\[?{re.escape(num)}\]?[\.\)]\s*(.+?)(?=\n\s*\[?\d+\]?[\.\)]|\Z)",
                    re.DOTALL,
                )
                match = pattern.search(ref_section.content)
                if match:
                    ref_text = match.group(0).strip()
                    return re.sub(r"\s+", " ", ref_text)

    return None


def _extract_ref_from_pdf(pdf_path: Path, cite_link: Link) -> str | None:
    """Open the PDF and extract reference text by searching the target page.

    LaTeX named destinations often have inaccurate y-coordinates, so
    we search for the author surname on the target page instead.
    """
    try:
        import fitz
    except ImportError:
        return None

    # Extract author surname from citation text
    # "(Kingma & Ba, 2015)" -> "Kingma"
    # "(Zhao et al., 2024)" -> "Zhao"
    # "Houlsby et al., 2019;" -> "Houlsby"
    author = re.match(r"\(?\s*([A-Z][a-z]+)", cite_link.text)
    if not author:
        return None
    surname = author.group(1)

    # Also extract the year for disambiguation
    year_match = re.search(r"\d{4}", cite_link.text)
    year = year_match.group(0) if year_match else ""

    try:
        with fitz.open(pdf_path) as pdf:
            page = pdf[cite_link.target_page]

            # Search for "Surname," on the target page
            instances = page.search_for(f"{surname},")
            if not instances:
                instances = page.search_for(surname)
            if not instances:
                return None

            # Filter to instances near a column margin (start of a bib entry).
            # Two-column layouts have left col at ~35-80pt, right col at ~290-320pt.
            # Entries that appear mid-line (indented continuations or co-author
            # mentions) have higher x0 values within their column.
            pw = page.rect.width
            col2_start = pw / 2 - 20  # ~290 for 612pt page
            margin_instances = [
                r for r in instances
                if r.x0 < 100 or (col2_start < r.x0 < col2_start + 50)
            ]
            candidates = margin_instances if margin_instances else instances

            # If multiple matches, prefer the one whose surrounding text
            # contains the year (disambiguates "Zhao" in other entries)
            best_rect = candidates[0]
            if year and len(candidates) > 1:
                for r in candidates:
                    clip = fitz.Rect(0, r.y0 - 2, page.rect.width, r.y0 + 40)
                    nearby = page.get_text("text", clip=clip)
                    if year in nearby:
                        best_rect = r
                        break

            # Extract text from the matched position, constrained to the
            # correct column in two-column layouts
            if best_rect.x0 > pw / 2 - 20:
                # Right column
                col_left = pw / 2 - 20
                col_right = pw
            else:
                # Left column (or single-column)
                col_left = 0
                col_right = pw / 2 - 20 if pw > 500 else pw

            clip = fitz.Rect(col_left, best_rect.y0 + 1, col_right, best_rect.y0 + 42)
            text = page.get_text("text", clip=clip).strip()

            if not text:
                return None

            # Clean up and trim to start from the author surname
            text = re.sub(r"\s+", " ", text)
            idx = text.find(f"{surname},")
            if idx == -1:
                idx = text.find(surname)
            if idx > 0:
                text = text[idx:]
            return text
    except Exception:
        return None


def render_goto(doc: Document, ref_id: str, show_header: bool = True) -> bool:
    """Jump to a reference. Returns True if found, False otherwise."""
    registry = build_ref_registry(doc)

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

    max_sentences = 10
    paper_id = doc.metadata.arxiv_id

    if entry.kind == "section":
        # Find and render a preview of the section
        for section in doc.sections:
            if section.heading == entry.target:
                if show_header:
                    render_header(doc)

                # Print heading (no section ref — you're already navigating here)
                indent = "  " * (section.level - 1)
                heading_label = f"{indent}[bold cyan]{section.heading}[/bold cyan]"
                console.print(heading_label)
                console.print()

                # Print up to max_sentences with inline citation refs
                total = len(section.sentences)
                shown = section.sentences[:max_sentences]
                seen_refs: set[str] = set()
                for sent in shown:
                    text = annotate_text(sent.text, doc, registry,
                                         span_start=sent.span.start, span_end=sent.span.end,
                                         seen_refs=seen_refs)
                    console.print(f"  {text}")

                if not shown and section.content:
                    lines = [l.strip() for l in section.content.split("\n") if l.strip()]
                    total = len(lines)
                    for line in lines[:max_sentences]:
                        text = annotate_text(line, doc, registry, seen_refs=seen_refs)
                        console.print(f"  {text}")

                console.print()

                if total > max_sentences:
                    console.print(f"[dim]Showing {max_sentences} of {total} sentences. Full section: paper read {paper_id} \"{section.heading}\"[/dim]")
                    console.print()

                _print_ref_footer(registry, paper_id)
                return True
        console.print(f"[red]Section not found: {entry.target}[/red]")
        return False

    elif entry.kind == "external":
        if show_header:
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
        if show_header:
            render_header(doc)
        console.print(f"  [bold]Citation {entry.ref_id}:[/bold] {entry.label}")
        console.print()

        # Find the matching Link to get target coordinates
        cite_link = None
        for link in doc.links:
            if link.kind == "citation" and link.text == entry.label:
                cite_link = link
                break

        ref_text = _resolve_citation_text(doc, cite_link, entry)
        if ref_text:
            console.print(f"  [dim]{ref_text}[/dim]")
        else:
            console.print("  [dim]Could not resolve reference text.[/dim]")
        console.print()
        return True

    elif entry.kind in ("figure", "table", "equation"):
        # Find matching layout element
        for elem in doc.layout_elements:
            if elem.label == entry.target:
                if show_header:
                    render_header(doc)
                _render_layout_element(elem, entry.ref_id)
                return True
        console.print(f"[red]Layout element not found: {entry.target}[/red]")
        return False

    return False


def _render_layout_element(elem: LayoutElement, ref_id: str) -> None:
    """Render a single layout element (figure, table, or equation)."""
    kind_style = {"figure": "green", "table": "blue", "equation": "magenta"}
    style = kind_style.get(elem.kind, "white")

    console.print(f"  [bold {style}]{elem.label}[/bold {style}] {_ref_tag(ref_id)}")
    console.print(f"  [dim]Page {elem.box.page + 1} · "
                  f"bbox ({elem.box.x0:.0f}, {elem.box.y0:.0f}, {elem.box.x1:.0f}, {elem.box.y1:.0f}) · "
                  f"conf {elem.confidence:.0%}[/dim]")
    if elem.image_path:
        console.print(f"  [dim]Image:[/dim] {elem.image_path}")
    if elem.caption:
        console.print(f"  {elem.caption}")
    console.print()


def render_layout_list(
    doc: Document, kind: str | None = None, show_header: bool = True,
) -> None:
    """List detected layout elements (figures, tables, equations).

    If kind is None, show all; otherwise filter to that kind.
    """
    if show_header:
        render_header(doc)

    registry = build_ref_registry(doc)
    elements = doc.layout_elements
    if kind:
        elements = [e for e in elements if e.kind == kind]

    if not elements:
        label = kind or "layout element"
        console.print(f"  [dim]No {label}s detected.[/dim]")
        console.print(f"  [dim]Run: paper detect <id> to trigger layout detection.[/dim]")
        console.print()
        return

    ref_map: dict[str, str] = {}
    for entry in registry:
        if entry.kind in ("figure", "table", "equation"):
            ref_map[entry.target] = entry.ref_id

    for elem in elements:
        ref_id = ref_map.get(elem.label, "")
        _render_layout_element(elem, ref_id)

    kind_label = kind or "element"
    console.print(f"  [dim]{len(elements)} {kind_label}(s) detected[/dim]")
    console.print()

    _print_ref_footer(registry, doc.metadata.arxiv_id)
