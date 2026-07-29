"""Container expansion through the ingestion use case — members ingested, containers
transparent, nesting handled, and the guarantee still holds."""

from __future__ import annotations

import io
import zipfile
from email.message import EmailMessage
from pathlib import Path

from apx.adapters.expansion.archives import ZipExpander
from apx.adapters.expansion.composite import CompositeExpander
from apx.adapters.expansion.mail import EmlExpander
from apx.adapters.extraction.files import FileExtractor
from apx.core.app.ingest import ingest_folder


def _expander() -> CompositeExpander:
    return CompositeExpander([ZipExpander(), EmlExpander()])


def _ingest(folder: Path):
    return ingest_folder(folder, matter="m", tenant="t", extractor=FileExtractor(),
                         expander=_expander())


def test_zip_is_expanded_into_its_members(tmp_path: Path) -> None:
    d = tmp_path / "dossier"
    d.mkdir()
    with zipfile.ZipFile(d / "pieces.zip", "w") as zf:
        zf.writestr("contrat.txt", "Contrat de bail commercial.")
        zf.writestr("note.txt", "Note interne.")
    result = _ingest(d)
    provs = {p.provenance_path for p in result.pieces}
    assert provs == {"pieces.zip/contrat.txt", "pieces.zip/note.txt"}  # container transparent
    assert result.inventory.in_corpus == 2 and result.inventory.is_consistent()


def test_email_yields_its_body_and_its_attachment(tmp_path: Path) -> None:
    d = tmp_path / "dossier"
    d.mkdir()
    msg = EmailMessage()
    msg["Subject"] = "Sinistre du 3 mars"
    msg["From"] = "adverse@x.fr"
    msg["To"] = "me@cab.fr"
    msg.set_content("Veuillez trouver le rapport en pièce jointe.")
    msg.add_attachment(b"contenu du rapport", maintype="text", subtype="plain",
                       filename="rapport.txt")
    (d / "mail.eml").write_bytes(msg.as_bytes())
    result = _ingest(d)
    provs = {p.provenance_path for p in result.pieces}
    assert "mail.eml" in provs             # the body is a piece
    assert "mail.eml/rapport.txt" in provs  # so is the attachment
    assert result.inventory.in_corpus == 2


def test_a_transparent_container_is_neither_piece_nor_failure(tmp_path: Path) -> None:
    d = tmp_path / "dossier"
    d.mkdir()
    with zipfile.ZipFile(d / "box.zip", "w") as zf:
        zf.writestr("only.txt", "x")
    result = _ingest(d)
    assert result.inventory.in_corpus == 1 and result.inventory.open_register_entries == 0


def test_a_zip_within_a_zip_is_expanded(tmp_path: Path) -> None:
    d = tmp_path / "dossier"
    d.mkdir()
    inner = io.BytesIO()
    with zipfile.ZipFile(inner, "w") as zf:
        zf.writestr("deep.txt", "profond")
    with zipfile.ZipFile(d / "outer.zip", "w") as zf:
        zf.writestr("inner.zip", inner.getvalue())
    result = _ingest(d)
    assert "outer.zip/inner.zip/deep.txt" in {p.provenance_path for p in result.pieces}


def test_without_an_expander_a_zip_stays_an_unexpanded_failure(tmp_path: Path) -> None:
    d = tmp_path / "dossier"
    d.mkdir()
    with zipfile.ZipFile(d / "pieces.zip", "w") as zf:
        zf.writestr("a.txt", "x")
    result = ingest_folder(d, matter="m", tenant="t", extractor=FileExtractor())  # no expander
    assert result.inventory.in_corpus == 0 and result.inventory.open_register_entries == 1
