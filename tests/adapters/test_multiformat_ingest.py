"""End-to-end multi-format ingestion (story 2.3): a folder mixing .msg (with an attachment),
.xlsx, .docx, an image and an unsupported extension lands the right counts — pieces in corpus,
unsupported/empty in the register (counted in the denominator, never vanished), custodian
inherited, and the inventory guarantee (submitted = corpus + failures + exclusions) holds.

The .msg worker is mocked (a valid Outlook compound file cannot be synthesised from the stdlib);
every other format is real.
"""

from __future__ import annotations

import base64
import zipfile
from pathlib import Path

import pytest

from apx.adapters.expansion.composite import CompositeExpander
from apx.adapters.extraction import msg as msgmod
from apx.adapters.extraction.composite import CompositeExtractor
from apx.adapters.extraction.files import FileExtractor
from apx.adapters.extraction.msg import MsgExpander, MsgExtractor
from apx.core.app.ingest import ingest_folder
from apx.core.domain.failures import ErrorClass

openpyxl = pytest.importorskip("openpyxl")
_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _docx(path: Path, text: str) -> None:
    xml = (f'<?xml version="1.0"?><w:document xmlns:w="{_W}"><w:body>'
           f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body></w:document>")
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", xml)


def _xlsx(path: Path, value: str) -> None:
    wb = openpyxl.Workbook()
    wb.active["A1"] = value
    wb.save(path)


def test_mixed_folder_lands_the_right_counts(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def fake_worker(path: Path, mode: str) -> dict:
        if mode == "attachments":
            return {"ok": True, "attachments": [
                {"name": "note.txt", "b64": base64.b64encode(b"note jointe").decode("ascii")}]}
        return {"ok": True, "text": "From: a@x.fr\nSubject: dossier\n\ncorps",
                "method": "extract-msg", "version": "extract-msg/0.56.0"}

    monkeypatch.setattr(msgmod, "_run_msg_worker", fake_worker)

    (tmp_path / "courriel.msg").write_bytes(b"placeholder; the worker is mocked")
    _xlsx(tmp_path / "facture.xlsx", "Facture n° 2021-045")
    _docx(tmp_path / "acte.docx", "Acte introductif d'instance.")
    (tmp_path / "photo.png").write_bytes(b"\x89PNG\r\n")          # no OCR here → unsupported
    (tmp_path / "inconnu.xyz").write_bytes(b"???")               # unknown format → unsupported

    extractor = CompositeExtractor([MsgExtractor(), FileExtractor()])
    expander = CompositeExpander([MsgExpander()])
    result = ingest_folder(tmp_path, matter="dossier", tenant="t", extractor=extractor,
                           custodian="M. Dupont", expander=expander)

    # pieces: .msg body + note.txt member + .xlsx + .docx = 4
    assert result.inventory.in_corpus == 4
    # failures: photo.png + inconnu.xyz, both unsupported-format, both counted in the denominator
    assert result.inventory.open_register_entries == 2
    classes = {f.error_class for f in result.failures}
    assert classes == {ErrorClass.UNSUPPORTED_FORMAT}
    assert all(pc.custodian == "M. Dupont" for pc in result.pieces)      # inherited everywhere
    assert "courriel.msg/note.txt" in {pc.provenance_path for pc in result.pieces}  # member prov
    assert result.inventory.is_consistent()   # submitted_pieces == in_corpus + open_register
