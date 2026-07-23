"""Deliberately violating fixture: a piece foreign key declared ON DELETE CASCADE, so
no_cascade_delete (AD-7) MUST report a violation. AST-parsed only; never imported."""


def ForeignKey(target: str, ondelete: str | None = None) -> object:
    return (target, ondelete)


piece_id = ForeignKey("piece.id", ondelete="CASCADE")
