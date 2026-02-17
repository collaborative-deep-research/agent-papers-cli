"""Parse PDFs into structured Document objects using PyMuPDF + PySBD.

NOTE: The current heading detection uses font-size heuristics which are fragile
across different paper styles/templates. A future version should support GROBID
(https://github.com/kermitt2/grobid) as an alternative parsing backend — GROBID
uses ML models trained on millions of papers and produces much more reliable
section/heading extraction via TEI XML output. The parser interface (parse_paper)
is designed to make this a drop-in replacement.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import fitz  # PyMuPDF
import pysbd

from paper.models import Box, Document, Link, Metadata, Section, Sentence, Span
from paper import storage

# Patterns for filtering false-positive headings
_ARXIV_HEADER_RE = re.compile(r"arXiv:\d+\.\d+", re.IGNORECASE)
_SECTION_NUM_RE = re.compile(r"^[A-Z]?\.?\d*\.?\d*$")  # "1", "2.1", "A", "A.1"
_FIGURE_TABLE_RE = re.compile(r"^(Figure|Table|Fig\.)\s+\d+", re.IGNORECASE)
_CITATION_RE = re.compile(r"\[(\d+(?:\s*[,;\u2013-]\s*\d+)*)\]")


def parse_paper(arxiv_id: str, pdf_path: Path) -> Document:
    """Parse a PDF into a structured Document.

    Uses cached result if available.
    """
    if storage.has_parsed(arxiv_id):
        return Document.load(storage.parsed_path(arxiv_id))

    with fitz.open(pdf_path) as doc_fitz:
        document = _extract_document(doc_fitz, arxiv_id)

    # Cache the parsed result
    document.save(storage.parsed_path(arxiv_id))

    # Update index with title
    if document.metadata.title:
        storage.update_index(arxiv_id, document.metadata.title)

    return document


def _extract_document(doc_fitz: fitz.Document, arxiv_id: str) -> Document:
    """Extract text, detect headings, segment sections, split sentences."""
    # Step 1: Extract all text lines with font info
    lines = _extract_lines(doc_fitz)

    # Step 2: Determine body font size (most common)
    body_size = _detect_body_font_size(lines)

    # Step 3: Build raw text with character offsets
    raw_text, lines = _build_raw_text(lines)

    # Step 4: Try PDF outline first, fall back to font-based headings
    headings = _extract_headings_from_outline(doc_fitz)
    if headings:
        headings = _resolve_outline_offsets(headings, lines)
    else:
        headings = _extract_headings_from_fonts(lines, body_size)

    # Step 5: Merge adjacent heading fragments (e.g., "1" + "Introduction")
    headings = _merge_heading_fragments(headings)

    # Step 6: Segment into sections
    sections = _segment_sections(raw_text, lines, headings)

    # Step 7: Split sentences in each section
    _split_sentences(sections)

    # Step 8: Extract metadata
    metadata = _extract_metadata(doc_fitz, lines, body_size, arxiv_id)

    # Step 9: Page info
    pages = [
        {"page_number": i, "width": p.rect.width, "height": p.rect.height}
        for i, p in enumerate(doc_fitz)
    ]

    # Step 10: Extract links
    links = _extract_links(doc_fitz, raw_text, lines)
    links.extend(_detect_citations(raw_text))

    return Document(
        metadata=metadata,
        sections=sections,
        raw_text=raw_text,
        pages=pages,
        links=links,
    )


@dataclass
class _Line:
    """A merged text line (all spans on one visual line combined)."""
    text: str
    font_size: float  # dominant font size
    font_name: str
    is_bold: bool
    page: int
    bbox: tuple[float, float, float, float]
    char_start: int = 0
    char_end: int = 0


def _extract_lines(doc_fitz: fitz.Document) -> list[_Line]:
    """Extract text as merged lines (not individual spans)."""
    all_lines = []
    for page_num, page in enumerate(doc_fitz):
        blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
        for block in blocks:
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                spans = line.get("spans", [])
                if not spans:
                    continue

                # Merge all spans in this line
                parts = []
                size_weight: Counter[float] = Counter()
                any_bold = False
                font_names: Counter[str] = Counter()

                for span in spans:
                    text = span["text"]
                    if not text.strip():
                        continue
                    parts.append(text)
                    size = round(span["size"], 1)
                    size_weight[size] += len(text)
                    fname = span.get("font", "")
                    font_names[fname] += len(text)
                    if "bold" in fname.lower() or "Medium" in fname or fname.endswith("-Medi"):
                        any_bold = True

                merged_text = " ".join(parts).strip()
                # Collapse multiple spaces
                merged_text = re.sub(r"\s+", " ", merged_text)
                if not merged_text:
                    continue

                dominant_size = size_weight.most_common(1)[0][0] if size_weight else 10.0
                dominant_font = font_names.most_common(1)[0][0] if font_names else ""
                bbox = line["bbox"]

                all_lines.append(_Line(
                    text=merged_text,
                    font_size=dominant_size,
                    font_name=dominant_font,
                    is_bold=any_bold,
                    page=page_num,
                    bbox=tuple(bbox),
                ))
    return all_lines


def _detect_body_font_size(lines: list[_Line]) -> float:
    """Find the most common font size (= body text)."""
    size_counts: Counter[float] = Counter()
    for ln in lines:
        size_counts[ln.font_size] += len(ln.text)
    if not size_counts:
        return 10.0
    return size_counts.most_common(1)[0][0]


def _build_raw_text(lines: list[_Line]) -> tuple[str, list[_Line]]:
    """Concatenate lines into raw_text, recording character offsets."""
    parts: list[str] = []
    offset = 0

    for ln in lines:
        if offset > 0:
            parts.append("\n")
            offset += 1
        ln.char_start = offset
        ln.char_end = offset + len(ln.text)
        parts.append(ln.text)
        offset = ln.char_end

    return "".join(parts), lines


def _extract_headings_from_outline(doc_fitz: fitz.Document) -> list[dict]:
    """Try to get headings from PDF's built-in outline/ToC."""
    toc = doc_fitz.get_toc()
    if not toc or len(toc) < 3:
        return []

    headings = []
    for level, title, page_num in toc:
        headings.append({
            "heading": title.strip(),
            "level": level,
            "page": page_num - 1,  # 0-indexed
        })
    return headings


