"""Parse PDFs into structured Document objects using PyMuPDF + PySBD."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import fitz  # PyMuPDF
import pysbd

from paper.models import Box, Document, Metadata, Section, Sentence, Span
from paper import storage


def parse_paper(arxiv_id: str, pdf_path: Path) -> Document:
    """Parse a PDF into a structured Document.

    Uses cached result if available.
    """
    if storage.has_parsed(arxiv_id):
        return Document.load(storage.parsed_path(arxiv_id))

    doc_fitz = fitz.open(pdf_path)
    try:
        document = _extract_document(doc_fitz, arxiv_id)
    finally:
        doc_fitz.close()

    # Cache the parsed result
    document.save(storage.parsed_path(arxiv_id))

    # Update index with title
    if document.metadata.title:
        storage.update_index(arxiv_id, document.metadata.title)

    return document


def _extract_document(doc_fitz: fitz.Document, arxiv_id: str) -> Document:
    """Extract text, detect headings, segment sections, split sentences."""
    # Step 1: Extract all text blocks with font info
    blocks = _extract_blocks(doc_fitz)

    # Step 2: Determine body font size (most common)
    body_size = _detect_body_font_size(blocks)

    # Step 3: Build raw text and detect headings
    raw_text, text_elements = _build_raw_text(blocks, body_size)

    # Step 4: Try PDF outline first, fall back to font-based headings
    headings = _extract_headings_from_outline(doc_fitz)
    if not headings:
        headings = _extract_headings_from_fonts(text_elements, body_size)

    # Step 5: Segment into sections
    sections = _segment_sections(raw_text, text_elements, headings)

    # Step 6: Split sentences in each section
    _split_sentences(sections)

    # Step 7: Extract metadata
    metadata = _extract_metadata(doc_fitz, text_elements, body_size, arxiv_id)

    # Step 8: Page info
    pages = [
        {"page_number": i, "width": p.rect.width, "height": p.rect.height}
        for i, p in enumerate(doc_fitz)
    ]

    return Document(
        metadata=metadata,
        sections=sections,
        raw_text=raw_text,
        pages=pages,
    )


@dataclass
class _TextElement:
    """Internal representation of a text span during parsing."""
    text: str
    font_size: float
    font_name: str
    is_bold: bool
    page: int
    bbox: tuple[float, float, float, float]  # x0, y0, x1, y1
    char_start: int = 0  # offset into raw_text
    char_end: int = 0


def _extract_blocks(doc_fitz: fitz.Document) -> list[_TextElement]:
    """Extract text elements with font metadata from all pages."""
    elements = []
    for page_num, page in enumerate(doc_fitz):
        blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
        for block in blocks:
            if block.get("type") != 0:  # text blocks only
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span["text"].strip()
                    if not text:
                        continue
                    font_name = span.get("font", "")
                    is_bold = "bold" in font_name.lower() or "Bold" in font_name
                    elements.append(_TextElement(
                        text=text,
                        font_size=round(span["size"], 1),
                        font_name=font_name,
                        is_bold=is_bold,
                        page=page_num,
                        bbox=tuple(span["bbox"]),
                    ))
    return elements


def _detect_body_font_size(elements: list[_TextElement]) -> float:
    """Find the most common font size (= body text)."""
    size_counts: Counter[float] = Counter()
    for el in elements:
        # Weight by text length to favor actual body text
        size_counts[el.font_size] += len(el.text)
    if not size_counts:
        return 10.0
    return size_counts.most_common(1)[0][0]


def _build_raw_text(
    elements: list[_TextElement], body_size: float
) -> tuple[str, list[_TextElement]]:
    """Concatenate elements into raw_text, recording character offsets."""
    parts: list[str] = []
    offset = 0

    for el in elements:
        if offset > 0:
            # Add newline between elements from different lines
            parts.append("\n")
            offset += 1

        el.char_start = offset
        el.char_end = offset + len(el.text)
        parts.append(el.text)
        offset = el.char_end

    raw_text = "".join(parts)
    return raw_text, elements


def _extract_headings_from_outline(doc_fitz: fitz.Document) -> list[dict]:
    """Try to get headings from PDF's built-in outline/ToC."""
    toc = doc_fitz.get_toc()
    if not toc or len(toc) < 2:
        return []

    headings = []
    for level, title, page_num in toc:
        headings.append({
            "heading": title.strip(),
            "level": level,
            "page": page_num - 1,  # 0-indexed
        })
    return headings


