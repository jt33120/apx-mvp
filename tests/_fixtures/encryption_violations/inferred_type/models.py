"""Deliberately violating fixture (story 1.7, AD-31): a sensitive column declared with an
INFERRED type — `mapped_column()` with no positional type, so SQLAlchemy infers a plaintext
`String` from `Mapped[str]`. The allowlist check must STILL fire; an inferred-type column
cannot smuggle content past the guard by omitting the type. AST-parsed only; never imported."""

from typing import Any

Mapped = Any


def mapped_column(*args: object, **kwargs: object) -> Any:
    return None


class Piece:
    provenance_path: Mapped[str] = mapped_column(nullable=False)  # inferred String — forbidden