def _resolve_outline_offsets(
    headings: list[dict], lines: list[_Line]
) -> list[dict]:
    """Match outline headings to lines to populate char_start/char_end.

    Outline headings from get_toc() only have page numbers, not character
    offsets.  We find each heading's text in the lines on its target page.
    """
    resolved = []
    for h in headings:
        page = h["page"]
        heading_text = h["heading"]
        heading_lower = heading_text.lower().strip()

        best_line = None
        best_score = 0

        for ln in lines:
            if ln.page != page:
                continue
            ln_lower = ln.text.lower().strip()
            # Exact match
            if ln_lower == heading_lower:
                best_line = ln
                break
            # Substring match (heading text appears in line or vice versa)
            if heading_lower in ln_lower or ln_lower in heading_lower:
                score = len(heading_lower) / max(len(ln_lower), 1)
                if score > best_score:
                    best_score = score
                    best_line = ln

        if best_line:
            resolved.append({
                **h,
                "char_start": best_line.char_start,
                "char_end": best_line.char_end,
            })
        else:
            # Fallback: use the first line on the target page
            for ln in lines:
                if ln.page == page:
                    resolved.append({
                        **h,
                        "char_start": ln.char_start,
                        "char_end": ln.char_end,
                    })
                    break
            else:
                resolved.append(h)

    return resolved


