"""Enabling encryption on a store with existing plaintext must not brick it (story 1.7, AD-31).

The 1.7 backfill re-encrypts values written before the columns became EncryptedText. Proven:
a legacy plaintext value is unreadable, the backfill encrypts it, the ORM then reads it, and a
re-run is a no-op. Key-free when there is nothing to encrypt.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from apx.adapters.store_postgres.backfill import encrypt_backfill
from apx.adapters.store_postgres.models import Base, Piece
from apx.adapters.store_postgres.store import SqlStore
from apx.core.app.ingest import IngestedPiece, IngestionResult
from apx.core.domain.crypto import DecryptionError, MissingEncryptionKey, is_ciphertext

TENANT, MATTER, SCOPE = "t", "m", "wall"


def _store(engine) -> SqlStore:  # noqa: ANN001
    Base.metadata.create_all(engine)
    store = SqlStore(sessionmaker(bind=engine, future=True))
    piece = IngestedPiece(
        id="p1", matter=MATTER, tenant=TENANT, content_hash="c" * 64, text_key="k" * 64,
        provenance_path="/enc/path.pdf", custodian="c", extraction_method="text",
        extractor_version="v", schema_version="s", ingestion_timestamp=datetime.now(UTC),
        full_text="body", text_version="v",
    )
    store.save(IngestionResult(pieces=[piece]), SCOPE, actor="a")
    return store


def test_a_legacy_plaintext_value_is_backfilled_and_becomes_readable(tmp_path) -> None:  # noqa: ANN001
    engine = create_engine(f"sqlite:///{tmp_path / 'apx.db'}", future=True)
    _store(engine)
    # simulate a pre-1.7 plaintext value landing in an encrypted column
    with engine.begin() as conn:
        conn.execute(text("UPDATE piece SET provenance_path = '/legacy/plain.pdf'"))
    # before the backfill: reading it through the ORM fails closed (not ciphertext)
    with pytest.raises(DecryptionError), Session(engine) as s:
        _ = s.get(Piece, "p1").provenance_path

    with engine.begin() as conn:
        assert encrypt_backfill(conn) == 1  # one value encrypted

    with engine.begin() as conn:  # raw: it is now ciphertext at rest
        assert is_ciphertext(conn.exec_driver_sql("SELECT provenance_path FROM piece").scalar())
    with Session(engine) as s:  # and the ORM reads back the original plaintext
        assert s.get(Piece, "p1").provenance_path == "/legacy/plain.pdf"


def test_the_backfill_is_idempotent(tmp_path) -> None:  # noqa: ANN001
    engine = create_engine(f"sqlite:///{tmp_path / 'apx.db'}", future=True)
    _store(engine)  # all values already encrypted through the ORM
    with engine.begin() as conn:
        assert encrypt_backfill(conn) == 0  # nothing to do — already ciphertext
    with engine.begin() as conn:
        # custodianship moved off `piece` into the piece_custodian SET (Story 2.5); seed a legacy
        # plaintext value there to prove the backfill still covers it.
        conn.execute(text("UPDATE piece_custodian SET custodian = 'plain'"))
        assert encrypt_backfill(conn) == 1  # the one plaintext value
        assert encrypt_backfill(conn) == 0  # re-run is a no-op


def test_the_backfill_needs_no_key_when_there_is_nothing_to_encrypt(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:  # noqa: ANN001
    # the cipher is loaded ONLY when a plaintext value is found — so a fresh/all-encrypted store
    # backfills without APX_ENCRYPTION_KEY (the CI upgrade→downgrade→upgrade runs without one).
    import apx.adapters.store_postgres.crypto_types as ct

    def _no_key() -> object:
        raise MissingEncryptionKey("no key in this test")

    engine = create_engine(f"sqlite:///{tmp_path / 'apx.db'}", future=True)
    _store(engine)  # everything encrypted
    monkeypatch.setattr(ct, "cipher", _no_key)
    with engine.begin() as conn:
        assert encrypt_backfill(conn) == 0  # never touches the (now key-less) cipher
