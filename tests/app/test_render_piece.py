"""render_piece (Story 3.5c-2): the scope pre-filter runs FIRST (out-of-scope → ``None``, no bytes
read), the render byte bound is applied before the bytes are loaded (over → offer the original), a
missing/tampered blob offers the original (fail-closed, never a crash), an unhandled format offers
the original, and a good render returns the document with its matter for the edge to audit."""

from __future__ import annotations

from apx.core.app.read.render import RenderOutcome, render_piece
from apx.core.domain.crypto import DecryptionError
from apx.core.ports.read import PieceView
from apx.core.ports.render import RenderedDocument


class _Reader:
    def __init__(self, view: PieceView | None) -> None:
        self.view = view

    def read_piece(self, *, tenant: str, scopes: set[str], piece_id: str) -> PieceView | None:
        return self.view


class _Originals:
    def __init__(self, size: int | None, data: bytes = b"", exc: Exception | None = None) -> None:
        self._size, self._data, self._exc = size, data, exc
        self.opened = False

    def put(self, tenant, content_hash, data, kind="original"):  # noqa: ANN001, ANN201, D102
        ...

    def size(self, tenant: str, content_hash: str, kind: str = "original") -> int | None:
        return self._size

    def open(self, tenant: str, content_hash: str, kind: str = "original") -> bytes:
        self.opened = True
        if self._exc is not None:
            raise self._exc
        return self._data


class _Renderer:
    def __init__(self, doc: RenderedDocument | None) -> None:
        self.doc = doc
        self.calls: list[tuple[str, bytes]] = []

    def render(self, *, filename: str, data: bytes) -> RenderedDocument | None:
        self.calls.append((filename, data))
        return self.doc


_VIEW = PieceView("p", "m", "c" * 64, "annexe.xlsx", "spreadsheet", ocr=False)
_DOC = RenderedDocument("html", "annexe.xlsx", "<table></table>", truncated=False)


def test_out_of_scope_is_none_and_reads_no_bytes() -> None:
    originals = _Originals(size=10)
    out = render_piece(tenant="t", scopes=set(), piece_id="p", reader=_Reader(None),
                       originals=originals, renderer=_Renderer(_DOC), max_bytes=100)
    assert out is None and originals.opened is False   # existence not disclosed, nothing read


def test_a_good_render_returns_the_document_with_its_matter() -> None:
    renderer = _Renderer(_DOC)
    out = render_piece(tenant="t", scopes={"w"}, piece_id="p", reader=_Reader(_VIEW),
                       originals=_Originals(size=10, data=b"xlsxbytes"), renderer=renderer,
                       max_bytes=100)
    assert isinstance(out, RenderOutcome) and out.document is _DOC
    assert out.matter == "m" and out.piece_id == "p" and out.reason is None
    assert renderer.calls == [("annexe.xlsx", b"xlsxbytes")]   # renderer got the filename + bytes


def test_over_the_bound_offers_the_original_without_loading_it() -> None:
    originals = _Originals(size=1000)
    out = render_piece(tenant="t", scopes={"w"}, piece_id="p", reader=_Reader(_VIEW),
                       originals=originals, renderer=_Renderer(_DOC), max_bytes=100)
    assert out is not None and out.document is None and out.reason  # offer the original
    assert originals.opened is False                               # never loaded (the 3.5d rule)


def test_an_absent_blob_offers_the_original() -> None:
    out = render_piece(tenant="t", scopes={"w"}, piece_id="p", reader=_Reader(_VIEW),
                       originals=_Originals(size=None), renderer=_Renderer(_DOC), max_bytes=100)
    assert out is not None and out.document is None and out.reason


def test_a_tampered_blob_offers_the_original_not_a_crash() -> None:
    out = render_piece(tenant="t", scopes={"w"}, piece_id="p", reader=_Reader(_VIEW),
                       originals=_Originals(size=10, exc=DecryptionError("bad tag")),
                       renderer=_Renderer(_DOC), max_bytes=100)
    assert out is not None and out.document is None and out.reason


def test_an_unrenderable_format_offers_the_original() -> None:
    out = render_piece(tenant="t", scopes={"w"}, piece_id="p", reader=_Reader(_VIEW),
                       originals=_Originals(size=10, data=b"x"), renderer=_Renderer(None),
                       max_bytes=100)
    assert out is not None and out.document is None and out.reason  # renderer said None


class _BoomRenderer:
    def render(self, *, filename: str, data: bytes) -> RenderedDocument | None:
        raise RuntimeError("renderer contract violation")


def test_a_renderer_that_raises_offers_the_original_not_a_500() -> None:
    # the port promises None on failure; render_piece enforces it at the boundary, so a renderer
    # that raises still fails CLOSED to offer-the-original (never a 500, never unsanitised content).
    out = render_piece(tenant="t", scopes={"w"}, piece_id="p", reader=_Reader(_VIEW),
                       originals=_Originals(size=10, data=b"x"), renderer=_BoomRenderer(),
                       max_bytes=100)
    assert out is not None and out.document is None and out.reason
