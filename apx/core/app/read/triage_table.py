"""Read the triage surface (Story 4.10) — through the ONE read entry point (AD-14).

Three thin seams over :class:`TriageTableReader`: the table itself, one *pièce*'s change log, and
the *matter*-level change log. Each is a pure read — nothing here writes, and nothing here decides:
the côté a row carries is *derived* by the reader from the order, the line and the pins (AD-39), and
this layer never re-derives or overrides it.

Fail-closed like every other read: an empty scope set reads nothing (AD-12), and out-of-scope is
indistinguishable from absent (FR-14). The API depends on this module, never on the store adapter
(AD-4).
"""

from __future__ import annotations

from apx.core.domain.triage_table import ChangeLogEntry, TriageTable
from apx.core.ports.triage_table import TriageTableReader


def read_triage_table(
    *, tenant: str, matter: str, scopes: set[str], reader: TriageTableReader,
    version_no: int | None = None,
) -> TriageTable | None:
    """The whole table for one *ranking version* (the latest when ``version_no`` is None), or
    ``None`` when out of scope / absent / not yet ranked — the surface renders that as its own
    honest state, never as an empty table pretending to be a result."""
    if not scopes:
        return None  # fail closed — no scope reads nothing (AD-12)
    return reader.read_triage_table(
        tenant=tenant, matter=matter, scopes=scopes, version_no=version_no)


def read_piece_change_log(
    *, tenant: str, matter: str, piece_id: str, scopes: set[str], reader: TriageTableReader,
) -> tuple[ChangeLogEntry, ...] | None:
    """One row's change log, ascending by ``seq`` — ``previous → new``, author, timestamp (FR-20).
    ``()`` means nobody has labelled the *pièce* yet; ``None`` means out of scope or absent."""
    if not scopes:
        return None
    return reader.read_label_change_log_paired(
        tenant=tenant, matter=matter, piece_id=piece_id, scopes=scopes)


def read_matter_change_log(
    *, tenant: str, matter: str, scopes: set[str], reader: TriageTableReader, limit: int = 200,
) -> tuple[ChangeLogEntry, ...] | None:
    """The *matter*-level change log, newest first, bounded — the panel beside the table. The bound
    is stated by the caller and applied in the query; it is a panel page size, never a truncation of
    an evidential claim (AD-20 governs exhaustive RESULT SETS, which this is not)."""
    if not scopes:
        return None
    return reader.read_matter_change_log(
        tenant=tenant, matter=matter, scopes=scopes, limit=limit)
