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
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

from apx.adapters.store_postgres.models import Base, PieceCustodian
from apx.adapters.store_postgres.store import SqlStore
from apx.core.app.ingest import IngestedFailure, IngestedPiece, IngestionResult
from apx.core.domain.crypto import DecryptionError
from apx.core.domain.failures import ErrorClass
from apx.core.domain.triage import Label, PieceLabel, TriageOutcome

TOKEN = "SEEDED-TOKEN-9F3A2C1D"  # distinctive; a raw store that holds it in cleartext leaks
TENANT, MATTER, SCOPE = "t", "m", "wall"

# every content-bearing column that MUST be ciphertext at rest (the AC1 set, incl. the PII
# actor/reviewer columns the review added)
ENCRYPTED_COLUMNS = [
    ("piece", "provenance_path"),
    ("piece_provenance", "provenance_path"),  # the provenance SET holds the token too (Story 2.5)
    ("piece_custodian", "custodian"),  # custodianship is the CUSTODIAN_LINK set now (Story 2.5)
    ("failure", "filename"),
    ("failure", "submitted_path"),
    ("failure", "detail"),
    ("audit_record", "actor"),
    ("audit_record", "detail"),
    ("piece_label", "rationale"),
    ("user_account", "mfa_secret"),
    ("recall_review", "reviewer"),
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
    store.save(IngestionResult(pieces=[piece], failures=[failure]), SCOPE, actor=f"Me {TOKEN}")
    store.save_labels(
        MATTER, TENANT, {SCOPE},
        TriageOutcome(labels=(PieceLabel("piece-1", Label.DISCARD, f"écarté car {TOKEN}"),)),
        "criteria", "avocat",
    )
    # a recall review seeds recall_review.reviewer (PII) with the token
    store.record_recall_review(MATTER, TENANT, {SCOPE}, {"piece-1": False}, f"reviewer {TOKEN}")
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


def test_a_seeded_secret_value_is_absent_from_every_raw_store(seeded) -> None:  # noqa: ANN001
    # FR-51/AC4 (story 1.8): the raw-store inspection extends to seeded SECRET values, not only
    # content tokens. The seed includes a TOTP secret; assert that secret appears in no store.
    engine, _store = seeded
    secret = f"TOTPSEED{TOKEN}"
    with engine.connect() as conn:
        for table, col in ENCRYPTED_COLUMNS:
            rows = conn.exec_driver_sql(f"SELECT {col} FROM {table}").fetchall()
            blob = "\n".join(str(v[0]) for v in rows if v[0] is not None)
            assert secret not in blob, f"the seeded secret leaked in cleartext in {table}.{col}"


def test_the_orm_decrypts_transparently_and_search_still_works(seeded) -> None:  # noqa: ANN001
    _engine, store = seeded
    # read back through the ORM: the encrypted columns decrypt to their plaintext
    inv = store.inventory(MATTER, TENANT, {SCOPE})
    assert inv.in_corpus == 1 and inv.open_register_entries == 1
    labels = store.labels(MATTER, TENANT, {SCOPE})
    assert labels.pieces[0].rationale == f"écarté car {TOKEN}"
    assert store.mfa_status(TENANT, store.list_users(TENANT)[0].id)[1] == f"TOTPSEED{TOKEN}"
    # exhaustive search still runs over the (plaintext) text index — the exception's payoff
    assert store.search(TENANT, {SCOPE}, TOKEN).total == 1


def test_the_audit_chain_verifies_after_the_encrypted_detail_round_trips(seeded) -> None:  # noqa: ANN001
    # the chain is computed over the PLAINTEXT detail/actor, and read_audit decrypts before it
    # recomputes — so encrypting those columns does not break tamper-evidence.
    _engine, store = seeded
    trail = store.read_audit(MATTER, TENANT, {SCOPE})
    assert trail.verified


def test_a_relocated_ciphertext_fails_to_decrypt(seeded) -> None:  # noqa: ANN001
    # AAD binding: a ciphertext is bound to its column. Copy piece.provenance_path's ciphertext
    # into piece_custodian.custodian (a DB-write attacker relocating a value across columns) — the
    # AAD no longer matches, so a read fails closed instead of silently decrypting one column's
    # value as another's. Without AAD both columns share a key and the relocation would succeed.
    engine, store = seeded
    with engine.begin() as conn:
        prov_ct = conn.exec_driver_sql("SELECT provenance_path FROM piece").scalar()
        conn.execute(text("UPDATE piece_custodian SET custodian = :v"), {"v": prov_ct})
    with pytest.raises(DecryptionError), Session(engine) as session:
        row = session.scalars(select(PieceCustodian).where(
            PieceCustodian.piece_id == "piece-1")).first()
        _ = row.custodian  # decrypting the relocated ciphertext fails (AAD mismatch)


def test_a_tampered_audit_field_degrades_to_unverified_not_a_crash(seeded) -> None:  # noqa: ANN001
    # Pre-encryption a tampered audit row → verified=False. That must survive encryption: a
    # non-ciphertext (tampered / legacy) detail must NOT 500 the whole tenant read (FR-24).
    engine, store = seeded
    with engine.begin() as conn:
        conn.execute(text("UPDATE audit_record SET detail = 'tampered plaintext' WHERE seq = 1"))
    trail = store.read_audit(MATTER, TENANT, {SCOPE})  # does not raise
    assert trail.verified is False
    assert any("illisible" in e.detail for e in trail.entries)  # the bad row is shown, redacted


def test_a_truncated_ciphertext_audit_field_degrades_not_crashes(seeded) -> None:  # noqa: ANN001
    # the 1.8 regression: a TRUNCATED apxenc token (too short for a nonce) made AESGCM raise a
    # bare ValueError that escaped read_audit's DecryptionError catch → whole-tenant 500. It must
    # degrade to verified=False like any other unreadable row.
    engine, store = seeded
    with engine.begin() as conn:
        conn.execute(text("UPDATE audit_record SET actor = 'apxenc:v1:AAAA' WHERE seq = 1"))
    trail = store.read_audit(MATTER, TENANT, {SCOPE})  # does not raise
    assert trail.verified is False
