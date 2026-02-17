"""Tests for link extraction, citation detection, ref registry, and goto."""

import pytest

from paper.models import Document, Link, Metadata, Section, Sentence, Span
from paper.parser import _detect_citations
from paper.renderer import (
    RefEntry, build_ref_registry, render_goto,
    annotate_text, _find_cite_end_in_text,
)


class TestDetectCitations:
    def test_single_citation(self):
        text = "As shown in [1], the method works."
        links = _detect_citations(text)
        assert len(links) == 1
        assert links[0].kind == "citation"
        assert links[0].text == "[1]"

    def test_multi_citation(self):
        text = "Prior work [2, 3] has shown this."
        links = _detect_citations(text)
        assert len(links) == 1
        assert links[0].text == "[2, 3]"

    def test_range_citation(self):
        text = "Many studies [1-5] agree."
        links = _detect_citations(text)
        assert len(links) == 1
        assert links[0].text == "[1-5]"

    def test_no_named_citations(self):
        """Named citations like [Smith et al., 2023] should NOT match."""
        text = "As noted by [Smith et al., 2023], the results are clear."
        links = _detect_citations(text)
        assert len(links) == 0

    def test_deduplication(self):
        text = "See [1] and also [1] again."
        links = _detect_citations(text)
        assert len(links) == 1

    def test_multiple_different_citations(self):
        text = "Results from [1] and [2] confirm [3]."
        links = _detect_citations(text)
        assert len(links) == 3
        markers = {lk.text for lk in links}
        assert markers == {"[1]", "[2]", "[3]"}

    def test_span_offsets(self):
        text = "See [1] here."
        links = _detect_citations(text)
        assert links[0].span.start == 4
        assert links[0].span.end == 7
        assert text[4:7] == "[1]"


class TestBuildRefRegistry:
    def _make_doc(self, num_sections=2, num_ext_links=1, num_citations=1):
        sections = [
            Section(
                heading=f"Section {i}",
                level=1,
                content=f"Content of section {i}.",
                spans=[Span(start=i * 100, end=i * 100 + 50)],
            )
            for i in range(1, num_sections + 1)
        ]
        links = []
        for i in range(num_ext_links):
            links.append(Link(
                kind="external",
                text=f"Link {i}",
                url=f"https://example.com/{i}",
                target_page=-1,
                page=0,
                span=Span(start=0, end=10),
            ))
        for i in range(1, num_citations + 1):
            links.append(Link(
                kind="citation",
                text=f"[{i}]",
                url="",
                target_page=-1,
                page=0,
                span=Span(start=0, end=3),
            ))
        return Document(
            metadata=Metadata(title="Test", arxiv_id="2302.13971"),
            sections=sections,
            raw_text="x" * 300,
            links=links,
        )

    def test_section_refs(self):
        doc = self._make_doc(num_sections=3, num_ext_links=0, num_citations=0)
        registry = build_ref_registry(doc)
        section_refs = [e for e in registry if e.kind == "section"]
        assert len(section_refs) == 3
        assert section_refs[0].ref_id == "s1"
        assert section_refs[2].ref_id == "s3"

    def test_external_refs(self):
        doc = self._make_doc(num_sections=1, num_ext_links=3, num_citations=0)
        registry = build_ref_registry(doc)
        ext_refs = [e for e in registry if e.kind == "external"]
        assert len(ext_refs) == 3
        assert ext_refs[0].ref_id == "e1"
        assert ext_refs[0].target == "https://example.com/0"

    def test_citation_refs(self):
        doc = self._make_doc(num_sections=1, num_ext_links=0, num_citations=4)
        registry = build_ref_registry(doc)
        cite_refs = [e for e in registry if e.kind == "citation"]
        assert len(cite_refs) == 4
        assert cite_refs[0].ref_id == "c1"
        assert cite_refs[3].ref_id == "c4"

    def test_ordering(self):
        """Refs should be ordered: sections, then externals, then citations."""
        doc = self._make_doc(num_sections=2, num_ext_links=2, num_citations=2)
        registry = build_ref_registry(doc)
        kinds = [e.kind for e in registry]
        # All sections first, then externals, then citations
        assert kinds == ["section", "section", "external", "external", "citation", "citation"]

    def test_empty_doc(self):
        doc = Document()
        registry = build_ref_registry(doc)
        assert registry == []


