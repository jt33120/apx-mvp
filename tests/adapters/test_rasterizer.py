"""The scanned-PDF page rasteriser (Story 3.5c-4): page n → PNG at the OCR dpi (so the image aligns
with the stored word boxes), one page at a time; an out-of-range page, a non-PDF, or absent poppler
→ None (offer the original), never a raise. Exercised with a fake pdf2image (poppler is not
installed everywhere), plus a real-poppler pass when the binary is available."""

from __future__ import annotations

import io
import shutil
import sys
import types

import pytest

from apx.adapters.render_image.rasterizer import Pdf2ImageRasterizer


class _FakeImage:
    def save(self, buffer: io.BytesIO, format: str) -> None:  # noqa: A002 — mirror PIL's kwarg name
        assert format == "PNG"
        buffer.write(b"\x89PNG-fake-page")


def _fake_pdf2image(monkeypatch: pytest.MonkeyPatch, page_count: int) -> None:
    def _convert(path, dpi, first_page, last_page, fmt, output_folder):  # noqa: ANN001, ANN202
        assert dpi == 200 and first_page == last_page and fmt == "png"   # one page, PNG, OCR dpi
        return [_FakeImage()] if 1 <= first_page <= page_count else []    # out of range → []
    monkeypatch.setitem(sys.modules, "pdf2image", types.SimpleNamespace(convert_from_path=_convert))


def test_dpi_matches_the_ocr_dpi() -> None:
    # the page image and the stored OCR boxes must share ONE pixel space — the rasterise dpi MUST
    # equal the dpi the scan was OCR'd at (Story 3.5c-1), or the overlay drifts off the words.
    from apx.adapters.ocr_tesseract.tesseract import _DPI as ocr_dpi
    from apx.adapters.render_image.rasterizer import _DPI as raster_dpi
    assert raster_dpi == ocr_dpi


def test_rasterises_a_page_to_png(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_pdf2image(monkeypatch, page_count=3)
    png = Pdf2ImageRasterizer().rasterize(data=b"%PDF fake scan", page=0)
    assert png == b"\x89PNG-fake-page"


def test_an_out_of_range_page_is_none(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_pdf2image(monkeypatch, page_count=3)
    assert Pdf2ImageRasterizer().rasterize(data=b"%PDF fake scan", page=9) is None


def test_a_negative_page_is_none() -> None:
    assert Pdf2ImageRasterizer().rasterize(data=b"%PDF", page=-1) is None


def test_a_rasterise_failure_is_none_never_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202 — poppler missing / not a PDF
        raise RuntimeError("Unable to get page count. Is poppler installed?")
    monkeypatch.setitem(sys.modules, "pdf2image",
                        types.SimpleNamespace(convert_from_path=_boom))
    assert Pdf2ImageRasterizer().rasterize(data=b"not a pdf", page=0) is None   # offer the original


def test_real_poppler_rasterises_a_page(tmp_path) -> None:
    if shutil.which("pdftoppm") is None:
        pytest.skip("poppler (pdftoppm) not installed")
    from PIL import Image
    buffer = io.BytesIO()
    Image.new("RGB", (200, 300), "white").save(buffer, format="PDF")   # a real 1-page PDF via PIL
    pdf_bytes = buffer.getvalue()
    png = Pdf2ImageRasterizer().rasterize(data=pdf_bytes, page=0)
    assert png is not None and png[:4] == b"\x89PNG"                    # a real PNG, page 0
    assert Pdf2ImageRasterizer().rasterize(data=pdf_bytes, page=5) is None   # out of range → None
    assert Pdf2ImageRasterizer().rasterize(data=b"not a pdf at all", page=0) is None  # non-PDF
