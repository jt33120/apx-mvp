"""The one audited configuration surface (story 1.9, AD-25): set/get/get_all through the store,
each change validated and recorded with before/after (so it is reversible), a no-op writes no
phantom entry, an unknown key or wrong-typed value is refused, and a value written by a direct DB
edit that skipped the surface is detectable. SQLite everywhere.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from apx.adapters.store_postgres.models import AuditRecord, Base, TenantSetting
from apx.adapters.store_postgres.store import SqlStore
from apx.core.domain.config import CONFIG_SCHEMA, ConfigError, dumps_value

TENANT = "cabinet"


@pytest.fixture
def store() -> SqlStore:
    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine)
    return SqlStore(sessionmaker(bind=engine, future=True))


def test_get_returns_the_schema_default_until_set(store: SqlStore) -> None:
    assert store.get_config(TENANT, "interface_language") == "fr"
    assert store.get_config(TENANT, "off_corpus_refusal_enabled") is True


def test_set_config_persists_validates_and_audits_before_after(store: SqlStore) -> None:
    change = store.set_config(TENANT, "patron", "interface_language", "en")
    assert change.changed and change.before == "fr" and change.after == "en"
    assert store.get_config(TENANT, "interface_language") == "en"
    # the change is on the audit trail with before/after (reversible)
    with store._sf() as s:
        detail = s.scalar(
            select(AuditRecord.detail).where(AuditRecord.action == "config_changed"))
    assert '"before": "fr"' in detail and '"after": "en"' in detail


def test_reversibility_set_back_to_before_restores(store: SqlStore) -> None:
    first = store.set_config(TENANT, "patron", "interface_language", "en")
    store.set_config(TENANT, "patron", "interface_language", first.before)  # roll back
    assert store.get_config(TENANT, "interface_language") == "fr"


def test_setting_the_same_value_is_a_no_op_with_no_phantom_entry(store: SqlStore) -> None:
    store.set_config(TENANT, "patron", "interface_language", "en")
    again = store.set_config(TENANT, "patron", "interface_language", "en")
    assert again.changed is False
    with store._sf() as s:
        n = len(s.execute(
            select(AuditRecord).where(AuditRecord.action == "config_changed")).all())
    assert n == 1  # only the first change was recorded


def test_unknown_key_and_bad_value_are_refused_never_defaulted(store: SqlStore) -> None:
    with pytest.raises(ConfigError):
        store.set_config(TENANT, "patron", "nope", 1)
    with pytest.raises(ConfigError):
        store.set_config(TENANT, "patron", "mfa_required", "yes")  # not a bool
    # a refused write persisted nothing
    with store._sf() as s:
        assert s.execute(select(TenantSetting)).first() is None


def test_get_all_config_merges_defaults_with_stored_values(store: SqlStore) -> None:
    store.set_config(TENANT, "patron", "taxonomy", ["conclusions", "pièce"])
    by_key = {c.key: c for c in store.get_all_config(TENANT)}
    assert set(by_key) == set(CONFIG_SCHEMA)  # every declared key is present
    assert by_key["taxonomy"].value == ["conclusions", "pièce"]
    assert by_key["interface_language"].value == "fr"           # untouched → default
    assert by_key["cascade_stage3_max_share"].default == 0.5    # the default is surfaced


def test_retrieval_key_change_flags_staleness_on_the_record(store: SqlStore) -> None:
    store.set_config(TENANT, "patron", "chunking_config_version", "v2")  # affects_retrieval
    with store._sf() as s:
        detail = s.scalar(
            select(AuditRecord.detail).where(AuditRecord.action == "config_changed"))
    assert '"retrieval": true' in detail


def test_provenance_flags_a_direct_db_edit(store: SqlStore) -> None:
    # a value set through the surface is audited...
    store.set_config(TENANT, "patron", "interface_language", "en")
    # ...a value inserted straight into the table (bypassing set_config) is NOT
    with store._sf() as s, s.begin():
        s.add(TenantSetting(tenant=TENANT, key="model_provider", value=dumps_value("rogue")))
    prov = {p.key: p for p in store.config_provenance(TENANT)}
    assert prov["interface_language"].audited is True
    assert prov["model_provider"].audited is False  # detected as an unaudited direct edit


def test_provenance_flags_a_direct_edit_of_an_already_audited_key(store: SqlStore) -> None:
    store.set_config(TENANT, "patron", "interface_language", "en")
    with store._sf() as s, s.begin():  # tamper with the value straight in the table
        row = s.get(TenantSetting, {"tenant": TENANT, "key": "interface_language"})
        row.value = dumps_value("de-sneaked")
    prov = {p.key: p for p in store.config_provenance(TENANT)}
    assert prov["interface_language"].audited is False  # value no longer matches the audit


def test_provenance_flags_a_direct_delete_that_reverts_off_the_record(store: SqlStore) -> None:
    # a value set to non-default through the surface, then the row DELETEd straight in the DB —
    # the effective value silently reverts to the default (e.g. MFA turned back off), undetected
    # unless provenance reconciles the audit against the ABSENCE of a row (AD-25).
    store.set_config(TENANT, "patron", "mfa_required", True)
    with store._sf() as s, s.begin():
        s.delete(s.get(TenantSetting, {"tenant": TENANT, "key": "mfa_required"}))
    prov = {p.key: p for p in store.config_provenance(TENANT)}
    assert "mfa_required" in prov and prov["mfa_required"].audited is False


def test_provenance_degrades_not_500_on_an_undecryptable_audit_detail(store: SqlStore) -> None:
    # after a key rotation (or a tamper), a config_changed detail may not decrypt; provenance must
    # degrade like read_audit, not raise (the detection surface must survive the state it detects).
    store.set_config(TENANT, "patron", "interface_language", "en")
    with store._sf() as s, s.begin():  # overwrite the ciphertext with a non-decryptable token
        rec = s.execute(
            select(AuditRecord).where(AuditRecord.action == "config_changed")).scalars().one()
        s.execute(
            AuditRecord.__table__.update()
            .where(AuditRecord.id == rec.id)
            .values(detail="apxenc:v1:not-a-real-ciphertext"))
    prov = store.config_provenance(TENANT)  # must not raise
    assert isinstance(prov, list)


def test_out_of_range_and_non_finite_numeric_values_are_refused(store: SqlStore) -> None:
    for bad in (2.0, -1.0, 0.0, float("inf"), float("nan")):
        with pytest.raises(ConfigError):
            store.set_config(TENANT, "patron", "cascade_stage3_max_share", bad)
    ok = store.set_config(TENANT, "patron", "cascade_stage3_max_share", 0.9)
    assert ok.changed and store.get_config(TENANT, "cascade_stage3_max_share") == 0.9


def test_audit_chain_verifies_with_a_config_change_interleaved(store: SqlStore) -> None:
    # a config_changed row (matter=None, JSON detail, non-ASCII) sits on the per-tenant chain
    # among matter entries; the whole-chain verification must still recompute cleanly, and the
    # config entry must NOT appear in a matter's slice (it is matterless).
    from datetime import UTC, datetime

    from apx.core.app.ingest import IngestedPiece, IngestionResult

    piece = IngestedPiece(
        id="p1", matter="m1", tenant=TENANT, content_hash="c" * 8, text_key="t" * 8,
        provenance_path="/x.pdf", custodian="c", extraction_method="text", extractor_version="v",
        schema_version="s", ingestion_timestamp=datetime.now(UTC), full_text="le contrat",
        text_version="v")
    store.save(IngestionResult(pieces=[piece]), "wall", actor="a")
    store.set_config(TENANT, "patron", "taxonomy", ["pièce adverse"])  # non-ASCII JSON detail
    trail = store.read_audit("m1", TENANT, {"wall"})
    assert trail.verified is True
    assert all(e.action != "config_changed" for e in trail.entries)  # matterless → not in slice
