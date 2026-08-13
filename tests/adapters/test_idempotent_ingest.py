"""Idempotent ingestion with stable identity (Story 2.5; FR-4, AD-8/AD-9).

Through the real SQLite store: re-importing material neither duplicates nor destroys it, a file
in two folders is ONE pièce carrying both provenance paths, every custodian is kept as a set
(deduplication never collapses two into one), the same file in two matters is two pièces, and an
induced write conflict leaves exactly one copy without failing the job. The v1 defect — ids reused
from 1 so a second upload overwrote the first — is what these tests make impossible.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from apx.adapters.store_postgres.models import Base, Piece
from apx.adapters.store_postgres.store import SqlStore
from apx.core.app.ingest import IngestedPiece, IngestionResult
from apx.core.domain.dedup import text_key
from apx.core.domain.identity import content_hash, piece_id

TENANT, SCOPE = "t", "w"


@pytest.fixture
def store() -> SqlStore:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return SqlStore(sessionmaker(bind=engine, future=True))


def _piece(
    content: str, *, prov: str, cust: str = "Dupont", matter: str = "m",
    tenant: str = TENANT, ts: datetime | None = None,
) -> IngestedPiece:
    """An ingested pièce whose id is derived from (tenant, content, matter) — so two calls with the
    same content and matter are the SAME pièce, at possibly different paths/custodians."""
    ch = content_hash(content.encode())
    return IngestedPiece(
        id=piece_id(tenant, ch, matter), matter=matter, tenant=tenant, content_hash=ch,
        text_key=text_key(content), provenance_path=prov, custodian=cust,
        extraction_method="text", extractor_version="v", schema_version="s",
        ingestion_timestamp=ts or datetime.now(UTC), full_text=content, text_version="v")


def _corpus(store: SqlStore, matter: str = "m") -> int:
    return store.inventory(matter, TENANT, {SCOPE}).in_corpus


def _piece_row(store: SqlStore, pid: str) -> Piece:
    with store._sf() as s:
        return s.get(Piece, pid)


# ── AC2: re-import is a non-destructive no-op with a recognised-already-present line ───────────
def test_reimport_leaves_corpus_unchanged_prior_piece_unmodified_and_reports_already_present(
    store: SqlStore,
) -> None:
    first_ts = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)
    p = _piece("corps du contrat", prov="folderA/contrat.pdf", ts=first_ts)
    out1 = store.save(IngestionResult(pieces=[p]), actor="Me Dupont", scope=SCOPE)
    assert (out1.pieces_new, out1.pieces_already_present) == (1, 0)
    assert out1.pieces_written == 1  # back-compat alias == pieces_new
    corpus_before = _corpus(store)

    # a SECOND import of the same content — a later timestamp, the same path
    later = _piece("corps du contrat", prov="folderA/contrat.pdf",
                   ts=datetime(2026, 6, 6, 9, 0, tzinfo=UTC))
    out2 = store.save(IngestionResult(pieces=[later]), actor="Me Dupont", scope=SCOPE)

    assert (out2.pieces_new, out2.pieces_already_present) == (0, 1)  # recognised-already-present
    assert _corpus(store) == corpus_before                          # count unchanged (AD-40)
    row = _piece_row(store, p.id)
    # the prior pièce is UNMODIFIED — its first-seen timestamp survived (no merge/overwrite)
    assert row.ingestion_timestamp.replace(tzinfo=None) == first_ts.replace(tzinfo=None)
    assert row.provenance_path == "folderA/contrat.pdf"


# ── AC3: a file in two folders → one pièce, two provenance paths; custodians kept as a set ─────
def test_same_content_two_paths_is_one_piece_with_both_provenance_paths(store: SqlStore) -> None:
    a = _piece("meme document", prov="folderA/x.txt")
    b = _piece("meme document", prov="folderB/x.txt")  # same content, other path → same id
    assert a.id == b.id
    store.save(IngestionResult(pieces=[a, b]),
        actor="Me Dupont", scope=SCOPE)  # both in one job (a folder walk)
    assert _corpus(store) == 1                               # ONE pièce
    assert store.provenances(a.id) == {"folderA/x.txt", "folderB/x.txt"}  # both paths recorded


def test_custodians_are_unioned_across_imports_never_collapsed(store: SqlStore) -> None:
    # who held a document is the fact in issue in ordonnance 145 CPC work — dedup may never
    # collapse two custodians into one (AD-9 CUSTODIAN_LINK, unioned by every import job).
    store.save(IngestionResult(pieces=[_piece("dossier", prov="a.txt", cust="Dupont")]),
        actor="Me Dupont",
               scope=SCOPE)
    store.save(IngestionResult(pieces=[_piece("dossier", prov="b.txt", cust="Martin")]),
        actor="Me Dupont",
               scope=SCOPE)
    pid = _piece("dossier", prov="a.txt").id
    assert _corpus(store) == 1
    assert store.custodians(pid) == {"Dupont", "Martin"}     # the set, never collapsed
    assert store.provenances(pid) == {"a.txt", "b.txt"}

    # a THIRD import under an already-seen custodian does not duplicate the set member
    store.save(IngestionResult(pieces=[_piece("dossier", prov="c.txt", cust="Dupont")]),
        actor="Me Dupont",
               scope=SCOPE)
    assert store.custodians(pid) == {"Dupont", "Martin"}
    assert store.provenances(pid) == {"a.txt", "b.txt", "c.txt"}


# ── AC4: the same file in two matters is two pièces (matter is in identity; no cross-matter) ───
def test_same_file_in_two_matters_is_two_pieces(store: SqlStore) -> None:
    store.save(IngestionResult(pieces=[_piece("piece", prov="x.txt", matter="m-a")]),
        actor="Me Dupont", scope=SCOPE)
    store.save(IngestionResult(pieces=[_piece("piece", prov="x.txt", matter="m-b")]),
        actor="Me Dupont", scope=SCOPE)
    a = _piece("piece", prov="x.txt", matter="m-a")
    b = _piece("piece", prov="x.txt", matter="m-b")
    assert a.id != b.id                                     # distinct identities (matter is in id)
    assert _corpus(store, "m-a") == 1 and _corpus(store, "m-b") == 1
    # neither pièce leaks into the other's matter — the custodian/provenance sets are per-pièce
    assert store.provenances(a.id) == {"x.txt"} and store.provenances(b.id) == {"x.txt"}


# ── AC5 (failure path): an induced write conflict → exactly one copy, the job does not fail ────
def test_an_induced_write_conflict_leaves_exactly_one_copy_and_does_not_fail(
    store: SqlStore, monkeypatch: pytest.MonkeyPatch,
) -> None:
    r = IngestionResult(pieces=[_piece("unique", prov="x.txt")])
    store.save(r, actor="Me Dupont", scope=SCOPE)  # the first worker commits the one copy

    # Induce the exact race a second worker hits: its top existence check reads STALE (pièce not
    # visible yet), so it takes the INSERT path and collides on the unique key at flush — the
    # SAVEPOINT rolls back, the except RE-QUERIES, finds the row genuinely present, and absorbs it
    # (exactly one copy, no raise). Blind ONLY the first Piece.get (the stale top read); the
    # except's re-query must see the real committed row — that precision is the fix for swallowing
    # genuine integrity failures.
    real_get = Session.get
    piece_gets = {"n": 0}

    def _stale_first_piece_get(self, entity, ident, *a, **k):  # noqa: ANN001, ANN202
        if entity is Piece:
            piece_gets["n"] += 1
            if piece_gets["n"] == 1:
                return None  # the stale read a concurrent worker would have
        return real_get(self, entity, ident, *a, **k)

    monkeypatch.setattr(Session, "get", _stale_first_piece_get)
    out = store.save(r,
        actor="Me Dupont", scope=SCOPE)  # must NOT raise — the genuine duplicate is absorbed

    assert out.pieces_new == 0 and out.pieces_already_present == 1  # recognised, not duplicated
    with store._sf() as s:
        assert s.scalar(select(func.count()).select_from(Piece)) == 1  # exactly one copy


def test_a_genuine_integrity_failure_fails_loudly_never_a_silent_drop(store: SqlStore) -> None:
    # The precise-absorb fix (review): only a real duplicate is "already present". A malformed pièce
    # (a NULL in a NOT NULL column) must fail LOUDLY — never vanish, silently miscounted as
    # already-present with zero rows written. Without the fix the bare `except IntegrityError`
    # swallowed it and reported success.
    bad = _piece("boom", prov="x.txt")
    object.__setattr__(bad, "text_version", None)  # break a NOT NULL column (frozen dataclass)
    with pytest.raises(IntegrityError):
        store.save(IngestionResult(pieces=[bad]), actor="Me Dupont", scope=SCOPE)
    with store._sf() as s:
        assert s.scalar(select(func.count()).select_from(Piece)) == 0  # nothing partially written