def _is_false_positive_heading(text: str, page: int, is_first_heading: bool) -> bool:
    """Filter out things that look like headings but aren't."""
    # arxiv header line
    if _ARXIV_HEADER_RE.search(text):
        return True
    # Figure/Table captions
    if _FIGURE_TABLE_RE.match(text):
        return True
    # Very long text is not a heading
    if len(text) > 80:
        return True
    # Text with colon followed by content (body text pattern like
    # "Example: the model predicted..." or "backstory: Jaxon said...")
    colon_idx = text.find(": ")
    if colon_idx >= 0 and len(text) - colon_idx > 4:
        return True
    # Text ending with period that doesn't look like a numbered section
    # (e.g., "English CommonCrawl [67%].", "Rotary Embeddings [GPTNeo]. We remove the")
    if text.endswith(".") and not re.match(r"^\d+\.\s", text):
        return True
    if ". " in text and len(text) > 60:
        return True
    # Purely numeric / table data (e.g., "88.0 81.1", "88.0", "24.9 31.0")
    # but NOT short section numbers like "3", "4.1", "12"
    if re.match(r"^[\d\s.,\-+%]+$", text):
        stripped = text.strip()
        if not (_SECTION_NUM_RE.match(stripped) and len(stripped) <= 3):
            return True
    # Author lists (contain ∗ † or affiliation symbols ♣ ♢ ♠)
    if any(c in text for c in "∗†♣♢♠♦♯♮"):
        return True
    # Text ending with comma, question mark, or hyphen (word break)
    if text.endswith(",") or text.endswith("?") or text.endswith("-"):
        return True
    return False


def _extract_headings_from_fonts(
    lines: list[_Line], body_size: float
) -> list[dict]:
    """Detect headings by font size and bold style relative to body text."""
    # Threshold: section headings are usually noticeably larger than body
    heading_threshold = body_size * 1.15

    # Collect distinct heading font sizes for level assignment
    candidate_sizes = set()
    for ln in lines:
        if ln.font_size > heading_threshold and not _is_false_positive_heading(ln.text, ln.page, False):
            candidate_sizes.add(ln.font_size)

    # Also consider bold-at-body-size as the lowest heading level
    heading_sizes = sorted(candidate_sizes, reverse=True)

    # Assign levels: largest = 1, next = 2, etc.
    size_to_level = {size: i + 1 for i, size in enumerate(heading_sizes)}
    bold_heading_level = len(heading_sizes) + 1

    # Identify title font size (largest on page 0, excluding arXiv header)
    page0 = [
        ln for ln in lines
        if ln.page == 0 and not _ARXIV_HEADER_RE.search(ln.text)
    ]
    title_size = max((ln.font_size for ln in page0), default=0) if page0 else 0

    headings = []
    seen_first_section = False

    for ln in lines:
        if _is_false_positive_heading(ln.text, ln.page, not seen_first_section):
            continue

        is_heading = False
        level = 0

        if ln.font_size > heading_threshold:
            # Skip title-sized text (title + subtitle, within 1pt)
            if ln.font_size >= title_size - 1.0 and ln.page == 0:
                continue
            # On page 0, before we've seen a real section heading,
            # only accept things that look like actual sections (not author names)
            if ln.page == 0 and not seen_first_section and not _looks_like_section_heading(ln.text):
                continue
            is_heading = True
            level = size_to_level.get(ln.font_size, 1)

        elif ln.is_bold and ln.font_size >= body_size * 0.95:
            # Bold body-sized text: only if it looks like a section heading
            if _looks_like_section_heading(ln.text):
                is_heading = True
                level = bold_heading_level

        if is_heading:
            seen_first_section = True
            headings.append({
                "heading": ln.text,
                "level": level,
                "page": ln.page,
                "char_start": ln.char_start,
                "char_end": ln.char_end,
                "font_size": ln.font_size,
            })

    return headings


