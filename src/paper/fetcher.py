"""Download papers from arxiv and manage local PDF cache."""

from __future__ import annotations

import hashlib
import logging
import os
import re
import tempfile
from pathlib import Path

import httpx
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, DownloadColumn
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from paper import storage

logger = logging.getLogger(__name__)

# Default download timeout in seconds. Override with PAPER_DOWNLOAD_TIMEOUT env var.
DEFAULT_TIMEOUT = int(os.environ.get("PAPER_DOWNLOAD_TIMEOUT", "120"))

# Email for Unpaywall API (no key needed, just an email identifier).
UNPAYWALL_EMAIL = os.environ.get(
    "UNPAYWALL_EMAIL", "agent-papers-cli@users.noreply.github.com"
)

# Patterns for arxiv ID extraction
ARXIV_ID_PATTERNS = [
    # Direct ID: 2301.12345 or 2301.12345v2
    re.compile(r"^(\d{4}\.\d{4,5}(?:v\d+)?)$"),
    # URL: arxiv.org/abs/2301.12345 or arxiv.org/pdf/2301.12345
    re.compile(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5}(?:v\d+)?)"),
    # Old-style: arxiv.org/abs/cs/0123456
    re.compile(r"arxiv\.org/(?:abs|pdf)/([\w.-]+/\d{7}(?:v\d+)?)"),
]

# Patterns for DOI extraction
DOI_URL_PATTERN = re.compile(r"(?:https?://)?doi\.org/(10\.\d{4,9}/[^\s]+)")
DOI_BARE_PATTERN = re.compile(r"^(10\.\d{4,9}/[^\s]+)$")


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


def resolve_doi(reference: str) -> str | None:
    """Extract a DOI from a bare DOI or doi.org URL.

    Returns the DOI string (e.g. ``10.1038/s41586-023-06845-4``) or None.
    """
    reference = reference.strip().rstrip("/")
    m = DOI_URL_PATTERN.search(reference)
    if m:
        return m.group(1).rstrip(".")
    m = DOI_BARE_PATTERN.match(reference)
    if m:
        return m.group(1).rstrip(".")
    return None


def _doi_to_paper_id(doi: str) -> str:
    """Convert a DOI into a cache-safe paper_id.

    Uses ``doi-`` prefix with slashes replaced by underscores, matching
    the sanitisation in :func:`storage._sanitize_paper_id`.
    """
    return f"doi-{doi}"


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((httpx.TransportError, httpx.TimeoutException)),
    reraise=True,
)
def _resolve_doi_to_pdf_url(doi: str) -> str:
    """Resolve a DOI to a downloadable PDF URL.

    Resolution strategies (tried in order):
    1. bioRxiv/medRxiv DOIs (``10.1101/...``) -- use the bioRxiv API.
    2. Unpaywall API -- returns open-access PDF links for free.
    3. Direct ``doi.org`` redirect with ``Accept: application/pdf``.

    Raises :class:`ValueError` if no PDF URL can be found.
    """
    # --- Strategy 1: bioRxiv / medRxiv ---
    if doi.startswith("10.1101/"):
        url = _resolve_biorxiv_doi(doi)
        if url:
            return url

    # --- Strategy 2: Unpaywall API ---
    url = _resolve_unpaywall(doi)
    if url:
        return url

    # --- Strategy 3: Direct doi.org with Accept: application/pdf ---
    url = _resolve_doi_direct(doi)
    if url:
        return url

    raise ValueError(
        f"Could not find an open-access PDF for DOI: {doi}\n"
        "The paper may not be freely available. Try downloading the PDF "
        "manually and passing the local file path instead."
    )


def _resolve_biorxiv_doi(doi: str) -> str | None:
    """Resolve a bioRxiv/medRxiv DOI via the bioRxiv API."""
    # The bioRxiv API returns metadata including the PDF URL.
    # https://api.biorxiv.org/details/biorxiv/{doi}
    for server in ("biorxiv", "medrxiv"):
        api_url = f"https://api.biorxiv.org/details/{server}/{doi}"
        try:
            resp = httpx.get(api_url, timeout=DEFAULT_TIMEOUT, follow_redirects=True)
            if resp.status_code == 200:
                data = resp.json()
                collection = data.get("collection", [])
                if collection:
                    # Use the latest version
                    entry = collection[-1]
                    jatsxml = entry.get("jatsxml", "")
                    # jatsxml looks like:
                    # "https://www.biorxiv.org/content/10.1101/2022.03.19.484946v2"
                    # Append .full.pdf to get the PDF
                    if jatsxml:
                        return jatsxml + ".full.pdf"
        except (httpx.HTTPError, ValueError, KeyError):
            logger.debug("bioRxiv API failed for %s on %s", doi, server)
            continue
    return None


