"""The manage-CLI backup/restore codec (story 1.11). A raw ``SELECT *`` yields column types JSON
cannot carry natively — on Postgres a DETERMINED ``piece_date`` comes back as a pure ``date`` (not
a ``datetime``), and the pre-fix codec crashed on it. The codec must round-trip date, datetime and
bytes losslessly. SQLite for the end-to-end leg.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime

from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import sessionmaker

from apx.adapters.store_postgres.models import Base, Piece
from apx.adapters.store_postgres.store import SqlStore
from apx.core.app.ingest import IngestedPiece, IngestionResult
from apx.manage import _json_default, _revive, backup, restore

TENANT = "cabinet"


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

    out = tmp_path / "cabinet.json"
    backup(src, TENANT, str(out))     # exercises the manage-CLI backup path end to end
    dst = _store(tmp_path, "dst")
    restore(dst, str(out))            # and the restore path, into an empty store

    with dst._sf() as s:
        got = s.scalar(select(Piece.piece_date).where(Piece.id == "p0"))
    assert got == determined                                   # the determined date survived
    assert dst.inventory("m", TENANT, {"w"}).in_corpus == 1    # and the denominator with it
