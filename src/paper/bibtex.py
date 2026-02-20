"""Generate BibTeX entries for papers using multi-source metadata enrichment."""

from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Optional

import httpx

from paper import storage

TIMEOUT = int(os.getenv("PAPER_BIBTEX_TIMEOUT", "15"))

# --- Data model for enriched metadata ---


@dataclass
class BibMetadata:
    """Enriched bibliographic metadata from multiple sources."""

    title: str = ""
    authors: list[str] = field(default_factory=list)
    year: Optional[int] = None
    month: Optional[str] = None
    abstract: str = ""
    arxiv_id: str = ""
    doi: str = ""
    venue: str = ""
    volume: str = ""
    number: str = ""
    pages: str = ""
    publisher: str = ""
    url: str = ""
    entry_type: str = ""  # inproceedings, article, misc
    source: str = ""  # which API provided the venue/doi


# --- Citation key generation ---

_STOP_WORDS = {"a", "an", "the", "on", "in", "of", "for", "and", "with", "to", "from"}


def _make_citation_key(meta: BibMetadata) -> str:
    """Generate a citation key like vaswani2017attention."""
    # First author last name
    last_name = "unknown"
    if meta.authors:
        parts = meta.authors[0].split()
        if parts:
            last_name = parts[-1].lower()
            last_name = re.sub(r"[^a-z]", "", last_name)

    year = str(meta.year) if meta.year else ""

    # First meaningful word from title
    title_word = ""
    if meta.title:
        words = re.findall(r"[a-zA-Z]+", meta.title)
        for w in words:
            if w.lower() not in _STOP_WORDS:
                title_word = w.lower()
                break

    return f"{last_name}{year}{title_word}"


# --- Entry type detection ---

_CONFERENCE_PATTERNS = re.compile(
    r"\b(proceedings|proc\.|conference|conf\.|workshop|symposium|ICML|NeurIPS|ICLR|"
    r"ACL|EMNLP|NAACL|CVPR|ICCV|ECCV|AAAI|IJCAI|SIGIR|KDD|WWW|CHI|ICSE)\b",
    re.IGNORECASE,
)

_JOURNAL_PATTERNS = re.compile(
    r"\b(journal|transactions|letters|review|magazine|annals|J\.|Trans\.)\b",
    re.IGNORECASE,
)


def _detect_entry_type(meta: BibMetadata) -> str:
    """Detect whether the paper is inproceedings, article, or misc."""
    if meta.venue:
        if _CONFERENCE_PATTERNS.search(meta.venue):
            return "inproceedings"
        if _JOURNAL_PATTERNS.search(meta.venue):
            return "article"
        # Non-empty venue but unclear type — default to inproceedings
        return "inproceedings"

    if meta.arxiv_id:
        return "article"

    return "misc"


# --- arxiv API ---

_ARXIV_NS = {"atom": "http://www.w3.org/2005/Atom"}


def fetch_arxiv_metadata(arxiv_id: str) -> BibMetadata:
    """Fetch structured metadata from the arxiv API."""
    url = f"https://export.arxiv.org/api/query?id_list={arxiv_id}&max_results=1"
    resp = httpx.get(url, timeout=TIMEOUT, follow_redirects=True)
    resp.raise_for_status()

    root = ET.fromstring(resp.text)
    entry = root.find("atom:entry", _ARXIV_NS)
    if entry is None:
        return BibMetadata(arxiv_id=arxiv_id)

    title = entry.findtext("atom:title", "", _ARXIV_NS).strip()
    # Collapse multi-line titles
    title = re.sub(r"\s+", " ", title)

    authors = []
    for author_el in entry.findall("atom:author", _ARXIV_NS):
        name = author_el.findtext("atom:name", "", _ARXIV_NS).strip()
        if name:
            authors.append(name)

    abstract = entry.findtext("atom:summary", "", _ARXIV_NS).strip()
    abstract = re.sub(r"\s+", " ", abstract)

    published = entry.findtext("atom:published", "", _ARXIV_NS)
    year = None
    month = None
    if published:
        m = re.match(r"(\d{4})-(\d{2})", published)
        if m:
            year = int(m.group(1))
            month = m.group(2)

    # Check for DOI link
    doi = ""
    for link_el in entry.findall("atom:link", _ARXIV_NS):
        href = link_el.get("href", "")
        if "doi.org/" in href:
            doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", href)

    return BibMetadata(
        title=title,
        authors=authors,
        year=year,
        month=month,
        abstract=abstract,
        arxiv_id=arxiv_id,
        doi=doi,
        url=f"https://arxiv.org/abs/{arxiv_id}",
        source="arxiv",
    )


