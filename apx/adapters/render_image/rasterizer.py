"""Scanned-PDF page rasterisation for the pièce viewer (Story 3.5c-4, AD-14's render path).

Rasterises ONE page of a scanned PDF to a PNG (poppler via pdf2image), at the SAME dpi the OCR ran
at (Story 3.5c-1), so the page pixels match the stored OCR word boxes the viewer draws over them.
One page per call — a 340-page scan renders page by page, never whole. The decrypted bytes and
poppler's temp output stay on the ENCRYPTED data volume (``spool_dir``, AD-31 — the Story 3.5c-3
lesson), removed in ``finally``. pdf2image/PIL are imported lazily and the system binary (poppler)
ships in the image; where it is absent (or the input is not a PDF, or the page is out of range), a
rasterise returns ``None`` and the edge offers the original (FR-44) — never a raise, never a 500.
"""

from __future__ import annotations

import contextlib
import io
import os
import tempfile

from apx.adapters.spool import spool_dir

# MUST match ``ocr_tesseract.tesseract._DPI`` — the dpi the scan was rasterised at for OCR, so the
# page image and the stored word boxes share one pixel space. A lockstep test asserts the equality.
_DPI = 200


class Pdf2ImageRasterizer:
    """Implements the ``PageRasterizer`` port for scanned PDFs via poppler (Story 3.5c-4). A non-PDF
    (images are client-rendered from the original), an out-of-range page, or absent poppler →
    ``None`` (the edge offers the original)."""

    def __init__(self, dpi: int = _DPI) -> None:
        self._dpi = dpi

    def rasterize(self, *, data: bytes, page: int) -> bytes | None:
        if page < 0:
            return None
        spool = spool_dir()
        pdf_path: str | None = None
        try:
            fd, pdf_path = tempfile.mkstemp(suffix=".pdf", dir=spool)
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
            return self._rasterize_page(pdf_path, page, spool)
        except Exception:  # noqa: BLE001 — non-PDF / bad page / missing poppler → None (offer original)
            return None
        finally:
            if pdf_path is not None:
                with contextlib.suppress(OSError):
                    os.unlink(pdf_path)

    def _rasterize_page(self, pdf_path: str, page: int, spool: str) -> bytes | None:
        from pdf2image import convert_from_path

        # poppler writes the page PNG into `out` (on the encrypted volume); pdf2image returns it as
        # a PIL image opened from that file — saved to bytes INSIDE the `with`, before cleanup.
        with tempfile.TemporaryDirectory(dir=spool) as out:
            images = convert_from_path(
                pdf_path, dpi=self._dpi, first_page=page + 1, last_page=page + 1,
                fmt="png", output_folder=out)
            if not images:
                return None  # the page is out of range for this PDF
            buffer = io.BytesIO()
            images[0].save(buffer, format="PNG")
            return buffer.getvalue()
