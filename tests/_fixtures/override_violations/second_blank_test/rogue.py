"""A second definition of what a blank reason is — the drift FR-25 cannot survive."""


class MissingReason(ValueError):
    pass


def guard(reason: str) -> None:
    if not reason.strip():
        raise MissingReason("a reason is required")
