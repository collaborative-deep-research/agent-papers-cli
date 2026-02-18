"""PubMed search via NCBI E-utilities."""

from __future__ import annotations

from xml.etree import ElementTree

import httpx

from search.models import SearchResult

PUBMED_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
TIMEOUT = 15


def _extract_text(tag: ElementTree.Element) -> str:
    """Extract all text from an XML element, including nested rich text."""
    return " ".join(t.strip() for t in tag.itertext())


def search_pubmed(
    query: str,
    *,
    limit: int = 10,
    offset: int = 0,
) -> list[SearchResult]:
    """Search PubMed and return paper results."""
    # Step 1: search for IDs
    resp = httpx.get(
        f"{PUBMED_BASE}/esearch.fcgi",
        params={
            "db": "pubmed",
            "term": query,
            "retmax": limit,
            "retstart": offset,
            "usehistory": "n",
            "sort": "relevance",
        },
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    root = ElementTree.fromstring(resp.content)
    ids = [el.text for el in root.findall("./IdList/Id") if el.text]

    if not ids:
        return []

    # Step 2: fetch details
    resp = httpx.get(
        f"{PUBMED_BASE}/efetch.fcgi",
        params={
            "db": "pubmed",
            "id": ",".join(ids),
            "retmode": "xml",
        },
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    papers = ElementTree.fromstring(resp.content)

    results = []
    for article_el in papers.findall("./PubmedArticle"):
        article = article_el.find(".//Article")
        if article is None:
            continue

        pmid_el = article_el.find(".//PMID")
        pmid = pmid_el.text if pmid_el is not None else ""

        title_el = article.find(".//ArticleTitle")
        title = _extract_text(title_el) if title_el is not None else ""

        # Build abstract
        abstract_parts = []
        if article.find(".//Abstract") is not None:
            for ab_text in article.findall(".//Abstract/AbstractText"):
                label = ab_text.attrib.get("Label")
                if label:
                    abstract_parts.append(f"{label}:")
                abstract_parts.append(_extract_text(ab_text))
        abstract = " ".join(abstract_parts)

        # Authors
        authors = []
        for author in article.findall(".//Author"):
            last = author.find("./LastName")
            first = author.find("./ForeName")
            if last is not None and first is not None:
                authors.append(f"{last.text} {first.text}")
        author_str = ", ".join(authors[:3])
        if len(authors) > 3:
            author_str += ", et al."

        # Year
        year_el = article.find(".//Journal/JournalIssue/PubDate/Year")
        year = int(year_el.text) if year_el is not None and year_el.text else None

        # Venue
        venue_el = article.find(".//Journal/Title")
        venue = venue_el.text if venue_el is not None else ""

        results.append(
            SearchResult(
                title=title,
                url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                snippet=abstract[:300] if abstract else "",
                year=year,
                authors=author_str,
                venue=venue,
                paper_id=pmid,
            )
        )
    return results
