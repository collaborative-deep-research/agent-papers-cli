"""Tests for search renderer output formatting."""

from io import StringIO

from rich.console import Console

from search.models import BrowseResult, CitationResult, SearchResult, SnippetResult
from search.renderer import (
    render_browse_result,
    render_citation_results,
    render_paper_details,
    render_search_results,
    render_snippet_results,
)


def _capture_output(render_fn, *args, **kwargs) -> str:
    """Capture Rich console output as plain text."""
    buf = StringIO()
    # Temporarily replace the module-level console
    import search.renderer as mod
    original = mod.console
    mod.console = Console(file=buf, force_terminal=False, width=120)
    try:
        render_fn(*args, **kwargs)
    finally:
        mod.console = original
    return buf.getvalue()


class TestRenderSearchResults:
    def test_empty_results(self):
        output = _capture_output(render_search_results, [])
        assert "No results found" in output

    def test_reference_ids(self):
        results = [
            SearchResult(title="Paper A", url="https://example.com/a", snippet="Snippet A"),
            SearchResult(title="Paper B", url="https://example.com/b", snippet="Snippet B"),
        ]
        output = _capture_output(render_search_results, results)
        assert "[r1]" in output
        assert "[r2]" in output
        assert "Paper A" in output
        assert "Paper B" in output

    def test_arxiv_suggestive_prompt(self):
        results = [
            SearchResult(
                title="RLHF Paper",
                url="https://arxiv.org/abs/2204.05862",
                arxiv_id="2204.05862",
            ),
        ]
        output = _capture_output(render_search_results, results)
        assert "paper read 2204.05862" in output
        assert "paper outline 2204.05862" in output

    def test_non_arxiv_suggestive_prompt(self):
        results = [
            SearchResult(title="Blog Post", url="https://blog.example.com/post"),
        ]
        output = _capture_output(render_search_results, results)
        assert "search browse" in output

    def test_metadata_display(self):
        results = [
            SearchResult(
                title="T",
                authors="Alice, Bob",
                year=2024,
                venue="NeurIPS",
                citation_count=100,
            ),
        ]
        output = _capture_output(render_search_results, results)
        assert "Alice, Bob" in output
        assert "2024" in output
        assert "NeurIPS" in output
        assert "cited by 100" in output

    def test_source_header(self):
        results = [SearchResult(title="T")]
        output = _capture_output(render_search_results, results, source="Google")
        assert "from Google" in output


class TestRenderSnippetResults:
    def test_empty(self):
        output = _capture_output(render_snippet_results, [])
        assert "No snippets found" in output

    def test_snippet_output(self):
        results = [
            SnippetResult(
                text="RLHF aligns models.",
                section="Introduction",
                kind="abstract",
                paper_title="Survey Paper",
                score=0.95,
            ),
        ]
        output = _capture_output(render_snippet_results, results)
        assert "[s1]" in output
        assert "Survey Paper" in output
        assert "RLHF aligns models" in output
        assert "0.95" in output


class TestRenderCitationResults:
    def test_empty(self):
        output = _capture_output(render_citation_results, [], direction="citations")
        assert "No citations found" in output

    def test_citation_output(self):
        results = [
            CitationResult(
                title="Citing Paper",
                paper_id="xyz",
                year=2025,
                is_influential=True,
                contexts=["...as shown by..."],
            ),
        ]
        output = _capture_output(render_citation_results, results)
        assert "[c1]" in output
        assert "Citing Paper" in output
        assert "*" in output  # influential marker
        assert "as shown by" in output

    def test_details_suggestion(self):
        results = [CitationResult(title="T", paper_id="abc123")]
        output = _capture_output(render_citation_results, results)
        assert "search semanticscholar details abc123" in output


class TestRenderPaperDetails:
    def test_full_details(self):
        result = SearchResult(
            title="Detail Paper",
            url="https://arxiv.org/abs/2301.99999",
            snippet="Full abstract.",
            year=2023,
            authors="Eve, Frank",
            venue="ACL",
            citation_count=200,
            paper_id="abc",
            arxiv_id="2301.99999",
        )
        output = _capture_output(render_paper_details, result)
        assert "Detail Paper" in output
        assert "paper read 2301.99999" in output
        assert "citations abc" in output
        assert "references abc" in output


class TestRenderBrowseResult:
    def test_browse_output(self):
        result = BrowseResult(
            url="https://example.com",
            title="Example",
            content="Page content here.",
            word_count=3,
        )
        output = _capture_output(render_browse_result, result)
        assert "3 words" in output
        assert "Page content here" in output
