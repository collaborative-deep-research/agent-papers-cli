"""Tests for paper.bibtex — BibTeX generation and metadata enrichment."""

import json
from unittest.mock import patch, MagicMock

import pytest

from paper.bibtex import (
    BibMetadata,
    _make_citation_key,
    _detect_entry_type,
    _escape_bibtex,
    format_bibtex,
    fetch_arxiv_metadata,
    fetch_s2_metadata,
    fetch_crossref_metadata,
    enrich_metadata,
    generate_bibtex,
)
from paper import storage


# --- Fixtures ---


@pytest.fixture
def tmp_papers_dir(tmp_path, monkeypatch):
    """Override PAPERS_DIR to use a temp directory."""
    monkeypatch.setattr(storage, "PAPERS_DIR", tmp_path)
    return tmp_path


def _make_doc(title="Attention Is All You Need", authors=None, arxiv_id="1706.03762", url=""):
    """Create a minimal mock Document for testing."""
    from paper.models import Document, Metadata

    return Document(
        metadata=Metadata(
            title=title,
            authors=authors or ["Ashish Vaswani", "Noam Shazeer"],
            arxiv_id=arxiv_id,
            url=url or (f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else ""),
        ),
    )


# --- Citation key generation ---


class TestMakeCitationKey:
    def test_basic(self):
        meta = BibMetadata(title="Attention Is All You Need", authors=["Ashish Vaswani"], year=2017)
        assert _make_citation_key(meta) == "vaswani2017attention"

    def test_skips_stop_words(self):
        meta = BibMetadata(title="On the Properties of Neural Networks", authors=["Jane Smith"], year=2020)
        assert _make_citation_key(meta) == "smith2020properties"

    def test_no_year(self):
        meta = BibMetadata(title="Some Title", authors=["Jane Smith"])
        assert _make_citation_key(meta) == "smithsome"

    def test_no_authors(self):
        meta = BibMetadata(title="Some Title", year=2020)
        assert _make_citation_key(meta) == "unknown2020some"

    def test_no_title(self):
        meta = BibMetadata(authors=["Jane Smith"], year=2020)
        assert _make_citation_key(meta) == "smith2020"

    def test_hyphenated_last_name(self):
        meta = BibMetadata(title="Test", authors=["Jean-Pierre Dupont"], year=2021)
        key = _make_citation_key(meta)
        assert key.startswith("dupont2021")

    def test_empty_metadata(self):
        meta = BibMetadata()
        assert _make_citation_key(meta) == "unknown"


# --- Entry type detection ---


class TestDetectEntryType:
    def test_conference_venue(self):
        meta = BibMetadata(venue="Proceedings of NeurIPS 2020")
        assert _detect_entry_type(meta) == "inproceedings"

    def test_journal_venue(self):
        meta = BibMetadata(venue="Journal of Machine Learning Research")
        assert _detect_entry_type(meta) == "article"

    def test_transactions(self):
        meta = BibMetadata(venue="IEEE Transactions on Pattern Analysis")
        assert _detect_entry_type(meta) == "article"

    def test_workshop(self):
        meta = BibMetadata(venue="Workshop on Representation Learning")
        assert _detect_entry_type(meta) == "inproceedings"

    def test_unknown_venue(self):
        meta = BibMetadata(venue="Some Venue")
        assert _detect_entry_type(meta) == "inproceedings"

    def test_arxiv_no_venue(self):
        meta = BibMetadata(arxiv_id="2301.12345")
        assert _detect_entry_type(meta) == "article"

    def test_no_venue_no_arxiv(self):
        meta = BibMetadata()
        assert _detect_entry_type(meta) == "misc"

    def test_icml(self):
        meta = BibMetadata(venue="ICML")
        assert _detect_entry_type(meta) == "inproceedings"

    def test_acl(self):
        meta = BibMetadata(venue="Proceedings of ACL")
        assert _detect_entry_type(meta) == "inproceedings"


# --- BibTeX escaping ---


