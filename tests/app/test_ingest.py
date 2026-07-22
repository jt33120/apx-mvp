"""Ingestion tests: the inventory guarantee holds on a real folder (no DB)."""

from __future__ import annotations

from pathlib import Path

from apx.adapters.extraction.files import FileExtractor
from apx.core.app.ingest import ingest_folder
from apx.core.domain.failures import ErrorClass


def _make_matter(root: Path) -> None:
    (root / "d").mkdir()
    (root / "d" / "letter.txt").write_text("Maître, veuillez trouver ci-joint…", encoding="utf-8")
    (root / "d" / "note.md").write_text("# Note\nLe dossier 145 CPC…", encoding="utf-8")
    (root / "d" / "empty.txt").write_text("   \n", encoding="utf-8")     # extracted-empty
    (root / "d" / "photo.jpg").write_bytes(b"\xff\xd8\xff not an image")  # unsupported-format
    (root / ".DS_Store").write_bytes(b"noise")                            # exclusion
    (root / "d" / ".gitkeep").write_bytes(b"")                            # exclusion


def test_inventory_accounts_for_every_file(tmp_path: Path) -> None:
    _make_matter(tmp_path)
    r = ingest_folder(tmp_path, matter="m", tenant="t", extractor=FileExtractor())
    inv = r.inventory
    assert inv.is_consistent()
    assert inv.submitted == 6
    assert inv.in_corpus == 2  # letter.txt, note.md
    assert inv.failures == 2  # empty.txt (extracted-empty), photo.jpg (unsupported-format)
    assert inv.exclusions == 2  # .DS_Store, .gitkeep


def test_failures_are_classified_and_listed(tmp_path: Path) -> None:
    _make_matter(tmp_path)
    r = ingest_folder(tmp_path, matter="m", tenant="t", extractor=FileExtractor())
    classes = {f.submitted_path.split("/")[-1]: f.error_class for f in r.failures}
    assert classes["empty.txt"] == ErrorClass.EXTRACTED_EMPTY
    assert classes["photo.jpg"] == ErrorClass.UNSUPPORTED_FORMAT


def test_same_content_same_matter_yields_the_same_piece_id(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("identical bytes", encoding="utf-8")
    (tmp_path / "b.txt").write_text("identical bytes", encoding="utf-8")
    r = ingest_folder(tmp_path, matter="m", tenant="t", extractor=FileExtractor())
    ids = {p.id for p in r.pieces}
    # Same (content, matter) → same id, even at different paths (AD-40).
    assert len(ids) == 1 and len(r.pieces) == 2


def test_extracted_empty_is_not_counted_in_corpus(tmp_path: Path) -> None:
    (tmp_path / "blank.txt").write_text("", encoding="utf-8")
    r = ingest_folder(tmp_path, matter="m", tenant="t", extractor=FileExtractor())
    assert r.inventory.in_corpus == 0
    assert r.inventory.failures == 1  # an absence claim must never assert it was searched
