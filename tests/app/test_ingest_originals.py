"""Original retention through the ingestion use case (story 3.5a): every pièce's original bytes
are retained at rest via the OriginalStore port — including a container MEMBER's, whose bytes exist
only transiently during ingestion (the reason retention lives here, not in the worker). A retention
failure is a register entry, never an escape; without a store, nothing is retained (unchanged)."""

from __future__ import annotations

import os
from email.message import EmailMessage
from pathlib import Path

from apx.adapters.expansion.composite import CompositeExpander
from apx.adapters.expansion.mail import EmlExpander
from apx.adapters.extraction.files import FileExtractor
from apx.adapters.originals_fs import FilesystemOriginalStore
from apx.core.app.ingest import ingest_folder
from apx.core.domain.crypto import Cipher
from apx.core.domain.failures import ErrorClass


def _store(root: Path) -> FilesystemOriginalStore:
    return FilesystemOriginalStore(root, Cipher(os.urandom(32)))


def test_a_pieces_original_is_retained_at_rest(tmp_path: Path) -> None:
    src, blobs = tmp_path / "in", tmp_path / "blobs"
    src.mkdir()
    (src / "contrat.txt").write_bytes(b"Contrat de bail commercial. Article 4 : depot de garantie.")
    store = _store(blobs)
    result = ingest_folder(src, matter="m", tenant="t", extractor=FileExtractor(),
                           original_store=store)
    (piece,) = result.pieces
    # the original is retrievable by (tenant, content_hash) — the viewer's raw material
    assert store.open("t", piece.content_hash) == (src / "contrat.txt").read_bytes()


def test_a_container_members_original_is_retained(tmp_path: Path) -> None:
    # THE ac-critical case: an attachment's bytes live only in a tmpdir during ingestion, yet its
    # own original is retained — so a .msg attachment is a pièce the viewer can render (Story 3.5).
    src, blobs = tmp_path / "in", tmp_path / "blobs"
    src.mkdir()
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = "Sinistre", "adverse@x.fr", "me@cab.fr"
    msg.set_content("Rapport en pièce jointe.")
    msg.add_attachment(b"CONTENU DU RAPPORT ADVERSE", maintype="text", subtype="plain",
                       filename="rapport.txt")
    (src / "mail.eml").write_bytes(msg.as_bytes())
    store = _store(blobs)
    result = ingest_folder(src, matter="m", tenant="t", extractor=FileExtractor(),
                           expander=CompositeExpander([EmlExpander()]), original_store=store)

    by_prov = {p.provenance_path: p for p in result.pieces}
    assert "mail.eml/rapport.txt" in by_prov       # the attachment is a pièce in its own right
    attach = by_prov["mail.eml/rapport.txt"]
    assert store.open("t", attach.content_hash) == b"CONTENU DU RAPPORT ADVERSE"  # its OWN original
    # and the email body's original (the .eml itself) is retained too
    assert store.open("t", by_prov["mail.eml"].content_hash) == (src / "mail.eml").read_bytes()


def test_a_retention_failure_is_a_register_entry_never_an_escape(tmp_path: Path) -> None:
    class _FailingStore:
        def put(self, tenant: str, content_hash: str, data: bytes) -> None:
            raise OSError("disk full")

        def open(self, tenant: str, content_hash: str) -> bytes:  # pragma: no cover - unused here
            raise FileNotFoundError

    src = tmp_path / "in"
    src.mkdir()
    (src / "note.txt").write_bytes(b"une note")
    result = ingest_folder(src, matter="m", tenant="t", extractor=FileExtractor(),
                           original_store=_FailingStore())
    assert result.pieces == []                     # a pièce we cannot retain is NOT a Piece
    (failure,) = result.failures
    assert failure.error_class is ErrorClass.RESOURCE_EXHAUSTED   # recorded, never an escape
    assert result.inventory.is_consistent()


def test_without_a_store_nothing_is_retained_and_pieces_are_unchanged(tmp_path: Path) -> None:
    src = tmp_path / "in"
    src.mkdir()
    (src / "a.txt").write_bytes(b"alpha")
    result = ingest_folder(src, matter="m", tenant="t", extractor=FileExtractor())  # no store
    assert len(result.pieces) == 1 and result.inventory.is_consistent()  # behaviour unchanged
