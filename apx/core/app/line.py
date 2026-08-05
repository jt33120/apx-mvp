"""The line-placement act (Story 4.8, FR-17) — the tool draws the line and commits.

A thin Application-layer seam over the :class:`LinePlacementRecorder` port: a caller (the API, or
the later Story-4.9 priced move) depends on this **core** function, never on the store adapter
(AD-4). The recorder (the store) owns the guarantee — it chooses the cut recall-first, stores it by
the identity of the last retained *pièce* (never a bare integer, FR-17), and appends the placement
atomically with one audit entry (AD-22/AD-37/AD-49). Placing the line never reorders the underlying
ranked order (FR-17). It imports Ports only (AD-4), touches no store.
"""

from __future__ import annotations

from apx.core.domain.line import LinePlacementView
from apx.core.ports.line import LinePlacementRecorder


def place_line(
    recorder: LinePlacementRecorder, *, tenant: str, matter: str, actor: str, scopes: set[str],
    version_no: int | None = None,
) -> LinePlacementView | None:
    """Draw and commit **the line** through the recorder port (FR-17). Returns the placement view,
    or ``None`` when the tool commits to no line (no *pièce* in a retain-band — never fabricated) or
    the *matter* has no such ranking version. The recorder owns the recall-first choice, the
    identity-not-integer storage, the monotonic seq, the conditional commit and the atomic audit;
    this seam keeps the caller off the adapter (AD-4)."""
    return recorder.place_line(
        tenant=tenant, matter=matter, actor=actor, scopes=scopes, version_no=version_no)


def read_current_line(
    recorder: LinePlacementRecorder, *, tenant: str, matter: str, scopes: set[str],
    version_no: int | None = None,
) -> LinePlacementView | None:
    """The CURRENT line over a *ranking version* through the recorder port — a VIEW naming its
    version (AD-23). Returns ``None`` when out of scope, absent, or with no line placed yet
    (non-disclosing)."""
    return recorder.read_current_line(
        tenant=tenant, matter=matter, scopes=scopes, version_no=version_no)
