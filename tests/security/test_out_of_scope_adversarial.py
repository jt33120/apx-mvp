"""The Chinese-wall adversarial suite (Story 3.3, AD-12/AD-13/AD-14, FR-14).

The leak this proves impossible has no error message: a cross-*matter* result is a
professional-conduct violation that looks exactly like a correct answer. So the wall is proven
*adversarially* — the out-of-scope *matter* holds the deliberately **best** matches (every exact
term; on a real DB, a nearer vector), and a query under the *other* scope must return **zero**
out-of-scope results **and zero** out-of-scope metadata (ids, snippets, filenames, counts, the
*denominator*). Over BOTH engines, plus the failure register.

- **AC3/AC4 — deterministic + register:** a real end-to-end round-trip on SQLite (over
  ``full_text_normalized`` / the ``matter_scope`` join), asserting zero out-of-scope leak and a
  *denominator* computed within scope.
- **AC3 — semantic:** the compiled statement carries the ``matter_scope`` pre-filter *before* the
  top-``k`` — an out-of-scope chunk, however similar, is filtered before selection (proven always);
  a Postgres-gated behavioural test plants a **nearer** out-of-scope chunk and asserts exclusion.
- **AC5 — mutating:** revoke mid-session / grant mid-run — the wall moves on the next query, its old
  position never leaks (scope is re-resolved live, AD-13).
- **AC6 — fail-closed:** an empty scope reads an empty *corpus*, for an admin and a system identity
  alike (the engines take no ``is_admin`` — no implicit super-user corpus read, AD-12).
"""

from __future__ import annotations

import os
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import sessionmaker

from apx.adapters.store_postgres.models import Base, Failure
from apx.adapters.store_postgres.semantic_query import semantic_search_stmt
from apx.adapters.store_postgres.store import SqlStore
from apx.core.app.ingest import IngestedFailure, IngestedPiece, IngestionResult
from apx.core.app.read.deterministic import search_exhaustive
from apx.core.app.read.semantic import search_semantic
from apx.core.domain.failures import ErrorClass

TENANT = "cabinet"
S_IN, S_OUT = "wall-in", "wall-out"          # two RBAC scopes in one tenant
M_IN, M_OUT = "matter-in", "matter-out"      # a matter under each


def _piece(pid: str, matter: str, full_text: str, *, extraction: str = "text") -> IngestedPiece:
    return IngestedPiece(
        id=pid, matter=matter, tenant=TENANT, content_hash=pid, text_key=pid,
        provenance_path=f"/{matter}/{pid}.txt", custodian="c", extraction_method=extraction,
        extractor_version="v", schema_version="s", ingestion_timestamp=datetime.now(UTC),
        full_text=full_text, text_version="v")


def _fail(pid: str, matter: str) -> IngestedFailure:
    return IngestedFailure(
        filename=f"{pid}.pdf", submitted_path=f"/{matter}/{pid}.pdf", matter=matter, tenant=TENANT,
        error_class=ErrorClass.PASSWORD_PROTECTED, detail="x", custodian="c")


@pytest.fixture
def store() -> SqlStore:
    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine)
    s = SqlStore(sessionmaker(bind=engine, future=True))
    # In-scope matter: ONE piece carrying the query term.
    s.save(IngestionResult(pieces=[_piece("in1", M_IN, "le contrat de cession de brevet")]),
           scope=S_IN, actor="admin")
    # Out-of-scope matter: the deliberately BEST/most matches for the same term.
    s.save(IngestionResult(pieces=[
        _piece("out1", M_OUT, "le contrat de cession de brevet"),
        _piece("out2", M_OUT, "une autre cession de brevet"),
    ]), scope=S_OUT, actor="admin")
    return s


