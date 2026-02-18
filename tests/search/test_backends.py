"""Tests for search backends with mocked HTTP calls."""

from unittest.mock import patch, MagicMock

import pytest

from search.models import SearchResult, SnippetResult, CitationResult, BrowseResult


# --- Fixtures for mock responses ---


def _mock_response(json_data, status_code=200):
    """Create a mock httpx.Response."""
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = json_data
    mock.raise_for_status.return_value = None
    return mock


# --- Google backend ---


class TestGoogleWeb:
    @patch("search.backends.google.httpx.post")
    def test_search_web(self, mock_post, monkeypatch):
        monkeypatch.setenv("SERPER_API_KEY", "test-key")
        mock_post.return_value = _mock_response({
            "organic": [
                {
                    "title": "RLHF Paper",
                    "link": "https://arxiv.org/abs/2204.05862",
                    "snippet": "We apply RLHF...",
                    "position": 1,
                },
                {
                    "title": "Some Blog",
                    "link": "https://blog.example.com/rlhf",
                    "snippet": "A guide to RLHF.",
                    "position": 2,
                },
            ]
        })

        from search.backends.google import search_web
        results = search_web("RLHF", num_results=2)

        assert len(results) == 2
        assert results[0].title == "RLHF Paper"
        assert results[0].arxiv_id == "2204.05862"
        assert results[1].arxiv_id == ""
        mock_post.assert_called_once()

    @patch("search.backends.google.httpx.post")
    def test_search_scholar(self, mock_post, monkeypatch):
        monkeypatch.setenv("SERPER_API_KEY", "test-key")
        mock_post.return_value = _mock_response({
            "organic": [
                {
                    "title": "Attention Is All You Need",
                    "link": "https://arxiv.org/abs/1706.03762",
                    "snippet": "We propose...",
                    "publicationInfo": "Vaswani et al.",
                    "year": 2017,
                    "citedBy": 100000,
                },
            ]
        })

        from search.backends.google import search_scholar
        results = search_scholar("attention mechanism")

        assert len(results) == 1
        assert results[0].year == 2017
        assert results[0].citation_count == 100000
        assert results[0].authors == "Vaswani et al."

    @patch("search.backends.google.httpx.post")
    def test_scholar_year_string(self, mock_post, monkeypatch):
        monkeypatch.setenv("SERPER_API_KEY", "test-key")
        mock_post.return_value = _mock_response({
            "organic": [{"title": "T", "link": "", "snippet": "", "year": "2023", "citedBy": 0}]
        })

        from search.backends.google import search_scholar
        results = search_scholar("test")
        assert results[0].year == 2023


# --- Semantic Scholar backend ---


class TestSemanticScholarPapers:
    @patch("search.backends.semanticscholar._get")
    def test_search_papers(self, mock_get):
        mock_get.return_value = _mock_response({
            "total": 100,
            "offset": 0,
            "next": 10,
            "data": [
                {
                    "paperId": "abc123",
                    "corpusId": "456",
                    "url": "https://www.semanticscholar.org/paper/abc123",
                    "title": "Test Paper",
                    "abstract": "An abstract about testing.",
                    "authors": [{"name": "Alice"}, {"name": "Bob"}],
                    "year": 2024,
                    "venue": "NeurIPS",
                    "citationCount": 50,
                    "openAccessPdf": {"url": "https://arxiv.org/pdf/2401.00001"},
                    "externalIds": {"ArXiv": "2401.00001"},
                    "isOpenAccess": True,
                },
            ],
        })

        from search.backends.semanticscholar import search_papers
        results = search_papers("test", limit=1)

        assert len(results) == 1
        assert results[0].title == "Test Paper"
        assert results[0].arxiv_id == "2401.00001"
        assert results[0].year == 2024
        assert results[0].citation_count == 50
        assert "Alice" in results[0].authors

    @patch("search.backends.semanticscholar._get")
    def test_search_papers_with_filters(self, mock_get):
        mock_get.return_value = _mock_response({"total": 0, "offset": 0, "next": 0, "data": []})

        from search.backends.semanticscholar import search_papers
        results = search_papers("test", year="2023-2024", min_citations=10, venue="ACL")

        assert results == []
        call_kwargs = mock_get.call_args
        params = call_kwargs.kwargs.get("params") or call_kwargs[1].get("params", {})
        assert params["year"] == "2023-2024"
        assert params["minCitationCount"] == 10
        assert params["venue"] == "ACL"


