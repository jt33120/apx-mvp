"""Spreadsheet (.xlsx) extraction via openpyxl (story 2.3, AD-28's named Office tool).

A .xlsx is read across every sheet, cached formula values (not formula text); an empty
workbook is `extracted-empty` (NOT in corpus), a corrupt file is `unreadable`. openpyxl is
imported lazily inside the adapter, so these tests skip cleanly where it is not installed.
"""

from __future__ import annotations

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


def test_xlsx_reads_cached_formula_values_not_formula_text(tmp_path: Path) -> None:
    # data_only=True: a saved workbook carries the last cached value; a formula string
    # like "=A1+A2" must never surface as searchable text.
    p = tmp_path / "calcul.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws["A1"] = 2
    ws["A2"] = 3
    ws["A3"] = 5           # a plausible cached value; we assert the formula text is absent
    wb.save(p)
    out = FileExtractor().extract(p)
    assert out.ok and "=" not in out.text          # no formula text leaks


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