# ── AC3 + AC4: the deterministic engine leaks no out-of-scope result, metadata or denominator ──
def test_deterministic_engine_leaks_no_out_of_scope_result_or_metadata(store: SqlStore) -> None:
    res = search_exhaustive(tenant=TENANT, scopes={S_IN}, query="cession", reader=store)
    assert {r.piece_id for r in res.results} == {"in1"}         # only the in-scope match
    assert {r.matter for r in res.results} == {M_IN}            # no out-of-scope matter
    blob = " ".join(f"{r.piece_id} {r.matter} {r.snippet}" for r in res.results)
    assert "out1" not in blob and "out2" not in blob and M_OUT not in blob  # no out-of-scope id
    # AC4: the denominator counts ONLY the in-scope corpus (1), never in-scope + out-of-scope (3)
    assert res.denominator.in_corpus == 1


def test_deterministic_ocr_share_is_computed_within_scope_only() -> None:
    # AC4 metadata channel: the OCR share must count only in-scope pièces, else it leaks the
    # existence of out-of-scope OCR material. In-scope is all text (share 0.0); the out-of-scope
    # matter holds an OCR pièce — a tenant-wide share would be > 0 and leak.
    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine)
    s = SqlStore(sessionmaker(bind=engine, future=True))
    s.save(IngestionResult(pieces=[_piece("in1", M_IN, "acte de cession")]),
           scope=S_IN, actor="admin")
    s.save(IngestionResult(pieces=[
        _piece("out-ocr", M_OUT, "acte de cession", extraction="tesseract")]),
        scope=S_OUT, actor="admin")
    res = search_exhaustive(tenant=TENANT, scopes={S_IN}, query="cession", reader=s)
    assert {r.piece_id for r in res.results} == {"in1"}    # the OCR out-of-scope match is excluded
    assert res.ocr_share == 0.0                            # in-scope all text — not 1/2 tenant-wide


def test_deterministic_engine_finds_every_in_scope_match_when_the_scope_is_held(
        store: SqlStore) -> None:
    # the out-of-scope matter, queried in ITS scope, returns both — proving the exclusion above was
    # the wall, not a failure to match.
    res = search_exhaustive(tenant=TENANT, scopes={S_OUT}, query="cession", reader=store)
    assert {r.piece_id for r in res.results} == {"out1", "out2"}
    assert res.denominator.in_corpus == 2


# ── AC3: the failure register (register_all, fixed to a query pre-filter) leaks nothing ────────
def test_register_all_never_returns_an_out_of_scope_failure(store: SqlStore) -> None:
    store.save(IngestionResult(failures=[_fail("in-f", M_IN)]), scope=S_IN, matter=M_IN,
               tenant=TENANT)
    # the out-of-scope matter has MORE / worse failures — still never disclosed
    store.save(IngestionResult(failures=[_fail("out-f1", M_OUT), _fail("out-f2", M_OUT)]),
               scope=S_OUT, matter=M_OUT, tenant=TENANT)
    entries = store.register_all(TENANT, {S_IN}, is_admin=False)
    assert {e.matter for e in entries} == {M_IN}                # zero out-of-scope
    assert all("out" not in e.filename for e in entries)        # no out-of-scope filename


class _NeverEmbedder:
    """An embedder that fails if called — proving the semantic engine short-circuits an empty scope
    BEFORE it embeds (fail-closed, AD-12), never reaching the model or the DB."""

    dimensions = 1024

    def embed(self, texts: list[str]) -> list[list[float]]:
        raise AssertionError("an empty scope must read nothing without embedding")


class _NeverReader:
    def search_semantic(self, **_: object) -> list:
        raise AssertionError("an empty scope must read nothing without querying")


# ── AC6: fail-closed with no scope, for administrative AND system identities alike ────────────
def test_both_engines_read_empty_with_no_scope_regardless_of_identity(store: SqlStore) -> None:
    # neither engine takes an is_admin — there is structurally no super-user corpus read (AD-12).
    det = search_exhaustive(tenant=TENANT, scopes=set(), query="cession", reader=store)
    assert det.results == () and det.denominator.in_corpus == 0
    # the semantic engine short-circuits an empty scope before embedding or querying
    sem = search_semantic(
        tenant=TENANT, scopes=set(), query="cession", embedder=_NeverEmbedder(),
        reader=_NeverReader(), k=10, config_get=lambda _key: 0.3)
    assert sem.results == ()


