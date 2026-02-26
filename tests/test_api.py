"""Verify that the public API modules export all expected symbols."""


def test_search_api_imports():
    from search.api import (
        search_papers, search_snippets, get_citations, get_references,
        get_paper_details, search_scholar, search_web, search_pubmed, browse,
        SearchResult, SnippetResult, CitationResult, BrowseResult,
    )
    for fn in (search_papers, search_snippets, get_citations, get_references,
               get_paper_details, search_scholar, search_web, search_pubmed, browse):
        assert callable(fn)


def test_paper_api_imports():
    from paper.api import (
        fetch_paper, resolve_arxiv_id, parse_paper,
        has_pdf, has_parsed, pdf_path, list_papers,
        Document, Metadata, Section,
    )
    for fn in (fetch_paper, resolve_arxiv_id, parse_paper,
               has_pdf, has_parsed, pdf_path, list_papers):
        assert callable(fn)
