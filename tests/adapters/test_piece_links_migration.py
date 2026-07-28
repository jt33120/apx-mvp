"""The 0018 data backfill — piece scalars → the provenance/custodian SETS (Story 2.5).

The subtle part is re-encryption: an EncryptedText AAD binds a ciphertext to its column, so the
value cannot be copied verbatim — it is decrypted under the old column's AAD and re-encrypted under
the new one. These tests seed the pre-0018 shape (a `piece` with scalar custodian/provenance),
run the backfill, and prove the SET rows read back through the ORM (i.e. under the NEW AAD); then
the downgrade helper restores a representative scalar. Idempotent and key-free on an empty table.
"""

from __future__ import annotations

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from apx.adapters.store_postgres.backfill import (
    link_id,
    migrate_piece_scalars_to_links,
    revert_piece_links_to_scalar,
)
from apx.adapters.store_postgres.crypto_types import cipher
from apx.adapters.store_postgres.models import PieceCustodian, PieceProvenance


def _pre_0018_schema(engine) -> None:  # noqa: ANN001
    """The pieces table as it was BEFORE this migration (scalar custodian + provenance), plus the
    two empty SET tables the migration creates."""
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE piece (id TEXT PRIMARY KEY, custodian TEXT, provenance_path TEXT)"))
    PieceProvenance.__table__.create(engine)
    PieceCustodian.__table__.create(engine)


def _seed_piece(engine, pid: str, custodian: str, path: str) -> None:  # noqa: ANN001
    """Insert one legacy piece with its scalar values ENCRYPTED under the old column AADs."""
    c = cipher()
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO piece (id, custodian, provenance_path) VALUES (:i, :c, :p)"),
            {"i": pid, "c": c.encrypt(custodian, aad="piece.custodian"),
             "p": c.encrypt(path, aad="piece.provenance_path")})


def test_backfill_moves_scalars_into_the_sets_readable_under_the_new_aad(tmp_path) -> None:  # noqa: ANN001
    engine = create_engine(f"sqlite:///{tmp_path / 'apx.db'}", future=True)
    _pre_0018_schema(engine)
    _seed_piece(engine, "p1", "Dupont", "/folderA/contrat.pdf")

    with engine.begin() as conn:
        assert migrate_piece_scalars_to_links(conn) == 2  # one custodian + one provenance row

    # the ORM reads the SET values back — proving they were re-encrypted under the NEW column AAD
    with Session(engine) as s:
        cust = s.scalars(select(PieceCustodian)).all()
        prov = s.scalars(select(PieceProvenance)).all()
    assert [c.custodian for c in cust] == ["Dupont"]
    assert [p.provenance_path for p in prov] == ["/folderA/contrat.pdf"]
    # the deterministic id is sha256(piece_id \0 plaintext) — the store computes the SAME at runtime
    assert cust[0].id == link_id("p1", "Dupont")


def test_backfill_is_idempotent_and_a_downgrade_restores_the_scalar(tmp_path) -> None:  # noqa: ANN001
    engine = create_engine(f"sqlite:///{tmp_path / 'apx.db'}", future=True)
    _pre_0018_schema(engine)
    _seed_piece(engine, "p1", "Martin", "/x.pdf")
    with engine.begin() as conn:
        assert migrate_piece_scalars_to_links(conn) == 2
        assert migrate_piece_scalars_to_links(conn) == 0  # re-run writes nothing (idempotent)

    # downgrade: the representative custodian is restored into the (nullable, re-added) scalar
    with engine.begin() as conn:
        conn.execute(text("UPDATE piece SET custodian = NULL"))  # simulate the re-added column
        assert revert_piece_links_to_scalar(conn) == 1
    with engine.connect() as conn:
        raw = conn.exec_driver_sql("SELECT custodian FROM piece WHERE id = 'p1'").scalar()
    assert cipher().decrypt(raw, aad="piece.custodian") == "Martin"  # readable under the piece AAD


def test_backfill_is_a_noop_on_an_empty_piece_table(tmp_path) -> None:  # noqa: ANN001
    engine = create_engine(f"sqlite:///{tmp_path / 'apx.db'}", future=True)
    _pre_0018_schema(engine)
    with engine.begin() as conn:
        assert migrate_piece_scalars_to_links(conn) == 0  # no rows → key-free no-op
