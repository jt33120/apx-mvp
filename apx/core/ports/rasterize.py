"""The page-rasterise port — the scanned-document page-image boundary (AD-4, AD-14, Story 3.5c-4).

The pièce viewer renders a scanned PDF as a **page image** with the OCR text drawn over it. The
image is rasterised page by page (poppler) so a 340-page scan never loads whole; the core depends on
this port, and the adapter (``adapters/render_image``, pdf2image) does the rasterising. The image is
produced at the SAME dpi the OCR ran at (Story 3.5c-1), so the page pixels align with the stored
word boxes the overlay draws.
"""

from __future__ import annotations

from typing import Protocol


class PageRasterizer(Protocol):
    def rasterize(self, *, data: bytes, page: int) -> bytes | None:
        """Rasterise page ``page`` (0-indexed) of a scanned PDF in ``data`` to **PNG** bytes, at the
        OCR dpi (so the image pixel space matches the stored OCR word boxes). Returns ``None`` for a
        non-PDF (images are client-rendered from the original), an out-of-range page, or ANY failure
        (a missing poppler, an unreadable file) — the edge then offers the original (FR-44). Never
        raises, never a 500, and reads one page at a time — never the whole PDF into memory beyond
        the read."""
        ...
