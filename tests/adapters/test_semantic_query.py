"""The PostgreSQL semantic-search query (Story 3.1, AD-13/AD-16). The pgvector ``<=>`` cosine
operator is PostgreSQL-only (halfvec degrades to JSON on the SQLite baseline, exactly as the
migrations are PG-only), so CI proves the query by its **compiled shape** — the scope predicate is
joined from the authoritative ``matter_scope`` as a PRE-filter, tenant-first, ranked by distance,
bounded by k — plus the empty-scope fail-closed short-circuit. The live vector round-trip runs on
the target where pgvector + the HNSW index exist."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apx.adapters.store_postgres.models import Base
from apx.adapters.store_postgres.semantic_query import results_from_rows, semantic_search_stmt
from apx.adapters.store_postgres.store import SqlStore


def _sql(scopes=frozenset({"matter-a"}), *, k=10, min_similarity=0.3) -> str:
    stmt = semantic_search_stmt(
        tenant="t1", scopes=scopes, query_vector=[0.1, 0.2, 0.3, 0.4], k=k,
        min_similarity=min_similarity,
    )
    return str(stmt.compile(dialect=postgresql.dialect())).lower()


def test_scope_is_joined_from_matter_scope_as_a_query_pre_filter() -> None:
    sql = _sql()
    assert "matter_scope" in sql                       # the authoritative scope source (AD-13)
    assert "join matter_scope" in sql
    assert "matter_scope.scope in" in sql              # the scope PRE-filter, in the query
    assert "chunk.tenant = " in sql                    # tenant first (AD-12)


def test_the_chinese_wall_is_tenant_qualified_on_both_sides() -> None:
    # The load-bearing Chinese-wall lines (AD-12/AD-13): the join equates matter_scope.tenant to the
    # chunk's tenant AND matter_scope.tenant is pinned to the caller's tenant literal. Scope strings
    # are not tenant-qualified, so dropping either would let a same-named cross-tenant scope leak.
    sql = _sql()
    assert "matter_scope.tenant = chunk.tenant" in sql   # the join's tenant equality
    assert sql.count("matter_scope.tenant") >= 2         # + pinned to the caller's tenant in WHERE


def test_the_query_ranks_by_cosine_distance_and_bounds_by_k() -> None:
    sql = _sql(k=7)
    assert "<=>" in sql                                # pgvector cosine distance
    assert "order by" in sql and "<=>" in sql.split("order by", 1)[1]
    assert "limit" in sql


def test_a_similarity_floor_is_applied_in_the_query() -> None:
    # min_similarity 0.3 → distance <= 0.7 in the WHERE (cosine similarity = 1 - distance)
    sql = _sql(min_similarity=0.3)
    assert "<=>" in sql.split("where", 1)[1].split("order by", 1)[0]   # the floor is a query filter


def _store() -> SqlStore:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return SqlStore(sessionmaker(bind=engine, future=True))


def test_cosine_distance_is_inverted_to_similarity_preserving_rank() -> None:
    # pgvector `<=>` is cosine DISTANCE; similarity = 1 - distance. This mapping never runs in CI
    # via the store (SQLite can't execute `<=>`), so it is unit-tested here directly (a wrong
    # inversion would otherwise be an invisible ranking regression).
    from collections import namedtuple

    Row = namedtuple("Row", "piece_id chunk_id distance")
    out = results_from_rows([Row("p1", "c1", 0.25), Row("p2", "c2", 0.0), Row("p3", "c3", 1.0)])
    assert [r.similarity for r in out] == [0.75, 1.0, 0.0]        # 1 - distance, order preserved
    assert [r.chunk_id for r in out] == ["c1", "c2", "c3"]


def test_an_empty_scope_reads_nothing_without_touching_the_database() -> None:
    # fail-closed (AD-12): no scope → empty, and no query is run (so it is safe even on SQLite).
    store = _store()
    assert store.search_semantic(
        tenant="t1", scopes=set(), query_vector=[0.1, 0.2, 0.3, 0.4], k=10, min_similarity=0.3
    ) == []