class TestSemanticScholarSnippets:
    @patch("search.backends.semanticscholar._get")
    def test_search_snippets(self, mock_get):
        mock_get.return_value = _mock_response({
            "data": [
                {
                    "snippet": {
                        "text": "RLHF aligns language models with human preferences.",
                        "section": "Introduction",
                        "snippetKind": "abstract",
                    },
                    "paper": {
                        "title": "RLHF Survey",
                        "corpusId": "789",
                    },
                    "score": 0.92,
                },
            ],
        })

        from search.backends.semanticscholar import search_snippets
        results = search_snippets("RLHF alignment")

        assert len(results) == 1
        assert results[0].text == "RLHF aligns language models with human preferences."
        assert results[0].section == "Introduction"
        assert results[0].score == 0.92


class TestSemanticScholarCitations:
    @patch("search.backends.semanticscholar._get")
    def test_get_citations(self, mock_get):
        mock_get.return_value = _mock_response({
            "data": [
                {
                    "citingPaper": {
                        "paperId": "xyz",
                        "title": "Follow-up Paper",
                        "year": 2025,
                        "venue": "ICML",
                        "authors": [{"name": "Carol"}],
                    },
                    "isInfluential": True,
                    "contexts": ["...building on the work of..."],
                },
            ],
        })

        from search.backends.semanticscholar import get_citations
        results = get_citations("abc123", limit=1)

        assert len(results) == 1
        assert results[0].title == "Follow-up Paper"
        assert results[0].is_influential
        assert len(results[0].contexts) == 1

    @patch("search.backends.semanticscholar._get")
    def test_get_references(self, mock_get):
        mock_get.return_value = _mock_response({
            "data": [
                {
                    "citedPaper": {
                        "paperId": "ref1",
                        "title": "Foundation Paper",
                        "year": 2020,
                        "venue": "NeurIPS",
                        "authors": [{"name": "Dave"}],
                    },
                    "isInfluential": False,
                    "contexts": [],
                },
            ],
        })

        from search.backends.semanticscholar import get_references
        results = get_references("abc123")

        assert len(results) == 1
        assert results[0].title == "Foundation Paper"
        assert not results[0].is_influential


class TestSemanticScholarDetails:
    @patch("search.backends.semanticscholar._get")
    def test_get_paper_details(self, mock_get):
        mock_get.return_value = _mock_response({
            "paperId": "abc",
            "corpusId": "123",
            "url": "https://www.semanticscholar.org/paper/abc",
            "title": "Detail Paper",
            "abstract": "Full abstract here.",
            "authors": [{"name": "Eve"}, {"name": "Frank"}, {"name": "Grace"}, {"name": "Heidi"}],
            "year": 2023,
            "venue": "ACL",
            "citationCount": 200,
            "openAccessPdf": None,
            "externalIds": {"ArXiv": "2301.99999"},
            "isOpenAccess": True,
        })

        from search.backends.semanticscholar import get_paper_details
        result = get_paper_details("abc")

        assert result.title == "Detail Paper"
        assert result.arxiv_id == "2301.99999"
        assert "et al." in result.authors  # 4 authors -> truncated


# --- PubMed backend ---