def _extract_headings_from_fonts(
    elements: list[_TextElement], body_size: float
) -> list[dict]:
    """Detect headings by font size relative to body text."""
    headings = []
    # Threshold: anything 1.2x body size or larger is a heading
    heading_threshold = body_size * 1.15

    # Collect distinct heading sizes for level assignment
    heading_sizes = sorted(
        {el.font_size for el in elements if el.font_size > heading_threshold},
        reverse=True,
    )

    # Map font sizes to heading levels
    size_to_level = {size: i + 1 for i, size in enumerate(heading_sizes)}

    for el in elements:
        if el.font_size > heading_threshold:
            # Also check: short text (headings are usually brief)
            if len(el.text) < 200:
                headings.append({
                    "heading": el.text,
                    "level": size_to_level.get(el.font_size, 1),
                    "page": el.page,
                    "char_start": el.char_start,
                    "char_end": el.char_end,
                })
        elif el.is_bold and el.font_size >= body_size:
            # Bold text at body size could be a subheading
            # Only if it's short and looks like a heading
            text = el.text.strip()
            if len(text) < 100 and not text.endswith("."):
                headings.append({
                    "heading": text,
                    "level": max(size_to_level.values(), default=0) + 1,
                    "page": el.page,
                    "char_start": el.char_start,
                    "char_end": el.char_end,
                })

    return headings


def _segment_sections(
    raw_text: str,
    elements: list[_TextElement],
    headings: list[dict],
) -> list[Section]:
    """Split document into sections based on detected headings."""
    if not headings:
        # No headings found — treat entire document as one section
        return [Section(
            heading="(Full Document)",
            level=1,
            content=raw_text,
            spans=[Span(start=0, end=len(raw_text))],
            page_start=elements[0].page if elements else 0,
            page_end=elements[-1].page if elements else 0,
        )]

    sections = []

    for i, h in enumerate(headings):
        # Section content spans from this heading to the next
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
        # Find the last page this section touches
        for el in elements:
            if el.char_start >= start and el.char_start < end:
                page_end = max(page_end, el.page)

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

            # Find this sentence in the section content
            idx = section.content.find(sent_text, offset)
            if idx == -1:
                idx = offset

            # Map back to raw_text offsets
            section_start = section.spans[0].start if section.spans else 0
            # The content may not start at section_start (heading was stripped),
            # so we approximate
            abs_start = section_start + idx
            abs_end = abs_start + len(sent_text)

            section.sentences.append(Sentence(
                text=sent_text,
                span=Span(start=abs_start, end=abs_end),
                page=section.page_start,  # approximate
            ))
            offset = idx + len(sent_text)


def _extract_metadata(
    doc_fitz: fitz.Document,
    elements: list[_TextElement],
    body_size: float,
    arxiv_id: str,
) -> Metadata:
    """Extract title and basic metadata."""
    # Title is typically the largest text on page 1
    page1_elements = [el for el in elements if el.page == 0]
    title = ""
    if page1_elements:
        largest = max(page1_elements, key=lambda el: el.font_size)
        title = largest.text.strip()

    # Get metadata from PDF properties
    pdf_meta = doc_fitz.metadata or {}

    return Metadata(
        title=title or pdf_meta.get("title", ""),
        authors=[a.strip() for a in pdf_meta.get("author", "").split(",") if a.strip()],
        arxiv_id=arxiv_id,
        url=f"https://arxiv.org/abs/{arxiv_id}",
    )
