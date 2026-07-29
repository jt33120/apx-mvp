"""Container expansion (story 2.4, FR-57/AD-17/AD-38): the new expanders (.zip/.7z/.mbox/PDF
portfolio), the config-bounded depth / member-count / expansion-ratio guards (a zip bomb is a
register entry, not an outage), and the end-to-end guarantees through the ingestion use case —
members carry provenance THROUGH a container three levels deep, custodian inherited, and an
unopened container is one `container-unopenable` entry of cardinality `unknown`.
"""

from __future__ import annotations

import io
import mailbox
import zipfile
from pathlib import Path

import pytest

from apx.adapters.expansion.archives import SevenZipExpander, ZipExpander
from apx.adapters.expansion.composite import CompositeExpander
from apx.adapters.expansion.mail import EmlExpander, MboxExpander
from apx.adapters.expansion.pdf import PdfPortfolioExpander
from apx.adapters.extraction.files import FileExtractor
from apx.core.app.ingest import ingest_folder
from apx.core.domain.config import ExpansionBounds
from apx.core.domain.failures import ErrorClass
from apx.core.ports.expansion import ContainerUnopenable


def _text_pdf(path: Path, text: str) -> None:
    """A minimal born-digital PDF with one line of extractable text (pypdf recovers the xref)."""
    stream = f"BT /F1 18 Tf 20 100 Td ({text}) Tj ET".encode()
    path.write_bytes(
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 144]"
        b"/Resources<</Font<</F1 4 0 R>>>>/Contents 5 0 R>>endobj\n"
        b"4 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n"
        b"5 0 obj<</Length " + str(len(stream)).encode() + b">>stream\n" + stream
        + b"\nendstream endobj\ntrailer<</Root 1 0 R/Size 6>>\nstartxref\n0\n%%EOF\n")


def _eml(path: Path, subject: str, body: str, attachments: dict[str, bytes] | None = None) -> None:
    from email.message import EmailMessage

    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = "a@x.fr", "b@y.fr", subject
    msg.set_content(body)
    for name, data in (attachments or {}).items():
        msg.add_attachment(data, maintype="application", subtype="octet-stream", filename=name)
    path.write_bytes(msg.as_bytes())


