"""The deterministic exhaustive engine (Story 3.2, AD-20/AD-21). Proven in CI with a fake reader
that applies the real normalisation rule in memory; the pg query is proven pg-side (Task 4)."""

from __future__ import annotations

import pytest

from apx.core.app.read.deterministic import MovingPopulation, search_exhaustive
from apx.core.domain.inventory import Inventory
from apx.core.domain.normalization import NORMALIZATION, normalize
from apx.core.domain.retrieval import DeterministicResult, RegisterHit, TruthStatus
from apx.core.ports.read import ExactSearch


class _FakeReader:
    """In-memory deterministic reader — the CI stand-in for the PostgreSQL normalised query. Applies
    the real ``normalize`` rule (containment), scope pre-filter, and returns the AD-42 bundle."""

    def __init__(self, pieces, register=(), open_jobs=()) -> None:
        self.pieces = pieces          # (matter, piece_id, scope, full_text)
        self.register = register      # (matter, filename, error_class, scope)
        self._open_jobs = list(open_jobs)

    def open_import_jobs(self, *, tenant, scopes):
        return [j for (j, scope) in self._open_jobs if scope in scopes]

    def exact_search(self, *, tenant, scopes, normalized_query):
        hits = [
            DeterministicResult(matter=m, piece_id=pid, snippet=text[:40])
            for (m, pid, scope, text) in self.pieces
            if scope in scopes and normalized_query in normalize(text)
        ]
        reg = [
            RegisterHit(matter=m, filename=fn, error_class=ec)
            for (m, fn, ec, scope) in self.register
            if scope in scopes and normalized_query in normalize(fn)
        ]
        in_scope = [p for p in self.pieces if p[2] in scopes]
        denom = Inventory(submitted_pieces=len(in_scope) + 1, in_corpus=len(in_scope),
                          open_register_entries=1, unknown_cardinality_entries=0)
        return ExactSearch(results=hits, register_hits=reg, denominator=denom,
                           ocr_share=0.1, below_quality_share=0.0)


_PIECES = [
    ("m-a", "p1", "matter-a", "Le contrat de l'État national"),   # matches "etat"
    ("m-a", "p2", "matter-a", "un bail commercial ordinaire"),
    ("m-b", "p3", "matter-b", "l'État fédéral"),                  # out of a matter-a scope
]
_REGISTER = [("m-a", "état-civil.pdf", "unreadable", "matter-a")]  # a register NAME match


def _run(scopes, query="etat", **kw):
    return search_exhaustive(
        tenant="t1", scopes=scopes, query=query,
        reader=_FakeReader(_PIECES, register=_REGISTER, **kw),
    )


def test_it_returns_the_complete_match_set_as_exhaustive_with_its_denominator() -> None:
    rs = _run({"matter-a"})
    assert rs.truth_status is TruthStatus.EXHAUSTIVE
    assert [r.piece_id for r in rs.results] == ["p1"]            # every in-scope match, no top-k
    assert rs.denominator.in_corpus == 2 and rs.denominator.open_register_entries == 1
    assert rs.normalization == NORMALIZATION and rs.ocr_share == 0.1


def test_scope_is_a_prefilter_an_out_of_scope_match_never_appears() -> None:
    assert "p3" not in [r.piece_id for r in _run({"matter-a"}).results]   # p3 (matter-b) excluded


def test_the_register_is_searched_separately_never_inside_the_results() -> None:
    rs = _run({"matter-a"})
    assert rs.register_hits and rs.register_hits[0].filename == "état-civil.pdf"
    assert all(isinstance(r, DeterministicResult) for r in rs.results)    # no register hit inside


def test_it_refuses_over_a_matter_with_an_open_import_job_naming_it() -> None:
    with pytest.raises(MovingPopulation) as exc:
        _run({"matter-a"}, open_jobs=[("job-123", "matter-a")])
    assert "job-123" in str(exc.value)                          # names the job, never a partial set


def test_an_empty_scope_yields_an_empty_exhaustive_set_fail_closed() -> None:
    rs = _run(set())
    assert rs.results == () and rs.truth_status is TruthStatus.EXHAUSTIVE
    assert rs.denominator.in_corpus == 0
