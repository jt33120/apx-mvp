"""Continuity over HTTP (Story 5.9, FR-53): the refusal, and the check on the export's face.

Two boundary properties, and both are about what a caller is TOLD.

**The refusal (FR-53's fourth consequence).** *Where the audit store cannot be written at all, the
application refuses the affected actions rather than degrading to an unaudited mode; read-only
functions may continue.* A write path that answered 500 would read as *the server broke* rather than
as *the act was refused and nothing was written*, and a write path that answered 200 would be the
unaudited mode the requirement forbids. The handler is registered once, for every route — the
difference between a property and a habit.

**The check on the face (AC-6).** The export carries, per chain, the continuity check RUN OVER THE
DOCUMENT: the reader's own recomputation, the comparison against the outside witness, and whether
the two agree with the verdict the producer printed. It is computed by the same pure function a
recipient of the payload can call, which is the point of it being there at all.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from apx.adapters.store_postgres.models import Base, TruncationMarker
from apx.adapters.store_postgres.store import SqlStore
from apx.api import app as app_module
from apx.api.app import app
from apx.core.app.ingest import IngestedPiece, IngestionResult

SECRET = "test-secret"
TENANT, WALL, MATTER = "t", "w", "affaire-a"
_AUDIT_TABLES = ("audit_record", "audit_chain_head")


@pytest.fixture(autouse=True)
def _reset_state():  # noqa: ANN201
    app_module._store.cache_clear()
    app_module._login_limiter._fails.clear()
    yield
    app_module._store.cache_clear()
    app_module._login_limiter._fails.clear()


def _prepare(tmp_path: Path, monkeypatch) -> tuple[SqlStore, object]:  # noqa: ANN001
    url = f"sqlite:///{tmp_path / 'apx.db'}"
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("APX_SECRET_KEY", SECRET)
    return SqlStore(sessionmaker(bind=engine, future=True)), engine


def _login(c: TestClient, email: str, pw: str = "pw12345678") -> None:
    assert c.post(
        "/api/login", json={"tenant": TENANT, "email": email, "password": pw}
    ).status_code == 200


def _refuse_audit_writes(engine) -> object:  # noqa: ANN001
    """Make the audit store unwritable at the DBAPI edge — the shape of a revoked INSERT or a full
    disk, and NOT of a collision or a lock wait, which AD-22 says are a different state."""
    def _refuse(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001, ANN202
        lowered = statement.lower().lstrip()
        if lowered.startswith(("insert", "update")) and any(
                table in lowered for table in _AUDIT_TABLES):
            raise OperationalError(statement, parameters, Exception("audit store is unwritable"))

    event.listen(engine, "before_cursor_execute", _refuse)
    return _refuse


# ── the refusal (AC-2) ────────────────────────────────────────────────────────────────────────

def test_a_write_is_refused_with_503_and_a_sentence_when_the_record_cannot_be_written(
    tmp_path: Path, monkeypatch,  # noqa: ANN001
) -> None:
    store, engine = _prepare(tmp_path, monkeypatch)
    store.create_user(TENANT, "patron@t.fr", "pw12345678", "Le patron", {WALL}, is_admin=True)
    subject = store.create_user(TENANT, "greffe@t.fr", "pw12345678", "Le greffe", set())
    with TestClient(app) as c:
        _login(c, "patron@t.fr")
        # The API's own store is a different SqlStore over the same file; the fault is installed on
        # the engine the request will use, so route it through the cached store's own engine.
        listener = _refuse_audit_writes(app_module._store()._sf.kw["bind"])
        try:
            r = c.post(f"/api/admin/users/{subject}/grant", json={"scope": WALL})
        finally:
            event.remove(app_module._store()._sf.kw["bind"], "before_cursor_execute", listener)
    assert r.status_code == 503, r.text
    body = r.json()
    assert "journal d'audit" in body["sentence_fr"]
    assert "rien n'a été enregistré" in body["sentence_fr"].lower()
    # …and the grant did not happen
    assert WALL not in store.scopes_for(subject)


def test_reads_keep_answering_while_writes_are_refused(
    tmp_path: Path, monkeypatch,  # noqa: ANN001
) -> None:
    """*Read-only functions may continue.* A product that stopped answering questions because it
    could not write would have turned a durability condition into an outage."""
    store, engine = _prepare(tmp_path, monkeypatch)
    store.create_user(TENANT, "patron@t.fr", "pw12345678", "Le patron", {WALL}, is_admin=True)
    with TestClient(app) as c:
        _login(c, "patron@t.fr")
        bind = app_module._store()._sf.kw["bind"]
        listener = _refuse_audit_writes(bind)
        try:
            assert c.get("/api/admin/dr").status_code == 200
            assert c.get("/api/admin/users").status_code == 200
            assert c.get("/api/admin/config").status_code == 200
            assert c.get("/api/matters").status_code == 200
        finally:
            event.remove(bind, "before_cursor_execute", listener)


# ── the disaster-recovery surface reports the whole loss (AC-9) ────────────────────────────────

def test_the_dr_status_names_the_kind_the_chains_and_the_total(
    tmp_path: Path, monkeypatch,  # noqa: ANN001
) -> None:
    """The administrator signing the FR-25 reason used to be shown the WORST chain's pair and never
    the total nor which *matters* fell — the flattering half of data the store already held."""
    store, _ = _prepare(tmp_path, monkeypatch)
    store.create_user(TENANT, "patron@t.fr", "pw12345678", "Le patron", {WALL}, is_admin=True)
    with store._sf() as s, s.begin():
        s.add(TruncationMarker(
            tenant=TENANT, detected_at=datetime.now(UTC), journal_seq=9, live_seq=4,
            kind=TruncationMarker.KIND_BOTH, chains="t\x1faffaire-a:9->4", entries_lost=5,
            forks="t\x1faffaire-b@3"))
    with TestClient(app) as c:
        _login(c, "patron@t.fr")
        body = c.get("/api/admin/dr").json()
    truncation = body["truncation"]
    assert truncation["active"] and truncation["kind"] == "both"
    assert truncation["entries_lost"] == 5
    assert "affaire-a" in truncation["chains"] and "affaire-b" in truncation["forks"]
    assert body["journal_gaps"]["gaps"] == 0 and body["journal_degraded"] is False


def test_a_recorded_journal_gap_keeps_the_alarm_on_after_a_restart(
    tmp_path: Path, monkeypatch,  # noqa: ANN001
) -> None:
    """The alarm used to be a boolean in one process's memory. A fresh API process must still see
    that a head went unwitnessed — the condition that makes a later truncation undetectable."""
    from apx.adapters.store_postgres.models import JournalGap

    store, _ = _prepare(tmp_path, monkeypatch)
    store.create_user(TENANT, "patron@t.fr", "pw12345678", "Le patron", {WALL}, is_admin=True)
    with store._sf() as s, s.begin():
        s.add(JournalGap(
            id="g1", tenant=TENANT, scope=TENANT, seq=41, chain="a" * 64,
            at=datetime.now(UTC), detail="[Errno 28] No space left on device"))
    with TestClient(app) as c:
        _login(c, "patron@t.fr")
        body = c.get("/api/admin/dr").json()
    assert body["journal_gaps"]["gaps"] == 1 and body["journal_gaps"]["last_seq"] == 41
    assert body["journal_degraded"] is True, (
        "a persisted gap must raise the alarm even in a process that never saw the failure")


# ── the check on the export's face (AC-6) ─────────────────────────────────────────────────────

def test_the_export_carries_the_continuity_check_run_on_the_document(
    tmp_path: Path, monkeypatch,  # noqa: ANN001
) -> None:
    """FR-53: *a continuity check runs on export and its result appears on the export's face*. The
    payload carries, per chain, the verdict a reader recomputes FROM THE DOCUMENT — the same pure
    call whoever holds the payload can make — not a verdict only the server can produce."""
    from apx.core.domain.head_journal import HeadJournal

    store, engine = _prepare(tmp_path, monkeypatch)
    monkeypatch.setenv("APX_HEAD_JOURNAL", str(tmp_path / "outside" / "heads.journal"))
    store = SqlStore(
        sessionmaker(bind=engine, future=True),
        head_journal=HeadJournal(tmp_path / "outside" / "heads.journal"))
    store.create_user(TENANT, "claire@t.fr", "pw12345678", "Claire Fontaine", {WALL})
    store.save(IngestionResult(pieces=[IngestedPiece(
        id="p1", matter=MATTER, tenant=TENANT, content_hash="h" * 16, text_key="k" * 16,
        provenance_path="/dossier/p1.pdf", custodian="Me Martin", extraction_method="text",
        extractor_version="v1", schema_version="slice-a",
        ingestion_timestamp=datetime.now(UTC), full_text="le contrat", text_version="v")]),
        WALL, actor="Claire Fontaine", matter=MATTER, tenant=TENANT)
    with TestClient(app) as c:
        _login(c, "claire@t.fr")
        r = c.post(f"/api/matters/{MATTER}/record/export?tier=full")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["trail"], "§9 must carry the entries the verdict is computed over"
    readings = {x["chain_scope"]: x for x in body["continuity"]}
    own = readings[MATTER]
    assert own["recomputable"] is True and own["verified"] is True
    assert own["agrees_with_producer"] is True and own["sound"] is True
    assert own["witness_state"] == "current"
    assert "se vérifie de bout en bout" in own["sentence_fr"]


def test_a_numbers_only_export_says_the_continuity_is_the_producers_word(
    tmp_path: Path, monkeypatch,  # noqa: ANN001
) -> None:
    store, engine = _prepare(tmp_path, monkeypatch)
    store.create_user(TENANT, "claire@t.fr", "pw12345678", "Claire Fontaine", {WALL})
    store.save(IngestionResult(), WALL, actor="Claire Fontaine", matter=MATTER, tenant=TENANT)
    with TestClient(app) as c:
        _login(c, "claire@t.fr")
        body = c.post(f"/api/matters/{MATTER}/record/export?tier=numbers-only").json()
    assert body["trail"] == [], "numbers-only carries no entry details (FR-26 §11)"
    own = next(x for x in body["continuity"] if x["chain_scope"] == MATTER)
    assert own["recomputable"] is False and own["verified"] is None
    assert own["agrees_with_producer"] is None and own["sound"] is False
    assert "affirmée par le producteur" in own["sentence_fr"]
