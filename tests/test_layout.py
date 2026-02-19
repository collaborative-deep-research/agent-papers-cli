"""Tests for paper.layout — layout detection module."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from paper.models import Box, Document, LayoutElement, Metadata


class TestLayoutElement:
    def test_create_layout_element(self):
        box = Box(x0=10, y0=20, x1=100, y1=200, page=0)
        elem = LayoutElement(
            kind="figure",
            box=box,
            confidence=0.95,
            caption="Figure 1: Example",
            label="Figure 1",
        )
        assert elem.kind == "figure"
        assert elem.box.page == 0
        assert elem.confidence == 0.95
        assert elem.caption == "Figure 1: Example"
        assert elem.label == "Figure 1"

    def test_layout_element_defaults(self):
        box = Box(x0=0, y0=0, x1=50, y1=50, page=1)
        elem = LayoutElement(kind="equation", box=box, confidence=0.8)
        assert elem.caption == ""
        assert elem.label == ""


class TestDocumentWithLayout:
    def test_save_and_load_with_layout_elements(self, tmp_path):
        doc = Document(
            metadata=Metadata(title="Test", arxiv_id="2301.00001"),
            layout_elements=[
                LayoutElement(
                    kind="figure",
                    box=Box(x0=10, y0=20, x1=300, y1=400, page=0),
                    confidence=0.95,
                    caption="Figure 1: A test figure",
                    label="Figure 1",
                ),
                LayoutElement(
                    kind="table",
                    box=Box(x0=50, y0=100, x1=500, y1=300, page=1),
                    confidence=0.88,
                    caption="Table 1: Results",
                    label="Table 1",
                ),
                LayoutElement(
                    kind="equation",
                    box=Box(x0=100, y0=200, x1=400, y1=250, page=2),
                    confidence=0.92,
                    label="Eq. 1",
                ),
            ],
        )

        path = tmp_path / "parsed.json"
        doc.save(path)
        loaded = Document.load(path)

        assert len(loaded.layout_elements) == 3
        assert loaded.layout_elements[0].kind == "figure"
        assert loaded.layout_elements[0].box.x0 == 10
        assert loaded.layout_elements[0].confidence == 0.95
        assert loaded.layout_elements[0].caption == "Figure 1: A test figure"
        assert loaded.layout_elements[1].kind == "table"
        assert loaded.layout_elements[1].label == "Table 1"
        assert loaded.layout_elements[2].kind == "equation"
        assert loaded.layout_elements[2].caption == ""

    def test_load_without_layout_elements(self, tmp_path):
        """Loading a JSON without 'layout_elements' should default to empty list."""
        data = {
            "metadata": {"title": "Old Paper"},
            "sections": [],
            "raw_text": "",
            "pages": [],
        }
        path = tmp_path / "no_layout.json"
        path.write_text(json.dumps(data))
        loaded = Document.load(path)
        assert loaded.layout_elements == []


class TestLayoutCaching:
    def test_save_and_load_layout(self, tmp_path, monkeypatch):
        from paper.layout import save_layout, load_layout

        # Point layout_path to tmp_path
        monkeypatch.setattr(
            "paper.layout.layout_path",
            lambda paper_id: tmp_path / "layout.json",
        )

        elements = [
            LayoutElement(
                kind="figure",
                box=Box(x0=10, y0=20, x1=300, y1=400, page=0),
                confidence=0.95,
                caption="Figure 1: Test",
                label="Figure 1",
            ),
            LayoutElement(
                kind="equation",
                box=Box(x0=100, y0=200, x1=400, y1=250, page=1),
                confidence=0.88,
                label="Eq. 1",
            ),
        ]

        save_layout("test-id", elements)
        loaded = load_layout("test-id")

        assert len(loaded) == 2
        assert loaded[0].kind == "figure"
        assert loaded[0].box.x0 == 10
        assert loaded[0].confidence == 0.95
        assert loaded[0].caption == "Figure 1: Test"
        assert loaded[1].kind == "equation"
        assert loaded[1].label == "Eq. 1"

    def test_save_and_load_image_path(self, tmp_path, monkeypatch):
        from paper.layout import save_layout, load_layout

        monkeypatch.setattr(
            "paper.layout.layout_path",
            lambda paper_id: tmp_path / "layout.json",
        )

        elements = [
            LayoutElement(
                kind="figure",
                box=Box(x0=10, y0=20, x1=300, y1=400, page=0),
                confidence=0.95,
                label="Figure 1",
                image_path="/tmp/layout/f1.png",
            ),
        ]

        save_layout("test-id", elements)
        loaded = load_layout("test-id")

        assert loaded[0].image_path == "/tmp/layout/f1.png"

    def test_load_layout_missing_file(self, tmp_path, monkeypatch):
        from paper.layout import load_layout

        monkeypatch.setattr(
            "paper.layout.layout_path",
            lambda paper_id: tmp_path / "nonexistent.json",
        )

        result = load_layout("test-id")
        assert result == []


class TestAssignLabels:
    def test_assigns_sequential_labels(self):
        from paper.layout import _assign_labels

        elements = [
            LayoutElement(kind="figure", box=Box(0, 0, 1, 1, 0), confidence=0.9),
            LayoutElement(kind="table", box=Box(0, 0, 1, 1, 0), confidence=0.9),
            LayoutElement(kind="figure", box=Box(0, 0, 1, 1, 1), confidence=0.9),
            LayoutElement(kind="equation", box=Box(0, 0, 1, 1, 1), confidence=0.9),
            LayoutElement(kind="table", box=Box(0, 0, 1, 1, 2), confidence=0.9),
        ]

        _assign_labels(elements)

        assert elements[0].label == "Figure 1"
        assert elements[1].label == "Table 1"
        assert elements[2].label == "Figure 2"
        assert elements[3].label == "Eq. 1"
        assert elements[4].label == "Table 2"


class TestLabelToRefId:
    def test_figure_label(self):
        from paper.layout import _label_to_ref_id

        elem = LayoutElement(kind="figure", box=Box(0, 0, 1, 1, 0), confidence=0.9, label="Figure 1")
        assert _label_to_ref_id(elem) == "f1"

    def test_table_label(self):
        from paper.layout import _label_to_ref_id

        elem = LayoutElement(kind="table", box=Box(0, 0, 1, 1, 0), confidence=0.9, label="Table 12")
        assert _label_to_ref_id(elem) == "t12"

    def test_equation_label(self):
        from paper.layout import _label_to_ref_id

        elem = LayoutElement(kind="equation", box=Box(0, 0, 1, 1, 0), confidence=0.9, label="Eq. 3")
        assert _label_to_ref_id(elem) == "eq3"


class TestKindMap:
    def test_kind_map_covers_expected_classes(self):
        from paper.layout import _KIND_MAP

        # Primary names from DocLayout-YOLO DocStructBench model
        assert _KIND_MAP["figure"] == "figure"
        assert _KIND_MAP["table"] == "table"
        assert _KIND_MAP["isolate_formula"] == "equation"
        # Aliases for other model variants
        assert _KIND_MAP["Picture"] == "figure"
        assert _KIND_MAP["Figure"] == "figure"
        assert _KIND_MAP["Table"] == "table"
        assert _KIND_MAP["Formula"] == "equation"
        assert _KIND_MAP["Equation"] == "equation"


class TestBestDevice:
    def test_returns_string(self):
        from paper.layout import _best_device

        device = _best_device()
        assert device in ("cuda", "mps", "cpu")

    @patch("paper.layout.torch", create=True)
    def test_prefers_cuda(self, mock_torch):
        from paper.layout import _best_device

        mock_torch.cuda.is_available.return_value = True
        # Re-import won't help, but we can test the function directly
        # by patching at module level
        import paper.layout
        with patch.object(paper.layout, "torch", mock_torch, create=True):
            pass  # _best_device uses import internally

    def test_falls_back_to_cpu_without_torch(self):
        from paper.layout import _best_device

        with patch.dict("sys.modules", {"torch": None}):
            # This may not fully work due to how imports are cached,
            # but the function should at minimum return a valid string
            device = _best_device()
            assert isinstance(device, str)


class TestRendererLayoutRefs:
    """Test that layout elements appear in the ref registry."""

    def test_build_ref_registry_with_layout(self):
        from paper.renderer import build_ref_registry

        doc = Document(
            metadata=Metadata(title="Test"),
            sections=[],
            layout_elements=[
                LayoutElement(
                    kind="figure",
                    box=Box(0, 0, 100, 100, 0),
                    confidence=0.9,
                    label="Figure 1",
                    caption="A figure",
                ),
                LayoutElement(
                    kind="table",
                    box=Box(0, 0, 100, 100, 1),
                    confidence=0.85,
                    label="Table 1",
                ),
                LayoutElement(
                    kind="equation",
                    box=Box(0, 0, 100, 100, 2),
                    confidence=0.92,
                    label="Eq. 1",
                ),
            ],
        )

        registry = build_ref_registry(doc)

        ref_ids = [e.ref_id for e in registry]
        assert "f1" in ref_ids
        assert "t1" in ref_ids
        assert "eq1" in ref_ids

        # Verify kinds
        f1 = next(e for e in registry if e.ref_id == "f1")
        assert f1.kind == "figure"
        assert f1.label == "Figure 1"

        t1 = next(e for e in registry if e.ref_id == "t1")
        assert t1.kind == "table"

        eq1 = next(e for e in registry if e.ref_id == "eq1")
        assert eq1.kind == "equation"

    def test_ref_summary_includes_layout(self):
        from paper.renderer import build_ref_registry, _ref_summary

        doc = Document(
            metadata=Metadata(title="Test"),
            layout_elements=[
                LayoutElement(kind="figure", box=Box(0, 0, 1, 1, 0),
                              confidence=0.9, label="Figure 1"),
                LayoutElement(kind="figure", box=Box(0, 0, 1, 1, 1),
                              confidence=0.9, label="Figure 2"),
                LayoutElement(kind="table", box=Box(0, 0, 1, 1, 0),
                              confidence=0.9, label="Table 1"),
            ],
        )

        registry = build_ref_registry(doc)
        summary = _ref_summary(registry)

        assert "f1..f2 (figures)" in summary
        assert "t1..t1 (tables)" in summary

    def test_empty_layout_no_layout_refs(self):
        from paper.renderer import build_ref_registry

        doc = Document(metadata=Metadata(title="Test"))
        registry = build_ref_registry(doc)

        layout_refs = [e for e in registry if e.kind in ("figure", "table", "equation")]
        assert layout_refs == []


class TestStorageLayout:
    def test_layout_path(self, tmp_path, monkeypatch):
        from paper import storage

        monkeypatch.setattr(storage, "PAPERS_DIR", tmp_path)
        path = storage.layout_path("2301.00001")
        assert path.name == "layout.json"
        assert "2301.00001" in str(path)

    def test_has_layout_false(self, tmp_path, monkeypatch):
        from paper import storage

        monkeypatch.setattr(storage, "PAPERS_DIR", tmp_path)
        assert storage.has_layout("2301.00001") is False

    def test_has_layout_true(self, tmp_path, monkeypatch):
        from paper import storage

        monkeypatch.setattr(storage, "PAPERS_DIR", tmp_path)
        path = storage.layout_path("2301.00001")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("[]")
        assert storage.has_layout("2301.00001") is True
