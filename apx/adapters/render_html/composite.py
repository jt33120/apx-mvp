"""Compose pièce renderers: the first that renders the format wins (mirrors extraction/composite).

The edge composes the office renderer (``.docx``/``.xlsx``, in-process) ahead of the ``.msg`` one
(out-of-process, GPL-isolated); each returns ``None`` for a format it does not handle, so the chain
routes each format to its renderer and a format no renderer handles stays ``None`` (the edge then
offers the original — FR-44). Every member returns SANITISED HTML (they all route through the one
``_rendered`` site), so the composite carries the sanitisation guarantee unchanged.
"""

from __future__ import annotations

from collections.abc import Iterable

from apx.core.ports.render import PieceRenderer, RenderedDocument


class CompositePieceRenderer:
    """Implements the ``PieceRenderer`` port by delegating to a chain; the first renderer that
    returns a document (not ``None``) wins."""

    def __init__(self, renderers: Iterable[PieceRenderer]) -> None:
        self._renderers = tuple(renderers)

    def render(self, *, filename: str, data: bytes) -> RenderedDocument | None:
        for renderer in self._renderers:
            document = renderer.render(filename=filename, data=data)
            if document is not None:
                return document
        return None  # no renderer handled it — the edge offers the original (FR-44)