def test_register_all_no_scope_admin_sees_only_matterless_system_sees_nothing(
        store: SqlStore) -> None:
    store.save(IngestionResult(failures=[_fail("in-f", M_IN)]), scope=S_IN, matter=M_IN,
               tenant=TENANT)
    # an undetermined-matter (matter IS NULL) failure — inserted directly (arises pre-attribution)
    with store._sf() as s, s.begin():
        s.add(Failure(
            id="undet-1", tenant=TENANT, matter=None, filename="mystery.bin",
            submitted_path="/mystery.bin", error_class="unknown", cardinality="one",
            resolution_state="open", timestamp=datetime.now(UTC)))
    # admin, NO scope → only the matter-less entry (never a scoped matter's)
    admin = store.register_all(TENANT, set(), is_admin=True)
    assert [e.matter for e in admin] == [None]
    assert all(e.matter is None for e in admin)
    # any ordinary/non-admin identity with no scope → an empty register, fail closed. (The AD-48
    # tenant-bound MAINTENANCE principal — which may read a whole partition for aggregates without
    # producing a result set — is a distinct, deferred guarantee; not exercised here.)
    assert store.register_all(TENANT, set(), is_admin=False) == []


# ── AC5: the mutating suite — revoke moves the wall immediately, its old position never leaks ──
def test_revoke_moves_the_wall_immediately_and_the_old_scope_never_leaks(store: SqlStore) -> None:
    uid = store.create_user(TENANT, "a@a.test", "password1", "Avocat A", {S_IN})
    _, scopes = store.identity(uid)
    assert scopes == {S_IN}
    before = search_exhaustive(tenant=TENANT, scopes=scopes, query="cession", reader=store)
    assert {r.piece_id for r in before.results} == {"in1"}          # sees the in-scope matter
    store.revoke_scope(TENANT, "boss", uid, S_IN)                   # audited wall move
    _, scopes_after = store.identity(uid)                          # scope re-resolved live (AD-13)
    assert scopes_after == set()
    after = search_exhaustive(tenant=TENANT, scopes=scopes_after, query="cession", reader=store)
    assert after.results == ()                                      # wall moved on the next query


def test_grant_mid_run_opens_the_wall_only_after_the_grant(store: SqlStore) -> None:
    uid = store.create_user(TENANT, "b@b.test", "password1", "Avocat B", set())
    before = search_exhaustive(
        tenant=TENANT, scopes=store.identity(uid)[1], query="cession", reader=store)
    assert before.results == ()                                    # no scope yet → nothing
    store.grant_scope(TENANT, "boss", uid, S_IN)
    after = search_exhaustive(
        tenant=TENANT, scopes=store.identity(uid)[1], query="cession", reader=store)
    assert {r.piece_id for r in after.results} == {"in1"}          # the grant opens it, next query


# ── AC3 (semantic): the scope is a pre-filter applied BEFORE the top-k ─────────────────────────
def test_semantic_scope_pre_filter_precedes_the_top_k() -> None:
    stmt = semantic_search_stmt(
        tenant=TENANT, scopes={S_IN}, query_vector=[0.1, 0.2, 0.3, 0.4], k=5, min_similarity=0.0)
    sql = str(stmt.compile(dialect=postgresql.dialect())).lower()
    assert "join matter_scope" in sql
    assert "matter_scope.scope in" in sql                          # the scope PRE-filter (AD-13)
    assert "matter_scope.matter = chunk.matter" in sql
    assert "matter_scope.tenant = chunk.tenant" in sql             # tenant on both sides (AD-12)
    # The scope predicate lives in the WHERE of the SAME single SELECT that carries the ORDER BY
    # <=> … LIMIT — one flat statement, no subquery that could re-rank after filtering. By SQL
    # semantics a WHERE filters rows before ORDER BY/LIMIT, so an out-of-scope chunk (however
    # similar) never enters the top-k. (The behavioural proof of that exclusion is the Postgres-
    # gated test below; the textual index<limit check would be tautological, so it is not made.)
    assert "select" in sql and sql.count("select") == 1 and "limit" in sql