class TestEscapeBibtex:
    def test_ampersand(self):
        assert _escape_bibtex("AT&T Labs") == r"AT\&T Labs"

    def test_percent(self):
        assert _escape_bibtex("100% accuracy") == r"100\% accuracy"

    def test_dollar(self):
        assert _escape_bibtex("$x$ variable") == r"\$x\$ variable"

    def test_hash(self):
        assert _escape_bibtex("item #1") == r"item \#1"

    def test_underscore(self):
        assert _escape_bibtex("var_name") == r"var\_name"

    def test_tilde(self):
        assert _escape_bibtex("~approx") == r"\~{}approx"

    def test_caret(self):
        assert _escape_bibtex("x^2") == r"x\^{}2"

    def test_multiple_specials(self):
        assert _escape_bibtex("A & B % C") == r"A \& B \% C"

    def test_no_special(self):
        assert _escape_bibtex("plain text") == "plain text"


# --- BibTeX formatting ---


class TestFormatBibtex:
    def test_full_inproceedings(self):
        meta = BibMetadata(
            title="Attention Is All You Need",
            authors=["Ashish Vaswani", "Noam Shazeer"],
            year=2017,
            venue="Advances in Neural Information Processing Systems",
            doi="10.5555/3295222.3295349",
            arxiv_id="1706.03762",
            url="https://arxiv.org/abs/1706.03762",
            entry_type="inproceedings",
        )
        bib = format_bibtex(meta)
        assert bib.startswith("@inproceedings{vaswani2017attention,")
        assert "title = {Attention Is All You Need}" in bib
        assert "author = {Ashish Vaswani and Noam Shazeer}" in bib
        assert "year = {2017}" in bib
        assert "booktitle = {Advances in Neural Information Processing Systems}" in bib
        assert "doi = {10.5555/3295222.3295349}" in bib
        assert "eprint = {1706.03762}" in bib
        assert "archiveprefix = {arXiv}" in bib

    def test_arxiv_article(self):
        meta = BibMetadata(
            title="Some New Method",
            authors=["Jane Smith"],
            year=2023,
            arxiv_id="2301.12345",
            entry_type="article",
        )
        bib = format_bibtex(meta)
        assert bib.startswith("@article{smith2023some,")
        assert "journal = {arXiv preprint arXiv:2301.12345}" in bib

    def test_misc_entry(self):
        meta = BibMetadata(
            title="A Technical Report",
            authors=["Bob Jones"],
            year=2022,
            entry_type="misc",
        )
        bib = format_bibtex(meta)
        assert bib.startswith("@misc{jones2022technical,")

    def test_with_volume_pages(self):
        meta = BibMetadata(
            title="Deep Learning",
            authors=["Yann LeCun"],
            year=2015,
            venue="Nature",
            volume="521",
            number="7553",
            pages="436--444",
            publisher="Nature Publishing Group",
            entry_type="article",
        )
        bib = format_bibtex(meta)
        assert "volume = {521}" in bib
        assert "number = {7553}" in bib
        assert "pages = {436--444}" in bib
        assert "publisher = {Nature Publishing Group}" in bib
        assert "journal = {Nature}" in bib

    def test_escapes_ampersand_in_title(self):
        meta = BibMetadata(
            title="Language & Vision",
            authors=["Test Author"],
            year=2023,
            entry_type="misc",
        )
        bib = format_bibtex(meta)
        assert r"Language \& Vision" in bib

    def test_abstract_included(self):
        meta = BibMetadata(
            title="Test",
            authors=["Author"],
            year=2023,
            abstract="This is the abstract.",
            entry_type="misc",
        )
        bib = format_bibtex(meta)
        assert "abstract = {This is the abstract.}" in bib

    def test_closing_brace(self):
        meta = BibMetadata(title="Test", entry_type="misc")
        bib = format_bibtex(meta)
        assert bib.endswith("}")


# --- arxiv API fetch (mocked) ---


