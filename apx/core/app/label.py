"""The per-*pièce* labelling act (Story 4.5, FR-40) — the explicit act that sets a taxonomy label.

A thin Application-layer seam over the :class:`TaxonomyLabelRecorder` port: a caller (the API, or
the later FR-20 editable-cell table) depends on this **core** function, never on the store adapter
(AD-4). The recorder (the store) owns the guarantee — it validates the label against the *tenant*'s
current taxonomy (out-of-taxonomy can never leak, FR-40), mints the per-*pièce* monotonic ``seq``,
and appends the change-log entry atomically with one audit entry (AD-22/AD-37). Labelling is
**orthogonal** to ranking: it never moves a *pièce* or the line (FR-43). It imports Ports only
(AD-4), touches no store.
"""

from __future__ import annotations

from apx.core.ports.taxonomy_label import TaxonomyLabelRecorder


def assign_taxonomy_label(
    recorder: TaxonomyLabelRecorder, *, tenant: str, matter: str, actor: str, piece_id: str,
    label: str, scopes: set[str], expected_seq: int | None = None,
) -> int:
    """Assign a *pièce*'s taxonomy label through the recorder port (FR-40). Returns the new
    change-log ``seq``. Raises ``OutOfTaxonomyLabel`` (an invalid label), ``StaleLabel`` (a moved
    ``expected_seq``), or a scope error — the recorder owns validation, the monotonic seq, the
    conditional commit and the atomic audit; this seam keeps the caller off the adapter (AD-4)."""
    return recorder.assign_label(
        tenant=tenant, matter=matter, actor=actor, piece_id=piece_id, label=label,
        scopes=scopes, expected_seq=expected_seq)


def revert_taxonomy_label(
    recorder: TaxonomyLabelRecorder, *, tenant: str, matter: str, actor: str, piece_id: str,
    to_seq: int, scopes: set[str],
) -> int:
    """Revert a *pièce*'s taxonomy label to the value it held at ``to_seq`` — reversible from the
    change log (FR-40/FR-20). A reversal is a NEW entry (append-only, AD-7). Returns the new
    ``seq``. Raises ``ValueError`` when ``to_seq`` is not an entry of the *pièce*, or
    ``OutOfTaxonomyLabel`` when the restored value is no longer in the *tenant*'s taxonomy."""
    return recorder.revert_label(
        tenant=tenant, matter=matter, actor=actor, piece_id=piece_id, to_seq=to_seq, scopes=scopes)
