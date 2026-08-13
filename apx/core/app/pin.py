"""The pin act (Story 4.11, FR-43 / FR-25) — moving a single *pièce* across **the line**.

A thin Application-layer seam over the :class:`PinRecorder` port: a caller (the API, or the later
triage-table surface) depends on this **core** function, never on the store adapter (AD-4). The
recorder (the store) owns the guarantee — it validates the mandatory reason (FR-25), mints the
per-*pièce* monotonic ``seq``, and appends the ledger entry atomically with one *override* audit
entry (AD-22/AD-37). A pin is **orthogonal** to ranking: it never moves the ranked order and never
moves **the line** — exactly one *pièce* crosses (FR-43, the derivation is Story 4.7). It imports
Ports only (AD-4), touches no store.
"""

from __future__ import annotations

from apx.core.domain.pin import PinLogRecord
from apx.core.domain.triage_sets import Pin, PinSide
from apx.core.ports.pin import PinRecorder


def pin_piece(
    recorder: PinRecorder, *, tenant: str, matter: str, actor: str, piece_id: str, side: PinSide,
    reason: str, scopes: set[str], expected_seq: int | None = None,
) -> int:
    """Pin a *pièce* into or out of the *retained set* through the recorder port (FR-43). Returns
    the new ledger ``seq``. Raises ``MissingOverrideReason`` (a blank reason, FR-25), ``StalePin``
    (a moved ``expected_seq``), or a scope error — the recorder owns validation, the monotonic seq,
    conditional commit and the atomic *override* audit; this seam keeps the caller off the adapter
    (AD-4)."""
    return recorder.pin_piece(
        tenant=tenant, matter=matter, actor=actor, piece_id=piece_id, side=side, reason=reason,
        scopes=scopes, expected_seq=expected_seq)


def remove_pin(
    recorder: PinRecorder, *, tenant: str, matter: str, actor: str, piece_id: str, scopes: set[str],
    expected_seq: int | None = None,
) -> int:
    """Remove a *pièce*'s pin through the recorder port — a recorded, reversible act (FR-43). A
    removal is a NEW ``removed`` entry (append-only, AD-7). Returns the new ``seq``. Raises
    ``ValueError`` when there is no active pin to remove, or a stale/scope error."""
    return recorder.remove_pin(
        tenant=tenant, matter=matter, actor=actor, piece_id=piece_id, scopes=scopes,
        expected_seq=expected_seq)


def read_current_pins(
    recorder: PinRecorder, *, tenant: str, matter: str, scopes: set[str]
) -> tuple[Pin, ...] | None:
    """The in-force pins for a *matter* through the recorder port — the input `read_triage_sets`
    consumes. Returns ``None`` when out of scope or absent (non-disclosing)."""
    return recorder.read_current_pins(tenant=tenant, matter=matter, scopes=scopes)


def read_pin_log(
    recorder: PinRecorder, *, tenant: str, matter: str, scopes: set[str]
) -> tuple[PinLogRecord, ...] | None:
    """Every entry of the *matter*'s pin ledger with its actor and reason — what the export carries
    (FR-26), not the in-force view. ``None`` when out of scope or absent (non-disclosing)."""
    return recorder.read_pin_log(tenant=tenant, matter=matter, scopes=scopes)
