"""Tests for paper.storage — ~/.papers/ cache management."""

import json
import pytest

from paper import storage


@pytest.fixture
def tmp_papers_dir(tmp_path, monkeypatch):
    """Override PAPERS_DIR to use a temp directory."""
    monkeypatch.setattr(storage, "PAPERS_DIR", tmp_path)
    return tmp_path


class TestSanitizePaperId:
    def test_normal_id(self):
        assert storage._sanitize_paper_id("2302.13971") == "2302.13971"

    def test_path_traversal(self):
        result = storage._sanitize_paper_id("../etc/passwd")
        assert "/" not in result
        assert not result.startswith(".")

    def test_backslash(self):
        result = storage._sanitize_paper_id("..\\etc\\passwd")
        assert "\\" not in result
        assert not result.startswith(".")

    def test_leading_dots(self):
        assert storage._sanitize_paper_id("...test") == "test"

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            storage._sanitize_paper_id("")

    def test_only_dots_raises(self):
        with pytest.raises(ValueError):
            storage._sanitize_paper_id("...")

    def test_old_style_arxiv(self):
        # Old-style IDs like cs/0601001 become cs_0601001
        assert storage._sanitize_paper_id("cs/0601001") == "cs_0601001"


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


class TestCorruptedJson:
    def test_corrupted_index_returns_empty(self, tmp_papers_dir):
        tmp_papers_dir.mkdir(parents=True, exist_ok=True)
        (tmp_papers_dir / "index.json").write_text("{invalid json")
        assert storage.list_papers() == {}

    def test_corrupted_metadata_returns_none(self, tmp_papers_dir):
        d = storage.paper_dir("2302.13971")
        (d / "metadata.json").write_text("not json at all")
        assert storage.load_metadata("2302.13971") is None

    def test_corrupted_index_recovers_on_update(self, tmp_papers_dir):
        tmp_papers_dir.mkdir(parents=True, exist_ok=True)
        (tmp_papers_dir / "index.json").write_text("{bad")
        storage.update_index("2302.13971", "LLaMA")
        papers = storage.list_papers()
        assert papers["2302.13971"] == "LLaMA"
