"""Tests for search data models."""

from search.models import BrowseResult, CitationResult, SearchResult, SnippetResult


class TestSearchResult:
    def test_basic_creation(self):
        r = SearchResult(title="Test Paper", url="https://example.com")
        assert r.title == "Test Paper"
        assert r.url == "https://example.com"
        assert r.snippet == ""
        assert r.year is None
        assert r.citation_count is None

    def test_has_arxiv_from_id(self):
        r = SearchResult(title="T", arxiv_id="2302.13971")
        assert r.has_arxiv()

    def test_has_arxiv_from_url(self):
        r = SearchResult(title="T", url="https://arxiv.org/abs/2302.13971")
        assert r.has_arxiv()

    def test_no_arxiv(self):
        r = SearchResult(title="T", url="https://example.com")
        assert not r.has_arxiv()

    def test_full_result(self):
        r = SearchResult(
            title="RLHF Paper",
            url="https://arxiv.org/abs/2204.05862",
            snippet="We apply RLHF...",
            year=2022,
            authors="Bai et al.",
            venue="arXiv",
            citation_count=3612,
            paper_id="abc123",
            arxiv_id="2204.05862",
        )
        assert r.year == 2022
        assert r.citation_count == 3612
        assert r.has_arxiv()


class TestSnippetResult:
    def test_creation(self):
        s = SnippetResult(
            text="RLHF improves alignment",
            section="Introduction",
            kind="abstract",
            paper_title="Test",
            score=0.95,
        )
        assert s.text == "RLHF improves alignment"
        assert s.score == 0.95


class TestCitationResult:
    def test_creation(self):
        c = CitationResult(
            title="Citing Paper",
            paper_id="xyz",
            year=2024,
            is_influential=True,
            contexts=["...as shown by Bai et al..."],
        )
        assert c.is_influential
        assert len(c.contexts) == 1

    def test_defaults(self):
        c = CitationResult(title="T")
        assert not c.is_influential
        assert c.contexts == []


class TestBrowseResult:
    def test_creation(self):
        b = BrowseResult(
            url="https://example.com",
            title="Example",
            content="Hello world",
            word_count=2,
        )
        assert b.word_count == 2
