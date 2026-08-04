"""Rasterise a scanned-PDF page for the viewer (Story 3.5c-4) — through the ONE scoped read entry
point (AD-14).

A page render is one of AD-14's enumerated *second read paths*, so it runs the same scope
**pre-filter** as every tenant-data read: ``open_piece`` first (AD-13/14) — an out-of-scope or
absent pièce yields ``None`` and the edge answers the non-disclosing 404. Then, because ``/page``
serves the document's *readable content*, three guards run before poppler is ever invoked (reviewer
findings):

- **It is a scan.** ``/page`` requires a stored OCR layer (Story 3.5c-1). A born-digital / no-layout
  PDF is offered as the original (the client renders it, per the hybrid choice) — so no PDF is ever
  served page-by-page **unaudited**, and no page is rendered for a pièce that was never OCR'd.
- **The page is in range and not a *pixel bomb*.** The stored layout carries each page's exact pixel
  dimensions (the space the OCR boxes live in); a page whose ``width × height`` exceeds
  ``max_pixels`` is offered as the original — so a tiny PDF declaring a giant page can never spike
  poppler's memory, even though its *file* is under the byte bound.
- **The file fits the scan byte bound**, then the bytes are read and one page rasterised.

Mirrors ``render_piece``. The audit of the open (FR-45) is the edge's write, done on the served
``/page`` (the content), consistent with ``/original`` and ``/render``.
"""

from __future__ import annotations

from dataclasses import dataclass

from apx.core.app.read.piece import open_piece
from apx.core.domain.crypto import DecryptionError
from apx.core.domain.ocr_layout import OcrLayout
from apx.core.ports.originals import OriginalStore
from apx.core.ports.rasterize import PageRasterizer
from apx.core.ports.read import PieceReader


@dataclass(frozen=True)
class ScanPageOutcome:
    """The result of an IN-SCOPE page-render attempt. ``png`` is the rasterised page, or ``None``
    when the pièce is in scope but the page cannot be produced (not a scan, an out-of-range page, a
    pixel-bomb page, over the byte bound, or an unavailable blob) — the edge then offers the
    original (FR-44), and ``reason`` is the honest limit. The whole call returns ``None`` only for
    out-of-scope/absent — never disclosing which."""

    matter: str
    piece_id: str
    png: bytes | None
    reason: str | None = None


_NOT_A_SCAN = "cette pièce n'a pas de couche OCR — ouvrez l'original"
_NO_SUCH_PAGE = "page inexistante"
_TOO_LARGE_PIXELS = "page trop grande pour un rendu — ouvrez l'original"
_TOO_LARGE_BYTES = "scan trop volumineux pour un rendu — ouvrez l'original"
_UNAVAILABLE = "l'original de cette pièce n'est pas disponible"
_NOT_RENDERED = "page non rendue — ouvrez l'original"


def _scan_layout(originals: OriginalStore, tenant: str, content_hash: str) -> OcrLayout | None:
    """The pièce's stored OCR layout, or ``None`` if it has none (born-digital / non-OCR) or the
    blob is unreadable/malformed — treated as "not a scan" (offer the original), never a raise."""
    try:
        raw = originals.open(tenant, content_hash, kind="ocr-layout")
    except (FileNotFoundError, DecryptionError):
        return None
    try:
        return OcrLayout.from_json(raw.decode())
    except (ValueError, KeyError, TypeError, UnicodeDecodeError):
        return None


def read_scan_page(
    *,
    tenant: str,
    scopes: set[str],
    piece_id: str,
    page: int,
    reader: PieceReader,
    originals: OriginalStore,
    rasterizer: PageRasterizer,
    max_bytes: int,
    max_pixels: int,
) -> ScanPageOutcome | None:
    """Rasterise page ``page`` of an in-scope scanned PDF, or say why to offer the original instead.
    Returns ``None`` for an out-of-scope or absent pièce (the edge 404s, disclosing nothing).
    Fail-closed: an empty scope reads nothing; a non-scan, an out-of-range or pixel-bomb page, and
    an over-bound scan are all offered as the original **before** the (large) original is loaded or
    poppler is invoked; a missing/tampered blob offers the original."""
    view = open_piece(tenant=tenant, scopes=scopes, piece_id=piece_id, reader=reader)
    if view is None:
        return None  # out-of-scope or absent — indistinguishable, discloses nothing (FR-14/FR-44)

    def offer(reason: str) -> ScanPageOutcome:
        return ScanPageOutcome(view.matter, view.piece_id, None, reason)

    layout = _scan_layout(originals, tenant, view.content_hash)
    if layout is None:
        return offer(_NOT_A_SCAN)                      # not a scan — client renders the raw file
    if page < 0 or page >= len(layout.pages):
        return offer(_NO_SUCH_PAGE)
    dims = layout.pages[page]
    if dims.width * dims.height > max_pixels:
        return offer(_TOO_LARGE_PIXELS)                # pixel-bomb guard — poppler is never invoked
    size = originals.size(tenant, view.content_hash)
    if size is None:
        return offer(_UNAVAILABLE)
    if size > max_bytes:
        return offer(_TOO_LARGE_BYTES)                 # never load an over-bound scan
    try:
        data = originals.open(tenant, view.content_hash)
    except (FileNotFoundError, DecryptionError):
        return offer(_UNAVAILABLE)
    png = rasterizer.rasterize(data=data, page=page)
    if png is None:
        return offer(_NOT_RENDERED)
    return ScanPageOutcome(view.matter, view.piece_id, png, None)
