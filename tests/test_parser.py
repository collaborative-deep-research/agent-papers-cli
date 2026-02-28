"""Tests for paper.parser — PDF parsing, heading detection, sentence splitting."""

from unittest.mock import MagicMock

import pytest

from paper.parser import (
    _Line,
    _extract_metadata,
    _is_false_positive_heading,
    _looks_like_section_heading,
    _merge_heading_fragments,
)


class TestIsFalsePositiveHeading:
    def test_arxiv_header(self):
        assert _is_false_positive_heading("arXiv:2302.13971v1 [cs.CL] 27 Feb 2023", 0, False)

    def test_figure_caption(self):
        assert _is_false_positive_heading("Figure 1: Training loss over epochs", 1, False)

    def test_table_caption(self):
        assert _is_false_positive_heading("Table 2: Results on benchmark", 1, False)

    def test_long_text(self):
        assert _is_false_positive_heading("A" * 121, 1, False)

    def test_period_ending(self):
        assert _is_false_positive_heading("English CommonCrawl [67%].", 1, False)

    def test_numeric_table_data(self):
        assert _is_false_positive_heading("88.0 81.1", 1, False)

    def test_author_with_asterisk(self):
        assert _is_false_positive_heading("Hugo Touvron ∗ , Thibaut Lavril ∗", 0, False)

    def test_question_mark(self):
        assert _is_false_positive_heading("How do I send an HTTP request?", 5, False)

    def test_valid_heading_passes(self):
        assert not _is_false_positive_heading("Introduction", 0, False)

    def test_numbered_section_passes(self):
        assert not _is_false_positive_heading("2 Approach", 1, False)


class TestLooksLikeSectionHeading:
    def test_numbered_section(self):
        assert _looks_like_section_heading("1 Introduction")

    def test_dotted_subsection(self):
        assert _looks_like_section_heading("2.1 Pre-training Data")

    def test_keyword_abstract(self):
        assert _looks_like_section_heading("Abstract")

    def test_keyword_conclusion(self):
        assert _looks_like_section_heading("Conclusion")

    def test_keyword_related_work(self):
        assert _looks_like_section_heading("Related Work")

    def test_bare_number(self):
        assert _looks_like_section_heading("1")

    def test_appendix_letter(self):
        assert _looks_like_section_heading("A")

    def test_short_capitalized(self):
        assert _looks_like_section_heading("Architecture")

    def test_rejects_long_sentence(self):
        # Note: period-ending text is filtered by _is_false_positive_heading,
        # not _looks_like_section_heading. Long lowercase text should be rejected.
        assert not _looks_like_section_heading(
            "we use a standard cross-entropy loss function to optimize the weights across all layers"
        )

    def test_rejects_long_text(self):
        assert not _looks_like_section_heading(
            "This is a very long piece of text that is definitely not a section heading at all"
        )


class TestMergeHeadingFragments:
    def test_merges_number_and_title(self):
        headings = [
            {"heading": "1", "level": 1, "page": 0, "char_start": 0, "char_end": 1, "font_size": 12.0},
            {"heading": "Introduction", "level": 1, "page": 0, "char_start": 2, "char_end": 14, "font_size": 12.0},
        ]
        merged = _merge_heading_fragments(headings)
        assert len(merged) == 1
        assert merged[0]["heading"] == "1 Introduction"

    def test_no_merge_different_pages(self):
        headings = [
            {"heading": "1", "level": 1, "page": 0, "char_start": 0, "char_end": 1, "font_size": 12.0},
            {"heading": "Introduction", "level": 1, "page": 1, "char_start": 100, "char_end": 112, "font_size": 12.0},
        ]
        merged = _merge_heading_fragments(headings)
        assert len(merged) == 2

    def test_no_merge_different_font_sizes(self):
        headings = [
            {"heading": "1", "level": 1, "page": 0, "char_start": 0, "char_end": 1, "font_size": 14.0},
            {"heading": "Introduction", "level": 2, "page": 0, "char_start": 2, "char_end": 14, "font_size": 10.0},
        ]
        merged = _merge_heading_fragments(headings)
        assert len(merged) == 2

    def test_no_merge_non_number(self):
        headings = [
            {"heading": "Abstract", "level": 1, "page": 0, "char_start": 0, "char_end": 8, "font_size": 12.0},
            {"heading": "Introduction", "level": 1, "page": 0, "char_start": 10, "char_end": 22, "font_size": 12.0},
        ]
        merged = _merge_heading_fragments(headings)
        assert len(merged) == 2

    def test_empty_list(self):
        assert _merge_heading_fragments([]) == []

    def test_single_heading(self):
        headings = [{"heading": "Abstract", "level": 1, "page": 0, "char_start": 0, "char_end": 8, "font_size": 12.0}]
        assert _merge_heading_fragments(headings) == headings


