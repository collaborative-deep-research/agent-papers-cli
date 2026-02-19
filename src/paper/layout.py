"""Detect figures, tables, and equations in PDF pages using DocLayout-YOLO.

Uses the doclayout_yolo library with a DocLayout-YOLO model pre-trained on
DocStructBench.  Model weights are downloaded lazily to ~/.papers/.models/ on
first use.  Detection results are cached per-paper in layout.json.

Supports MPS (Apple Metal), CUDA, and CPU backends — PyTorch picks the
best available device automatically.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING

import fitz  # PyMuPDF
import numpy as np

from paper.models import Box, LayoutElement

if TYPE_CHECKING:
    from doclayout_yolo import YOLOv10

logger = logging.getLogger(__name__)

# DocLayout-YOLO class names → our element kinds.
# We only keep the three we care about; the rest (plain text, title, etc.)
# are already handled by the text parser.
_KIND_MAP: dict[str, str] = {
    "figure": "figure",
    "table": "table",
    "isolate_formula": "equation",
    # Aliases in case model variant uses different names:
    "Picture": "figure",
    "Figure": "figure",
    "Table": "table",
    "Formula": "equation",
    "Equation": "equation",
}

_RENDER_DPI = 150  # good speed/accuracy balance for detection

# Default DocLayout-YOLO model identifier — resolved at download time.
_DEFAULT_MODEL = "juliozhao/DocLayout-YOLO-DocStructBench"
_MODEL_FILENAME = "doclayout_yolo_docstructbench_imgsz1024.pt"

_model_instance: YOLOv10 | None = None


# ------------------------------------------------------------------
# Model management
# ------------------------------------------------------------------

def _models_dir() -> Path:
    d = Path.home() / ".papers" / ".models"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _best_device() -> str:
    """Pick the best available PyTorch device."""
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "mps"
    except ImportError:
        pass
    return "cpu"


def _load_model() -> YOLOv10:
    """Load (and lazily download) the DocLayout-YOLO model."""
    global _model_instance
    if _model_instance is not None:
        return _model_instance

    try:
        from doclayout_yolo import YOLOv10
    except ImportError:
        raise ImportError(
            "Layout detection requires the 'doclayout_yolo' package.\n"
            "Install it with:  pip install paper-cli[layout]"
        )

    model_path = _models_dir() / _MODEL_FILENAME

    if not model_path.exists():
        logger.info("Downloading DocLayout-YOLO model (first time only)...")
        _download_model(model_path)

    _model_instance = YOLOv10(str(model_path))
    return _model_instance


def _download_model(dest: Path) -> None:
    """Download the DocLayout-YOLO weights from HuggingFace."""
    try:
        from huggingface_hub import hf_hub_download
        downloaded = hf_hub_download(
            repo_id=_DEFAULT_MODEL,
            filename=_MODEL_FILENAME,
            local_dir=str(dest.parent),
        )
        # hf_hub_download may place it in a subfolder; ensure it's at dest
        dl_path = Path(downloaded)
        if dl_path != dest:
            dl_path.rename(dest)
    except ImportError:
        # Fallback: direct httpx download
        import httpx
        url = f"https://huggingface.co/{_DEFAULT_MODEL}/resolve/main/{_MODEL_FILENAME}"
        logger.info("Downloading model from %s ...", url)
        tmp = dest.with_suffix(".tmp")
        with httpx.stream("GET", url, follow_redirects=True, timeout=120) as resp:
            resp.raise_for_status()
            with open(tmp, "wb") as f:
                for chunk in resp.iter_bytes(chunk_size=1024 * 64):
                    f.write(chunk)
        tmp.rename(dest)


# ------------------------------------------------------------------
# Core detection
# ------------------------------------------------------------------

def _render_page(pdf_path: Path, page_num: int) -> tuple[np.ndarray, float, float]:
    """Render a PDF page to a numpy array, returning (image, scale_x, scale_y)."""
    with fitz.open(pdf_path) as doc:
        page = doc[page_num]
        pix = page.get_pixmap(dpi=_RENDER_DPI)
        scale_x = page.rect.width / pix.width
        scale_y = page.rect.height / pix.height
        # Convert pixmap to numpy array (RGB)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        if pix.n == 4:  # RGBA → RGB
            img = img[:, :, :3]
        return img, scale_x, scale_y


def detect_page(pdf_path: Path, page_num: int, conf: float = 0.25) -> list[LayoutElement]:
    """Detect figures, tables, and equations on a single PDF page."""
    model = _load_model()
    device = _best_device()

    img, scale_x, scale_y = _render_page(pdf_path, page_num)
    results = model(img, device=device, conf=conf, verbose=False)

    elements: list[LayoutElement] = []
    for det in results[0].boxes:
        cls_id = int(det.cls)
        cls_name = model.names.get(cls_id, "")
        kind = _KIND_MAP.get(cls_name)
        if kind is None:
            continue

        x0, y0, x1, y1 = det.xyxy[0].tolist()
        box = Box(
            x0=x0 * scale_x,
            y0=y0 * scale_y,
            x1=x1 * scale_x,
            y1=y1 * scale_y,
            page=page_num,
        )
        elements.append(LayoutElement(
            kind=kind,
            box=box,
            confidence=float(det.conf),
        ))

    return elements


def detect_all_pages(pdf_path: Path, conf: float = 0.25) -> list[LayoutElement]:
    """Detect layout elements across all pages of a PDF."""
    with fitz.open(pdf_path) as doc:
        num_pages = len(doc)

    all_elements: list[LayoutElement] = []
    for page_num in range(num_pages):
        all_elements.extend(detect_page(pdf_path, page_num, conf=conf))

    # Sort by page, then top-to-bottom
    all_elements.sort(key=lambda e: (e.box.page, e.box.y0))

    # Assign labels (Figure 1, Table 1, Eq. 1, ...)
    _assign_labels(all_elements)

    # Extract captions
    _extract_captions(all_elements, pdf_path)

    return all_elements


def _assign_labels(elements: list[LayoutElement]) -> None:
    """Assign sequential labels like 'Figure 1', 'Table 2', 'Eq. 3'."""
    counters: dict[str, int] = {"figure": 0, "table": 0, "equation": 0}
    prefix_map = {"figure": "Figure", "table": "Table", "equation": "Eq."}
    for elem in elements:
        counters[elem.kind] += 1
        elem.label = f"{prefix_map[elem.kind]} {counters[elem.kind]}"


def _extract_captions(elements: list[LayoutElement], pdf_path: Path) -> None:
    """Extract caption text for figures and tables using spatial heuristics.

    Figures: search below the bounding box for "Figure N" / "Fig. N".
    Tables: search above the bounding box for "Table N".
    """
    _CAPTION_RE = re.compile(r"(Figure|Fig\.|Table)\s+\d+", re.IGNORECASE)
    SEARCH_HEIGHT = 50  # points to search above/below

    with fitz.open(pdf_path) as doc:
        for elem in elements:
            if elem.kind == "equation":
                continue
            page = doc[elem.box.page]

            if elem.kind == "figure":
                # Search below
                search_rect = fitz.Rect(
                    elem.box.x0, elem.box.y1,
                    elem.box.x1, min(elem.box.y1 + SEARCH_HEIGHT, page.rect.height),
                )
            else:
                # Table: search above
                search_rect = fitz.Rect(
                    elem.box.x0, max(elem.box.y0 - SEARCH_HEIGHT, 0),
                    elem.box.x1, elem.box.y0,
                )

            text = page.get_text("text", clip=search_rect).strip()
            if _CAPTION_RE.match(text):
                # Take first ~200 chars as caption
                elem.caption = re.sub(r"\s+", " ", text)[:200]


# ------------------------------------------------------------------
# Caching
# ------------------------------------------------------------------

def layout_path(paper_id: str) -> Path:
    from paper import storage
    return storage.paper_dir(paper_id) / "layout.json"


def has_layout(paper_id: str) -> bool:
    return layout_path(paper_id).exists()


def save_layout(paper_id: str, elements: list[LayoutElement]) -> None:
    """Save layout detection results to cache."""
    data = [asdict(e) for e in elements]
    path = layout_path(paper_id)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    tmp.rename(path)


def load_layout(paper_id: str) -> list[LayoutElement]:
    """Load cached layout detection results."""
    path = layout_path(paper_id)
    if not path.exists():
        return []
    data = json.loads(path.read_text())
    return [
        LayoutElement(
            kind=d["kind"],
            box=Box(**d["box"]),
            confidence=d["confidence"],
            caption=d.get("caption", ""),
            label=d.get("label", ""),
        )
        for d in data
    ]


def detect_layout(paper_id: str, pdf_path: Path, force: bool = False) -> list[LayoutElement]:
    """Detect layout elements, using cache if available.

    This is the main entry point for layout detection.  It follows the
    two-stage pattern: text parsing returns fast, layout detection runs
    lazily on first access.
    """
    if not force and has_layout(paper_id):
        return load_layout(paper_id)

    elements = detect_all_pages(pdf_path)
    save_layout(paper_id, elements)
    return elements
