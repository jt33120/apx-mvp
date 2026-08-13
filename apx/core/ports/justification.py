"""The justification recorder port (Story 4.6, FR-41 / FR-18 / FR-11 / AD-4).

The one boundary the justification act persists across: the store adapter implements it (the
version-bound justification + the version-independent rejection ledger + the show-time containment
verification), and the ``core/app`` seam depends only on this Protocol (AD-4 — the core imports no
adapter). The store owns the guarantees — it verifies every named extract by exact containment at
read time (an unresolved extract makes the justification ``is_unverified``, never ordinary), mints
the per-*pièce* monotonic ``seq`` for a reject/restore, and appends atomically with one audit entry.
"""

from __future__ import annotations

from typing import Protocol

from apx.core.domain.justification import (
    EvidenceExtract,
    JustificationBasis,
    VerifiedJustification,
)


class JustificationStore(Protocol):
    def record_justification(
        self, *, tenant: str, matter: str, actor: str, piece_id: str,
        sentence: str, basis: JustificationBasis, evidence: tuple[EvidenceExtract, ...],
        source_language: str | None = None, scopes: set[str], version_no: int | None = None,
    ) -> None:
        """Record a *pièce*'s justification against a *ranking version* (FR-41) — write-once per
        (version, *pièce*), atomic with one ``justification_recorded`` audit entry. The sentence is
        a model summary; the evidence (chunk id + quoted passage) is the checkable control. Raises a
        typed error for a duplicate, an absent ranking version, or an out-of-scope *matter*."""
        ...

    def read_justification(
        self, *, tenant: str, matter: str, scopes: set[str], piece_id: str,
        version_no: int | None = None, interface_language: str | None = None,
    ) -> VerifiedJustification | None:
        """A *pièce*'s justification AS SHOWN (FR-41/FR-11): every named extract re-verified by
        exact containment at read time (an unresolved extract ⇒ ``is_unverified``, never ordinary),
        the
        current rejection state folded in, the derived confidence carried. Returns ``None`` when out
        of scope or absent (non-disclosing). Not audited (a read)."""
        ...

    def reject_justification(
        self, *, tenant: str, matter: str, actor: str, piece_id: str, scopes: set[str],
        reason: str | None = None, expected_seq: int | None = None,
    ) -> int:
        """Reject the tool's assessment for a *pièce* in one action (FR-18) — set aside, reversibly
        (append-only, AD-7), recorded in the *audit record*. Returns the new ``seq``. Raises a typed
        error when already rejected, on a stale ``expected_seq``, or an out-of-scope *matter*."""
        ...

    def restore_justification(
        self, *, tenant: str, matter: str, actor: str, piece_id: str, scopes: set[str],
        reason: str | None = None, expected_seq: int | None = None,
    ) -> int:
        """Re-instate a rejected assessment (FR-18) — the reversal, a NEW ``restored`` entry (never
        a delete). Returns the new ``seq``. Raises a typed error when there is nothing to restore,
        on a stale ``expected_seq``, or an out-of-scope *matter*."""
        ...

    def matter_is_held(self, *, tenant: str, matter: str, scopes: set[str]) -> bool:
        """Whether the caller may see this *matter* at all (AD-13). A read that must fail closed on
        its own asks this rather than inferring scope from another read's ``None`` — which conflates
        "out of scope" with "nothing recorded" and leaks the difference (Story 5.7)."""
        ...
