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
from apx.core.domain.ocr_layout import OcrLayout, OcrPage, OcrWord
from apx.core.ports.extraction import Extractor

_LANG = os.environ.get("APX_OCR_LANG", "fra+eng")
_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".gif", ".webp"}
_DPI = 200  # the ONE rasterisation dpi for scanned PDFs (used by _pdf_pages AND recorded in the
#             layout); an image is OCR'd at native resolution and records dpi=0 instead


class TesseractExtractor:
    """Implements the Extractor port for images and scanned PDFs, via Tesseract."""

    version = "tesseract/1"

    def extract(self, path: Path) -> ExtractOutcome:
        suffix = path.suffix.lower()
        if suffix in _IMAGE_SUFFIXES:
            # an image is OCR'd at its NATIVE resolution — no rasterisation — so dpi=0 records
            # "native pixels" (the boxes are still in the image's own pixel space).
            return self._ocr(lambda: self._image_pages(path), dpi=0)
        if suffix == ".pdf":
            return self._ocr(lambda: self._pdf_pages(path), dpi=_DPI)
        return ExtractOutcome("", "tesseract", self.version, ErrorClass.UNSUPPORTED_FORMAT)

    def _ocr(self, pages: Callable[[], Iterable[object]], dpi: int) -> ExtractOutcome:
        # A missing binding, a missing binary, or an unreadable page all degrade to a
        # failure (WithOcr then keeps the primary's) — never an outage, never a fake.
        # ONE pass per page via image_to_data: it yields BOTH the per-word boxes (the layout, for
        # the viewer's overlay — Story 3.5c-1) AND the text (reconstructed from the same words, so
        # no doubled OCR cost; fr-fold-v1 normalisation absorbs whitespace differences downstream).
        try:
            import pytesseract
            ocr_pages: list[OcrPage] = []
            page_texts: list[str] = []
            for page in pages():
                data = pytesseract.image_to_data(
                    page, lang=_LANG, output_type=pytesseract.Output.DICT)
                words, page_text = _words_and_text(data)
                ocr_pages.append(OcrPage(
                    width=int(page.width), height=int(page.height), words=tuple(words)))
                page_texts.append(page_text)
            text = "\n".join(page_texts)
        except Exception:  # noqa: BLE001
            return ExtractOutcome("", "tesseract", self.version, ErrorClass.UNREADABLE)
        if not text.strip():
            return ExtractOutcome("", "tesseract", self.version, ErrorClass.EXTRACTED_EMPTY)
        layout = OcrLayout(pages=tuple(ocr_pages), dpi=dpi)
        return ExtractOutcome(text, "tesseract", self.version, layout=layout)

    def _image_pages(self, path: Path) -> Iterable[object]:
        from PIL import Image
        return [Image.open(path)]

    def _pdf_pages(self, path: Path) -> Iterable[object]:
        from pdf2image import convert_from_path
        return convert_from_path(str(path), dpi=_DPI)


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


def _words_and_text(data: dict) -> tuple[list[OcrWord], str]:
    """From a Tesseract ``image_to_data`` DICT, the recognised words (with boxes) and the page text
    reconstructed from the SAME words — grouped into lines by (block, paragraph, line), joined with
    spaces, lines with newlines. Blank entries and negative-confidence rows (Tesseract's structural
    markers, ``conf == -1``) are skipped."""
    words: list[OcrWord] = []
    lines: list[str] = []
    current: list[str] = []
    last_key: tuple[int, int, int] | None = None
    for i in range(len(data["text"])):
        text = str(data["text"][i]).strip()
        try:
            conf = float(data["conf"][i])
        except (TypeError, ValueError):
            continue  # a non-numeric conf (an exotic build) skips THIS word, never the whole doc
        if not text or conf < 0:
            continue
        words.append(OcrWord(
            text=text, left=int(data["left"][i]), top=int(data["top"][i]),
            width=int(data["width"][i]), height=int(data["height"][i]), confidence=conf))
        key = (int(data["block_num"][i]), int(data["par_num"][i]), int(data["line_num"][i]))
        if last_key is not None and key != last_key and current:
            lines.append(" ".join(current))
            current = []
        current.append(text)
        last_key = key
    if current:
        lines.append(" ".join(current))
    return words, "\n".join(lines)
