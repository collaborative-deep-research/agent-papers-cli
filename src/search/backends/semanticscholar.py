"""Semantic Scholar API wrapper."""

from __future__ import annotations

import os
from typing import Optional

import httpx
from tenacity import retry, retry_if_result, stop_after_attempt, wait_exponential

from search.config import get_s2_key
from search.models import CitationResult, SearchResult, SnippetResult

TIMEOUT = int(os.getenv("API_TIMEOUT", "15"))

S2_BASE = "https://api.semanticscholar.org/graph/v1"
PAPER_FIELDS = (
    "paperId,corpusId,url,title,abstract,authors,authors.name,"
    "year,venue,citationCount,openAccessPdf,externalIds,isOpenAccess"
)
CITATION_FIELDS = (
    "paperId,corpusId,contexts,intents,isInfluential,"
    "title,abstract,venue,year,authors"
)


def _headers() -> dict[str, str]:
    key = get_s2_key()
    if key:
        return {"x-api-key": key}
    return {}


@retry(
    retry=retry_if_result(lambda r: r.status_code == 429),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
)
def _get(url: str, **kwargs) -> httpx.Response:
    return httpx.get(url, **kwargs)


def _extract_arxiv_id(paper: dict) -> str:
    ext = paper.get("externalIds") or {}
    return ext.get("ArXiv", "")


def _format_authors(paper: dict) -> str:
    authors = paper.get("authors") or []
    names = [a.get("name", "") for a in authors[:3]]
    if len(authors) > 3:
        names.append("et al.")
    return ", ".join(names)


def _paper_to_result(paper: dict) -> SearchResult:
    arxiv_id = _extract_arxiv_id(paper)
    pdf = paper.get("openAccessPdf") or {}
    url = pdf.get("url") or paper.get("url", "")
    if not url and arxiv_id:
        url = f"https://arxiv.org/abs/{arxiv_id}"
    return SearchResult(
        title=paper.get("title", ""),
        url=url,
        snippet=(paper.get("abstract") or "")[:300],
        year=paper.get("year"),
        authors=_format_authors(paper),
        venue=paper.get("venue", ""),
        citation_count=paper.get("citationCount"),
        paper_id=paper.get("paperId", ""),
        arxiv_id=arxiv_id,
    )


def search_papers(
    query: str,
    *,
    year: Optional[str] = None,
    min_citations: Optional[int] = None,
    venue: Optional[str] = None,
    sort: Optional[str] = None,
    limit: int = 10,
    offset: int = 0,
) -> list[SearchResult]:
    """Keyword search for papers."""
    params: dict = {
        "query": query,
        "offset": offset,
        "limit": min(limit, 100),
        "fields": PAPER_FIELDS,
    }
    if year:
        params["year"] = year
    if min_citations is not None:
        params["minCitationCount"] = min_citations
    if venue:
        params["venue"] = venue
    if sort:
        params["sort"] = sort

    resp = _get(
        f"{S2_BASE}/paper/search",
        params=params,
        headers=_headers(),
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()

    return [_paper_to_result(p) for p in data.get("data", [])]


def search_snippets(
    query: str,
    *,
    year: Optional[str] = None,
    paper_ids: Optional[str] = None,
    venue: Optional[str] = None,
    limit: int = 10,
) -> list[SnippetResult]:
    """Snippet search — returns relevant text passages from papers."""
    params: dict = {"query": query, "limit": limit}
    if year:
        params["year"] = year
    if paper_ids:
        params["paperIds"] = paper_ids
    if venue:
        params["venue"] = venue

    resp = _get(
        f"{S2_BASE}/snippet/search",
        params=params,
        headers=_headers(),
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()

    results = []
    for item in data.get("data", []):
        snippet = item.get("snippet", {})
        paper = item.get("paper", {})
        results.append(
            SnippetResult(
                text=snippet.get("text", ""),
                section=snippet.get("section", ""),
                kind=snippet.get("snippetKind", ""),
                paper_title=paper.get("title", ""),
                paper_id=paper.get("corpusId", ""),
                score=item.get("score", 0.0),
            )
        )
    return results


def get_citations(
    paper_id: str,
    *,
    limit: int = 20,
    offset: int = 0,
) -> list[CitationResult]:
    """Get papers that cite the given paper."""
    resp = _get(
        f"{S2_BASE}/paper/{paper_id}/citations",
        params={"offset": offset, "limit": limit, "fields": CITATION_FIELDS},
        headers=_headers(),
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()

    results = []
    for item in data.get("data", []):
        citing = item.get("citingPaper", {})
        results.append(
            CitationResult(
                title=citing.get("title", ""),
                paper_id=citing.get("paperId", ""),
                year=citing.get("year"),
                venue=citing.get("venue", ""),
                authors=_format_authors(citing),
                is_influential=item.get("isInfluential", False),
                contexts=item.get("contexts", []),
            )
        )
    return results


def get_references(
    paper_id: str,
    *,
    limit: int = 20,
    offset: int = 0,
) -> list[CitationResult]:
    """Get papers referenced by the given paper."""
    resp = _get(
        f"{S2_BASE}/paper/{paper_id}/references",
        params={"offset": offset, "limit": limit, "fields": CITATION_FIELDS},
        headers=_headers(),
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()

    results = []
    for item in data.get("data", []):
        cited = item.get("citedPaper", {})
        results.append(
            CitationResult(
                title=cited.get("title", ""),
                paper_id=cited.get("paperId", ""),
                year=cited.get("year"),
                venue=cited.get("venue", ""),
                authors=_format_authors(cited),
                is_influential=item.get("isInfluential", False),
                contexts=item.get("contexts", []),
            )
        )
    return results


def get_paper_details(paper_id: str) -> SearchResult:
    """Get details for a single paper."""
    resp = _get(
        f"{S2_BASE}/paper/{paper_id}",
        params={"fields": PAPER_FIELDS},
        headers=_headers(),
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    return _paper_to_result(resp.json())
