"""Highlight operations: text search, coordinate conversion, PDF annotation."""

from __future__ import annotations

import json
import shutil
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import fitz  # PyMuPDF

from paper.models import Document, Highlight
from paper import storage


def search_pdf(pdf_path: Path, query: str) -> list[dict]:
    """Search for text in a PDF, returning matches with page coordinates.

    Each match is a dict with:
        page: int (0-indexed)
        rects: list of {x0, y0, x1, y1} (absolute PDF coords)
        context: str (surrounding text)
    """
    matches = []
    with fitz.open(pdf_path) as doc:
        for page_num in range(len(doc)):
            page = doc[page_num]
            hits = page.search_for(query)
            if not hits:
                continue

            # Get context around each hit
            for rect in hits:
                # Expand the rect vertically to grab context lines
                context_rect = fitz.Rect(
                    0, max(0, rect.y0 - 30),
                    page.rect.width, min(page.rect.height, rect.y1 + 30),
                )
                context_text = page.get_text("text", clip=context_rect).strip()

                matches.append({
                    "page": page_num,
                    "rects": [{"x0": rect.x0, "y0": rect.y0, "x1": rect.x1, "y1": rect.y1}],
                    "context": context_text,
                })

    return matches


def search_in_document(doc: Document, query: str, context_lines: int = 2) -> list[dict]:
    """Search Document.raw_text for matches with section context.

    Returns matches with section info for display. This complements
    search_pdf() by providing section-level context.
    """
    query_lower = query.lower()
    matches = []

    for section in doc.sections:
        text = section.content
        text_lower = text.lower()
        pos = 0

        while True:
            idx = text_lower.find(query_lower, pos)
            if idx == -1:
                break

            # Extract context
            line_start = text.rfind("\n", 0, idx)
            line_start = 0 if line_start == -1 else line_start + 1

            context_end = idx + len(query)
            for _ in range(context_lines):
                next_nl = text.find("\n", context_end)
                if next_nl == -1:
                    context_end = len(text)
                    break
                context_end = next_nl + 1

            context = text[line_start:context_end].strip()

            matches.append({
                "section": section.heading,
                "page": section.page_start,
                "context": context,
                "match_start": idx,
            })

            pos = idx + len(query)

    return matches


def to_scaled_position(
    rects: list[dict],
    page_width: float,
    page_height: float,
    page_number: int,  # 1-indexed for output
) -> dict:
    """Convert absolute PDF rects to normalized ScaledPosition format.

    Output matches react-pdf-highlighter-extended's ScaledPosition:
    coordinates normalized to 0-1 range (fraction of page dimensions).
    """
    scaled_rects = []
    for r in rects:
        x1 = r["x0"] / page_width
        y1 = r["y0"] / page_height
        x2 = r["x1"] / page_width
        y2 = r["y1"] / page_height
        scaled_rects.append({
            "x1": round(x1, 4),
            "y1": round(y1, 4),
            "x2": round(x2, 4),
            "y2": round(y2, 4),
            "width": round(x2 - x1, 4),
            "height": round(y2 - y1, 4),
            "pageNumber": page_number,
        })

    # Bounding rect = union of all rects
    if scaled_rects:
        bounding = {
            "x1": min(r["x1"] for r in scaled_rects),
            "y1": min(r["y1"] for r in scaled_rects),
            "x2": max(r["x2"] for r in scaled_rects),
            "y2": max(r["y2"] for r in scaled_rects),
            "pageNumber": page_number,
        }
        bounding["width"] = round(bounding["x2"] - bounding["x1"], 4)
        bounding["height"] = round(bounding["y2"] - bounding["y1"], 4)
    else:
        bounding = {"x1": 0, "y1": 0, "x2": 0, "y2": 0, "width": 0, "height": 0, "pageNumber": page_number}

    return {
        "boundingRect": bounding,
        "rects": scaled_rects,
    }


def match_to_json(match: dict, doc: Document) -> dict:
    """Convert a search match to app-compatible JSON format."""
    page_num = match["page"]
    page_info = doc.pages[page_num] if page_num < len(doc.pages) else {}
    page_width = page_info.get("width", 612)
    page_height = page_info.get("height", 792)

    position = to_scaled_position(
        match["rects"],
        page_width,
        page_height,
        page_num + 1,  # 1-indexed for the app
    )

    # Matches the app's POST /api/reader/{documentId}/highlights format
    return {
        "position": position,
        "content": {"text": match.get("context", "").strip()},
        "selectedText": match.get("context", "").strip(),
        "pageIndex": page_num,
        "type": "text",
    }


def add_highlight(
    paper_id: str,
    text: str,
    page: int,
    rects: list[dict],
    color: str = "yellow",
    note: str = "",
) -> Highlight:
    """Persist a highlight to storage."""
    highlights = storage.load_highlights(paper_id)

    # Next ID = max existing + 1
    next_id = max((h["id"] for h in highlights), default=0) + 1

    hl = Highlight(
        id=next_id,
        text=text,
        page=page,
        rects=rects,
        color=color,
        note=note,
        created_at=datetime.now(timezone.utc).isoformat(),
    )

    highlights.append(asdict(hl))
    storage.save_highlights(paper_id, highlights)
    return hl


def remove_highlight(paper_id: str, highlight_id: int) -> bool:
    """Remove a highlight by ID. Returns True if found and removed."""
    highlights = storage.load_highlights(paper_id)
    original_len = len(highlights)
    highlights = [h for h in highlights if h["id"] != highlight_id]

    if len(highlights) == original_len:
        return False

    storage.save_highlights(paper_id, highlights)
    return True


def annotate_pdf(pdf_path: Path, output_path: Path, highlights: list[dict]) -> None:
    """Add highlight annotations to a PDF copy.

    Each highlight dict should have: page (int), rects (list of {x0, y0, x1, y1}).
    """
    shutil.copy2(pdf_path, output_path)

    color_map = {
        "yellow": (1, 0.92, 0.23),
        "green": (0.56, 0.93, 0.56),
        "blue": (0.68, 0.85, 0.9),
        "pink": (1, 0.71, 0.76),
    }

    with fitz.open(output_path) as doc:
        for hl in highlights:
            page_num = hl["page"]
            if page_num >= len(doc):
                continue
            page = doc[page_num]
            color = color_map.get(hl.get("color", "yellow"), color_map["yellow"])

            for rect_data in hl["rects"]:
                rect = fitz.Rect(rect_data["x0"], rect_data["y0"], rect_data["x1"], rect_data["y1"])
                annot = page.add_highlight_annot(rect)
                annot.set_colors(stroke=color)
                annot.update()

        doc.save(output_path, incremental=True, encryption=fitz.PDF_ENCRYPT_KEEP)
