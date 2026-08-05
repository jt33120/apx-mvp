"""The taxonomy-label recorder port (Story 4.5, FR-40 / AD-37 / AD-4).

The one boundary the labelling act persists across: the store adapter implements it (the
append-only, version-independent ledger), and the ``core/app`` seam depends only on this Protocol
(AD-4 — the core imports no adapter). The store validates the label against the *tenant*'s current
taxonomy, mints the per-*pièce* monotonic ``seq`` inside its transaction (AD-37/AD-49), and appends
the change-log entry atomically with one audit entry (AD-22) — so the caller supplies only the
identity and the value.
"""

from __future__ import annotations

from typing import Protocol


class TaxonomyLabelRecorder(Protocol):
    def assign_label(
        self, *, tenant: str, matter: str, actor: str, piece_id: str, label: str,
        scopes: set[str], expected_seq: int | None = None,
    ) -> int:
        """Append one taxonomy-label change-log entry for a *pièce*, atomically with one audit entry
        (AD-22). Validates the label against the *tenant*'s current taxonomy ∪ {unlabelled} — an
        out-of-taxonomy label can never leak (FR-40); mints the per-*pièce* monotonic ``seq``
        (AD-49); the commit is conditional on ``expected_seq`` (a moved label fails loudly, AD-37).
        Returns the new ``seq``. Raises a typed error for an out-of-taxonomy label, a stale
        ``expected_seq``, or an out-of-scope *matter*."""
        ...

    def revert_label(
        self, *, tenant: str, matter: str, actor: str, piece_id: str, to_seq: int,
        scopes: set[str],
    ) -> int:
        """Revert a *pièce*'s taxonomy label to the value it held at ``to_seq`` by appending a NEW
        entry (append-only, AD-7) — reversible from the change log (FR-40/FR-20). Returns the new
        ``seq``. Raises a typed error when ``to_seq`` is not an entry of the *pièce*, the restored
        value is no longer in the taxonomy, or the *matter* is out of scope."""
        ...
