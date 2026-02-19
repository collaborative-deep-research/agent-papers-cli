"""Tests for paper.fetcher — arxiv URL resolution and PDF fetching."""

import pytest

from paper.fetcher import fetch_paper, resolve_arxiv_id


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


class TestFetchPaperLocal:
    def test_local_pdf(self, tmp_path):
        pdf = tmp_path / "my_paper.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake")
        paper_id, path = fetch_paper(str(pdf))
        assert paper_id == "my_paper"
        assert path == pdf.resolve()

    def test_local_pdf_tilde(self, tmp_path, monkeypatch):
        """Ensure ~ expansion works."""
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake")
        monkeypatch.setenv("HOME", str(tmp_path))
        paper_id, path = fetch_paper("~/test.pdf")
        assert paper_id == "test"
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
