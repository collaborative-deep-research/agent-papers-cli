"""Tests for paper.fetcher — arxiv URL resolution and PDF fetching."""

import hashlib

import pytest

from paper import storage
from paper.fetcher import _local_paper_id, fetch_paper, resolve_arxiv_id


class TestResolveArxivId:
    def test_bare_id(self):
        assert resolve_arxiv_id("2302.13971") == "2302.13971"

    def test_bare_id_with_version(self):
        assert resolve_arxiv_id("2302.13971v2") == "2302.13971v2"

    def test_abs_url(self):
        assert resolve_arxiv_id("https://arxiv.org/abs/2302.13971") == "2302.13971"

    def test_pdf_url(self):
        assert resolve_arxiv_id("https://arxiv.org/pdf/2302.13971") == "2302.13971"

    def test_abs_url_with_version(self):
        assert resolve_arxiv_id("https://arxiv.org/abs/2302.13971v1") == "2302.13971v1"

    def test_trailing_slash(self):
        assert resolve_arxiv_id("https://arxiv.org/abs/2302.13971/") == "2302.13971"

    def test_whitespace(self):
        assert resolve_arxiv_id("  2302.13971  ") == "2302.13971"

    def test_invalid_returns_none(self):
        assert resolve_arxiv_id("not-a-paper") is None

    def test_empty_returns_none(self):
        assert resolve_arxiv_id("") is None

    def test_five_digit_id(self):
        assert resolve_arxiv_id("2510.25744") == "2510.25744"


class TestLocalPaperId:
    def test_stem_included(self, tmp_path):
        pid = _local_paper_id(tmp_path / "my_paper.pdf")
        assert pid.startswith("my_paper-")

    def test_different_paths_different_ids(self, tmp_path):
        id1 = _local_paper_id(tmp_path / "dir1" / "paper.pdf")
        id2 = _local_paper_id(tmp_path / "dir2" / "paper.pdf")
        assert id1 != id2

    def test_deterministic(self, tmp_path):
        p = tmp_path / "paper.pdf"
        assert _local_paper_id(p) == _local_paper_id(p)

    def test_hash_length(self, tmp_path):
        pid = _local_paper_id(tmp_path / "paper.pdf")
        # Format: stem-hash8
        parts = pid.rsplit("-", 1)
        assert len(parts) == 2
        assert len(parts[1]) == 8


class TestFetchPaperLocal:
    def test_local_pdf(self, tmp_path, monkeypatch):
        monkeypatch.setattr(storage, "PAPERS_DIR", tmp_path / ".papers")
        pdf = tmp_path / "my_paper.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake")
        paper_id, path = fetch_paper(str(pdf))
        assert paper_id.startswith("my_paper-")
        assert path == pdf.resolve()

    def test_local_pdf_tilde(self, tmp_path, monkeypatch):
        """Ensure ~ expansion works."""
        monkeypatch.setattr(storage, "PAPERS_DIR", tmp_path / ".papers")
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake")
        monkeypatch.setenv("HOME", str(tmp_path))
        paper_id, path = fetch_paper("~/test.pdf")
        assert paper_id.startswith("test-")
        assert path == pdf.resolve()

    def test_local_pdf_not_found(self):
        """Non-existent .pdf path falls through to arxiv resolution."""
        with pytest.raises(ValueError, match="Could not parse reference"):
            fetch_paper("/nonexistent/path/paper.pdf")

    def test_non_pdf_file_not_matched(self, tmp_path):
        """A .txt file should not be treated as a local PDF."""
        txt = tmp_path / "notes.txt"
        txt.write_text("not a pdf")
        with pytest.raises(ValueError, match="Could not parse reference"):
            fetch_paper(str(txt))

    def test_saves_local_metadata(self, tmp_path, monkeypatch):
        """fetch_paper should write local metadata with source/path/mtime."""
        monkeypatch.setattr(storage, "PAPERS_DIR", tmp_path / ".papers")
        pdf = tmp_path / "meta_test.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake")
        paper_id, _ = fetch_paper(str(pdf))
        meta = storage.load_metadata(paper_id)
        assert meta["source"] == "local"
        assert meta["source_path"] == str(pdf.resolve())
        assert "source_mtime" in meta
