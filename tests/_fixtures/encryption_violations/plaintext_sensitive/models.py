"""Deliberately violating fixture (story 1.7, AD-31): a Piece whose provenance_path is a
plaintext Text column, not EncryptedText — so sensitive_columns_are_encrypted MUST fire.
AST-parsed only; never imported."""

from typing import Any

Mapped = Any
Text = Any


def mapped_column(*args: object, **kwargs: object) -> Any:
    return None


class Piece:
    provenance_path: Mapped[str] = mapped_column(Text, nullable=False)  # plaintext — forbidden
