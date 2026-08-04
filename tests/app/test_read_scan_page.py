"""read_scan_page (Story 3.5c-4): the scope pre-filter runs FIRST (out-of-scope → None, no bytes
read); then three guards run BEFORE the (large) original is loaded or poppler is invoked — it must
be a scan (a stored OCR layer), the page in range and not a pixel bomb, and the file within the byte
bound; then a good page returns the PNG with its matter. Mirrors render_piece."""

from __future__ import annotations

from apx.core.app.read.scan import ScanPageOutcome, read_scan_page
from apx.core.domain.crypto import DecryptionError
from apx.core.domain.ocr_layout import OcrLayout, OcrPage
from apx.core.ports.read import PieceView

_LAYOUT = OcrLayout(pages=(OcrPage(1000, 1200, ()), OcrPage(1000, 1200, ())), dpi=200)
_LAYOUT_JSON = _LAYOUT.to_json().encode()                         # 2 pages, 1.2 Mpx each
_BOMB_JSON = OcrLayout(pages=(OcrPage(20000, 20000, ()),), dpi=200).to_json().encode()  # 400 Mpx
_MANY_PX = 500_000_000


class _Reader:
    def __init__(self, view: PieceView | None) -> None:
        self.view = view

    def read_piece(self, *, tenant: str, scopes: set[str], piece_id: str) -> PieceView | None:
        return self.view


class _Originals:
    def __init__(self, size: int | None, data: bytes = b"", exc: Exception | None = None,
                 layout: bytes | None = _LAYOUT_JSON) -> None:
        self._size, self._data, self._exc, self._layout = size, data, exc, layout
        self.opened = False   # tracks the ORIGINAL (the large blob), not the small layout

    def put(self, tenant, content_hash, data, kind="original"):  # noqa: ANN001, ANN201, D102
        ...

    def size(self, tenant: str, content_hash: str, kind: str = "original") -> int | None:
        return self._size

    def open(self, tenant: str, content_hash: str, kind: str = "original") -> bytes:
        if kind == "ocr-layout":
            if self._layout is None:
                raise FileNotFoundError
            return self._layout
        self.opened = True
        if self._exc is not None:
            raise self._exc
        return self._data


class _Rasterizer:
    def __init__(self, png: bytes | None) -> None:
        self.png = png
        self.calls: list[tuple[bytes, int]] = []

    def rasterize(self, *, data: bytes, page: int) -> bytes | None:
        self.calls.append((data, page))
        return self.png


_VIEW = PieceView("p", "m", "c" * 64, "scan.pdf", "pdf", ocr=True)


def _read(**kw):  # noqa: ANN003, ANN202 — a thin helper threading the common defaults
    base = dict(tenant="t", scopes={"w"}, piece_id="p", page=0, reader=_Reader(_VIEW),
                originals=_Originals(size=10, data=b"pdfbytes"), rasterizer=_Rasterizer(b"PNG"),
                max_bytes=100, max_pixels=_MANY_PX)
    base.update(kw)
    return read_scan_page(**base)


def test_out_of_scope_is_none_and_reads_no_bytes() -> None:
    originals = _Originals(size=10)
    out = _read(scopes=set(), reader=_Reader(None), originals=originals)
    assert out is None and originals.opened is False   # existence not disclosed, nothing read


def test_a_page_is_rasterised_with_its_matter() -> None:
    rasterizer = _Rasterizer(b"\x89PNG-1")
    out = _read(page=1, originals=_Originals(size=10, data=b"pdfbytes"), rasterizer=rasterizer)
    assert isinstance(out, ScanPageOutcome) and out.png == b"\x89PNG-1"
    assert out.matter == "m" and out.piece_id == "p" and out.reason is None
    assert rasterizer.calls == [(b"pdfbytes", 1)]      # the rasteriser saw the bytes + page


def test_a_piece_with_no_ocr_layer_is_not_a_scan_and_reads_no_bytes() -> None:
    originals = _Originals(size=10, layout=None)        # born-digital / non-OCR — no stored layout
    out = _read(originals=originals)
    assert out is not None and out.png is None and out.reason
    assert originals.opened is False                   # the original is never rasterised here


def test_an_out_of_range_page_offers_the_original_without_loading() -> None:
    originals = _Originals(size=10)
    out = _read(page=9, originals=originals)            # the layout has 2 pages
    assert out is not None and out.png is None and originals.opened is False


def test_a_negative_page_offers_the_original() -> None:
    originals = _Originals(size=10)
    out = _read(page=-1, originals=originals)
    assert out is not None and out.png is None and originals.opened is False


def test_a_pixel_bomb_page_offers_the_original_without_loading() -> None:
    originals = _Originals(size=10, layout=_BOMB_JSON)  # a 400 Mpx page
    out = _read(originals=originals, max_pixels=100_000_000)
    assert out is not None and out.png is None and out.reason
    assert originals.opened is False                   # poppler is never invoked (no spike)


def test_over_the_byte_bound_offers_the_original_without_loading() -> None:
    originals = _Originals(size=1000)
    out = _read(originals=originals, max_bytes=100)
    assert out is not None and out.png is None and originals.opened is False


def test_an_absent_blob_offers_the_original() -> None:
    originals = _Originals(size=None)
    out = _read(originals=originals)
    assert out is not None and out.png is None and originals.opened is False


def test_a_tampered_blob_offers_the_original_not_a_crash() -> None:
    out = _read(originals=_Originals(size=10, exc=DecryptionError("bad tag")))
    assert out is not None and out.png is None and out.reason


def test_a_non_rasterisable_page_offers_the_original() -> None:
    out = _read(originals=_Originals(size=10, data=b"x"), rasterizer=_Rasterizer(None))
    assert out is not None and out.png is None and out.reason   # rasteriser said None
