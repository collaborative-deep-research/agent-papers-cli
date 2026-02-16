"""Tests for paper.storage — ~/.papers/ cache management."""

import json
import pytest

from paper import storage


@pytest.fixture
def tmp_papers_dir(tmp_path, monkeypatch):
    """Override PAPERS_DIR to use a temp directory."""
    monkeypatch.setattr(storage, "PAPERS_DIR", tmp_path)
    return tmp_path


class TestStorage:
    def test_paper_dir_creates_directory(self, tmp_papers_dir):
        d = storage.paper_dir("2302.13971")
        assert d.exists()
        assert d.name == "2302.13971"

    def test_pdf_path(self, tmp_papers_dir):
        p = storage.pdf_path("2302.13971")
        assert p.name == "paper.pdf"
        assert "2302.13971" in str(p)

    def test_has_pdf_false(self, tmp_papers_dir):
        assert not storage.has_pdf("2302.13971")

    def test_has_pdf_true(self, tmp_papers_dir):
        pdf = storage.pdf_path("2302.13971")
        pdf.parent.mkdir(parents=True, exist_ok=True)
        pdf.write_bytes(b"%PDF-1.4")
        assert storage.has_pdf("2302.13971")

    def test_save_and_load_metadata(self, tmp_papers_dir):
        storage.save_metadata("2302.13971", {"title": "LLaMA", "arxiv_id": "2302.13971"})
        meta = storage.load_metadata("2302.13971")
        assert meta["title"] == "LLaMA"

    def test_load_metadata_missing(self, tmp_papers_dir):
        assert storage.load_metadata("nonexistent") is None

    def test_update_and_list_index(self, tmp_papers_dir):
        storage.update_index("2302.13971", "LLaMA")
        storage.update_index("2510.25744", "Completion != Collaboration")
        papers = storage.list_papers()
        assert papers["2302.13971"] == "LLaMA"
        assert papers["2510.25744"] == "Completion != Collaboration"

    def test_list_papers_empty(self, tmp_papers_dir):
        assert storage.list_papers() == {}
