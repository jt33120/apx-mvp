"""Compose expanders: the first that recognises the container wins."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from apx.core.ports.expansion import Expander


class CompositeExpander:
    """Implements the Expander port by delegating to a chain of expanders."""

    def __init__(self, expanders: Iterable[Expander]) -> None:
        self._expanders = tuple(expanders)

    def members(self, path: Path) -> list[tuple[str, bytes]] | None:
        for expander in self._expanders:
            result = expander.members(path)
            if result is not None:
                return result
        return None

    def recognises(self, path: Path) -> bool:
        return any(expander.recognises(path) for expander in self._expanders)
