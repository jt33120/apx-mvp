"""The triage-table read port (Story 4.10, AD-14/AD-13).

The surface reads the whole table through **one** scoped entry point, exactly as the pièce viewer
does (``PieceReader``). No method takes an identifier without a *tenant* and a ``scopes`` argument,
and ``scopes`` is carried into the query as a **pre-filter** — never a post-filter over rows already
fetched (AD-13). Out of scope and absent return the same ``None``, so a caller cannot tell one from
the other (FR-14).
"""

from __future__ import annotations

from typing import Protocol

from apx.core.domain.triage_table import ChangeLogEntry, TriageTable


class TriageTableReader(Protocol):
    def read_triage_table(
        self, *, tenant: str, matter: str, scopes: set[str], version_no: int | None = None
    ) -> TriageTable | None:
        """The whole triage surface for ONE ranking version — the latest when ``version_no`` is
        None. Every part (order, line, pins, labels, counts) is read against that one version, so
        the parts cannot drift apart under a concurrent re-rank (AD-23). ``None`` when out of
        scope, absent, or with no ranking yet — the three are indistinguishable (FR-14)."""
        ...

    def read_label_change_log_paired(
        self, *, tenant: str, matter: str, piece_id: str, scopes: set[str]
    ) -> tuple[ChangeLogEntry, ...] | None:
        """One *pièce*'s change log as ``previous → new`` entries, ascending by ``seq``
        (FR-20/FR-40). ``None`` when out of scope or absent; ``()`` when nobody has labelled it."""
        ...

    def read_matter_change_log(
        self, *, tenant: str, matter: str, scopes: set[str], limit: int = 200
    ) -> tuple[ChangeLogEntry, ...] | None:
        """The *matter*'s whole change log, **newest first**, bounded by ``limit`` — the
        matter-level panel. ``None`` when out of scope or absent."""
        ...
