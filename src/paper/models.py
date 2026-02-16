"""Data models for parsed paper documents."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


@dataclass
class Box:
    """A bounding box on a specific page."""
    x0: float
    y0: float
    x1: float
    y1: float
    page: int


@dataclass
class Span:
    """A character offset range into the document's raw_text."""
    start: int
    end: int
    boxes: list[Box] = field(default_factory=list)


@dataclass
class Link:
    """A link extracted from the PDF."""
    kind: str          # "external", "internal", "citation"
    text: str          # anchor text or citation marker e.g. "[1]"
    url: str           # URL for external; empty for others
    target_page: int   # destination page for internal links (-1 if N/A)
    page: int          # page where the link appears
    span: Span         # character offset in raw_text


@dataclass
class Sentence:
    """A single sentence within a section."""
    text: str
    span: Span
    page: int


@dataclass
class Section:
    """A document section with heading, content, and sentences."""
    heading: str
    level: int
    content: str
    sentences: list[Sentence] = field(default_factory=list)
    spans: list[Span] = field(default_factory=list)
    page_start: int = 0
    page_end: int = 0


@dataclass
class Metadata:
    """Paper metadata."""
    title: str = ""
    authors: list[str] = field(default_factory=list)
    arxiv_id: str = ""
    url: str = ""
    abstract: str = ""


@dataclass
class Document:
    """A parsed paper document."""
    metadata: Metadata = field(default_factory=Metadata)
    sections: list[Section] = field(default_factory=list)
    raw_text: str = ""
    pages: list[dict] = field(default_factory=list)
    links: list[Link] = field(default_factory=list)

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False))

    @classmethod
    def load(cls, path: Path) -> Document:
        data = json.loads(path.read_text())
        meta = Metadata(**data.get("metadata", {}))
        sections = []
        for s in data.get("sections", []):
            sentences = [
                Sentence(
                    text=sent["text"],
                    span=Span(
                        start=sent["span"]["start"],
                        end=sent["span"]["end"],
                        boxes=[Box(**b) for b in sent["span"].get("boxes", [])],
                    ),
                    page=sent["page"],
                )
                for sent in s.get("sentences", [])
            ]
            spans = [
                Span(
                    start=sp["start"],
                    end=sp["end"],
                    boxes=[Box(**b) for b in sp.get("boxes", [])],
                )
                for sp in s.get("spans", [])
            ]
            sections.append(Section(
                heading=s["heading"],
                level=s["level"],
                content=s["content"],
                sentences=sentences,
                spans=spans,
                page_start=s.get("page_start", 0),
                page_end=s.get("page_end", 0),
            ))
        links = [
            Link(
                kind=lk["kind"],
                text=lk["text"],
                url=lk["url"],
                target_page=lk["target_page"],
                page=lk["page"],
                span=Span(
                    start=lk["span"]["start"],
                    end=lk["span"]["end"],
                    boxes=[Box(**b) for b in lk["span"].get("boxes", [])],
                ),
            )
            for lk in data.get("links", [])
        ]
        return cls(
            metadata=meta,
            sections=sections,
            raw_text=data.get("raw_text", ""),
            pages=data.get("pages", []),
            links=links,
        )
