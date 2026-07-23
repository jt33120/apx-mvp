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
