"""The pin recorder port (Story 4.11, FR-43 / FR-25 / AD-37 / AD-4).

The one boundary the pin act persists across: the store adapter implements it (the append-only,
version-independent pin ledger), and the ``core/app`` seam depends only on this Protocol (AD-4 — the
core imports no adapter). The store validates the mandatory reason, mints the per-*pièce* monotonic
``seq`` inside its transaction (AD-37/AD-49), and appends the ledger entry atomically with one audit
entry marked as an *override* (AD-22 / FR-25) — so the caller supplies only the identity, the side
and the reason.
"""

from __future__ import annotations

from typing import Protocol

from apx.core.domain.triage_sets import Pin, PinSide


class PinRecorder(Protocol):
    def pin_piece(
        self, *, tenant: str, matter: str, actor: str, piece_id: str, side: PinSide, reason: str,
        scopes: set[str], expected_seq: int | None = None,
    ) -> int:
        """Pin a *pièce* into or out of the *retained set* (FR-43), atomically with one audit entry
        marked as an *override* carrying the reason verbatim (FR-25). Requires a non-blank one-line
        reason (a blank one raises a typed error, nothing written); mints the per-*pièce* monotonic
        ``seq`` (AD-49); the commit is conditional on ``expected_seq`` (a moved pin fails loudly,
        AD-37). Touches only the pin ledger — never the ranked order, never **the line** — so
        exactly one *pièce* crosses and nothing else moves. Returns the new ``seq``. Raises a typed
        error for a blank reason, a stale ``expected_seq``, or an out-of-scope *matter*."""
        ...

    def remove_pin(
        self, *, tenant: str, matter: str, actor: str, piece_id: str, scopes: set[str],
        expected_seq: int | None = None,
    ) -> int:
        """Remove a *pièce*'s pin by appending a ``removed`` entry (append-only, AD-7 — never a
        delete) — a recorded, reversible act (FR-43), NOT an *override*. Returns the new ``seq``.
        Raises a typed error when there is no active pin to remove, on a stale ``expected_seq``, or
        an out-of-scope *matter*."""
        ...

    def read_current_pins(
        self, *, tenant: str, matter: str, scopes: set[str]
    ) -> tuple[Pin, ...] | None:
        """The in-force pins for a *matter* — a VIEW over the ledger (the latest action per *pièce*;
        ``removed`` lifts it), the input :meth:`read_triage_sets` consumes. Returns ``None`` when
        out of scope or absent (non-disclosing). Not audited (a read)."""
        ...
