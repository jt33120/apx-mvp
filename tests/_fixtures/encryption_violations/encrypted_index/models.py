"""Deliberately violating fixture (story 1.7, AD-31): a Piece whose full_text is
EncryptedText — but full_text is the named exception (the deterministic text index; you
cannot ILIKE ciphertext), so encrypting it would break exhaustive search (FR-13) and
sensitive_columns_are_encrypted MUST fire. AST-parsed only; never imported."""

from typing import Any

Mapped = Any
EncryptedText = Any


def mapped_column(*args: object, **kwargs: object) -> Any:
    return None


class Piece:
    full_text: Mapped[str] = mapped_column(EncryptedText, nullable=False)  # the index — forbidden
