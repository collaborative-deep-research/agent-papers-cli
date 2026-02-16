"""Tests for paper.models — data model serialization."""

import pytest

from paper.models import Document, Metadata, Section, Sentence, Span


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