def _zip_bytes(entries: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in entries.items():
            z.writestr(name, data)
    return buf.getvalue()


def _bounds(**over: int) -> ExpansionBounds:
    base = dict(max_depth=6, max_members=5000, max_expansion_ratio=100,
                attachments_per_message_max=1000)
    base.update(over)
    return ExpansionBounds(**base)


# ── ZipExpander — happy + the three bound breaches ────────────────────────────────────────────
def test_zip_expander_yields_members(tmp_path: Path) -> None:
    p = tmp_path / "dossier.zip"
    p.write_bytes(_zip_bytes({"a.txt": b"un", "sub/b.txt": b"deux"}))
    members = ZipExpander().members(p)
    assert sorted(n for n, _ in members) == ["a.txt", "sub/b.txt"]


def test_zip_bomb_is_refused_by_declared_ratio_before_decompressing(tmp_path: Path) -> None:
    # 2 MB of zeros compresses to ~KB, so the DECLARED ratio (~1000:1) trips the guard BEFORE any
    # member is read — the bomb is never decompressed whole.
    p = tmp_path / "bombe.zip"
    p.write_bytes(_zip_bytes({"zeros.bin": b"\0" * 2_000_000}))
    with pytest.raises(ContainerUnopenable, match="expansion ratio"):
        ZipExpander(_bounds(max_expansion_ratio=100)).members(p)


def test_too_many_members_is_refused(tmp_path: Path) -> None:
    p = tmp_path / "many.zip"
    p.write_bytes(_zip_bytes({f"f{i}.txt": b"x" for i in range(4)}))
    with pytest.raises(ContainerUnopenable, match="members exceed"):
        ZipExpander(_bounds(max_members=2)).members(p)


def test_a_corrupt_zip_is_container_unopenable_not_a_leaf(tmp_path: Path) -> None:
    p = tmp_path / "casse.zip"
    p.write_bytes(b"this is not a zip at all")
    with pytest.raises(ContainerUnopenable):
        ZipExpander().members(p)


# ── SevenZipExpander (py7zr) ──────────────────────────────────────────────────────────────────
def test_7z_expander_yields_members(tmp_path: Path) -> None:
    py7zr = pytest.importorskip("py7zr")
    p = tmp_path / "arch.7z"
    with py7zr.SevenZipFile(p, "w") as z:
        z.writestr(b"contenu du rapport", "rapport.txt")
    members = SevenZipExpander().members(p)
    assert members and members[0][0] == "rapport.txt" and members[0][1] == b"contenu du rapport"


def test_a_corrupt_7z_is_container_unopenable(tmp_path: Path) -> None:
    pytest.importorskip("py7zr")
    p = tmp_path / "casse.7z"
    p.write_bytes(b"not a 7z archive")
    with pytest.raises(ContainerUnopenable):
        SevenZipExpander().members(p)


# ── MboxExpander (stdlib) ─────────────────────────────────────────────────────────────────────
def test_mbox_expander_yields_one_member_per_message(tmp_path: Path) -> None:
    p = tmp_path / "export.mbox"
    box = mailbox.mbox(str(p))
    box.add(b"From: a@x.fr\nSubject: Un\n\npremier message")
    box.add(b"From: b@y.fr\nSubject: Deux\n\nsecond message")
    box.flush()
    box.close()
    members = MboxExpander().members(p)
    assert len(members) == 2 and all(n.endswith(".eml") for n, _ in members)


# ── PdfPortfolioExpander (pypdf) ──────────────────────────────────────────────────────────────
def test_pdf_portfolio_yields_embedded_files(tmp_path: Path) -> None:
    from pypdf import PdfWriter

    p = tmp_path / "portfolio.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.add_attachment("annexe.txt", b"piece jointe du portfolio")
    with p.open("wb") as fh:
        writer.write(fh)
    members = PdfPortfolioExpander().members(p)
    assert members and any(n == "annexe.txt" for n, _ in members)


def test_a_plain_pdf_is_a_leaf_not_a_container(tmp_path: Path) -> None:
    from pypdf import PdfWriter

    p = tmp_path / "plain.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    with p.open("wb") as fh:
        writer.write(fh)
    assert PdfPortfolioExpander().members(p) is None      # no embedded files → a leaf


# ── end-to-end through the ingestion use case ─────────────────────────────────────────────────
def _ingest(tmp_path: Path, *, bounds: ExpansionBounds | None = None):
    b = bounds or _bounds()
    return ingest_folder(
        tmp_path, matter="m", tenant="t", extractor=FileExtractor(), custodian="M. Dupont",
        expander=CompositeExpander([ZipExpander(b)]), bounds=b)


def test_a_container_three_levels_deep_yields_the_innermost_piece_with_full_provenance(
        tmp_path: Path) -> None:
    inner = _zip_bytes({"deep.txt": b"innermost legal content"})
    mid = _zip_bytes({"inner.zip": inner})
    (tmp_path / "outer.zip").write_bytes(_zip_bytes({"mid.zip": mid}))
    result = _ingest(tmp_path)
    assert result.inventory.in_corpus == 1
    piece = result.pieces[0]
    assert piece.provenance_path == "outer.zip/mid.zip/inner.zip/deep.txt"   # provenance through 3
    assert piece.custodian == "M. Dupont"                                    # inherited to the leaf
    assert result.inventory.is_consistent()


def test_a_zip_bomb_is_one_container_unopenable_entry_of_unknown_cardinality(
        tmp_path: Path) -> None:
    (tmp_path / "bombe.zip").write_bytes(_zip_bytes({"zeros.bin": b"\0" * 2_000_000}))
    result = _ingest(tmp_path)
    assert [f.error_class for f in result.failures] == [ErrorClass.CONTAINER_UNOPENABLE]
    assert result.inventory.in_corpus == 0 and result.inventory.unknown_cardinality_entries == 1
    assert result.inventory.unknown_cardinality_phrase() == "1 archive unopened, contents unknown"
    assert result.inventory.is_consistent()                 # the unknown is never summed


def test_a_container_nested_past_the_depth_limit_is_container_unopenable(tmp_path: Path) -> None:
    inner = _zip_bytes({"deep.txt": b"x"})
    (tmp_path / "outer.zip").write_bytes(_zip_bytes({"inner.zip": inner}))
    result = _ingest(tmp_path, bounds=_bounds(max_depth=1))   # inner.zip sits at depth 1 == limit
    assert [f.error_class for f in result.failures] == [ErrorClass.CONTAINER_UNOPENABLE]
    assert result.inventory.in_corpus == 0                   # deep.txt never reached
    assert "nesting depth" in (result.failures[0].detail or "")


# ── FR-6: a recognised but EMPTY container is recorded, never silently dropped ────────────────
def test_an_empty_archive_is_extracted_empty_not_vanished(tmp_path: Path) -> None:
    (tmp_path / "vide.zip").write_bytes(_zip_bytes({}))
    result = _ingest(tmp_path)
    assert result.inventory.submitted_pieces == 1 and result.inventory.in_corpus == 0
    assert [f.error_class for f in result.failures] == [ErrorClass.EXTRACTED_EMPTY]
    assert result.inventory.is_consistent()             # accounted, not a silent 0/0


def test_an_empty_mbox_is_extracted_empty_not_vanished(tmp_path: Path) -> None:
    (tmp_path / "vide.mbox").write_bytes(b"")           # a valid but empty mailbox
    result = ingest_folder(tmp_path, matter="m", tenant="t", extractor=FileExtractor(),
                           custodian="C", expander=CompositeExpander([MboxExpander()]))
    assert result.inventory.submitted_pieces == 1
    assert [f.error_class for f in result.failures] == [ErrorClass.EXTRACTED_EMPTY]


def test_an_email_with_a_body_but_no_attachments_still_yields_its_body(tmp_path: Path) -> None:
    # EmlExpander returns [] (no attachments) → the .eml must NOT vanish: its body is a piece.
    _eml(tmp_path / "note.eml", "Sans PJ", "Le corps du courriel sans pièce jointe.")
    result = ingest_folder(tmp_path, matter="m", tenant="t", extractor=FileExtractor(),
                           custodian="C", expander=CompositeExpander([EmlExpander()]))
    assert result.inventory.in_corpus == 1              # the body, not lost
    assert "corps du courriel" in result.pieces[0].full_text


# ── born-digital PDF (locks the pypdf.errors.PyPdfError fix) + portfolio cover text ───────────
def test_a_born_digital_pdf_extracts_its_text(tmp_path: Path) -> None:
    # Before the PdfError→PyPdfError fix, `_pdf` raised ImportError on EVERY pdf — this locks it.
    _text_pdf(tmp_path / "acte.pdf", "Conclusions en defense")
    out = FileExtractor().extract(tmp_path / "acte.pdf")
    assert out.ok and out.method == "pypdf" and "Conclusions en defense" in out.text


def test_a_pdf_portfolio_yields_its_embedded_members_and_its_cover_text(tmp_path: Path) -> None:
    from pypdf import PdfReader, PdfWriter

    p = tmp_path / "portfolio.pdf"
    _text_pdf(p, "Page de garde du portfolio")
    reader = PdfReader(str(p))
    writer = PdfWriter()
    writer.append(reader)
    writer.add_attachment("annexe.txt", b"contenu de l'annexe")
    with p.open("wb") as fh:
        writer.write(fh)
    result = ingest_folder(tmp_path, matter="m", tenant="t", extractor=FileExtractor(),
                           custodian="C", expander=CompositeExpander([PdfPortfolioExpander()]))
    provs = {pc.provenance_path for pc in result.pieces}
    assert "portfolio.pdf" in provs                     # the cover text — a piece (AC1)
    assert "portfolio.pdf/annexe.txt" in provs          # the embedded member — N+1


# ── the member-cap keeps an email/.msg body rather than folding it into "unknown" (R2 Low) ────
def test_the_member_cap_still_extracts_the_container_body(tmp_path: Path) -> None:
    _eml(tmp_path / "gros.eml", "Deux PJ", "Corps important à ne pas perdre.",
         {"a.txt": b"annexe A", "b.txt": b"annexe B"})
    result = ingest_folder(
        tmp_path, matter="m", tenant="t", extractor=FileExtractor(), custodian="C",
        expander=CompositeExpander([EmlExpander()]), bounds=_bounds(max_members=1))
    # 1 attachment (before the cap) + the body = 2 pieces; the container is 1 container-unopenable.
    assert result.inventory.in_corpus == 2 and result.inventory.unknown_cardinality_entries == 1
    assert any("Corps important" in pc.full_text for pc in result.pieces)   # body NOT folded away
    assert result.inventory.is_consistent()
