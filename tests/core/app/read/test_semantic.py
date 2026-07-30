"""The semantic engine (Story 3.1, AD-16/AD-20): embed → scoped nearest-neighbour → a SUGGESTIVE
set. Proven in CI with a Python-cosine fake reader (the pg HNSW query is proven pg-side, Task 3)."""

from __future__ import annotations

import math

from apx.core.app.read.semantic import search_semantic
from apx.core.domain.retrieval import SemanticResult, TruthStatus


class _FakeEmbedder:
    dimensions = 3
    model_id = "fake"
    model_version = "1"

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0, 0.0] for _ in texts]     # a fixed query direction


def _cos(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


class _FakeReader:
    """In-memory cosine reader — the CI stand-in for the PostgreSQL HNSW query. Applies the scope
    predicate as a pre-filter and the min-similarity floor, ranks, and truncates to k."""

    def __init__(self, rows: list[tuple[str, str, str, list[float]]]) -> None:
        self.rows = rows                            # (piece_id, chunk_id, scope, vector)

    def search_semantic(self, *, tenant, scopes, query_vector, k, min_similarity):
        if not scopes:
            return []
        scored = [
            SemanticResult(pid, cid, _cos(query_vector, vec))
            for (pid, cid, scope, vec) in self.rows
            if scope in scopes
        ]
        scored = [r for r in scored if r.similarity >= min_similarity]
        scored.sort(key=lambda r: r.similarity, reverse=True)
        return scored[:k]


_ROWS = [
    ("p1", "c1", "matter-a", [0.9, 0.1, 0.0]),      # close to the query
    ("p2", "c2", "matter-a", [0.2, 0.9, 0.0]),      # far
    ("p3", "c3", "matter-b", [1.0, 0.0, 0.0]),      # closest of all — but out of a matter-a scope
]


def _search(scopes, *, k=10, threshold=0.0):
    return search_semantic(
        tenant="t1", scopes=scopes, query="contrat de bail", embedder=_FakeEmbedder(),
        reader=_FakeReader(_ROWS), k=k, config_get=lambda key: threshold,
    )


def test_a_semantic_query_returns_a_suggestive_ranked_set_with_provenance() -> None:
    rs = _search({"matter-a"})
    assert rs.truth_status is TruthStatus.SUGGESTIVE
    assert rs.k == 10
    assert [r.chunk_id for r in rs.results] == ["c1", "c2"]     # ranked best-first, scoped to a
    assert all(r.piece_id and r.chunk_id for r in rs.results)   # openable handle present


def test_scope_is_a_prefilter_the_closest_out_of_scope_hit_never_appears() -> None:
    rs = _search({"matter-a"})
    assert "c3" not in [r.chunk_id for r in rs.results]         # p3 is closest but out of scope


def test_empty_scope_yields_an_empty_set_fail_closed() -> None:
    rs = _search(set())
    assert rs.results == () and rs.truth_status is TruthStatus.SUGGESTIVE


def test_k_bounds_the_result_count() -> None:
    assert len(_search({"matter-a"}, k=1).results) == 1


def test_the_similarity_threshold_excludes_below_threshold_hits_and_is_recorded() -> None:
    rs = _search({"matter-a"}, threshold=0.5)
    assert [r.chunk_id for r in rs.results] == ["c1"]           # c2 (cos≈0.22) is below 0.5
    assert rs.similarity_threshold == 0.5                       # recorded on the set