class TestPubMed:
    @patch("search.backends.pubmed.httpx.get")
    def test_search_pubmed(self, mock_get):
        # First call: esearch (returns IDs)
        search_xml = b"""<?xml version="1.0"?>
        <eSearchResult>
            <Count>100</Count>
            <RetStart>0</RetStart>
            <RetMax>1</RetMax>
            <IdList>
                <Id>12345678</Id>
            </IdList>
        </eSearchResult>"""

        # Second call: efetch (returns details)
        fetch_xml = b"""<?xml version="1.0"?>
        <PubmedArticleSet>
            <PubmedArticle>
                <MedlineCitation>
                    <PMID>12345678</PMID>
                    <Article>
                        <ArticleTitle>CRISPR Gene Therapy Study</ArticleTitle>
                        <Abstract>
                            <AbstractText>A study on CRISPR applications.</AbstractText>
                        </Abstract>
                        <AuthorList>
                            <Author>
                                <LastName>Smith</LastName>
                                <ForeName>John</ForeName>
                            </Author>
                        </AuthorList>
                        <Journal>
                            <Title>Nature</Title>
                            <JournalIssue>
                                <PubDate><Year>2024</Year></PubDate>
                            </JournalIssue>
                        </Journal>
                    </Article>
                </MedlineCitation>
            </PubmedArticle>
        </PubmedArticleSet>"""

        search_resp = MagicMock()
        search_resp.status_code = 200
        search_resp.content = search_xml
        search_resp.raise_for_status.return_value = None

        fetch_resp = MagicMock()
        fetch_resp.status_code = 200
        fetch_resp.content = fetch_xml
        fetch_resp.raise_for_status.return_value = None

        mock_get.side_effect = [search_resp, fetch_resp]

        from search.backends.pubmed import search_pubmed
        results = search_pubmed("CRISPR", limit=1)

        assert len(results) == 1
        assert results[0].title == "CRISPR Gene Therapy Study"
        assert results[0].year == 2024
        assert "Smith" in results[0].authors
        assert "pubmed.ncbi.nlm.nih.gov" in results[0].url

    @patch("search.backends.pubmed.httpx.get")
    def test_search_pubmed_no_results(self, mock_get):
        search_xml = b"""<?xml version="1.0"?>
        <eSearchResult>
            <Count>0</Count>
            <RetStart>0</RetStart>
            <RetMax>10</RetMax>
            <IdList/>
        </eSearchResult>"""

        resp = MagicMock()
        resp.status_code = 200
        resp.content = search_xml
        resp.raise_for_status.return_value = None
        mock_get.return_value = resp

        from search.backends.pubmed import search_pubmed
        results = search_pubmed("xyznonexistent")
        assert results == []


# --- Browse backend ---


class TestBrowseJina:
    @patch("search.backends.browse.httpx.get")
    def test_browse_jina(self, mock_get, monkeypatch):
        monkeypatch.setenv("JINA_API_KEY", "test-key")
        mock_get.return_value = _mock_response({
            "data": {
                "url": "https://example.com",
                "title": "Example Page",
                "content": "Hello world this is content",
            }
        })

        from search.backends.browse import browse_jina
        result = browse_jina("https://example.com")

        assert result.title == "Example Page"
        assert result.word_count == 5
        assert "Hello world" in result.content


class TestBrowseSerper:
    @patch("search.backends.browse.httpx.post")
    def test_browse_serper(self, mock_post, monkeypatch):
        monkeypatch.setenv("SERPER_API_KEY", "test-key")
        mock_post.return_value = _mock_response({
            "markdown": "# Example\n\nSome content here.",
            "metadata": {"title": "Example"},
        })

        from search.backends.browse import browse_serper
        result = browse_serper("https://example.com")

        assert result.title == "Example"
        assert "Some content here" in result.content


class TestBrowseDispatch:
    @patch("search.backends.browse.httpx.get")
    def test_browse_default_jina(self, mock_get, monkeypatch):
        monkeypatch.setenv("JINA_API_KEY", "test-key")
        mock_get.return_value = _mock_response({"data": {"url": "", "title": "", "content": "ok"}})

        from search.backends.browse import browse
        result = browse("https://example.com")
        assert result.content == "ok"

    def test_browse_unknown_backend(self):
        from search.backends.browse import browse
        with pytest.raises(ValueError, match="Unknown browse backend"):
            browse("https://example.com", backend="unknown")