def _looks_like_section_heading(text: str) -> bool:
    """Check if text looks like a plausible section heading."""
    text = text.strip()
    # Section with number: "1 Introduction", "2.1 Data", "A Appendix"
    if re.match(r"^[A-Z]?\d*\.?\d*\s+[A-Z]", text):
        return True
    # Common heading keywords — only trusted for short, capitalized text
    # (body text like "Our experiments are conducted..." also contains these)
    keywords = [
        "abstract", "introduction", "related work", "background",
        "method", "approach", "model", "experiment", "result",
        "discussion", "conclusion", "acknowledgement", "reference",
        "appendix", "supplementary", "evaluation", "analysis",
        "limitation", "future work", "overview", "preliminar",
        "setup", "dataset", "training", "implementation",
    ]
    text_lower = text.lower()
    if text[0].isupper() and len(text) < 40:
        for kw in keywords:
            if kw in text_lower:
                return True
    # Bare section number: "1", "2", "A", "B.1"
    if _SECTION_NUM_RE.match(text):
        return True
    # Short capitalized text without mid-sentence punctuation (likely heading).
    # For multi-word text, check title case: the last substantive word should
    # be capitalized to distinguish headings from body text fragments like
    # "Communicating Desires as Demands pressures".
    if len(text) < 50 and text[0].isupper() and not text.endswith(".") and ". " not in text:
        words = text.split()
        if len(words) <= 3:
            return True
        # Check that last non-trivial word (>3 chars) is capitalized
        substantive = [w for w in words if len(w) > 3 and w.isalpha()]
        if substantive and substantive[-1][0].isupper():
            return True
    return False


_TRAILING_CONJUNCTIONS = {"and", "or", "of", "for", "in", "the", "with", "to", "a", "an", "on", "by"}


def _merge_heading_fragments(headings: list[dict]) -> list[dict]:
    """Merge consecutive headings that are fragments of the same heading.

    Handles two cases:
    1. Bare section number followed by title: "1" + "Introduction"
    2. Heading ending with conjunction: "Detection and" + "Reframing"
    """
    if len(headings) < 2:
        return headings

    merged = []
    i = 0
    while i < len(headings):
        h = headings[i]

        # Check if this is a bare section number followed by a title
        if (
            i + 1 < len(headings)
            and _SECTION_NUM_RE.match(h["heading"].strip())
            and headings[i + 1]["page"] == h["page"]
            and "font_size" in headings[i + 1]
            and "font_size" in h
            and abs(headings[i + 1]["font_size"] - h["font_size"]) < 1.0
        ):
            next_h = headings[i + 1]
            combined = {
                "heading": f"{h['heading']} {next_h['heading']}",
                "level": min(h["level"], next_h["level"]),
                "page": h["page"],
                "char_start": h["char_start"],
                "char_end": next_h["char_end"],
            }
            i += 2
            # Continue merging while heading looks incomplete:
            # - ends with conjunction/preposition, OR
            # - next heading is a single non-number word (continuation like
            #   "3" + "Non-Violent Communication" + "Framework")
            while (
                i < len(headings)
                and headings[i]["page"] == combined["page"]
                and "font_size" in headings[i]
                and abs(headings[i].get("font_size", 0) - next_h.get("font_size", 0)) < 1.0
                and (
                    combined["heading"].split()[-1].lower() in _TRAILING_CONJUNCTIONS
                    or (
                        len(headings[i]["heading"].split()) == 1
                        and not _SECTION_NUM_RE.match(headings[i]["heading"].strip())
                    )
                )
            ):
                combined["heading"] += f" {headings[i]['heading']}"
                combined["char_end"] = headings[i]["char_end"]
                i += 1
            merged.append(combined)

        # Heading ending with conjunction: merge with next
        elif (
            i + 1 < len(headings)
            and h["heading"].split()[-1].lower() in _TRAILING_CONJUNCTIONS
            and headings[i + 1]["page"] == h["page"]
            and "font_size" in headings[i + 1]
            and "font_size" in h
            and abs(headings[i + 1]["font_size"] - h["font_size"]) < 1.0
        ):
            next_h = headings[i + 1]
            merged.append({
                "heading": f"{h['heading']} {next_h['heading']}",
                "level": min(h["level"], next_h["level"]),
                "page": h["page"],
                "char_start": h["char_start"],
                "char_end": next_h["char_end"],
            })
            i += 2
        else:
            merged.append(h)
            i += 1

    return merged


