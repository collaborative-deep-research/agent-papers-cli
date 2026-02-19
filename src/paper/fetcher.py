"""Download papers from arxiv and manage local PDF cache."""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
from pathlib import Path

import httpx
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, DownloadColumn

from paper import storage

# Default download timeout in seconds. Override with PAPER_DOWNLOAD_TIMEOUT env var.
DEFAULT_TIMEOUT = int(os.environ.get("PAPER_DOWNLOAD_TIMEOUT", "120"))

# Patterns for arxiv ID extraction
ARXIV_ID_PATTERNS = [
    # Direct ID: 2301.12345 or 2301.12345v2
    re.compile(r"^(\d{4}\.\d{4,5}(?:v\d+)?)$"),
    # URL: arxiv.org/abs/2301.12345 or arxiv.org/pdf/2301.12345
    re.compile(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5}(?:v\d+)?)"),
    # Old-style: arxiv.org/abs/cs/0123456
    re.compile(r"arxiv\.org/(?:abs|pdf)/([\w.-]+/\d{7}(?:v\d+)?)"),
]


def _local_paper_id(abs_path: Path) -> str:
    """Generate a unique paper_id for a local PDF from its absolute path.

    Returns ``{stem}-{hash8}`` where hash8 is the first 8 chars of the
    SHA-256 of the absolute path string.  This avoids cache collisions
    when different directories contain PDFs with the same filename.
    """
    hash8 = hashlib.sha256(str(abs_path).encode()).hexdigest()[:8]
    return f"{abs_path.stem}-{hash8}"


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
    """Fetch a paper PDF, returning (paper_id, pdf_path).

    Accepts arxiv IDs/URLs or local PDF file paths.
    Downloads from arxiv if not already cached.
    """
    # Check if reference is a local PDF file
    ref_path = Path(reference).expanduser()
    if ref_path.suffix.lower() == ".pdf" and ref_path.is_file():
        abs_path = ref_path.resolve()
        paper_id = _local_paper_id(abs_path)
        storage.save_local_metadata(paper_id, abs_path)
        return paper_id, abs_path

    arxiv_id = resolve_arxiv_id(reference)
    if arxiv_id is None:
        raise ValueError(
            f"Could not parse reference: {reference}\n"
            "Accepted formats: 2301.12345, arxiv.org/abs/2301.12345, /path/to/paper.pdf"
        )

    if storage.has_pdf(arxiv_id):
        return arxiv_id, storage.pdf_path(arxiv_id)

    url = pdf_url_for_id(arxiv_id)
    dest = storage.pdf_path(arxiv_id)

    # Download to a temp file first, then rename on success
    tmp_fd, tmp_path = tempfile.mkstemp(
        dir=dest.parent, suffix=".download", prefix="paper_"
    )
    tmp_file = Path(tmp_path)

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            DownloadColumn(),
        ) as progress:
            task = progress.add_task(f"Downloading {arxiv_id}...", total=None)

            with httpx.stream("GET", url, follow_redirects=True, timeout=DEFAULT_TIMEOUT) as response:
                response.raise_for_status()
                total = int(response.headers.get("content-length", 0))
                if total:
                    progress.update(task, total=total)

                with os.fdopen(tmp_fd, "wb") as f:
                    for chunk in response.iter_bytes(chunk_size=8192):
                        f.write(chunk)
                        progress.advance(task, len(chunk))

        # Atomic rename on success
        tmp_file.rename(dest)
    except Exception:
        # Clean up partial download
        tmp_file.unlink(missing_ok=True)
        raise

    # Save basic metadata
    storage.save_metadata(arxiv_id, {
        "arxiv_id": arxiv_id,
        "url": abs_url_for_id(arxiv_id),
        "pdf_url": url,
    })

    return arxiv_id, dest
