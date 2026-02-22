"""Tests for paper.fetcher — arxiv URL resolution, DOI resolution, and PDF fetching."""

import hashlib
from unittest.mock import patch, MagicMock

import httpx
import pytest

from paper import storage
from paper.fetcher import (
    _doi_to_paper_id,
    _local_paper_id,
    _resolve_biorxiv_doi,
    _resolve_doi_to_pdf_url,
    _resolve_unpaywall,
    _resolve_doi_direct,
    fetch_paper,
    resolve_arxiv_id,
    resolve_doi,
)


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


# ---------------------------------------------------------------------------
# DOI resolution tests
# ---------------------------------------------------------------------------


class TestResolveDoi:
    """Test DOI format detection from bare DOIs and doi.org URLs."""

    def test_bare_doi(self):
        assert resolve_doi("10.1038/s41586-023-06845-4") == "10.1038/s41586-023-06845-4"

    def test_bare_doi_biorxiv(self):
        assert resolve_doi("10.1101/2022.03.19.484946") == "10.1101/2022.03.19.484946"

    def test_bare_doi_elife(self):
        assert resolve_doi("10.7554/eLife.00461") == "10.7554/eLife.00461"

    def test_doi_url_https(self):
        assert resolve_doi("https://doi.org/10.1038/s41586-023-06845-4") == "10.1038/s41586-023-06845-4"

    def test_doi_url_http(self):
        assert resolve_doi("http://doi.org/10.1038/s41586-023-06845-4") == "10.1038/s41586-023-06845-4"

    def test_doi_url_no_scheme(self):
        assert resolve_doi("doi.org/10.1038/s41586-023-06845-4") == "10.1038/s41586-023-06845-4"

    def test_doi_url_trailing_slash(self):
        assert resolve_doi("https://doi.org/10.1038/s41586-023-06845-4/") == "10.1038/s41586-023-06845-4"

    def test_doi_with_whitespace(self):
        assert resolve_doi("  10.1038/s41586-023-06845-4  ") == "10.1038/s41586-023-06845-4"

    def test_doi_trailing_period(self):
        """A trailing period (from sentence endings) should be stripped."""
        assert resolve_doi("10.1038/s41586-023-06845-4.") == "10.1038/s41586-023-06845-4"

    def test_not_a_doi(self):
        assert resolve_doi("not-a-doi") is None

    def test_arxiv_id_not_a_doi(self):
        assert resolve_doi("2302.13971") is None

    def test_empty_returns_none(self):
        assert resolve_doi("") is None

    def test_doi_with_parens(self):
        """DOIs with complex suffixes."""
        assert resolve_doi("10.1002/(SICI)1097-0258") == "10.1002/(SICI)1097-0258"


class TestDoiToPaperId:
    def test_simple(self):
        assert _doi_to_paper_id("10.1038/s41586-023-06845-4") == "doi-10.1038/s41586-023-06845-4"

    def test_biorxiv(self):
        assert _doi_to_paper_id("10.1101/2022.03.19.484946") == "doi-10.1101/2022.03.19.484946"


class TestResolveBiorxivDoi:
    """Test bioRxiv API resolution (mocked)."""

    def test_biorxiv_success(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "collection": [
                {
                    "jatsxml": "https://www.biorxiv.org/content/10.1101/2022.03.19.484946v1",
                },
                {
                    "jatsxml": "https://www.biorxiv.org/content/10.1101/2022.03.19.484946v2",
                },
            ]
        }

        with patch("paper.fetcher.httpx.get", return_value=mock_response):
            url = _resolve_biorxiv_doi("10.1101/2022.03.19.484946")

        assert url == "https://www.biorxiv.org/content/10.1101/2022.03.19.484946v2.full.pdf"

    def test_biorxiv_empty_collection(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"collection": []}

        with patch("paper.fetcher.httpx.get", return_value=mock_response):
            url = _resolve_biorxiv_doi("10.1101/2022.03.19.484946")

        assert url is None

    def test_biorxiv_api_error(self):
        with patch("paper.fetcher.httpx.get", side_effect=httpx.ConnectError("fail")):
            url = _resolve_biorxiv_doi("10.1101/2022.03.19.484946")

        assert url is None


class TestResolveUnpaywall:
    """Test Unpaywall API resolution (mocked)."""

    def test_unpaywall_success(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "best_oa_location": {
                "url_for_pdf": "https://elifesciences.org/articles/00461.pdf",
            }
        }

        with patch("paper.fetcher.httpx.get", return_value=mock_response):
            url = _resolve_unpaywall("10.7554/eLife.00461")

        assert url == "https://elifesciences.org/articles/00461.pdf"

    def test_unpaywall_no_pdf(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "best_oa_location": {
                "url_for_landing_page": "https://example.com/paper",
                "url_for_pdf": None,
            }
        }

        with patch("paper.fetcher.httpx.get", return_value=mock_response):
            url = _resolve_unpaywall("10.1234/no-pdf")

        assert url is None

    def test_unpaywall_no_oa_location(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"best_oa_location": None}

        with patch("paper.fetcher.httpx.get", return_value=mock_response):
            url = _resolve_unpaywall("10.1234/paywalled")

        assert url is None

    def test_unpaywall_404(self):
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch("paper.fetcher.httpx.get", return_value=mock_response):
            url = _resolve_unpaywall("10.1234/nonexistent")

        assert url is None


