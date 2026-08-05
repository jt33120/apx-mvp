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
from apx.core.domain.line_projection import PricedMove


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

    def price_line_move(
        self, *, tenant: str, matter: str, scopes: set[str],
        candidate_last_retained_piece_id: str, version_no: int | None = None,
    ) -> PricedMove | None:
        """Price moving **the line** to a candidate position (FR-19): Δ *pièces*-to-read and the
        change in the projected discarded-set prevalence — a **projection from the ranking**, never
        a sampling bound (§0.2). Returns ``None`` when out of scope / absent / no ranking version
        (non-disclosing). Not audited (a preview)."""
        ...

    def move_line(
        self, *, tenant: str, matter: str, actor: str, scopes: set[str],
        last_retained_piece_id: str, expected_seq: int, priced_statement: str,
        version_no: int | None = None,
    ) -> LinePlacementView:
        """Commit a human move of **the line** to a chosen *pièce* (FR-19), atomically with one
        audit entry carrying old/new position and the **priced statement that was shown**. The move
        is serialised — a move against a superseded position raises a stale-line error and writes
        nothing. Never reorders the order. Raises a typed error for an out-of-scope *matter* or a
        *pièce* not in the ranked order."""
        ...
