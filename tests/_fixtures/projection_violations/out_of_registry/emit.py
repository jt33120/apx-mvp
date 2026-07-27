"""A module that fabricates a Projection OUTSIDE the registry — the AD-26 violation the sealed-type
check must catch (an emission path a projector was not written through). AST-scanned, never run."""

from __future__ import annotations

from apx.core.projection import Projection


def rogue() -> Projection:
    return Projection("rogue", (), {"leaked": "content that skipped the registry"})
