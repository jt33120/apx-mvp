"""The justification act (Story 4.6, FR-41 / FR-18 / FR-11) — why a *pièce* is where it is, in one
line, backed by named evidence.

A thin Application-layer seam over the :class:`JustificationStore` port: a caller (the API, or the
later triage-table surface) depends on this **core** function, never on the store adapter (AD-4).
The recorder (the store) owns the guarantees — write-once recording, show-time exact-containment
verification of every named extract, and the append-only reversible rejection ledger. It imports
Ports only (AD-4), touches no store.
"""

from __future__ import annotations

from apx.core.domain.justification import (
    EvidenceExtract,
    JustificationBasis,
    VerifiedJustification,
)
from apx.core.ports.justification import JustificationStore


def record_justification(
    store: JustificationStore, *, tenant: str, matter: str, actor: str, piece_id: str,
    sentence: str, basis: JustificationBasis, evidence: tuple[EvidenceExtract, ...],
    source_language: str | None = None, scopes: set[str], version_no: int | None = None,
) -> None:
    """Record a *pièce*'s justification through the recorder port (FR-41) — the sentence is a model
    summary, the evidence is the checkable control. Write-once; raises a typed error for a
    duplicate, an absent ranking version, or a scope error."""
    store.record_justification(
        tenant=tenant, matter=matter, actor=actor, piece_id=piece_id, sentence=sentence,
        basis=basis, evidence=evidence, source_language=source_language, scopes=scopes,
        version_no=version_no)


def read_justification(
    store: JustificationStore, *, tenant: str, matter: str, scopes: set[str], piece_id: str,
    version_no: int | None = None, interface_language: str | None = None,
) -> VerifiedJustification | None:
    """A *pièce*'s justification AS SHOWN through the recorder port (FR-41/FR-11): every named
    extract verified by exact containment at show time, the rejection state folded in, the derived
    confidence carried. Returns ``None`` when out of scope or absent (non-disclosing)."""
    return store.read_justification(
        tenant=tenant, matter=matter, scopes=scopes, piece_id=piece_id, version_no=version_no,
        interface_language=interface_language)


def reject_justification(
    store: JustificationStore, *, tenant: str, matter: str, actor: str, piece_id: str,
    scopes: set[str], reason: str | None = None, expected_seq: int | None = None,
) -> int:
    """Reject the tool's assessment for a *pièce* through the recorder port (FR-18) — set aside,
    reversibly, recorded in the *audit record*. Returns the new ``seq``. Raises a typed error when
    already rejected, or a stale/scope error."""
    return store.reject_justification(
        tenant=tenant, matter=matter, actor=actor, piece_id=piece_id, scopes=scopes, reason=reason,
        expected_seq=expected_seq)


def restore_justification(
    store: JustificationStore, *, tenant: str, matter: str, actor: str, piece_id: str,
    scopes: set[str], reason: str | None = None, expected_seq: int | None = None,
) -> int:
    """Re-instate a rejected assessment through the recorder port (FR-18) — the reversal, a NEW
    ``restored`` entry (never a delete). Returns the new ``seq``. Raises a typed error when there is
    nothing to restore, or a stale/scope error."""
    return store.restore_justification(
        tenant=tenant, matter=matter, actor=actor, piece_id=piece_id, scopes=scopes, reason=reason,
        expected_seq=expected_seq)
