"""The mechanical degradation pipeline is part of the test surface (Story 2.12, FR-54): each
degradation of real French public-domain text, ingested through the REAL path, produces exactly the
failure-register class it must — a corrupt ``.msg`` → ``corrupt-file``, a password-protected PDF →
``password-protected``, an unopenable archive → ``container-unopenable``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from apx.adapters.expansion.archives import ZipExpander
from apx.adapters.expansion.composite import CompositeExpander
from apx.adapters.extraction.composite import CompositeExtractor
from apx.adapters.extraction.files import FileExtractor
from apx.adapters.extraction.msg import MsgExtractor
from apx.core.app.ingest import IngestionResult, ingest_one_file
from apx.core.domain.config import ExpansionBounds
from apx.core.domain.failures import ErrorClass
from eval.degradation import corrupt_msg, password_protect_pdf, unopenable_archive


def _classes(result: IngestionResult) -> list[ErrorClass]:
    return [f.error_class for f in result.failures]


def test_a_corrupt_msg_is_a_corrupt_file_register_entry(tmp_path: Path) -> None:
    pytest.importorskip("extract_msg")  # the .msg path spawns the real GPL-isolated worker
    p = corrupt_msg(tmp_path / "casse.msg")
    result = ingest_one_file(
        p, "casse.msg", "m", "t", CompositeExtractor([MsgExtractor(), FileExtractor()]))
    assert _classes(result) == [ErrorClass.CORRUPT_FILE]


def test_a_password_protected_pdf_is_a_password_protected_register_entry(tmp_path: Path) -> None:
    p = password_protect_pdf(tmp_path / "protege.pdf")
    result = ingest_one_file(p, "protege.pdf", "m", "t", FileExtractor())
    assert _classes(result) == [ErrorClass.PASSWORD_PROTECTED]


def test_an_unopenable_archive_is_a_container_unopenable_register_entry(tmp_path: Path) -> None:
    p = unopenable_archive(tmp_path / "casse.zip")
    result = ingest_one_file(
        p, "casse.zip", "m", "t", CompositeExtractor([MsgExtractor(), FileExtractor()]),
        expander=CompositeExpander([ZipExpander(ExpansionBounds.defaults())]))
    assert _classes(result) == [ErrorClass.CONTAINER_UNOPENABLE]


def test_a_permission_encrypted_but_readable_pdf_is_not_withheld(tmp_path: Path) -> None:
    # review HIGH: a PDF encrypted with an EMPTY user password + owner restrictions is freely
    # READABLE (pypdf opens it with no credential). It must NOT be withheld as password-protected —
    # recall over precision, a readable document is never dropped. Only a real user-password gates.
    from pypdf import PdfWriter
    p = tmp_path / "restreint.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.encrypt(user_password="", owner_password="owner-only")
    with p.open("wb") as handle:
        writer.write(handle)
    assert FileExtractor().extract(p).error_class is not ErrorClass.PASSWORD_PROTECTED