class TestResolveDoiDirect:
    """Test direct doi.org resolution (mocked)."""

    def test_direct_pdf_redirect(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/pdf"}
        mock_response.url = "https://publisher.com/paper.pdf"

        with patch("paper.fetcher.httpx.head", return_value=mock_response):
            url = _resolve_doi_direct("10.1234/direct-pdf")

        assert url == "https://publisher.com/paper.pdf"

    def test_direct_html_page(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html"}
        mock_response.url = "https://publisher.com/landing"

        with patch("paper.fetcher.httpx.head", return_value=mock_response):
            url = _resolve_doi_direct("10.1234/html-only")

        assert url is None


class TestResolveDoiToPdfUrl:
    """Test the combined DOI-to-PDF resolution logic."""

    def test_biorxiv_tried_first(self):
        """bioRxiv DOIs should try the bioRxiv API first."""
        with patch("paper.fetcher._resolve_biorxiv_doi", return_value="https://biorxiv.org/paper.pdf") as mock_bio:
            url = _resolve_doi_to_pdf_url("10.1101/2022.03.19.484946")

        assert url == "https://biorxiv.org/paper.pdf"
        mock_bio.assert_called_once_with("10.1101/2022.03.19.484946")

    def test_unpaywall_fallback(self):
        """Non-bioRxiv DOIs should try Unpaywall."""
        with patch("paper.fetcher._resolve_unpaywall", return_value="https://unpaywall.org/paper.pdf") as mock_unp:
            url = _resolve_doi_to_pdf_url("10.7554/eLife.00461")

        assert url == "https://unpaywall.org/paper.pdf"
        mock_unp.assert_called_once_with("10.7554/eLife.00461")

    def test_direct_fallback(self):
        """If Unpaywall fails, try direct doi.org resolution."""
        with patch("paper.fetcher._resolve_unpaywall", return_value=None), \
             patch("paper.fetcher._resolve_doi_direct", return_value="https://pub.com/paper.pdf") as mock_direct:
            url = _resolve_doi_to_pdf_url("10.1234/some-paper")

        assert url == "https://pub.com/paper.pdf"
        mock_direct.assert_called_once_with("10.1234/some-paper")

    def test_all_strategies_fail_raises(self):
        """ValueError when no strategy can find a PDF."""
        with patch("paper.fetcher._resolve_unpaywall", return_value=None), \
             patch("paper.fetcher._resolve_doi_direct", return_value=None):
            with pytest.raises(ValueError, match="Could not find an open-access PDF"):
                _resolve_doi_to_pdf_url("10.1234/paywalled-paper")


class TestFetchPaperDoi:
    """Test fetch_paper() with DOI references."""

    def test_cached_doi(self, tmp_path, monkeypatch):
        """If the DOI paper is already cached, return it directly."""
        monkeypatch.setattr(storage, "PAPERS_DIR", tmp_path / ".papers")
        paper_id = "doi-10.7554_eLife.00461"
        # Pre-create the cached PDF
        d = tmp_path / ".papers" / paper_id
        d.mkdir(parents=True)
        pdf = d / "paper.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake")

        pid, path = fetch_paper("10.7554/eLife.00461")
        assert pid == "doi-10.7554/eLife.00461"
        assert path.exists()

    def test_doi_download(self, tmp_path, monkeypatch):
        """fetch_paper should resolve + download for an uncached DOI."""
        monkeypatch.setattr(storage, "PAPERS_DIR", tmp_path / ".papers")

        with patch("paper.fetcher._resolve_doi_to_pdf_url", return_value="https://example.com/paper.pdf"), \
             patch("paper.fetcher._download_pdf") as mock_dl:
            pid, path = fetch_paper("10.7554/eLife.00461")

        assert pid == "doi-10.7554/eLife.00461"
        mock_dl.assert_called_once()
        # Verify metadata was saved
        meta = storage.load_metadata(pid)
        assert meta["doi"] == "10.7554/eLife.00461"
        assert meta["url"] == "https://doi.org/10.7554/eLife.00461"

    def test_doi_url_reference(self, tmp_path, monkeypatch):
        """fetch_paper should handle doi.org URLs."""
        monkeypatch.setattr(storage, "PAPERS_DIR", tmp_path / ".papers")

        with patch("paper.fetcher._resolve_doi_to_pdf_url", return_value="https://example.com/paper.pdf"), \
             patch("paper.fetcher._download_pdf"):
            pid, _ = fetch_paper("https://doi.org/10.7554/eLife.00461")

        assert pid == "doi-10.7554/eLife.00461"

    def test_error_message_mentions_doi(self):
        """Error message for unrecognised refs should mention DOI format."""
        with pytest.raises(ValueError, match="DOI"):
            fetch_paper("not-a-valid-reference-at-all")
