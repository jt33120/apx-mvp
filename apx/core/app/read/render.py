"""Render a pièce for the viewer (Story 3.5c-2) — through the ONE scoped read entry point (AD-14).

A render is one of AD-14's enumerated *second read paths*, so it runs the same scope **pre-filter**
as every tenant-data read: ``open_piece`` first (AD-13/14) — an out-of-scope or absent pièce yields
``None`` and the edge answers the non-disclosing 404. Only then are the original bytes read (inside
the tenant boundary) and handed to the renderer. The **render byte bound** (Story 3.5b) is applied
before the bytes are read, so a huge pièce is never loaded to exhaust the reader's machine — it is
offered as the original instead (the 3.5d density rule). A format the renderer cannot render, or a
missing/tampered blob, is likewise "offer the original", never a 500.

This is a read + a pure transform; **recording the open in the audit record (FR-45) is the edge's
separate write**, performed only when rendered content is actually served — exactly as ``/original``
audits on serve (Story 3.5b) and the search endpoints audit a query separately (Story 3.4).
"""

from __future__ import annotations

from dataclasses import dataclass

from apx.core.app.read.piece import open_piece
from apx.core.domain.crypto import DecryptionError
from apx.core.ports.originals import OriginalStore
from apx.core.ports.read import PieceReader
from apx.core.ports.render import PieceRenderer, RenderedDocument


@dataclass(frozen=True)
class RenderOutcome:
    """The result of an IN-SCOPE render attempt. ``document`` is the sanitised render, or ``None``
    when the pièce is in scope but cannot be rendered inline (over the bound, an unsupported format,
    or an unavailable blob) — the edge then **offers the original** (FR-44), and ``reason`` is the
    honest, lawyer-language limit. ``matter``/``piece_id`` let the edge audit the open on a served
    render. The whole call returns ``None`` (not this) only for out-of-scope/absent — never
    disclosing which."""

    matter: str
    piece_id: str
    document: RenderedDocument | None
    reason: str | None = None


_UNAVAILABLE = "l'original de cette pièce n'est pas disponible"
_TOO_LARGE = "pièce trop volumineuse pour un rendu en ligne — ouvrez l'original"
_UNRENDERED = "format non rendu en ligne — ouvrez l'original"


def render_piece(
    *,
    tenant: str,
    scopes: set[str],
    piece_id: str,
    reader: PieceReader,
    originals: OriginalStore,
    renderer: PieceRenderer,
    max_bytes: int,
) -> RenderOutcome | None:
    """Render an in-scope pièce to sanitised inline HTML, or say why the original should be offered.
    Returns ``None`` for an out-of-scope or absent pièce (the edge 404s, disclosing nothing). Fail-
    closed throughout: an empty scope reads nothing (``open_piece``), an over-bound pièce is never
    loaded, a missing/tampered blob offers the original."""
    view = open_piece(tenant=tenant, scopes=scopes, piece_id=piece_id, reader=reader)
    if view is None:
        return None  # out-of-scope or absent — indistinguishable, discloses nothing (FR-14/FR-44)
    size = originals.size(tenant, view.content_hash)
    if size is None:
        return RenderOutcome(view.matter, view.piece_id, None, _UNAVAILABLE)
    if size > max_bytes:
        return RenderOutcome(view.matter, view.piece_id, None, _TOO_LARGE)  # never load it (3.5d)
    try:
        data = originals.open(tenant, view.content_hash)
    except (FileNotFoundError, DecryptionError):
        return RenderOutcome(view.matter, view.piece_id, None, _UNAVAILABLE)
    try:
        document = renderer.render(filename=view.filename, data=data)
    except Exception:  # noqa: BLE001 — enforce the port's no-raise contract at the boundary
        # A renderer that raises despite its contract still fails CLOSED to offer-the-original — not
        # a 500 leaking a stack trace, and it can never emit unsanitised HTML (nothing is returned).
        document = None
    if document is None:
        return RenderOutcome(view.matter, view.piece_id, None, _UNRENDERED)
    return RenderOutcome(view.matter, view.piece_id, document, None)
