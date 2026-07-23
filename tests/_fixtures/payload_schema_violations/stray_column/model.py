"""Deliberately violating fixture: a Chunk model with a non-enumerated 'foo' column — not a
scope/custodian, just outside the AD-9 set. chunk_columns_enumerated MUST fire, because
"any other column fails the build". AST-parsed only; never imported."""

from typing import Any

Mapped = Any


def mapped_column(*args: object, **kwargs: object) -> Any:
    return None


class Chunk:
    chunk_id: Mapped[str] = mapped_column(primary_key=True)
    foo: Mapped[str] = mapped_column()  # a column outside the AD-9 enumeration
