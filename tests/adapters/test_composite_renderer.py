"""The composite pièce renderer (Story 3.5c-3): dispatch to the first renderer that returns a
document; a format none handle → None (the edge offers the original)."""

from __future__ import annotations

from apx.adapters.render_html.composite import CompositePieceRenderer
from apx.core.ports.render import RenderedDocument


class _Fake:
    def __init__(self, handles: tuple[str, ...], tag: str) -> None:
        self._handles, self._tag = handles, tag

    def render(self, *, filename: str, data: bytes) -> RenderedDocument | None:
        if filename.endswith(self._handles):
            return RenderedDocument("html", filename, f"<p>{self._tag}</p>", truncated=False)
        return None


def test_dispatches_each_format_to_its_renderer() -> None:
    composite = CompositePieceRenderer(
        [_Fake((".docx", ".xlsx"), "office"), _Fake((".msg",), "msg")])
    assert composite.render(filename="a.docx", data=b"").html == "<p>office</p>"
    assert composite.render(filename="b.msg", data=b"").html == "<p>msg</p>"


def test_a_format_no_renderer_handles_is_none() -> None:
    composite = CompositePieceRenderer([_Fake((".docx",), "office"), _Fake((".msg",), "msg")])
    assert composite.render(filename="scan.pdf", data=b"") is None   # offer the original


def test_the_first_renderer_that_handles_it_wins() -> None:
    composite = CompositePieceRenderer([_Fake((".x",), "first"), _Fake((".x",), "second")])
    assert composite.render(filename="a.x", data=b"").html == "<p>first</p>"
