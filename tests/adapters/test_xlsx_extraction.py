"""Spreadsheet (.xlsx) extraction via openpyxl (story 2.3, AD-28's named Office tool).

A .xlsx is read across every sheet, cached formula values (not formula text); an empty
workbook is `extracted-empty` (NOT in corpus), a corrupt file is `unreadable`. openpyxl is
imported lazily inside the adapter, so these tests skip cleanly where it is not installed.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from apx.adapters.extraction.files import FileExtractor
from apx.core.domain.failures import ErrorClass

openpyxl = pytest.importorskip("openpyxl")


def _xlsx(path: Path, rows: list[list[object]], *, sheets: int = 1) -> None:
    wb = openpyxl.Workbook()
    for s in range(sheets):
        ws = wb.active if s == 0 else wb.create_sheet()
        for row in rows:
            ws.append(row)
    wb.save(path)


def test_xlsx_extracts_cell_values_across_sheets(tmp_path: Path) -> None:
    p = tmp_path / "facturation.xlsx"
    _xlsx(p, [["Facture n° 2021-045", "Honoraires"], ["Montant", 1500]], sheets=2)
    out = FileExtractor().extract(p)
    assert out.ok and out.method == "xlsx" and out.version
    assert "Facture n° 2021-045" in out.text and "Honoraires" in out.text
    assert "1500" in out.text                      # a numeric cell is rendered as text


def test_xlsx_reads_values_not_formula_text_when_values_are_present(tmp_path: Path) -> None:
    # A workbook with cached literals AND a formula cell: data_only=True surfaces the literals
    # (2, 3) and NOT the formula text. A REAL formula makes this live — flipping the adapter to
    # data_only=False would surface "=A1+A2" and fail this assertion (the vacuous prior version
    # wrote a literal 5, so it could never distinguish the two modes).
    p = tmp_path / "calcul.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws["A1"], ws["A2"], ws["A3"] = 2, 3, "=A1+A2"
    wb.save(p)
    out = FileExtractor().extract(p)
    assert out.ok and "2" in out.text and "3" in out.text
    assert "=" not in out.text and "A1+A2" not in out.text          # no formula text leaks


def test_xlsx_with_only_uncached_formulas_is_searchable_not_falsely_empty(tmp_path: Path) -> None:
    # openpyxl writes a formula with NO cached value, so data_only reads empty. Rather than a
    # false 'not in corpus' (which an absence claim would treat as searched), the extractor falls
    # back to the formula/label text so the sheet enters the corpus — recall over precision.
    p = tmp_path / "formules.xlsx"
    wb = openpyxl.Workbook()
    wb.active["A1"] = "=SUM(B1:B9)"
    wb.save(p)
    out = FileExtractor().extract(p)
    assert out.ok and "SUM" in out.text            # in corpus via the fallback, not extracted-empty


def test_xlsx_with_malformed_sheet_xml_is_unreadable(tmp_path: Path) -> None:
    # A VALID zip whose sheet XML is corrupt raises deep in openpyxl (ET.ParseError). It must map
    # to `unreadable`, never escape as an exception that would land a parser message in the
    # register via ingest's str(exc) path (AD-28). The sibling _docx already catches this.
    good = tmp_path / "good.xlsx"
    _xlsx(good, [["cellule"]])
    bad = tmp_path / "bad.xlsx"
    with zipfile.ZipFile(good) as zin, zipfile.ZipFile(bad, "w") as zout:
        for item in zin.namelist():
            data = b"<worksheet><broken" if item.endswith("sheet1.xml") else zin.read(item)
            zout.writestr(item, data)
    out = FileExtractor().extract(bad)
    assert not out.ok and out.error_class is ErrorClass.UNREADABLE


def test_empty_xlsx_is_extracted_empty(tmp_path: Path) -> None:
    p = tmp_path / "vide.xlsx"
    _xlsx(p, [])                                    # a workbook with a single blank sheet
    out = FileExtractor().extract(p)
    assert not out.ok and out.error_class is ErrorClass.EXTRACTED_EMPTY


def test_corrupt_xlsx_is_unreadable(tmp_path: Path) -> None:
    p = tmp_path / "casse.xlsx"
    p.write_bytes(b"not a zip at all")
    out = FileExtractor().extract(p)
    assert not out.ok and out.error_class is ErrorClass.UNREADABLE
