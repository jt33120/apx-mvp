"""The two truth-status-carrying search endpoints over HTTP (Story 3.4, FR-15).

Each engine has its OWN endpoint and its OWN response model — never combined — and each SERIALISES
its truth status: `/api/search/suggestive` ("suggestive", a wording that can never read as
completeness) and `/api/search/exhaustive` ("exhaustive", carrying the scoped denominator + the
AD-42 qualifications). Running or exporting a search is an AUDITED act. The exhaustive engine runs
for real on SQLite; the semantic engine's vector query is PostgreSQL-only, so its endpoint is
proven here through the fail-closed empty-scope path (its behavioural run is pg-gated elsewhere).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from apx.adapters.store_postgres.models import AuditRecord, Base
from apx.adapters.store_postgres.store import SqlStore
from apx.api import app as app_module
from apx.api.app import app
from apx.core.app.ingest import IngestedPiece, IngestionResult

SECRET = "test-secret"
TENANT, WALL = "t", "wall-a"


@pytest.fixture(autouse=True)
def _reset_state():
    app_module._store.cache_clear()
    app_module._login_limiter._fails.clear()
    yield
    app_module._store.cache_clear()
    app_module._login_limiter._fails.clear()


class _FakeEmbedder:
    """A stand-in for the BGE-M3 embedder so the suggestive endpoint's empty-scope path never loads
    a model. The real vector query is PostgreSQL-only; this test exercises the serialisation."""

    dimensions = 1024

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * self.dimensions for _ in texts]


def _prepare(tmp_path: Path, monkeypatch) -> SqlStore:
    url = f"sqlite:///{tmp_path / 'apx.db'}"
    Base.metadata.create_all(create_engine(url))
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("APX_SECRET_KEY", SECRET)
    monkeypatch.setattr(app_module, "_embedder", _FakeEmbedder)
    return SqlStore(sessionmaker(bind=create_engine(url), future=True))


def _piece(pid: str, full_text: str, matter: str = "m") -> IngestedPiece:
    return IngestedPiece(
        id=pid, matter=matter, tenant=TENANT, content_hash=pid, text_key=pid,
        provenance_path=f"/{pid}.txt", custodian="c", extraction_method="text",
        extractor_version="v", schema_version="s", ingestion_timestamp=datetime.now(UTC),
        full_text=full_text, text_version="v")


def _login(c: TestClient, email: str = "me@cab.fr", pw: str = "password1") -> None:
    r = c.post("/api/login", json={"tenant": TENANT, "email": email, "password": pw})
    assert r.status_code == 200, r.text


def _audit_actions(store: SqlStore) -> list[str]:
    with store._sf() as s:
        return list(s.scalars(select(AuditRecord.action).where(AuditRecord.tenant == TENANT)))


def test_exhaustive_endpoint_serialises_truth_status_and_denominator(tmp_path, monkeypatch) -> None:
    store = _prepare(tmp_path, monkeypatch)
    store.save(IngestionResult(pieces=[_piece("p1", "acte de cession de fonds")]),
               scope=WALL, actor="sys")
    store.create_user(TENANT, "me@cab.fr", "password1", "Me Durand", {WALL})
    c = TestClient(app)
    _login(c)
    r = c.get("/api/search/exhaustive", params={"q": "cession"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["truth_status"] == "exhaustive"                 # the status is on the wire (FR-15)
    assert body["denominator"]["in_corpus"] == 1              # the scoped seven-field denominator
    assert set(body["denominator"]) == {                      # all seven serialised (AD-38)
        "submitted_pieces", "in_corpus", "open_register_entries",
        "overridden_register_entries",                        # Story 5.6 — FR-25's third term
        "excluded_as_noise", "retired", "unknown_cardinality_entries"}
    assert body["normalization"] == "fr-fold-v1"
    assert [h["piece_id"] for h in body["results"]] == ["p1"]
    assert "register_hits" in body and body["ocr_share"] == 0.0


def test_the_query_is_an_audited_act_with_its_truth_status(tmp_path, monkeypatch) -> None:
    store = _prepare(tmp_path, monkeypatch)
    store.save(IngestionResult(pieces=[_piece("p1", "un bail commercial")]),
               scope=WALL, actor="sys")
    store.create_user(TENANT, "me@cab.fr", "password1", "Me Durand", {WALL})
    c = TestClient(app)
    _login(c)
    assert c.get("/api/search/exhaustive", params={"q": "bail"}).status_code == 200
    assert _audit_actions(store).count("search") == 1           # one audit entry per query (FR-15)


def test_exhaustive_export_carries_the_denominator_on_its_face(tmp_path, monkeypatch) -> None:
    store = _prepare(tmp_path, monkeypatch)
    store.save(IngestionResult(pieces=[_piece("p1", "clause de cession")]), scope=WALL, actor="sys")
    store.create_user(TENANT, "me@cab.fr", "password1", "Me Durand", {WALL})
    c = TestClient(app)
    _login(c)
    r = c.get("/api/search/exhaustive/export", params={"q": "introuvable-xyz"})
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/html")    # a court-readable doc, not JSON
    doc = r.text
    assert "Recherche exhaustive" in doc                        # the truth status on the face
    assert "Aucune occurrence" in doc                           # an honest absence, not "not found"
    assert "indexé de ce périmètre" in doc                     # the scoped denominator, in words
    assert "@media print" in doc                                # print-ready, read w/o the system
    assert _audit_actions(store).count("export-search") == 1    # the export is audited


def test_suggestive_endpoint_serialises_truth_status_and_non_completeness_wording(
        tmp_path, monkeypatch) -> None:
    # a caller with NO scope: the semantic engine short-circuits (fail-closed) BEFORE the pg-only
    # vector query, so the serialisation is exercised on SQLite. The truth status is on the wire.
    store = _prepare(tmp_path, monkeypatch)
    store.create_user(TENANT, "me@cab.fr", "password1", "Me Durand", set())   # no scope
    c = TestClient(app)
    _login(c)
    r = c.get("/api/search/suggestive", params={"q": "indemnisation", "k": 20})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["truth_status"] == "suggestive"                 # the status is on the wire (FR-15)
    assert body["results"] == [] and body["k"] == 20
    assert "denominator" not in body                            # suggestive has NO denominator
    assert "top 20 of the corpus by similarity" in body["wording"]   # cannot read as completeness


def test_suggestive_export_carries_the_non_completeness_wording(tmp_path, monkeypatch) -> None:
    store = _prepare(tmp_path, monkeypatch)
    store.create_user(TENANT, "me@cab.fr", "password1", "Me Durand", set())
    c = TestClient(app)
    _login(c)
    r = c.get("/api/search/suggestive/export", params={"q": "indemnisation"})
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/html")
    assert "ne constitue pas une preuve" in r.text             # cannot read as completeness
    assert "Suggestions — liste non exhaustive" in r.text
    assert _audit_actions(store).count("export-search") == 1


def test_no_scope_exhaustive_is_empty_and_fail_closed(tmp_path, monkeypatch) -> None:
    store = _prepare(tmp_path, monkeypatch)
    store.save(IngestionResult(pieces=[_piece("p1", "acte de cession")]), scope=WALL, actor="sys")
    store.create_user(TENANT, "me@cab.fr", "password1", "Me Durand", set())   # no scope
    c = TestClient(app)
    _login(c)
    body = c.get("/api/search/exhaustive", params={"q": "cession"}).json()
    assert body["results"] == [] and body["denominator"]["in_corpus"] == 0   # never all the corpus


def test_the_old_preview_endpoint_no_longer_claims_to_be_exhaustive() -> None:
    # the /api/search preview must not mislabel itself "exhaustive" — a capped preview isn't a proof
    doc = app_module.search_corpus.__doc__ or ""
    assert "PREVIEW" in doc and "TRUNCATES" in doc
    assert "search/suggestive" in doc and "search/exhaustive" in doc


def test_the_two_engines_are_distinct_endpoints_never_one_combined(tmp_path, monkeypatch) -> None:
    # the "never combined" guarantee is structural: two endpoints, two response models
    paths = {r.path for r in app.routes if "/api/search" in getattr(r, "path", "")}
    assert "/api/search/suggestive" in paths and "/api/search/exhaustive" in paths
    # and no single response model carries both engines' result shapes
    from apx.api.app import ExhaustiveOut, SuggestiveOut
    sug_fields, exh_fields = set(SuggestiveOut.model_fields), set(ExhaustiveOut.model_fields)
    assert "denominator" in exh_fields and "denominator" not in sug_fields
    assert "wording" in sug_fields and "wording" not in exh_fields
