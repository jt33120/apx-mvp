"""Encrypted at rest, proven by inspection (story 1.7, AD-31 / AD-26).

Seed a distinctive token into EVERY content-bearing field — a piece's provenance and
custodian, a failure's filename/path/detail, an audit detail, a triage rationale, a TOTP
secret — then read the RAW column bytes (past the ORM, so past decryption) and assert the
token appears in NO store. The one deliberate exception is ``piece.full_text``: it is the
AD-31 "deterministic text index" that exhaustive search (FR-13) runs an SQL ILIKE over, so
it cannot be application-encrypted — the test asserts the token IS present there, by name,
so the carve-out is visibly deliberate and nobody weakens the test to hide an oversight.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from apx.adapters.store_postgres.models import Base
from apx.adapters.store_postgres.store import SqlStore
from apx.core.app.ingest import IngestedFailure, IngestedPiece, IngestionResult
from apx.core.domain.failures import ErrorClass
from apx.core.domain.triage import Label, PieceLabel, TriageOutcome

TOKEN = "SEEDED-TOKEN-9F3A2C1D"  # distinctive; a raw store that holds it in cleartext leaks
TENANT, MATTER, SCOPE = "t", "m", "wall"

# every content-bearing column that MUST be ciphertext at rest (the AC1 set)
ENCRYPTED_COLUMNS = [
    ("piece", "provenance_path"),
    ("piece", "custodian"),
    ("failure", "filename"),
    ("failure", "submitted_path"),
    ("failure", "detail"),
    ("audit_record", "detail"),
    ("piece_label", "rationale"),
    ("user_account", "mfa_secret"),
]


@pytest.fixture
def seeded(tmp_path):  # noqa: ANN001, ANN201
    """A store on a file-backed SQLite (so a fresh connection sees committed rows), seeded
    with the token in every content-bearing field. Returns (engine, store)."""
    engine = create_engine(f"sqlite:///{tmp_path / 'apx.db'}", future=True)
    Base.metadata.create_all(engine)
    store = SqlStore(sessionmaker(bind=engine, future=True))
    now = datetime.now(UTC)

    piece = IngestedPiece(
        id="piece-1", matter=MATTER, tenant=TENANT, content_hash="c" * 64, text_key="k" * 64,
        provenance_path=f"/matters/{TOKEN}/contrat.pdf", custodian=f"custodian-{TOKEN}",
        extraction_method="text", extractor_version="v", schema_version="s",
        ingestion_timestamp=now, full_text=f"le contrat mentionne {TOKEN}", text_version="v",
    )
    failure = IngestedFailure(
        filename=f"{TOKEN}.docx", submitted_path=f"/in/{TOKEN}.docx",
        matter=MATTER, tenant=TENANT, error_class=ErrorClass.EXTRACTION_ERROR,
        detail=f"could not open {TOKEN}",
    )
    store.save(IngestionResult(pieces=[piece], failures=[failure]), SCOPE, actor="avocat")
    store.save_labels(
        MATTER, TENANT, {SCOPE},
        TriageOutcome(labels=(PieceLabel("piece-1", Label.DISCARD, f"écarté car {TOKEN}"),)),
        "criteria", "avocat",
    )
    uid = store.create_user(TENANT, "a@a.test", "password1", "Avocat A", set())
    store.set_mfa_secret(uid, f"TOTPSEED{TOKEN}")
    store.record_auth_event(TENANT, "system:auth", "login_failed", f"email={TOKEN}@x ip=1.2.3.4")
    return engine, store


def test_no_plaintext_token_in_any_raw_store_except_the_named_index(seeded) -> None:  # noqa: ANN001
    engine, _store = seeded
    with engine.connect() as conn:
        for table, col in ENCRYPTED_COLUMNS:
            raw = conn.exec_driver_sql(f"SELECT {col} FROM {table}").fetchall()  # past the ORM
            blob = "\n".join(str(v[0]) for v in raw if v[0] is not None)
            assert blob, f"{table}.{col} had no rows — the seed did not land"
            assert TOKEN not in blob, f"{table}.{col} leaked the token in cleartext"

        # AD-31 NAMED EXCEPTION — the deterministic text index. It is un-encrypted ON PURPOSE
        # (you cannot ILIKE ciphertext); protected by volume encryption + the start-up gate.
        ft = conn.exec_driver_sql("SELECT full_text FROM piece").fetchall()
        assert any(TOKEN in str(v[0]) for v in ft), (
            "piece.full_text is the AD-31 text-index exception and MUST hold the token in "
            "cleartext — if this fails, either encryption silently broke or the exception "
            "was removed without updating exhaustive search"
        )


def test_the_orm_decrypts_transparently_and_search_still_works(seeded) -> None:  # noqa: ANN001
    _engine, store = seeded
    # read back through the ORM: the encrypted columns decrypt to their plaintext
    inv = store.inventory(MATTER, TENANT, {SCOPE})
    assert inv.in_corpus == 1 and inv.failures == 1
    labels = store.labels(MATTER, TENANT, {SCOPE})
    assert labels.pieces[0].rationale == f"écarté car {TOKEN}"
    assert store.mfa_status(TENANT, store.list_users(TENANT)[0].id)[1] == f"TOTPSEED{TOKEN}"
    # exhaustive search still runs over the (plaintext) text index — the exception's payoff
    assert store.search(TENANT, {SCOPE}, TOKEN).total == 1


def test_the_audit_chain_verifies_after_the_encrypted_detail_round_trips(seeded) -> None:  # noqa: ANN001
    # the chain is computed over the PLAINTEXT detail, and read_audit decrypts before it
    # recomputes — so encrypting the detail column does not break tamper-evidence.
    _engine, store = seeded
    trail = store.read_audit(MATTER, TENANT, {SCOPE})
    assert trail.verified