# --- Semantic Scholar API ---

_S2_BASE = "https://api.semanticscholar.org/graph/v1"
_S2_FIELDS = "paperId,title,authors,authors.name,year,venue,externalIds,publicationVenue"


def _s2_headers() -> dict[str, str]:
    """Get Semantic Scholar API headers (key optional)."""
    key = os.environ.get("S2_API_KEY", "")
    if not key:
        # Try loading from dotenv locations
        try:
            from search.config import get_s2_key

            key = get_s2_key() or ""
        except ImportError:
            pass
    if key:
        return {"x-api-key": key}
    return {}


def fetch_s2_metadata(arxiv_id: str) -> Optional[BibMetadata]:
    """Fetch metadata from Semantic Scholar, using arxiv ID as lookup.

    Returns None if paper not found.
    """
    try:
        resp = httpx.get(
            f"{_S2_BASE}/paper/ArXiv:{arxiv_id}",
            params={"fields": _S2_FIELDS},
            headers=_s2_headers(),
            timeout=TIMEOUT,
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
    except httpx.HTTPError:
        return None

    data = resp.json()

    authors = [a.get("name", "") for a in (data.get("authors") or []) if a.get("name")]
    ext = data.get("externalIds") or {}
    doi = ext.get("DOI", "")

    venue = data.get("venue", "") or ""
    pub_venue = data.get("publicationVenue") or {}
    if not venue and pub_venue:
        venue = pub_venue.get("name", "")

    return BibMetadata(
        title=data.get("title", ""),
        authors=authors,
        year=data.get("year"),
        doi=doi,
        venue=venue,
        arxiv_id=arxiv_id,
        source="s2",
    )


# --- Crossref API ---


def fetch_crossref_metadata(doi: str) -> Optional[BibMetadata]:
    """Fetch metadata from Crossref using a DOI.

    Returns None if lookup fails.
    """
    try:
        resp = httpx.get(
            f"https://api.crossref.org/works/{doi}",
            headers={"User-Agent": "agent-papers-cli/0.1 (mailto:papers-cli@example.com)"},
            timeout=TIMEOUT,
            follow_redirects=True,
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
    except httpx.HTTPError:
        return None

    msg = resp.json().get("message", {})

    authors = []
    for a in msg.get("author", []):
        given = a.get("given", "")
        family = a.get("family", "")
        if given and family:
            authors.append(f"{given} {family}")
        elif family:
            authors.append(family)

    title_list = msg.get("title", [])
    title = title_list[0] if title_list else ""

    year = None
    date_parts = (msg.get("published-print") or msg.get("published-online") or {}).get(
        "date-parts", [[]]
    )
    if date_parts and date_parts[0]:
        year = date_parts[0][0]

    venue = ""
    container = msg.get("container-title", [])
    if container:
        venue = container[0]

    entry_type = msg.get("type", "")
    # Map crossref types to bibtex
    if "proceedings" in entry_type:
        bib_type = "inproceedings"
    elif entry_type in ("journal-article",):
        bib_type = "article"
    else:
        bib_type = ""

    return BibMetadata(
        title=title,
        authors=authors,
        year=year,
        doi=doi,
        venue=venue,
        volume=msg.get("volume", ""),
        number=msg.get("issue", ""),
        pages=msg.get("page", ""),
        publisher=msg.get("publisher", ""),
        entry_type=bib_type,
        source="crossref",
    )


# --- Metadata enrichment orchestrator ---


def enrich_metadata(doc) -> BibMetadata:
    """Enrich paper metadata from multiple sources.

    Starts with parsed metadata, then layers on arxiv API, Semantic Scholar,
    and Crossref data.
    """
    meta = doc.metadata
    arxiv_id = meta.arxiv_id

    # Start with what we have from PDF parsing
    bib = BibMetadata(
        title=meta.title,
        authors=list(meta.authors) if meta.authors else [],
        arxiv_id=arxiv_id,
        url=meta.url,
    )

    # Layer 1: arxiv API (if arxiv paper)
    if arxiv_id:
        arxiv_meta = fetch_arxiv_metadata(arxiv_id)
        # Prefer arxiv structured data over PDF extraction
        if arxiv_meta.title:
            bib.title = arxiv_meta.title
        if arxiv_meta.authors:
            bib.authors = arxiv_meta.authors
        if arxiv_meta.year:
            bib.year = arxiv_meta.year
            bib.month = arxiv_meta.month
        if arxiv_meta.abstract:
            bib.abstract = arxiv_meta.abstract
        if arxiv_meta.doi:
            bib.doi = arxiv_meta.doi
        if not bib.url:
            bib.url = arxiv_meta.url

    # Layer 2: Semantic Scholar (check for published version)
    if arxiv_id:
        s2_meta = fetch_s2_metadata(arxiv_id)
        if s2_meta:
            if s2_meta.venue:
                bib.venue = s2_meta.venue
                bib.source = "s2"
            if s2_meta.doi and not bib.doi:
                bib.doi = s2_meta.doi
            if s2_meta.year and not bib.year:
                bib.year = s2_meta.year
            # S2 often has cleaner author names
            if s2_meta.authors and len(s2_meta.authors) >= len(bib.authors):
                bib.authors = s2_meta.authors

    # Layer 3: Crossref (if we have a DOI)
    if bib.doi:
        cr_meta = fetch_crossref_metadata(bib.doi)
        if cr_meta:
            if cr_meta.venue:
                bib.venue = cr_meta.venue
            if cr_meta.volume:
                bib.volume = cr_meta.volume
            if cr_meta.number:
                bib.number = cr_meta.number
            if cr_meta.pages:
                bib.pages = cr_meta.pages
            if cr_meta.publisher:
                bib.publisher = cr_meta.publisher
            if cr_meta.entry_type:
                bib.entry_type = cr_meta.entry_type
                bib.source = "crossref"
            if cr_meta.year and not bib.year:
                bib.year = cr_meta.year

    # Determine entry type if not set by crossref
    if not bib.entry_type:
        bib.entry_type = _detect_entry_type(bib)

    return bib


# --- BibTeX formatting ---


def _escape_bibtex(s: str) -> str:
    """Escape special characters for BibTeX values."""
    # BibTeX special chars: & % $ # _ { } ~ ^
    # We wrap values in braces so most are fine, but & needs escaping
    return s.replace("&", r"\&")


def format_bibtex(meta: BibMetadata) -> str:
    """Format enriched metadata as a BibTeX entry."""
    key = _make_citation_key(meta)
    entry_type = meta.entry_type or "misc"

    fields: list[tuple[str, str]] = []

    if meta.title:
        fields.append(("title", f"{{{_escape_bibtex(meta.title)}}}"))

    if meta.authors:
        author_str = " and ".join(meta.authors)
        fields.append(("author", f"{{{_escape_bibtex(author_str)}}}"))

    if meta.year:
        fields.append(("year", f"{{{meta.year}}}"))

    if meta.month:
        fields.append(("month", f"{{{meta.month}}}"))

    # Venue field depends on entry type
    if meta.venue:
        if entry_type == "inproceedings":
            fields.append(("booktitle", f"{{{_escape_bibtex(meta.venue)}}}"))
        elif entry_type == "article":
            fields.append(("journal", f"{{{_escape_bibtex(meta.venue)}}}"))
    elif meta.arxiv_id and entry_type == "article":
        fields.append(("journal", f"{{arXiv preprint arXiv:{meta.arxiv_id}}}"))

    if meta.volume:
        fields.append(("volume", f"{{{meta.volume}}}"))

    if meta.number:
        fields.append(("number", f"{{{meta.number}}}"))

    if meta.pages:
        fields.append(("pages", f"{{{meta.pages}}}"))

    if meta.publisher:
        fields.append(("publisher", f"{{{_escape_bibtex(meta.publisher)}}}"))

    if meta.doi:
        fields.append(("doi", f"{{{meta.doi}}}"))

    if meta.url:
        fields.append(("url", f"{{{meta.url}}}"))

    if meta.arxiv_id:
        fields.append(("eprint", f"{{{meta.arxiv_id}}}"))
        fields.append(("archiveprefix", "{arXiv}"))

    if meta.abstract:
        fields.append(("abstract", f"{{{_escape_bibtex(meta.abstract)}}}"))

    # Build the entry
    lines = [f"@{entry_type}{{{key},"]
    for i, (name, value) in enumerate(fields):
        comma = "," if i < len(fields) - 1 else ""
        lines.append(f"  {name} = {value}{comma}")
    lines.append("}")

    return "\n".join(lines)


# --- Top-level API ---


def generate_bibtex(paper_id: str, doc, *, force: bool = False) -> str:
    """Generate a BibTeX entry for a paper, with caching.

    Returns the BibTeX string. Cached to ~/.papers/<id>/bibtex.bib.
    Use force=True to re-fetch from APIs.
    """
    bib_path = storage.bibtex_path(paper_id)

    if not force and bib_path.exists():
        return bib_path.read_text()

    meta = enrich_metadata(doc)
    bibtex = format_bibtex(meta)

    # Cache the result
    bib_path.write_text(bibtex)

    return bibtex