ARXIV_RESPONSE_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Attention Is All You Need</title>
    <author><name>Ashish Vaswani</name></author>
    <author><name>Noam Shazeer</name></author>
    <summary>The dominant sequence transduction models...</summary>
    <published>2017-06-12T00:00:00Z</published>
    <link href="http://dx.doi.org/10.5555/3295222" rel="related" title="doi"/>
  </entry>
</feed>
"""


class TestFetchArxivMetadata:
    @patch("paper.bibtex.httpx.get")
    def test_parses_response(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.text = ARXIV_RESPONSE_XML
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        meta = fetch_arxiv_metadata("1706.03762")
        assert meta.title == "Attention Is All You Need"
        assert meta.authors == ["Ashish Vaswani", "Noam Shazeer"]
        assert meta.year == 2017
        assert meta.month == "06"
        assert "dominant sequence" in meta.abstract
        assert meta.doi == "10.5555/3295222"

    @patch("paper.bibtex.httpx.get")
    def test_network_error_returns_fallback(self, mock_get):
        import httpx as _httpx

        mock_get.side_effect = _httpx.ConnectError("timeout")
        meta = fetch_arxiv_metadata("1706.03762")
        assert meta.arxiv_id == "1706.03762"
        assert meta.title == ""

    @patch("paper.bibtex.httpx.get")
    def test_no_entry(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.text = '<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"></feed>'
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        meta = fetch_arxiv_metadata("0000.00000")
        assert meta.arxiv_id == "0000.00000"
        assert meta.title == ""


# --- Semantic Scholar fetch (mocked) ---


class TestFetchS2Metadata:
    @patch("paper.bibtex.httpx.get")
    def test_parses_response(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "title": "Attention Is All You Need",
            "authors": [{"name": "Ashish Vaswani"}, {"name": "Noam Shazeer"}],
            "year": 2017,
            "venue": "Neural Information Processing Systems",
            "externalIds": {"DOI": "10.5555/3295222.3295349", "ArXiv": "1706.03762"},
            "publicationVenue": {"name": "Neural Information Processing Systems"},
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        meta = fetch_s2_metadata("1706.03762")
        assert meta is not None
        assert meta.venue == "Neural Information Processing Systems"
        assert meta.doi == "10.5555/3295222.3295349"
        assert meta.authors == ["Ashish Vaswani", "Noam Shazeer"]

    @patch("paper.bibtex.httpx.get")
    def test_404_returns_none(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_get.return_value = mock_resp

        assert fetch_s2_metadata("0000.00000") is None

    @patch("paper.bibtex.httpx.get")
    def test_network_error_returns_none(self, mock_get):
        import httpx

        mock_get.side_effect = httpx.ConnectError("timeout")
        assert fetch_s2_metadata("1706.03762") is None


# --- Crossref fetch (mocked) ---


class TestFetchCrossrefMetadata:
    @patch("paper.bibtex.httpx.get")
    def test_parses_response(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "message": {
                "title": ["Deep Learning"],
                "author": [
                    {"given": "Yann", "family": "LeCun"},
                    {"given": "Yoshua", "family": "Bengio"},
                ],
                "published-print": {"date-parts": [[2015]]},
                "container-title": ["Nature"],
                "volume": "521",
                "issue": "7553",
                "page": "436-444",
                "publisher": "Nature Publishing Group",
                "type": "journal-article",
            }
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        meta = fetch_crossref_metadata("10.1038/nature14539")
        assert meta is not None
        assert meta.title == "Deep Learning"
        assert meta.authors == ["Yann LeCun", "Yoshua Bengio"]
        assert meta.year == 2015
        assert meta.venue == "Nature"
        assert meta.volume == "521"
        assert meta.pages == "436-444"
        assert meta.entry_type == "article"

    @patch("paper.bibtex.httpx.get")
    def test_404_returns_none(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_get.return_value = mock_resp

        assert fetch_crossref_metadata("10.0000/nonexistent") is None


# --- Enrichment orchestrator (mocked) ---


class TestEnrichMetadata:
    @patch("paper.bibtex.fetch_crossref_metadata")
    @patch("paper.bibtex.fetch_s2_metadata")
    @patch("paper.bibtex.fetch_arxiv_metadata")
    def test_combines_sources(self, mock_arxiv, mock_s2, mock_crossref):
        mock_arxiv.return_value = BibMetadata(
            title="Attention Is All You Need",
            authors=["Ashish Vaswani", "Noam Shazeer"],
            year=2017,
            abstract="The dominant sequence...",
            arxiv_id="1706.03762",
        )
        mock_s2.return_value = BibMetadata(
            venue="NeurIPS",
            doi="10.5555/3295222.3295349",
            authors=["Ashish Vaswani", "Noam Shazeer", "Niki Parmar"],
        )
        mock_crossref.return_value = BibMetadata(
            venue="Advances in Neural Information Processing Systems",
            volume="30",
            pages="5998--6008",
            publisher="Curran Associates",
            entry_type="inproceedings",
        )

        doc = _make_doc()
        meta = enrich_metadata(doc)

        assert meta.title == "Attention Is All You Need"
        assert len(meta.authors) == 3  # S2 had more authors
        assert meta.year == 2017
        assert meta.venue == "Advances in Neural Information Processing Systems"
        assert meta.doi == "10.5555/3295222.3295349"
        assert meta.volume == "30"
        assert meta.entry_type == "inproceedings"

    @patch("paper.bibtex.fetch_crossref_metadata")
    @patch("paper.bibtex.fetch_s2_metadata")
    @patch("paper.bibtex.fetch_arxiv_metadata")
    def test_arxiv_only_fallback(self, mock_arxiv, mock_s2, mock_crossref):
        mock_arxiv.return_value = BibMetadata(
            title="New Paper",
            authors=["Author One"],
            year=2024,
            arxiv_id="2401.00001",
        )
        mock_s2.return_value = None
        mock_crossref.return_value = None

        doc = _make_doc(title="New Paper", authors=["Author One"], arxiv_id="2401.00001")
        meta = enrich_metadata(doc)

        assert meta.title == "New Paper"
        assert meta.entry_type == "article"  # arxiv default
        assert meta.venue == ""

    @patch("paper.bibtex.fetch_crossref_metadata")
    @patch("paper.bibtex.fetch_s2_metadata")
    @patch("paper.bibtex.fetch_arxiv_metadata")
    def test_local_pdf_no_arxiv(self, mock_arxiv, mock_s2, mock_crossref):
        doc = _make_doc(title="Local Paper", authors=["Test"], arxiv_id="")
        meta = enrich_metadata(doc)

        # Should not call arxiv or s2 APIs
        mock_arxiv.assert_not_called()
        mock_s2.assert_not_called()
        assert meta.title == "Local Paper"
        assert meta.entry_type == "misc"


# --- generate_bibtex with caching ---


class TestGenerateBibtex:
    @patch("paper.bibtex.enrich_metadata")
    def test_caches_result(self, mock_enrich, tmp_papers_dir):
        mock_enrich.return_value = BibMetadata(
            title="Test Paper",
            authors=["Test Author"],
            year=2023,
            entry_type="misc",
        )

        doc = _make_doc(title="Test Paper", arxiv_id="2301.00001")
        bib1 = generate_bibtex("2301.00001", doc)
        assert "@misc{" in bib1

        # Second call should use cache
        bib2 = generate_bibtex("2301.00001", doc)
        assert bib1 == bib2
        assert mock_enrich.call_count == 1  # Only called once

    @patch("paper.bibtex.enrich_metadata")
    def test_force_refetch(self, mock_enrich, tmp_papers_dir):
        mock_enrich.return_value = BibMetadata(
            title="Test Paper",
            authors=["Test Author"],
            year=2023,
            entry_type="misc",
        )

        doc = _make_doc(title="Test Paper", arxiv_id="2301.00001")
        generate_bibtex("2301.00001", doc)
        generate_bibtex("2301.00001", doc, force=True)
        assert mock_enrich.call_count == 2  # Called again with force
