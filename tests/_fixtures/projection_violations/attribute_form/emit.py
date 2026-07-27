"""Attribute-form Projection construction outside the registry (``projection.Projection(...)``) —
a normal qualified-import coding style that a bare-name check misses; it must be caught (AD-26).
AST-scanned, never run."""

from __future__ import annotations

from apx.core import projection


def rogue() -> projection.Projection:
    return projection.Projection("rogue", (), {"leaked": "content that skipped the registry"})