class TestRenderGoto:
    def _make_doc(self):
        return Document(
            metadata=Metadata(title="Test Paper", arxiv_id="2302.13971"),
            sections=[
                Section(
                    heading="Introduction",
                    level=1,
                    content="This is the intro. It references [1].",
                    sentences=[
                        Sentence(text="This is the intro.", span=Span(start=0, end=18), page=0),
                        Sentence(text="It references [1].", span=Span(start=19, end=37), page=0),
                    ],
                    spans=[Span(start=0, end=100)],
                    page_start=0,
                    page_end=0,
                ),
                Section(
                    heading="References",
                    level=1,
                    content="[1] Smith et al. A great paper. 2023.",
                    spans=[Span(start=100, end=200)],
                    page_start=1,
                    page_end=1,
                ),
            ],
            raw_text="Introduction\nThis is the intro. It references [1].\nReferences\n[1] Smith et al. A great paper. 2023.",
            links=[
                Link(kind="external", text="example", url="https://example.com",
                     target_page=-1, page=0, span=Span(start=10, end=20)),
                Link(kind="citation", text="[1]", url="", target_page=-1, page=0,
                     span=Span(start=35, end=38)),
            ],
        )

    def test_goto_section(self):
        doc = self._make_doc()
        result = render_goto(doc, "s1")
        assert result is True

    def test_goto_external(self):
        doc = self._make_doc()
        result = render_goto(doc, "e1")
        assert result is True

    def test_goto_citation(self):
        doc = self._make_doc()
        result = render_goto(doc, "c1")
        assert result is True

    def test_goto_section_truncates(self, capsys):
        """Long sections should be truncated to 10 sentences with a hint."""
        doc = Document(
            metadata=Metadata(title="Long Paper", arxiv_id="2302.13971"),
            sections=[
                Section(
                    heading="Methods",
                    level=1,
                    content=" ".join(f"Sentence {i}." for i in range(30)),
                    sentences=[
                        Sentence(text=f"Sentence {i}.", span=Span(start=i*12, end=i*12+11), page=0)
                        for i in range(30)
                    ],
                    spans=[Span(start=0, end=360)],
                ),
            ],
            raw_text="x" * 360,
            links=[],
        )
        result = render_goto(doc, "s1")
        assert result is True
        captured = capsys.readouterr().out
        assert "Showing 10 of 30 sentences" in captured
        assert 'paper read 2302.13971 "Methods"' in captured

    def test_goto_unknown(self):
        doc = self._make_doc()
        result = render_goto(doc, "z99")
        assert result is False


