"""The manage-CLI backup/restore codec (story 1.11). A raw ``SELECT *`` yields column types JSON
cannot carry natively — on Postgres a DETERMINED ``piece_date`` comes back as a pure ``date`` (not
a ``datetime``), and the pre-fix codec crashed on it. The codec must round-trip date, datetime and
bytes losslessly. SQLite for the end-to-end leg.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import sessionmaker

from apx.adapters.store_postgres.models import Base, Piece
from apx.adapters.store_postgres.store import SqlStore
from apx.backup_bundle import _json_default, _revive
from apx.core.app.ingest import IngestedPiece, IngestionResult
from apx.manage import backup, restore

TENANT = "cabinet"


@pytest.fixture(autouse=True)
def _data_volume(tmp_path, monkeypatch):  # noqa: ANN001, ANN201
    """The retained-original volume the CLI backs up from (Story 7.2). A SUBDIRECTORY of tmp_path,
    never tmp_path itself — the conftest's ingest root is tmp_path, and a root that can reach
    ``originals/`` is the configuration Story 7.1 refuses."""
    monkeypatch.setenv("APX_DATA_PATH", str(tmp_path / "data"))
    return tmp_path / "data"


def _store(tmp_path, name: str) -> SqlStore:  # noqa: ANN001
    engine = create_engine(f"sqlite:///{tmp_path / name}.db", future=True)
    Base.metadata.create_all(engine)
    return SqlStore(sessionmaker(bind=engine, future=True))


def _piece(pid: str) -> IngestedPiece:
    return IngestedPiece(
        id=pid, matter="m", tenant=TENANT, content_hash=pid * 8, text_key=pid * 8,
        provenance_path=f"/secret/{pid}.pdf", custodian="custodian-x", extraction_method="text",
        extractor_version="v1", schema_version="s1", ingestion_timestamp=datetime.now(UTC),
        full_text="le contrat", text_version="v")


def test_codec_round_trips_date_datetime_and_bytes() -> None:
    # The hard cases a raw SELECT can hand the codec. `date` is the one that actually occurs today
    # (a determined piece_date on Postgres); before the fix _json_default raised TypeError on it.
    original = {
        "d": date(2021, 6, 1),                                  # a pure date (piece_date, AD-40)
        "dt": datetime(2021, 6, 1, 12, 30, tzinfo=UTC),         # a timestamp
        "b": b"\x00\x01\x02\xff",                               # a future binary column
    }
    decoded = json.loads(json.dumps(original, default=_json_default), object_hook=_revive)
    assert decoded["d"] == date(2021, 6, 1)
    assert isinstance(decoded["d"], date) and not isinstance(decoded["d"], datetime)  # not widened
    assert decoded["dt"] == datetime(2021, 6, 1, 12, 30, tzinfo=UTC)
    assert decoded["b"] == b"\x00\x01\x02\xff"


def test_cli_backup_restore_round_trips_a_determined_piece_date(tmp_path) -> None:  # noqa: ANN001
    src = _store(tmp_path, "src")
    src.provision_tenant(TENANT, "a@x.fr", "pw12345678", "Admin", {"w"}, ["conclusions"])
    src.save(IngestionResult(pieces=[_piece("p0")]), "w", actor="admin")
    determined = date(2021, 6, 1)
    with src._sf() as s, s.begin():   # a determined piece_date — the codec's hard column type
        s.execute(update(Piece).where(Piece.id == "p0").values(
            piece_date=determined, piece_date_status="determined"))

    out = tmp_path / "bundle-cabinet"
    backup(src, TENANT, str(out))     # exercises the manage-CLI backup path end to end
    dst = _store(tmp_path, "dst")
    restore(dst, str(out))            # and the restore path, into an empty store

    with dst._sf() as s:
        got = s.scalar(select(Piece.piece_date).where(Piece.id == "p0"))
    assert got == determined                                   # the determined date survived
    assert dst.inventory("m", TENANT, {"w"}).in_corpus == 1    # and the denominator with it


# ── Story 7.2 — the CLI writes a sealed bundle, and the record says what it covered ────────────

def _last_backup_record(store: SqlStore):  # noqa: ANN202
    from apx.adapters.store_postgres.models import BackupRecord
    with store._sf() as s:
        return s.scalars(select(BackupRecord).where(BackupRecord.tenant == TENANT)).all()[-1]


def test_the_cli_records_the_coverage_it_achieved(tmp_path) -> None:  # noqa: ANN001
    """AD-32's outcome line stops being a bare 'success'. The one it replaces was recorded over a
    backup carrying 20 of 35 tables and none of the originals, and said nothing about either."""
    src = _store(tmp_path, "src")
    src.provision_tenant(TENANT, "a@x.fr", "pw12345678", "Admin", {"w"}, ["conclusions"])
    backup(src, TENANT, str(tmp_path / "bundle"))

    record = _last_backup_record(src)
    assert record.outcome == "success"
    from apx.adapters.store_postgres.backup_plan import backup_plan

    assert f"{len(backup_plan())} tables" in record.detail and "originaux" in record.detail


def test_a_backup_missing_a_retained_document_is_recorded_as_a_FAILURE(tmp_path) -> None:  # noqa: ANN001
    """The bundle is still written — a firm holding an incomplete backup is better off than one
    holding none — but the *worklist* must not read green over a tenant whose *pièce* has no
    document. AD-32's subject is the backup whose failure nobody knew about."""
    src = _store(tmp_path, "src")
    src.provision_tenant(TENANT, "a@x.fr", "pw12345678", "Admin", {"w"}, ["conclusions"])
    src.save(IngestionResult(pieces=[_piece("p0")]), "w", actor="admin")   # no original retained

    out = tmp_path / "bundle"
    message = backup(src, TENANT, str(out))
    assert out.is_dir()
    assert "INCOMPLET" in message

    record = _last_backup_record(src)
    assert record.outcome == "failure"
    assert src.backup_status(TENANT, interval_hours=24).overdue


def test_a_backup_with_no_data_volume_configured_is_refused(tmp_path, monkeypatch) -> None:  # noqa: ANN001
    """``from_env`` falls back to the host temp directory when ``APX_DATA_PATH`` is unset, and that
    directory is empty — so the bundle would be written with zero originals and report success.
    Refused instead, on the same gate the head journal has."""
    monkeypatch.delenv("APX_DATA_PATH", raising=False)
    src = _store(tmp_path, "src")
    src.provision_tenant(TENANT, "a@x.fr", "pw12345678", "Admin", {"w"}, ["conclusions"])
    with pytest.raises(RuntimeError, match="APX_DATA_PATH"):
        backup(src, TENANT, str(tmp_path / "bundle"))
