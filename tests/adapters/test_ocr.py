"""OCR fallback composition (stubbed — no Tesseract) and a real OCR pass when available."""

from __future__ import annotations

from pathlib import Path

import pytest

from apx.adapters.ocr_tesseract.tesseract import TesseractExtractor, WithOcr
from apx.core.domain.extraction import ExtractOutcome
from apx.core.domain.failures import ErrorClass


class _Stub:
    def __init__(self, outcome: ExtractOutcome) -> None:
        self._outcome = outcome
        self.called = False

    def extract(self, path: Path) -> ExtractOutcome:
        self.called = True
        return self._outcome


def _ok(text: str) -> ExtractOutcome:
    return ExtractOutcome(text, "x", "1")


def _fail(ec: ErrorClass) -> ExtractOutcome:
    return ExtractOutcome("", "x", "1", ec)


def test_born_digital_text_never_pays_the_ocr_cost() -> None:
    ocr = _Stub(_ok("OCR"))
    out = WithOcr(_Stub(_ok("digital")), ocr).extract(Path("doc.pdf"))
    assert out.text == "digital" and ocr.called is False


def test_a_scan_with_no_text_falls_back_to_ocr() -> None:
    out = WithOcr(_Stub(_fail(ErrorClass.EXTRACTED_EMPTY)), _Stub(_ok("texte océrisé"))).extract(
        Path("scan.pdf"))
    assert out.ok and out.text == "texte océrisé"


def test_an_unsupported_image_falls_back_to_ocr() -> None:
    out = WithOcr(_Stub(_fail(ErrorClass.UNSUPPORTED_FORMAT)), _Stub(_ok("mot"))).extract(
        Path("photo.png"))
    assert out.ok and out.text == "mot"


def test_when_ocr_also_fails_the_primary_failure_is_kept() -> None:
    out = WithOcr(_Stub(_fail(ErrorClass.EXTRACTED_EMPTY)), _Stub(_fail(ErrorClass.UNREADABLE))
                  ).extract(Path("scan.pdf"))
    assert not out.ok and out.error_class is ErrorClass.EXTRACTED_EMPTY


def test_other_failures_do_not_trigger_ocr() -> None:
    ocr = _Stub(_ok("OCR"))
    out = WithOcr(_Stub(_fail(ErrorClass.UNREADABLE)), ocr).extract(Path("x.txt"))
    assert not out.ok and ocr.called is False  # not a scan/image case


def test_ocr_builds_a_layout_and_reconstructs_text_in_one_pass(monkeypatch) -> None:
    # Story 3.5c-1: ONE image_to_data pass yields the word boxes AND the text (reconstructed from
    # the same words by line), so no doubled OCR cost — image_to_string is never called.
    import sys
    import types

    calls = {"data": 0, "string": 0}

    def _image_to_data(page, lang, output_type):  # noqa: ANN001, ANN202
        calls["data"] += 1
        return {
            "text": ["Contrat", "de", "bail", "", "Article"],
            "conf": [96, 91, 88, -1, 80],   # the -1 (structural marker) is skipped
            "left": [100, 190, 230, 0, 100], "top": [200, 200, 200, 0, 260],
            "width": [80, 20, 40, 0, 90], "height": [20, 20, 20, 0, 20],
            "block_num": [1, 1, 1, 0, 1], "par_num": [1, 1, 1, 0, 1], "line_num": [1, 1, 1, 0, 2],
        }

    def _image_to_string(page, lang):  # noqa: ANN001, ANN202 — must NOT be called
        calls["string"] += 1
        return "SHOULD NOT BE USED"

    fake = types.SimpleNamespace(
        image_to_data=_image_to_data, image_to_string=_image_to_string,
        Output=types.SimpleNamespace(DICT="dict"))
    monkeypatch.setitem(sys.modules, "pytesseract", fake)

    page = types.SimpleNamespace(width=1200, height=1600)
    out = TesseractExtractor()._ocr(lambda: [page], dpi=200)

    assert out.ok and out.method == "tesseract"
    assert out.text == "Contrat de bail\nArticle"   # words → lines by line_num, joined
    assert calls["string"] == 0 and calls["data"] == 1   # exactly ONE pass, via image_to_data
    assert out.layout is not None and out.layout.dpi == 200
    (p,) = out.layout.pages
    assert (p.width, p.height) == (1200, 1600)
    assert [w.text for w in p.words] == ["Contrat", "de", "bail", "Article"]   # blank/-1 skipped
    assert p.words[0].left == 100 and p.words[0].confidence == 96.0


def test_real_ocr_reads_rendered_text_when_tesseract_is_available(tmp_path: Path) -> None:
    pytesseract = pytest.importorskip("pytesseract")
    from PIL import Image, ImageDraw
    try:
        pytesseract.get_tesseract_version()
    except Exception:  # noqa: BLE001
        pytest.skip("tesseract binary not installed")
    img = Image.new("RGB", (360, 90), "white")
    ImageDraw.Draw(img).text((12, 30), "CONTRAT DE BAIL", fill="black")
    p = tmp_path / "scan.png"
    img.save(p)
    out = TesseractExtractor().extract(p)
    assert out.ok and "CONTRAT" in out.text.upper()
    # Story 3.5c-1: the REAL image_to_data path also produces a layout with boxed words (an image is
    # OCR'd at native resolution → dpi=0), so the boxes stored at ingestion are proven end-to-end.
    assert out.layout is not None and out.layout.dpi == 0
    (page,) = out.layout.pages
    assert page.width == 360 and page.height == 90
    assert page.words and all(w.width > 0 and w.height > 0 for w in page.words)   # real boxes
    assert "CONTRAT" in " ".join(w.text for w in page.words).upper()              # words carry text
