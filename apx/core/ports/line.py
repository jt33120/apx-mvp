"""The line-placement recorder port (Story 4.8, FR-17 / AD-37 / AD-4).

The one boundary the line-placement act persists across: the store adapter implements it (the
append-only, version-bound placement ledger), and the ``core/app`` seam depends only on this
Protocol (AD-4 — the core imports no adapter). The store recommends the cut recall-first, composes
the basis inherited from the *ranking version*, mints the per-version monotonic ``seq`` inside its
transaction (AD-37/AD-49), and appends the placement atomically with one audit entry (AD-22) — so
the caller supplies only the *matter* and (optionally) the version.
"""

from __future__ import annotations

from typing import Protocol

from apx.core.domain.line import LinePlacementView


class LinePlacementRecorder(Protocol):
    def place_line(
        self, *, tenant: str, matter: str, actor: str, scopes: set[str],
        version_no: int | None = None,
    ) -> LinePlacementView | None:
        """Draw and commit **the line** over a *ranking version* (FR-17), atomically with one audit
        entry (AD-22). The system chooses the cut recall-first and stores it by the identity of the
        **last retained *pièce*** — never a bare integer — with its basis, author and timestamp,
        appended as a NEW row (append-only, AD-7) with a per-version monotonic ``seq`` (AD-49).
        Touches only the placement ledger, so it never reorders the underlying order (FR-17).
        Returns the placement view, or ``None`` when the tool commits to no line (no *pièce* in a
        retain-band — never fabricated, AD-19) or the *matter* has no such ranking version. Raises a
        scope error for an out-of-scope *matter* (non-disclosing)."""
        ...

    def read_current_line(
        self, *, tenant: str, matter: str, scopes: set[str], version_no: int | None = None,
    ) -> LinePlacementView | None:
        """The CURRENT line over a *ranking version* — a VIEW (the max-``seq`` placement), naming
        its version (AD-23). Returns ``None`` when out of scope, absent, with no such ranking
        version, or with no line placed yet (non-disclosing). Not audited (a read)."""
        ...
