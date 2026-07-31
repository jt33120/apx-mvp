"""Open a pièce for the viewer (Story 3.5b) — a reader through the ONE read entry point (AD-14).

Given a pièce id, it returns the pièce's viewer metadata IFF the caller holds its *matter*'s scope
— the scope is a query **pre-filter** carried into the reader (AD-13), never a post-filter over a
fetched row. A pièce outside scope (or absent) yields ``None``: the caller cannot tell an
out-of-scope pièce from one that does not exist (FR-14/FR-44). An empty scope reads nothing — there
is **no admin bypass** (a Piece read is scoped like any other, the Story 3.3 gate; fail-closed,
AD-12).

This is a pure read — no side-effect. Recording the open in the audit record (FR-45) is a separate,
explicit write the edge performs when the *content* is served (``store.audit_piece_open``), exactly
as the search endpoints audit a query separately from the read (Story 3.4).
"""

from __future__ import annotations

from apx.core.ports.read import PieceReader, PieceView


def open_piece(
    *, tenant: str, scopes: set[str], piece_id: str, reader: PieceReader
) -> PieceView | None:
    """The pièce's viewer metadata if it is within the caller's scope, else ``None`` (a
    non-disclosing miss). Fail-closed: an empty scope reads nothing (AD-12). No admin bypass — a
    Piece read is scoped like any other (Story 3.3 gate)."""
    if not scopes:
        return None  # fail closed — no scope → nothing is visible (AD-12)
    return reader.read_piece(tenant=tenant, scopes=scopes, piece_id=piece_id)