class TestInlineCitationPlacement:
    """Test that [ref=cN] tags are placed right after the citation, not at end."""

    def test_find_cite_end_author_year(self):
        """surname + year found → position after year and closing paren."""
        link = Link(kind="citation", text="(Kingma & Ba, 2015)", url="",
                    target_page=-1, page=0, span=Span(start=0, end=0))
        text = "Adam ( Kingma & Ba , 2015 ), which maintains"
        pos = _find_cite_end_in_text(text, link)
        assert pos is not None
        # Should be right after "2015 )" — the closing paren
        assert text[:pos].rstrip().endswith(")")

    def test_find_cite_end_year_only_fallback(self):
        """Surname not in text, year appears once → use year position."""
        link = Link(kind="citation", text="(Houlsby et al., 2019;", url="",
                    target_page=-1, page=0, span=Span(start=0, end=0))
        text = ", 2019 ; Li & Liang , 2021 ; Hu et al."
        pos = _find_cite_end_in_text(text, link)
        assert pos is not None
        # Should be right after "2019" (before the semicolon)
        assert "2019" in text[:pos]
        assert pos < len(text)  # not at end

    def test_find_cite_end_word_boundary(self):
        """'Hu' should NOT match 'Huh'."""
        link = Link(kind="citation", text="(Hu et al., 2022)", url="",
                    target_page=-1, page=0, span=Span(start=0, end=0))
        text = "the-Explorer (LTE; Huh et al. , 2024 ), and Flora"
        pos = _find_cite_end_in_text(text, link)
        # "Hu" should not match "Huh" — no valid position
        assert pos is None

    def test_find_cite_end_no_false_year_match(self):
        """When surname IS in text but year is for a different citation, skip."""
        link = Link(kind="citation", text="(Hao et al., 2024)", url="",
                    target_page=-1, page=0, span=Span(start=0, end=0))
        text = "Huh et al. , 2024 ), and Flora ( Hao et al."
        pos = _find_cite_end_in_text(text, link)
        # "Hao" is found but "2024" in the window is Huh's year, not Hao's
        # Hao's year is beyond the text → should not place
        assert pos is None

    def test_annotate_inline_placement(self):
        """Ref tag should appear right after the citation, not at sentence end."""
        doc = Document(
            metadata=Metadata(title="Test", arxiv_id="test"),
            sections=[Section(heading="Intro", level=1, content="x",
                             spans=[Span(start=0, end=100)])],
            raw_text="Adam ( Kingma & Ba , 2015 ), which maintains estimates.",
            links=[Link(kind="citation", text="(Kingma & Ba, 2015)", url="",
                       target_page=-1, page=0, span=Span(start=0, end=50))],
        )
        registry = build_ref_registry(doc)
        text = "Adam ( Kingma & Ba , 2015 ), which maintains estimates."
        result = annotate_text(text, doc, registry, span_start=0, span_end=55)
        # [ref=c1] should appear BEFORE "which", not at end
        ref_pos = result.find("[ref=c1]")
        which_pos = result.find("which")
        assert ref_pos < which_pos

    def test_annotate_dedup_across_sentences(self):
        """Same citation shouldn't be annotated twice across sentence fragments."""
        doc = Document(
            metadata=Metadata(title="Test", arxiv_id="test"),
            sections=[Section(heading="Intro", level=1, content="x",
                             spans=[Span(start=0, end=100)])],
            raw_text="( Houlsby et al.\n, 2019 )",
            links=[Link(kind="citation", text="(Houlsby et al., 2019;", url="",
                       target_page=-1, page=0, span=Span(start=0, end=24))],
        )
        registry = build_ref_registry(doc)
        seen = set()
        # Sentence 1: has surname but not year
        annotate_text("( Houlsby et al.", doc, registry,
                      span_start=0, span_end=16, seen_refs=seen)
        # Sentence 2: has year — should place ref here
        result = annotate_text(", 2019 )", doc, registry,
                               span_start=17, span_end=24, seen_refs=seen)
        assert "[ref=c1]" in result

    def test_numeric_citation_inline(self):
        """Numeric citations [1] should be annotated right after the bracket."""
        doc = Document(
            metadata=Metadata(title="Test", arxiv_id="test"),
            sections=[Section(heading="Intro", level=1, content="x",
                             spans=[Span(start=0, end=50)])],
            raw_text="As shown in [1], the method works well for all cases.",
            links=[Link(kind="citation", text="[1]", url="",
                       target_page=-1, page=0, span=Span(start=12, end=15))],
        )
        registry = build_ref_registry(doc)
        text = "As shown in [1], the method works well for all cases."
        result = annotate_text(text, doc, registry, span_start=0, span_end=50)
        ref_pos = result.find("[ref=c1]")
        method_pos = result.find("the method")
        assert ref_pos < method_pos


class TestGotoCLI:
    def test_goto_help(self):
        from click.testing import CliRunner
        from paper.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["goto", "--help"])
        assert result.exit_code == 0
        assert "REF_ID" in result.output
        assert "REFERENCE" in result.output
