"""Tests for paper.parser — PDF parsing, heading detection, sentence splitting."""

import pytest

from paper.parser import (
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