def _segment_sections(
    raw_text: str,
    lines: list[_Line],
    headings: list[dict],
) -> list[Section]:
    """Split document into sections based on detected headings."""
    if not headings:
        return [Section(
            heading="(Full Document)",
            level=1,
            content=raw_text,
            spans=[Span(start=0, end=len(raw_text))],
            page_start=lines[0].page if lines else 0,
            page_end=lines[-1].page if lines else 0,
        )]

    sections = []

    for i, h in enumerate(headings):
        start = h.get("char_start", 0)
        if i + 1 < len(headings):
            end = headings[i + 1].get("char_start", len(raw_text))
        else:
            end = len(raw_text)

        content = raw_text[start:end].strip()
        # Remove the heading text from the content body
        heading_text = h["heading"]
        if content.startswith(heading_text):
            content = content[len(heading_text):].strip()

        page_start = h.get("page", 0)
        page_end = page_start
        for ln in lines:
            if ln.char_start >= start and ln.char_start < end:
                page_end = max(page_end, ln.page)

        sections.append(Section(
            heading=heading_text,
            level=h["level"],
            content=content,
            spans=[Span(start=start, end=end)],
            page_start=page_start,
            page_end=page_end,
        ))

    return sections


def _split_sentences(sections: list[Section]) -> None:
    """Split each section's content into sentences using PySBD."""
    segmenter = pysbd.Segmenter(language="en", clean=False)

    for section in sections:
        if not section.content:
            continue

        sentence_texts = segmenter.segment(section.content)
        offset = 0
        for sent_text in sentence_texts:
            sent_text = sent_text.strip()
            if not sent_text:
                continue

            idx = section.content.find(sent_text, offset)
            if idx == -1:
                idx = offset

            section_start = section.spans[0].start if section.spans else 0
            abs_start = section_start + idx
            abs_end = abs_start + len(sent_text)

            section.sentences.append(Sentence(
                text=sent_text,
                span=Span(start=abs_start, end=abs_end),
                page=section.page_start,
            ))
            offset = idx + len(sent_text)


def _extract_metadata(
    doc_fitz: fitz.Document,
    lines: list[_Line],
    body_size: float,
    arxiv_id: str,
) -> Metadata:
    """Extract title and basic metadata."""
    page1_lines = [ln for ln in lines if ln.page == 0]
    title = ""
    if page1_lines:
        # Title = largest font on page 1, excluding arxiv header
        candidates = [
            ln for ln in page1_lines
            if not _ARXIV_HEADER_RE.search(ln.text)
        ]
        if candidates:
            largest = max(candidates, key=lambda ln: ln.font_size)
            title = largest.text.strip()

    pdf_meta = doc_fitz.metadata or {}

    return Metadata(
        title=title or pdf_meta.get("title", ""),
        authors=[a.strip() for a in pdf_meta.get("author", "").split(",") if a.strip()],
        arxiv_id=arxiv_id,
        url=f"https://arxiv.org/abs/{arxiv_id}",
    )


