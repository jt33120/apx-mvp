"""The 0023 backfill — matter_scope.case_theory → case_theory_version v1 (Story 4.1).

Mirrors the 0018 pattern: the value is re-encrypted under the NEW column's AAD (an EncryptedText
AAD binds a ciphertext to its column), so the ORM reads it back cleanly. Key-free and idempotent on
an empty / already-versioned store (the CI cycle runs without APX_ENCRYPTION_KEY).
"""

from __future__ import annotations

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from apx.adapters.store_postgres.backfill import (
    backfill_case_theory_versions,
    case_theory_version_id,
)
from apx.adapters.store_postgres.crypto_types import cipher
from apx.adapters.store_postgres.models import CaseTheoryVersion


def _pre_0023_schema(engine) -> None:  # noqa: ANN001
    """``matter_scope`` as it exists before this migration, plus the empty version table it adds."""
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE matter_scope (tenant TEXT, matter TEXT, scope TEXT, "
            "submitted_pieces INTEGER, case_theory TEXT, PRIMARY KEY (tenant, matter))"))
    CaseTheoryVersion.__table__.create(engine)


def _seed_matter(engine, tenant: str, matter: str, theory: str | None) -> None:  # noqa: ANN001
    ct = cipher().encrypt(theory, aad="matter_scope.case_theory") if theory is not None else None
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO matter_scope (tenant, matter, scope, submitted_pieces, case_theory) "
                 "VALUES (:t, :m, 'w', 0, :ct)"),
            {"t": tenant, "m": matter, "ct": ct})


def test_backfill_seeds_version_1_readable_under_the_new_aad(tmp_path) -> None:  # noqa: ANN001
    engine = create_engine(f"sqlite:///{tmp_path / 'apx.db'}", future=True)
    _pre_0023_schema(engine)
    _seed_matter(engine, "t", "m", "contestation licenciement")
    with engine.begin() as conn:
        assert backfill_case_theory_versions(conn) == 1
    with Session(engine) as s:  # the ORM reads it → proving re-encryption under the new column AAD
        rows = s.scalars(select(CaseTheoryVersion)).all()
    assert len(rows) == 1
    assert rows[0].version_no == 1 and rows[0].text == "contestation licenciement"
    assert rows[0].actor == "system:backfill"  # the backfill principal (author unrecoverable)
    assert rows[0].id == case_theory_version_id("t", "m", 1, "contestation licenciement")


def test_backfill_is_idempotent(tmp_path) -> None:  # noqa: ANN001
    engine = create_engine(f"sqlite:///{tmp_path / 'apx.db'}", future=True)
    _pre_0023_schema(engine)
    _seed_matter(engine, "t", "m", "x")
    with engine.begin() as conn:
        assert backfill_case_theory_versions(conn) == 1
        assert backfill_case_theory_versions(conn) == 0  # a matter already versioned is skipped


def test_backfill_skips_a_matter_with_no_theory_and_is_noop_when_empty(tmp_path) -> None:  # noqa: ANN001
    engine = create_engine(f"sqlite:///{tmp_path / 'apx.db'}", future=True)
    _pre_0023_schema(engine)
    _seed_matter(engine, "t", "none", None)  # no theory → not seeded
    with engine.begin() as conn:
        assert backfill_case_theory_versions(conn) == 0
    with Session(engine) as s:
        assert s.scalars(select(CaseTheoryVersion)).all() == []