def _resolve_unpaywall(doi: str) -> str | None:
    """Resolve a DOI to a PDF URL via the Unpaywall API."""
    api_url = f"https://api.unpaywall.org/v2/{doi}"
    try:
        resp = httpx.get(
            api_url,
            params={"email": UNPAYWALL_EMAIL},
            timeout=DEFAULT_TIMEOUT,
            follow_redirects=True,
        )
        if resp.status_code == 200:
            data = resp.json()
            best = data.get("best_oa_location")
            if best:
                pdf_url = best.get("url_for_pdf")
                if pdf_url:
                    return pdf_url
                # Some entries have url_for_landing_page but not url_for_pdf
                # Fall through to next strategy
    except (httpx.HTTPError, ValueError, KeyError):
        logger.debug("Unpaywall API failed for %s", doi)
    return None


def _resolve_doi_direct(doi: str) -> str | None:
    """Try resolving doi.org directly with Accept: application/pdf."""
    try:
        resp = httpx.head(
            f"https://doi.org/{doi}",
            headers={"Accept": "application/pdf"},
            follow_redirects=True,
            timeout=DEFAULT_TIMEOUT,
        )
        content_type = resp.headers.get("content-type", "")
        if resp.status_code == 200 and "pdf" in content_type.lower():
            return str(resp.url)
    except httpx.HTTPError:
        logger.debug("Direct doi.org resolution failed for %s", doi)
    return None


def pdf_url_for_id(arxiv_id: str) -> str:
    return f"https://arxiv.org/pdf/{arxiv_id}"


def abs_url_for_id(arxiv_id: str) -> str:
    return f"https://arxiv.org/abs/{arxiv_id}"


def _download_pdf(url: str, dest: Path, label: str) -> None:
    """Download a PDF from *url* to *dest* with a Rich progress bar.

    Uses a temp file + atomic rename so partial downloads don't pollute
    the cache.
    """
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
            task = progress.add_task(f"Downloading {label}...", total=None)

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


def fetch_paper(reference: str) -> tuple[str, Path]:
    """Fetch a paper PDF, returning (paper_id, pdf_path).

    Accepts arxiv IDs/URLs, DOIs (bare or doi.org URLs), or local PDF
    file paths.  Downloads and caches if not already present.
    """
    # Check if reference is a local PDF file
    ref_path = Path(reference).expanduser()
    if ref_path.suffix.lower() == ".pdf" and ref_path.is_file():
        abs_path = ref_path.resolve()
        paper_id = _local_paper_id(abs_path)
        storage.save_local_metadata(paper_id, abs_path)
        return paper_id, abs_path

    # Try arxiv first
    arxiv_id = resolve_arxiv_id(reference)
    if arxiv_id is not None:
        if storage.has_pdf(arxiv_id):
            return arxiv_id, storage.pdf_path(arxiv_id)

        url = pdf_url_for_id(arxiv_id)
        dest = storage.pdf_path(arxiv_id)
        _download_pdf(url, dest, arxiv_id)

        storage.save_metadata(arxiv_id, {
            "arxiv_id": arxiv_id,
            "url": abs_url_for_id(arxiv_id),
            "pdf_url": url,
        })
        return arxiv_id, dest

    # Try DOI
    doi = resolve_doi(reference)
    if doi is not None:
        paper_id = _doi_to_paper_id(doi)
        if storage.has_pdf(paper_id):
            return paper_id, storage.pdf_path(paper_id)

        pdf_url = _resolve_doi_to_pdf_url(doi)
        dest = storage.pdf_path(paper_id)
        _download_pdf(pdf_url, dest, doi)

        storage.save_metadata(paper_id, {
            "doi": doi,
            "url": f"https://doi.org/{doi}",
            "pdf_url": pdf_url,
        })
        return paper_id, dest

    raise ValueError(
        f"Could not parse reference: {reference}\n"
        "Accepted formats: arxiv ID (2301.12345), arxiv URL, "
        "DOI (10.1038/...), doi.org URL, or /path/to/paper.pdf"
    )
