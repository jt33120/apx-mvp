"""OCR extraction via Tesseract — the scanned-document path.

The cascade's cheap path (born-digital text via pypdf) misses scans: a PDF with no
text layer, or a page delivered as an image. This adapter reads them with Tesseract —
Pillow opens images, pdf2image (poppler) rasterises scanned PDFs page by page — and
returns the recognised text. The Python bindings import lazily and the system binaries
(tesseract, tesseract-ocr-fra, poppler-utils) ship in the Docker image, so the app runs
unchanged where OCR is not installed: there, an OCR attempt simply degrades to a normal
extraction failure. Recall-first — nothing is ever fabricated.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterable
from pathlib import Path

from apx.core.domain.extraction import ExtractOutcome
from apx.core.domain.failures import ErrorClass
from apx.core.ports.extraction import Extractor

_LANG = os.environ.get("APX_OCR_LANG", "fra+eng")
_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".gif", ".webp"}


class TesseractExtractor:
    """Implements the Extractor port for images and scanned PDFs, via Tesseract."""

    version = "tesseract/1"

    def extract(self, path: Path) -> ExtractOutcome:
        suffix = path.suffix.lower()
        if suffix in _IMAGE_SUFFIXES:
            return self._ocr(lambda: self._image_pages(path))
        if suffix == ".pdf":
            return self._ocr(lambda: self._pdf_pages(path))
        return ExtractOutcome("", "tesseract", self.version, ErrorClass.UNSUPPORTED_FORMAT)

    def _ocr(self, pages: Callable[[], Iterable[object]]) -> ExtractOutcome:
        # A missing binding, a missing binary, or an unreadable page all degrade to a
        # failure (WithOcr then keeps the primary's) — never an outage, never a fake.
        try:
            import pytesseract
            text = "\n".join(pytesseract.image_to_string(page, lang=_LANG) for page in pages())
        except Exception:  # noqa: BLE001
            return ExtractOutcome("", "tesseract", self.version, ErrorClass.UNREADABLE)
        if not text.strip():
            return ExtractOutcome("", "tesseract", self.version, ErrorClass.EXTRACTED_EMPTY)
        return ExtractOutcome(text, "tesseract", self.version)

    def _image_pages(self, path: Path) -> Iterable[object]:
        from PIL import Image
        return [Image.open(path)]

    def _pdf_pages(self, path: Path) -> Iterable[object]:
        from pdf2image import convert_from_path
        return convert_from_path(str(path), dpi=200)


class WithOcr:
    """Compose a fast text extractor with an OCR fallback: try the primary; if it found
    no text (a scan) or does not support the format (an image), try OCR; otherwise keep
    the primary's result. Born-digital files never pay the OCR cost."""

    def __init__(self, primary: Extractor, ocr: Extractor) -> None:
        self._primary = primary
        self._ocr = ocr

    def extract(self, path: Path) -> ExtractOutcome:
        outcome = self._primary.extract(path)
        if outcome.ok:
            return outcome
        if outcome.error_class in (ErrorClass.EXTRACTED_EMPTY, ErrorClass.UNSUPPORTED_FORMAT):
            ocr_outcome = self._ocr.extract(path)
            if ocr_outcome.ok:
                return ocr_outcome
        return outcome
