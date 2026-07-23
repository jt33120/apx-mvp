"""Deliberately violating fixture: a Chunk model whose DB column is literally named 'scope'
via a positional mapped_column arg, behind an innocent attribute 'wall'. So
chunk_columns_enumerated (AD-9) MUST fire — proving the check reads the real DB column name,
not just the Python attribute (the exact stale-wall bypass). AST-parsed only; never imported."""

from typing import Any

Mapped = Any


def mapped_column(*args: object, **kwargs: object) -> Any:
    return None


class Chunk:
    chunk_id: Mapped[str] = mapped_column(primary_key=True)
    wall: Mapped[str] = mapped_column("scope")  # DB column literally 'scope' — forbidden
