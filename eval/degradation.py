"""Mechanical degradation of real French public-domain text into the failure modes the ingestion
register must name (Story 2.12, FR-54). Each function is deterministic; the degraded artefact,
ingested through the REAL path, must produce exactly the asserted ``ErrorClass``. This is the eval
"test surface" that drives the extractors to classify damage correctly — building it revealed that
neither ``corrupt-file`` nor ``password-protected`` was produced by any extractor, and closed that
gap (``files.py`` / ``msg_worker.py``).
"""

from __future__ import annotations

from pathlib import Path

# The degradation source — a short public-domain French legal text (well over 200 years old), so
# there is no licence to clear (the recorded provenance for FR-54's degradation inputs).
SOURCE_TEXT = (
    "Les hommes naissent et demeurent libres et égaux en droits. Les distinctions sociales ne "
    "peuvent être fondées que sur l'utilité commune."
)
SOURCE_PROVENANCE = (
    "Déclaration des droits de l'homme et du citoyen (1789), article 1 — public domain."
)


def corrupt_msg(dest: Path) -> Path:
    """Write a ``.msg`` whose OLE compound-file structure is destroyed: the real French text saved
    as raw bytes is not a valid compound file, so ``extract_msg.openMsg`` fails and the register
    class is ``corrupt-file``. Deterministic."""
    dest.write_bytes(b"CORRUPT-MSG-NOT-AN-OLE-COMPOUND-FILE " + SOURCE_TEXT.encode("utf-8"))
    return dest


def password_protect_pdf(dest: Path, *, password: str = "eval-secret") -> Path:
    """Write an ENCRYPTED PDF carrying the source text (in its metadata): a credential is required
    to read it, so extraction classifies it ``password-protected``. Deterministic given the
    password."""
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)  # A4
    writer.add_metadata({"/Subject": SOURCE_TEXT})
    writer.encrypt(password)
    with dest.open("wb") as handle:
        writer.write(handle)
    return dest


def unopenable_archive(dest: Path) -> Path:
    """Write a ``.zip`` whose archive structure is destroyed: the real French text saved as raw
    bytes is not a valid archive, so container expansion fails and the register class is
    ``container-unopenable``. Deterministic."""
    dest.write_bytes(b"PK-CORRUPT-NOT-A-VALID-ARCHIVE " + SOURCE_TEXT.encode("utf-8"))
    return dest