# ── AC3 (semantic, behavioural): a NEARER out-of-scope chunk is excluded — Postgres only ──────
_URL = os.environ.get("DATABASE_URL", "")
_IS_PG = _URL.startswith("postgresql")


@pytest.mark.skipif(not _IS_PG, reason="no PostgreSQL DATABASE_URL — CI runs this")
def test_semantic_engine_excludes_a_nearer_out_of_scope_chunk_on_postgres() -> None:
    from apx.adapters.store_postgres.chunk_writer import ChunkStore
    from apx.adapters.store_postgres.models import EMBEDDING_DIM, MatterScope, Piece
    from apx.core.domain.identity import piece_id
    from apx.core.domain.payload import PayloadRecord

    schema, cfg = "1", "c1"
    ts = datetime(2026, 7, 29, tzinfo=UTC)
    engine = create_engine(_URL, future=True)
    with engine.begin() as c:
        c.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    sf = sessionmaker(bind=engine, future=True)

    def _seed_piece(matter: str, scope: str) -> str:
        pid = piece_id(TENANT, f"h-{matter}", matter)
        with sf() as s, s.begin():
            s.add(MatterScope(matter=matter, tenant=TENANT, scope=scope))
            s.add(Piece(
                id=pid, tenant=TENANT, matter=matter, content_hash=f"h-{matter}", text_key="tk",
                provenance_path="/a.pdf", custodian="me", extraction_method="text",
                extractor_version="v", schema_version=schema, ingestion_timestamp=ts,
                piece_date=None, piece_date_status="undetermined", full_text="le bail",
                text_identity="ti", text_version="tv"))
        return pid

    def _payload(pid: str, matter: str) -> PayloadRecord:
        return PayloadRecord(
            tenant=TENANT, matter=matter, source_piece_id=pid, content_hash=f"h-{matter}",
            provenance_path="/a.pdf", custodian="me", extraction_method="text",
            extractor_version="v", schema_version=schema, chunking_config_version=cfg,
            ingestion_timestamp=ts, position=0,
            full_text="le bail", text_identity="ti", text_version="tv", piece_date=None,
            piece_date_status="undetermined")

    in_pid = _seed_piece(M_IN, S_IN)
    out_pid = _seed_piece(M_OUT, S_OUT)
    cs = ChunkStore(sf, schema_version=schema, chunking_config_version=cfg)
    query = [0.0] * EMBEDDING_DIM
    query[0] = 1.0
    far = [0.0] * EMBEDDING_DIM
    far[1] = 1.0
    # in-scope chunk is FAR from the query; out-of-scope chunk IS the query (nearest) — yet excluded
    cs.write_chunk(_payload(in_pid, M_IN), rbac_scope=S_IN, vector=far,
                   model_id="BAAI/bge-m3", model_version="bge-m3-1.0")
    cs.write_chunk(_payload(out_pid, M_OUT), rbac_scope=S_OUT, vector=query,
                   model_id="BAAI/bge-m3", model_version="bge-m3-1.0")

    store = SqlStore(sf)
    hits = store.search_semantic(
        tenant=TENANT, scopes={S_IN}, query_vector=query, k=5, min_similarity=0.0)
    ids = {h.piece_id for h in hits}
    assert out_pid not in ids           # the NEARER out-of-scope chunk is excluded by the wall
    assert ids == {in_pid}              # only the in-scope (farther) chunk survives
