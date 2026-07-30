"""The deterministic exact-search query (Story 3.2, AD-20/AD-21). The corpus is folded at write time
into ``piece.full_text_normalized`` by the SAME ``normalize()`` the query uses, so a plain ``LIKE``
(no ``unaccent``) suffices — one normalisation implementation, no divergence, and the round-trip is
CI-testable on SQLite. CI asserts the shape (scope pre-filter, tenant both sides, no LIMIT, escaped
containment) AND a real round-trip (an accented document is found by an un-accented query)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import create_engine, func, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apx.adapters.store_postgres.deterministic_query import exact_search_stmt
from apx.adapters.store_postgres.models import Base, MatterScope, Piece
from apx.core.domain.normalization import normalize


def _sql(scopes=frozenset({"matter-a"}), *, query="etat") -> str:
    stmt = exact_search_stmt(tenant="t1", scopes=scopes, normalized_query=query)
    return str(stmt.compile(dialect=postgresql.dialect())).lower()


def test_scope_is_a_prefilter_tenant_qualified_on_both_sides() -> None:
    sql = _sql()
    assert "join matter_scope" in sql
    assert "matter_scope.scope in" in sql               # the scope PRE-filter
    assert "matter_scope.matter = piece.matter" in sql       # joined to the authoritative source
    assert "matter_scope.tenant = piece.tenant" in sql       # the join's tenant equality
    assert sql.count("matter_scope.tenant = ") >= 2          # + the defence-in-depth literal pin
    assert "piece.tenant = " in sql                          # tenant first (AD-12)


def test_the_match_is_a_plain_escaped_like_over_the_normalized_column_no_limit() -> None:
    sql = _sql()
    assert "piece.full_text_normalized like" in sql          # the folded index, plain LIKE
    assert "unaccent" not in sql                             # one implementation — no SQL-side fold
    assert "escape" in sql                                   # LIKE metacharacters are escaped
    assert "limit" not in sql                                # never truncated (AD-20)


def _store():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)


def _seed(session, matter, pid, full_text):
    session.add(Piece(
        id=pid, tenant="t1", matter=matter, content_hash=pid, text_key=pid,
        provenance_path=f"{pid}.txt", extraction_method="text", extractor_version="v1",
        schema_version="v1", ingestion_timestamp=datetime.now(UTC), piece_date=None,
        piece_date_status="undetermined", full_text=full_text, text_identity=pid,
        text_version="v1"))
    session.merge(MatterScope(tenant="t1", matter=matter, scope="matter-a", submitted_pieces=1))


def test_an_accented_document_is_found_by_an_unaccented_query_round_trip() -> None:
    # the load-bearing property: the corpus and the query fold to ONE form, so no divergence can
    # cause a false absence. Runs end-to-end on SQLite (the event populated full_text_normalized).
    sf = _store()
    with sf() as s:
        _seed(s, "matter-a", "p1", "Le contrat de l'État national")
        _seed(s, "matter-a", "p2", "un bail commercial")
        s.commit()
    with sf() as s:
        hits = s.execute(exact_search_stmt(
            tenant="t1", scopes={"matter-a"}, normalized_query=normalize("etat"))).all()
    assert [h.id for h in hits] == ["p1"]                    # "État" found by "etat" — no miss


def test_a_percent_in_the_query_is_escaped_not_a_wildcard() -> None:
    sf = _store()
    with sf() as s:
        _seed(s, "matter-a", "p1", "au taux de 5 % du capital")
        _seed(s, "matter-a", "p2", "aucun pourcentage ici")
        s.commit()
    with sf() as s:
        # "5 %" must NOT wildcard-match p2; it matches only the literal "5 %"
        hits = s.execute(exact_search_stmt(
            tenant="t1", scopes={"matter-a"}, normalized_query=normalize("5 %"))).all()
    assert [h.id for h in hits] == ["p1"]
    with sf() as s:
        assert s.scalar(select(func.count()).select_from(Piece)) == 2   # sanity: both were stored


def _seed_ocr(session, matter, pid, full_text):
    session.add(Piece(
        id=pid, tenant="t1", matter=matter, content_hash=pid, text_key=pid,
        provenance_path=f"{pid}.pdf", extraction_method="tesseract", extractor_version="v1",
        schema_version="v1", ingestion_timestamp=datetime.now(UTC), piece_date=None,
        piece_date_status="undetermined", full_text=full_text, text_identity=pid,
        text_version="v1"))
    session.merge(MatterScope(tenant="t1", matter=matter, scope="matter-a", submitted_pieces=1))


def test_exact_search_carries_the_scoped_denominator_and_the_real_ocr_share() -> None:
    # MED-4: the SqlStore aggregation (denominator + ocr_share) is honesty-critical — assert it.
    from apx.adapters.store_postgres.store import SqlStore

    sf = _store()
    store = SqlStore(sf)
    with sf() as s:
        _seed(s, "matter-a", "p1", "un bail de l'État")     # text-extracted
        _seed(s, "matter-a", "p2", "autre document")        # text-extracted
        _seed_ocr(s, "matter-a", "p3", "scan de l'État")    # OCR-extracted (tesseract)
        s.commit()
    found = store.exact_search(tenant="t1", scopes={"matter-a"}, normalized_query=normalize("etat"))
    assert found.denominator.in_corpus == 3                  # the scoped denominator (AD-38)
    assert found.ocr_share == 1 / 3                          # a REAL figure, not a fabricated 0.0
    assert {r.piece_id for r in found.results} == {"p1", "p3"}   # both "État" docs, complete set
    # empty scope AND a blank query both fail closed (never the whole corpus)
    assert store.exact_search(tenant="t1", scopes=set(), normalized_query="etat").results == []
    assert store.exact_search(
        tenant="t1", scopes={"matter-a"}, normalized_query="").results == []