def _make_mock_fitz():
    """Create a minimal mock fitz.Document for _extract_metadata tests."""
    doc = MagicMock()
    doc.metadata = {"title": "", "author": ""}
    return doc


class TestExtractMetadata:
    """Tests for _extract_metadata — title extraction from PDF lines.

    The title is determined by finding all lines on page 0 with the largest
    font size (excluding arxiv headers).  Multi-line titles that span
    multiple _Line objects at the same font size are joined with a space.

    See: https://github.com/collaborative-deep-research/agent-papers-cli/issues/14
    """

    def test_single_line_title(self):
        """Standard single-line title is extracted correctly."""
        lines = [
            _Line("Is ChatGPT A Good Translator?", font_size=17.0,
                   font_name="Times", is_bold=True, page=0,
                   bbox=(72, 50, 500, 68)),
            _Line("Some Author", font_size=10.0,
                   font_name="Times", is_bold=False, page=0,
                   bbox=(72, 80, 300, 92)),
        ]
        meta = _extract_metadata(
            _make_mock_fitz(), lines, body_size=10.0, arxiv_id="2301.08745"
        )
        assert meta.title == "Is ChatGPT A Good Translator?"

    def test_multiline_title(self):
        """Multi-line titles should be joined into a single string.

        Example: the Tülu 3 paper has a title that spans two lines:
          Line 1: "Tülu 3: Pushing Frontiers in Open Language Model"
          Line 2: "Post-Training"
        Both lines share the same (largest) font size on page 0.
        """
        lines = [
            _Line("arXiv:2411.15124v2 [cs.CL] 25 Nov 2024", font_size=8.0,
                   font_name="CMR", is_bold=False, page=0,
                   bbox=(72, 10, 300, 18)),
            _Line("Tülu 3: Pushing Frontiers in Open Language Model",
                   font_size=17.0, font_name="Times", is_bold=True, page=0,
                   bbox=(72, 50, 540, 68)),
            _Line("Post-Training", font_size=17.0,
                   font_name="Times", is_bold=True, page=0,
                   bbox=(72, 70, 200, 88)),
            _Line("Author Name et al.", font_size=10.0,
                   font_name="Times", is_bold=False, page=0,
                   bbox=(72, 100, 300, 112)),
        ]
        meta = _extract_metadata(
            _make_mock_fitz(), lines, body_size=10.0, arxiv_id="2411.15124"
        )
        assert meta.title == (
            "Tülu 3: Pushing Frontiers in Open Language Model Post-Training"
        )

    def test_multiline_title_sorted_by_position(self):
        """Lines should be joined in top-to-bottom order, not insertion order."""
        lines = [
            _Line("Second Line of Title", font_size=17.0,
                   font_name="Times", is_bold=True, page=0,
                   bbox=(72, 70, 400, 88)),
            _Line("First Line of Title:", font_size=17.0,
                   font_name="Times", is_bold=True, page=0,
                   bbox=(72, 50, 400, 68)),
        ]
        meta = _extract_metadata(
            _make_mock_fitz(), lines, body_size=10.0, arxiv_id="test"
        )
        assert meta.title == "First Line of Title: Second Line of Title"

    def test_arxiv_header_excluded_from_title(self):
        """arXiv header lines should not be included in the title."""
        lines = [
            _Line("arXiv:2301.08745v1 [cs.CL] 20 Jan 2023", font_size=20.0,
                   font_name="CMR", is_bold=False, page=0,
                   bbox=(72, 10, 400, 22)),
            _Line("Actual Paper Title", font_size=17.0,
                   font_name="Times", is_bold=True, page=0,
                   bbox=(72, 50, 400, 68)),
        ]
        meta = _extract_metadata(
            _make_mock_fitz(), lines, body_size=10.0, arxiv_id="2301.08745"
        )
        assert meta.title == "Actual Paper Title"

    def test_subtitle_slightly_smaller_font_included(self):
        """Lines within 0.5pt of the title font size should be included.

        Some PDFs use a very slightly different font size for the
        subtitle line (e.g. 16.8 vs 17.0) — the 0.5pt tolerance
        ensures these are captured.
        """
        lines = [
            _Line("Main Title", font_size=17.0,
                   font_name="Times", is_bold=True, page=0,
                   bbox=(72, 50, 400, 68)),
            _Line("Subtitle Continues Here", font_size=16.8,
                   font_name="Times", is_bold=True, page=0,
                   bbox=(72, 70, 400, 88)),
        ]
        meta = _extract_metadata(
            _make_mock_fitz(), lines, body_size=10.0, arxiv_id="test"
        )
        assert meta.title == "Main Title Subtitle Continues Here"

    def test_fallback_to_pdf_metadata(self):
        """When no lines exist, fall back to fitz document metadata."""
        doc = _make_mock_fitz()
        doc.metadata = {"title": "Fallback Title", "author": "Some Author"}
        meta = _extract_metadata(doc, [], body_size=10.0, arxiv_id="test")
        assert meta.title == "Fallback Title"
