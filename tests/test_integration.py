"""Integration tests using real cached PDFs.

These tests verify end-to-end parsing on actual papers.  They are skipped
when the paper's PDF is not cached in ~/.papers/ (e.g., in CI).

To fetch a paper locally:
    uv run paper outline <arxiv_id>

See tests/README.md for why each paper is included and what it covers.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from paper import storage
from paper.models import Document
from paper.renderer import build_ref_registry


def _load_if_cached(arxiv_id: str) -> Document | None:
    """Parse a paper from cache, or return None if not cached."""
    pdf = storage.pdf_path(arxiv_id)
    if not pdf.exists():
        return None
    # Always re-parse from PDF (don't trust parsed.json — it may be stale)
    from paper.parser import parse_paper
    # Delete stale parsed.json so parse_paper re-extracts
    parsed = storage.parsed_path(arxiv_id)
    if parsed.exists():
        parsed.unlink()
    return parse_paper(arxiv_id, pdf)


# ---------------------------------------------------------------------------
# 2502.13811 — Outline-based parsing
#
# This paper has a PDF outline (20 TOC entries).  It caught a critical bug
# where _segment_sections defaulted char_start to 0 for every outline
# heading, making all sections contain the entire document.
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def doc_13811() -> Document:
    doc = _load_if_cached("2502.13811")
    if doc is None:
        pytest.skip("Paper 2502.13811 not cached (run: uv run paper outline 2502.13811)")
    return doc


class TestOutlineParsing:
    """Tests for papers parsed via PDF outline (get_toc)."""

    def test_sections_have_distinct_content(self, doc_13811: Document):
        """Each section should have unique content, not the whole document."""
        contents = set()
        for s in doc_13811.sections:
            if s.content:
                # Take first 100 chars as a fingerprint
                contents.add(s.content[:100])
        # If segmentation is broken, all sections share the same content
        assert len(contents) > 1, "All sections have identical content — outline offsets likely broken"

    def test_section_count_matches_outline(self, doc_13811: Document):
        """Should have roughly as many sections as TOC entries."""
        assert len(doc_13811.sections) >= 15  # paper has 20 TOC entries

    def test_first_section_is_introduction(self, doc_13811: Document):
        assert doc_13811.sections[0].heading == "Introduction"

    def test_most_sections_dont_start_with_title(self, doc_13811: Document):
        """Most sections should not start with the paper title.

        A few sections may start with the title due to running headers when
        the TOC heading text doesn't match any line on the page (e.g., TOC
        says "Proof of thm:kron-factored-proj-is-mora" but the PDF line is
        "A.2. Proof of Prop. 2").  The fallback picks the first line on the
        page, which is often the running header.

        We check that the *majority* of sections are correct — if more than
        20% start with the title, the offset resolution is likely broken.
        """
        title = doc_13811.metadata.title
        sections_with_sentences = [s for s in doc_13811.sections if s.sentences]
        bad = [s for s in sections_with_sentences if s.sentences[0].text.startswith(title)]
        ratio = len(bad) / max(len(sections_with_sentences), 1)
        assert ratio < 0.2, (
            f"{len(bad)}/{len(sections_with_sentences)} sections start with paper title: "
            f"{[s.heading for s in bad]}"
        )

    def test_has_links(self, doc_13811: Document):
        """Paper should have extracted links."""
        assert len(doc_13811.links) > 0
        kinds = {lk.kind for lk in doc_13811.links}
        assert "external" in kinds or "citation" in kinds

    def test_ref_registry_has_all_types(self, doc_13811: Document):
        registry = build_ref_registry(doc_13811)
        kinds = {e.kind for e in registry}
        assert "section" in kinds
        # This paper has external URLs
        assert "external" in kinds


# ---------------------------------------------------------------------------
# 2302.13971 — Font-based heading detection
#
# No PDF outline.  Headings are detected by comparing font sizes to body
# text.  Used as the primary test paper during initial development.
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def doc_13971() -> Document:
    doc = _load_if_cached("2302.13971")
    if doc is None:
        pytest.skip("Paper 2302.13971 not cached (run: uv run paper outline 2302.13971)")
    return doc


class TestFontBasedParsing:
    """Tests for papers parsed via font-size heuristics."""

    def test_sections_detected(self, doc_13971: Document):
        assert len(doc_13971.sections) >= 5

    def test_sections_have_distinct_content(self, doc_13971: Document):
        contents = set()
        for s in doc_13971.sections:
            if s.content:
                contents.add(s.content[:100])
        assert len(contents) > 1

    def test_sentences_parsed(self, doc_13971: Document):
        total = sum(len(s.sentences) for s in doc_13971.sections)
        assert total > 50, "Expected many sentences in a 27-page paper"

    def test_metadata_extracted(self, doc_13971: Document):
        assert doc_13971.metadata.title
        assert doc_13971.metadata.arxiv_id == "2302.13971"

    def test_ref_registry_sections(self, doc_13971: Document):
        registry = build_ref_registry(doc_13971)
        section_refs = [e for e in registry if e.kind == "section"]
        assert len(section_refs) == len(doc_13971.sections)

    def test_no_numeric_table_data_as_headings(self, doc_13971: Document):
        """Table values like '88.0' should not become section headings."""
        for s in doc_13971.sections:
            import re
            if re.match(r"^[\d\s.,\-+%]+$", s.heading.strip()):
                assert len(s.heading.strip()) <= 3, (
                    f"Numeric table data detected as heading: {s.heading!r}"
                )


# ---------------------------------------------------------------------------
# 2505.21451 — Font-based parsing with tricky formatting
#
# No PDF outline.  Tests robustness of heading detection against:
# - Author names at heading font size (affiliation symbols ♣ ♢ ♠)
# - Bold body text containing heading keywords ("experiments", "models")
# - Title at large font with arXiv header at even larger font
# - Multi-line wrapped headings requiring fragment merging
# - Small-caps section titles (section 4: PERSONACONFLICTS CORPUS)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def doc_21451() -> Document:
    doc = _load_if_cached("2505.21451")
    if doc is None:
        pytest.skip("Paper 2505.21451 not cached (run: uv run paper outline 2505.21451)")
    return doc


class TestTrickyFontBasedParsing:
    """Tests for papers with tricky font-based heading detection."""

    def test_no_author_names_as_sections(self, doc_21451: Document):
        """Author names should not appear as section headings."""
        headings = {s.heading for s in doc_21451.sections}
        for name in ["Jocelyn Shen", "Akhila Yerukola", "Maarten Sap"]:
            assert not any(name in h for h in headings), (
                f"Author name {name!r} detected as heading"
            )

    def test_title_not_as_section(self, doc_21451: Document):
        """Paper title should not appear in the section list."""
        headings = [s.heading for s in doc_21451.sections]
        assert headings[0] != "Words Like Knives :", (
            "Paper title detected as first section heading"
        )

    def test_no_body_text_as_sections(self, doc_21451: Document):
        """Sentence fragments should not be section headings."""
        for s in doc_21451.sections:
            assert not s.heading.endswith("-"), (
                f"Hyphenated word break as heading: {s.heading!r}"
            )
            assert not s.heading[0].islower(), (
                f"Lowercase-starting text as heading: {s.heading!r}"
            )

    def test_merged_headings(self, doc_21451: Document):
        """Multi-line headings should be merged."""
        headings = {s.heading for s in doc_21451.sections}
        assert "3 Non-Violent Communication Framework" in headings
        assert "7 LLMs for Detecting Conversational Breakdowns" in headings

    def test_sections_have_content(self, doc_21451: Document):
        sections_with_content = [s for s in doc_21451.sections if s.content]
        assert len(sections_with_content) >= 15

    def test_has_citations(self, doc_21451: Document):
        citations = [lk for lk in doc_21451.links if lk.kind == "citation"]
        assert len(citations) > 0
