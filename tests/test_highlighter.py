"""Tests for paper.highlighter — highlight search, storage, coordinate conversion."""

import json
import pytest

from paper import storage
from paper.highlighter import (
    add_highlight,
    match_to_json,
    remove_highlight,
    to_scaled_position,
)
from paper.models import Document, Metadata


@pytest.fixture
def tmp_papers_dir(tmp_path, monkeypatch):
    """Override PAPERS_DIR to use a temp directory."""
    monkeypatch.setattr(storage, "PAPERS_DIR", tmp_path)
    return tmp_path


@pytest.fixture
def sample_doc():
    """A minimal Document for testing."""
    return Document(
        metadata=Metadata(title="Test", arxiv_id="0000.00000"),
        sections=[],
        raw_text="",
        pages=[{"page_number": 0, "width": 612.0, "height": 792.0}],
    )


class TestToScaledPosition:
    def test_single_rect(self):
        rects = [{"x0": 72.0, "y0": 100.0, "x1": 540.0, "y1": 112.0}]
        result = to_scaled_position(rects, 612.0, 792.0, 1)

        assert result["boundingRect"]["pageNumber"] == 1
        assert result["boundingRect"]["x1"] == pytest.approx(72.0 / 612.0 * 100, abs=0.01)
        assert result["boundingRect"]["y1"] == pytest.approx(100.0 / 792.0 * 100, abs=0.01)
        assert len(result["rects"]) == 1

    def test_multiple_rects_bounding(self):
        rects = [
            {"x0": 72.0, "y0": 100.0, "x1": 540.0, "y1": 112.0},
            {"x0": 72.0, "y0": 112.0, "x1": 300.0, "y1": 124.0},
        ]
        result = to_scaled_position(rects, 612.0, 792.0, 1)

        # Bounding rect should encompass both
        assert result["boundingRect"]["x1"] == pytest.approx(72.0 / 612.0 * 100, abs=0.01)
        assert result["boundingRect"]["y2"] == pytest.approx(124.0 / 792.0 * 100, abs=0.01)
        assert len(result["rects"]) == 2

    def test_empty_rects(self):
        result = to_scaled_position([], 612.0, 792.0, 1)
        assert result["boundingRect"]["width"] == 0
        assert result["rects"] == []

    def test_width_height_computed(self):
        rects = [{"x0": 100.0, "y0": 200.0, "x1": 500.0, "y1": 220.0}]
        result = to_scaled_position(rects, 612.0, 792.0, 1)

        rect = result["rects"][0]
        assert rect["width"] == pytest.approx(rect["x2"] - rect["x1"], abs=0.001)
        assert rect["height"] == pytest.approx(rect["y2"] - rect["y1"], abs=0.001)


class TestMatchToJson:
    def test_basic_conversion(self, sample_doc):
        match = {
            "page": 0,
            "rects": [{"x0": 72.0, "y0": 100.0, "x1": 540.0, "y1": 112.0}],
            "context": "Some matched text",
        }
        result = match_to_json(match, sample_doc)

        assert result["selectedText"] == "Some matched text"
        assert result["pageIndex"] == 0
        assert result["position"]["boundingRect"]["pageNumber"] == 1
        assert "rects" in result["position"]

    def test_page_out_of_range_uses_defaults(self):
        doc = Document(pages=[])
        match = {
            "page": 5,
            "rects": [{"x0": 72.0, "y0": 100.0, "x1": 540.0, "y1": 112.0}],
            "context": "text",
        }
        # Should not crash; uses default 612x792
        result = match_to_json(match, doc)
        assert result["pageIndex"] == 5


class TestHighlightCrud:
    def test_add_highlight(self, tmp_papers_dir):
        hl = add_highlight(
            paper_id="0000.00000",
            text="test text",
            page=0,
            rects=[{"x0": 72.0, "y0": 100.0, "x1": 540.0, "y1": 112.0}],
            color="green",
            note="a note",
        )
        assert hl.id == 1
        assert hl.text == "test text"
        assert hl.color == "green"
        assert hl.note == "a note"

        # Verify persisted
        highlights = storage.load_highlights("0000.00000")
        assert len(highlights) == 1
        assert highlights[0]["id"] == 1

    def test_add_multiple_increments_id(self, tmp_papers_dir):
        add_highlight("0000.00000", "first", 0, [])
        hl2 = add_highlight("0000.00000", "second", 1, [])
        assert hl2.id == 2

        highlights = storage.load_highlights("0000.00000")
        assert len(highlights) == 2

    def test_remove_highlight(self, tmp_papers_dir):
        add_highlight("0000.00000", "to remove", 0, [])
        assert remove_highlight("0000.00000", 1) is True

        highlights = storage.load_highlights("0000.00000")
        assert len(highlights) == 0

    def test_remove_nonexistent(self, tmp_papers_dir):
        assert remove_highlight("0000.00000", 999) is False

    def test_remove_preserves_others(self, tmp_papers_dir):
        add_highlight("0000.00000", "keep", 0, [])
        add_highlight("0000.00000", "remove", 1, [])
        add_highlight("0000.00000", "also keep", 2, [])

        remove_highlight("0000.00000", 2)

        highlights = storage.load_highlights("0000.00000")
        assert len(highlights) == 2
        assert highlights[0]["text"] == "keep"
        assert highlights[1]["text"] == "also keep"


class TestHighlightStorage:
    def test_load_empty(self, tmp_papers_dir):
        assert storage.load_highlights("nonexistent") == []

    def test_save_and_load(self, tmp_papers_dir):
        data = [{"id": 1, "text": "hello", "page": 0, "rects": [], "color": "yellow"}]
        storage.save_highlights("0000.00000", data)

        loaded = storage.load_highlights("0000.00000")
        assert loaded == data

    def test_corrupted_highlights_returns_empty(self, tmp_papers_dir):
        d = storage.paper_dir("0000.00000")
        (d / "highlights.json").write_text("{bad json")
        assert storage.load_highlights("0000.00000") == []
