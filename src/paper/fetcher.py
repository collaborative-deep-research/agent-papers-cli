"""Download papers from arxiv and manage local PDF cache."""

from __future__ import annotations

import re
from pathlib import Path

import httpx
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, DownloadColumn

from paper import storage

# Patterns for arxiv ID extraction
ARXIV_ID_PATTERNS = [
    # Direct ID: 2301.12345 or 2301.12345v2
    re.compile(r"^(\d{4}\.\d{4,5}(?:v\d+)?)$"),
    # URL: arxiv.org/abs/2301.12345 or arxiv.org/pdf/2301.12345
    re.compile(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5}(?:v\d+)?)"),
    # Old-style: arxiv.org/abs/cs/0123456
    re.compile(r"arxiv\.org/(?:abs|pdf)/([\w.-]+/\d{7}(?:v\d+)?)"),
]


def resolve_arxiv_id(reference: str) -> str | None:
    """Extract arxiv ID from various input formats."""
    reference = reference.strip().rstrip("/")
    for pattern in ARXIV_ID_PATTERNS:
        m = pattern.search(reference)
        if m:
            return m.group(1)
    return None


def pdf_url_for_id(arxiv_id: str) -> str:
    return f"https://arxiv.org/pdf/{arxiv_id}"


def abs_url_for_id(arxiv_id: str) -> str:
    return f"https://arxiv.org/abs/{arxiv_id}"


def fetch_paper(reference: str) -> tuple[str, Path]:
    """Fetch a paper PDF, returning (arxiv_id, pdf_path).

    Downloads if not already cached.
    """
    arxiv_id = resolve_arxiv_id(reference)
    if arxiv_id is None:
        raise ValueError(
            f"Could not parse arxiv ID from: {reference}\n"
            "Accepted formats: 2301.12345, arxiv.org/abs/2301.12345, arxiv.org/pdf/2301.12345"
        )

    if storage.has_pdf(arxiv_id):
        return arxiv_id, storage.pdf_path(arxiv_id)

    url = pdf_url_for_id(arxiv_id)
    dest = storage.pdf_path(arxiv_id)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        DownloadColumn(),
    ) as progress:
        task = progress.add_task(f"Downloading {arxiv_id}...", total=None)

        with httpx.stream("GET", url, follow_redirects=True, timeout=60) as response:
            response.raise_for_status()
            total = int(response.headers.get("content-length", 0))
            if total:
                progress.update(task, total=total)

            with open(dest, "wb") as f:
                for chunk in response.iter_bytes(chunk_size=8192):
                    f.write(chunk)
                    progress.advance(task, len(chunk))

    # Save basic metadata
    storage.save_metadata(arxiv_id, {
        "arxiv_id": arxiv_id,
        "url": abs_url_for_id(arxiv_id),
        "pdf_url": url,
    })

    return arxiv_id, dest