# TODO(v2): Figure/table refs [ref=f...] — needs caption detection
def _extract_links(
    doc_fitz: fitz.Document,
    raw_text: str,
    lines: list[_Line],
) -> list[Link]:
    """Extract external, internal, and citation links from the PDF.

    Handles three PyMuPDF link kinds:
    - LINK_URI (2): external URLs
    - LINK_GOTO (1): internal page jumps
    - LINK_NAMED (4): named destinations — citation links in LaTeX PDFs
      have nameddest like "cite.adam"; often split across multiple rects
      (e.g., "(Kingma & Ba," + "2015)") which we merge by nameddest.
    """
    results: list[Link] = []
    seen_urls: set[str] = set()

    # Collect LINK_NAMED fragments in document order so we can group
    # consecutive same-dest fragments on the same page (split citations
    # like "(Kingma & Ba," + "2015)").
    named_in_order: list[tuple[str, int, fitz.Rect, int]] = []

    for page_num, page in enumerate(doc_fitz):
        page_links = page.get_links()
        for link in page_links:
            kind_code = link.get("kind", -1)
            from_rect = link.get("from", fitz.Rect())

            if kind_code == fitz.LINK_URI:
                anchor_text, span = _find_anchor(lines, page_num, from_rect)
                url = link.get("uri", "")
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                results.append(Link(
                    kind="external",
                    text=anchor_text,
                    url=url,
                    target_page=-1,
                    page=page_num,
                    span=span,
                ))

            elif kind_code == fitz.LINK_GOTO:
                anchor_text, span = _find_anchor(lines, page_num, from_rect)
                target_page = link.get("page", -1)
                results.append(Link(
                    kind="internal",
                    text=anchor_text,
                    url="",
                    target_page=target_page,
                    page=page_num,
                    span=span,
                ))

            elif kind_code == fitz.LINK_NAMED:
                nameddest = link.get("nameddest", "")
                target_page = link.get("page", -1)
                to_point = link.get("to")
                target_xy = [to_point.x, to_point.y] if to_point else []
                if nameddest:
                    named_in_order.append(
                        (nameddest, page_num, fitz.Rect(from_rect), target_page, target_xy)
                    )

    # Group consecutive same-dest fragments on the same page, then
    # keep only the first occurrence of each nameddest for the registry.
    seen_named: set[str] = set()
    i = 0
    while i < len(named_in_order):
        dest, pg, rect, tp, txy = named_in_order[i]

        # Collect consecutive fragments with same dest on same page
        group_rects = [rect]
        j = i + 1
        while j < len(named_in_order):
            nd, npg, nr, _ntp, _ntxy = named_in_order[j]
            if nd == dest and npg == pg:
                group_rects.append(nr)
                j += 1
            else:
                break

        # Build anchor text from the rects in this group
        page_obj = doc_fitz[pg]
        text_parts = []
        for r in group_rects:
            text = page_obj.get_text("text", clip=r).strip()
            if text:
                text_parts.append(text)

        anchor_text = " ".join(text_parts)
        # Clean up split author-year: "(Kingma & Ba," + "2015)"
        anchor_text = re.sub(r",\s+", ", ", anchor_text)
        anchor_text = re.sub(r"\s+\)", ")", anchor_text)

        # Use union of first and last fragment spans so cross-line
        # citations (surname on one line, year on the next) are covered.
        _, first_span = _find_anchor(lines, pg, group_rects[0])
        if len(group_rects) > 1:
            _, last_span = _find_anchor(lines, pg, group_rects[-1])
            link_span = Span(start=first_span.start, end=max(first_span.end, last_span.end))
        else:
            link_span = first_span
        is_citation = dest.startswith("cite.")

        # Keep all citation occurrences (different spans for each location
        # in the paper) but dedup non-citation named links.
        if is_citation or dest not in seen_named:
            seen_named.add(dest)
            results.append(Link(
                kind="citation" if is_citation else "internal",
                text=anchor_text,
                url="",
                target_page=tp,
                page=pg,
                span=link_span,
                target_xy=txy,
                dest_name=dest,
            ))

        i = j

    return results


def _find_anchor(
    lines: list[_Line], page_num: int, rect: fitz.Rect
) -> tuple[str, Span]:
    """Find the line that intersects a link rect, returning text and span."""
    for ln in lines:
        if ln.page != page_num:
            continue
        if fitz.Rect(ln.bbox).intersects(fitz.Rect(rect)):
            return ln.text, Span(start=ln.char_start, end=ln.char_end)
    return "", Span(start=0, end=0)


def _detect_citations(raw_text: str) -> list[Link]:
    """Detect numeric citation markers like [1], [2, 3], [1-5]."""
    results: list[Link] = []
    seen: set[str] = set()

    for m in _CITATION_RE.finditer(raw_text):
        marker = m.group(0)
        if marker in seen:
            continue
        seen.add(marker)

        # Determine which page this citation is on (approximate: char offset 0 = page 0)
        results.append(Link(
            kind="citation",
            text=marker,
            url="",
            target_page=-1,
            page=0,
            span=Span(start=m.start(), end=m.end()),
        ))

    return results
