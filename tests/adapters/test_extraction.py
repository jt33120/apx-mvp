"""Real-format extraction: Word (.docx) and email (.eml), standard-library only."""

from __future__ import annotations

import zipfile
from pathlib import Path

from apx.adapters.extraction.files import FileExtractor
from apx.core.app.ingest import ingest_folder
from apx.core.domain.failures import ErrorClass

_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _docx(path: Path, paragraphs: list[str]) -> None:
    body = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragraphs)
    xml = f'<?xml version="1.0"?><w:document xmlns:w="{_W}"><w:body>{body}</w:body></w:document>'
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", xml)


def _eml(path: Path, subject: str, body: str, subtype: str = "plain") -> None:
    raw = (
        f"From: avocat@cabinet.fr\r\nTo: client@x.fr\r\nSubject: {subject}\r\n"
        f"Content-Type: text/{subtype}; charset=utf-8\r\n\r\n{body}"
    )
    path.write_bytes(raw.encode("utf-8"))


def test_docx_extracts_paragraph_text(tmp_path: Path) -> None:
    p = tmp_path / "conclusions.docx"
    _docx(p, ["Conclusions en défense.", "Sur le fond du litige."])
    out = FileExtractor().extract(p)
    assert out.ok and out.method == "docx"
    assert "Conclusions en défense." in out.text and "Sur le fond du litige." in out.text


def test_empty_docx_is_extracted_empty(tmp_path: Path) -> None:
    p = tmp_path / "vide.docx"
    _docx(p, [""])
    out = FileExtractor().extract(p)
    assert not out.ok and out.error_class is ErrorClass.EXTRACTED_EMPTY


def test_corrupt_docx_is_unreadable(tmp_path: Path) -> None:
    p = tmp_path / "casse.docx"
    p.write_bytes(b"not a zip at all")
    out = FileExtractor().extract(p)
    assert not out.ok and out.error_class is ErrorClass.UNREADABLE


def test_eml_plain_includes_routing_headers_and_body(tmp_path: Path) -> None:
    p = tmp_path / "mail.eml"
    _eml(p, "Sinistre du 3 mars", "Bonjour Maître, veuillez trouver le rapport.")
    out = FileExtractor().extract(p)
    assert out.ok and out.method == "eml"
    assert "Sinistre du 3 mars" in out.text        # subject
    assert "avocat@cabinet.fr" in out.text          # from
    assert "veuillez trouver le rapport" in out.text  # body


def test_eml_html_body_is_stripped(tmp_path: Path) -> None:
    p = tmp_path / "mail.eml"
    _eml(p, "Convocation",
         "<html><body><p>Audience le <b>12 mai</b>.</p><script>evil()</script></body></html>",
         subtype="html")
    out = FileExtractor().extract(p)
    assert out.ok and "Audience le 12 mai." in out.text
    assert "<" not in out.text and "evil()" not in out.text  # tags and script gone


def test_unsupported_format_stays_unsupported(tmp_path: Path) -> None:
    p = tmp_path / "image.png"
    p.write_bytes(b"\x89PNG\r\n")
    assert FileExtractor().extract(p).error_class is ErrorClass.UNSUPPORTED_FORMAT


def test_ingest_folder_picks_up_docx_and_eml(tmp_path: Path) -> None:
    _docx(tmp_path / "acte.docx", ["Acte introductif d'instance."])
    _eml(tmp_path / "courriel.eml", "RDV", "Confirmons le rendez-vous de lundi.")
    result = ingest_folder(tmp_path, matter="m", tenant="t", extractor=FileExtractor())
    assert result.inventory.in_corpus == 2 and result.inventory.is_consistent()  # both entered
