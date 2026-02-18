"""Web content extraction via Jina Reader or Serper scrape."""

from __future__ import annotations

import httpx

from search.config import get_jina_key, get_serper_key
from search.models import BrowseResult

TIMEOUT = 30


def browse_jina(url: str, *, timeout: int = TIMEOUT) -> BrowseResult:
    """Fetch webpage content using Jina Reader API."""
    api_key = get_jina_key()

    resp = httpx.get(
        f"https://r.jina.ai/{url}",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json().get("data", {})

    content = data.get("content", "")
    return BrowseResult(
        url=data.get("url", url),
        title=data.get("title", ""),
        content=content,
        word_count=len(content.split()),
    )


def browse_serper(url: str, *, timeout: int = TIMEOUT) -> BrowseResult:
    """Fetch webpage content using Serper scrape API."""
    api_key = get_serper_key()

    resp = httpx.post(
        "https://scrape.serper.dev",
        json={"url": url, "includeMarkdown": True},
        headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()

    content = data.get("markdown") or data.get("text", "")
    return BrowseResult(
        url=url,
        title=data.get("metadata", {}).get("title", ""),
        content=content,
        word_count=len(content.split()),
    )


def browse(url: str, *, backend: str = "jina", timeout: int = TIMEOUT) -> BrowseResult:
    """Fetch webpage content using the specified backend."""
    if backend == "jina":
        return browse_jina(url, timeout=timeout)
    elif backend == "serper":
        return browse_serper(url, timeout=timeout)
    else:
        raise ValueError(f"Unknown browse backend: {backend!r}. Use 'jina' or 'serper'.")
