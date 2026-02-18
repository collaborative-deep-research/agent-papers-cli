"""Google web search via Serper API."""

from __future__ import annotations

import os

import httpx

from search.config import get_serper_key
from search.models import SearchResult

TIMEOUT = int(os.getenv("API_TIMEOUT", "10"))


def search_web(
    query: str,
    *,
    num_results: int = 10,
    gl: str = "us",
    hl: str = "en",
) -> list[SearchResult]:
    """Web search via Serper (Google)."""
    api_key = get_serper_key()
    resp = httpx.post(
        "https://google.serper.dev/search",
        json={"q": query, "num": num_results, "gl": gl, "hl": hl},
        headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()

    results = []
    for item in data.get("organic", []):
        arxiv_id = ""
        url = item.get("link", "")
        if "arxiv.org/abs/" in url:
            arxiv_id = url.split("arxiv.org/abs/")[-1].split("v")[0]
        elif "arxiv.org/pdf/" in url:
            arxiv_id = url.split("arxiv.org/pdf/")[-1].replace(".pdf", "").split("v")[0]

        results.append(
            SearchResult(
                title=item.get("title", ""),
                url=url,
                snippet=item.get("snippet", ""),
                arxiv_id=arxiv_id,
            )
        )
    return results


def search_scholar(
    query: str,
    *,
    num_results: int = 10,
) -> list[SearchResult]:
    """Google Scholar search via Serper."""
    api_key = get_serper_key()
    resp = httpx.post(
        "https://google.serper.dev/scholar",
        json={"q": query, "num": num_results},
        headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()

    results = []
    for item in data.get("organic", []):
        url = item.get("link", "")
        arxiv_id = ""
        if "arxiv.org/abs/" in url:
            arxiv_id = url.split("arxiv.org/abs/")[-1].split("v")[0]

        year = item.get("year")
        if isinstance(year, str):
            try:
                year = int(year)
            except ValueError:
                year = None

        results.append(
            SearchResult(
                title=item.get("title", ""),
                url=url,
                snippet=item.get("snippet", ""),
                authors=item.get("publicationInfo", ""),
                year=year,
                citation_count=item.get("citedBy"),
            )
        )
    return results
