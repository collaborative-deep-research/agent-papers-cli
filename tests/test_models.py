"""Tests for paper.models — data model serialization."""

import pytest

from paper.models import Document, Link, Metadata, Section, Sentence, Span


class TestDocumentSerialization:
    def test_save_and_load_roundtrip(self, tmp_path):
        doc = Document(
            metadata=Metadata(
                title="Test Paper",
                authors=["Alice", "Bob"],
                arxiv_id="2302.13971",
                url="https://arxiv.org/abs/2302.13971",
            ),
            sections=[
                Section(
                    heading="Introduction",
                    level=1,
                    content="This is the intro.",
                    sentences=[
                        Sentence(
                            text="This is the intro.",
                            span=Span(start=0, end=18),
                            page=0,
                        )
                    ],
                    spans=[Span(start=0, end=18)],
                    page_start=0,
                    page_end=0,
                )
            ],
            raw_text="Introduction\nThis is the intro.",
            pages=[{"page_number": 0, "width": 612, "height": 792}],
        )

        path = tmp_path / "parsed.json"
        doc.save(path)
        loaded = Document.load(path)

        assert loaded.metadata.title == "Test Paper"
        assert loaded.metadata.authors == ["Alice", "Bob"]
        assert len(loaded.sections) == 1
        assert loaded.sections[0].heading == "Introduction"
        assert loaded.sections[0].sentences[0].text == "This is the intro."
        assert loaded.raw_text == "Introduction\nThis is the intro."

    def test_empty_document(self, tmp_path):
        doc = Document()
        path = tmp_path / "empty.json"
        doc.save(path)
        loaded = Document.load(path)
        assert loaded.metadata.title == ""
        assert loaded.sections == []

    def test_roundtrip_with_links(self, tmp_path):
        doc = Document(
            metadata=Metadata(title="Link Test", arxiv_id="2302.13971"),
            sections=[
                Section(heading="Intro", level=1, content="See [1].",
                        spans=[Span(start=0, end=20)]),
            ],
            raw_text="Intro\nSee [1].",
            links=[
                Link(kind="external", text="example", url="https://example.com",
                     target_page=-1, page=0, span=Span(start=0, end=7)),
                Link(kind="citation", text="[1]", url="", target_page=-1,
                     page=0, span=Span(start=10, end=13)),
                Link(kind="internal", text="Section 2", url="",
                     target_page=3, page=0, span=Span(start=5, end=14)),
            ],
        )

        path = tmp_path / "links.json"
        doc.save(path)
        loaded = Document.load(path)

        assert len(loaded.links) == 3
        assert loaded.links[0].kind == "external"
        assert loaded.links[0].url == "https://example.com"
        assert loaded.links[0].span.start == 0
        assert loaded.links[1].kind == "citation"
        assert loaded.links[1].text == "[1]"
        assert loaded.links[2].kind == "internal"
        assert loaded.links[2].target_page == 3

    def test_load_without_links_field(self, tmp_path):
        """Loading a JSON without 'links' should default to empty list."""
        import json
        data = {
            "metadata": {"title": "Old Paper"},
            "sections": [],
            "raw_text": "",
            "pages": [],
        }
        path = tmp_path / "no_links.json"
        path.write_text(json.dumps(data))
        loaded = Document.load(path)
        assert loaded.links == []
