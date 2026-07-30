"""The AD-20 no-truncation gate (Story 3.2): a function that produces an exhaustive result set takes
NO limit/top-k/page-size parameter — an exhaustive set is never truncated (a truncation would
downgrade it to suggestive, no configuration preventing that). Anchored on the exhaustive TYPE."""

from __future__ import annotations

from pathlib import Path

from apx.checks.no_truncation import exhaustive_engine_takes_no_limit


def _mod(tmp_path: Path, name: str, src: str) -> Path:
    d = tmp_path / name
    d.mkdir()
    (d / f"{name}.py").write_text(src, encoding="utf-8")
    return d


def test_it_fires_on_an_exhaustive_search_that_takes_a_limit(tmp_path: Path) -> None:
    src = (
        "from apx.core.domain.retrieval import ExhaustiveResultSet\n"
        "def search(tenant, scopes, query, *, limit=100) -> ExhaustiveResultSet: ...\n"
    )
    r = exhaustive_engine_takes_no_limit([_mod(tmp_path, "bad", src)])
    assert not r.ok and "limit" in r.detail


def test_it_fires_on_top_k_and_page_size_too(tmp_path: Path) -> None:
    for i, param in enumerate(["top_k", "page_size", "max_results"]):
        src = (
            "from apx.core.domain.retrieval import ExhaustiveResultSet\n"
            f"def find(tenant, scopes, q, {param}=50) -> ExhaustiveResultSet: ...\n"
        )
        r = exhaustive_engine_takes_no_limit([_mod(tmp_path, f"p{i}", src)])
        assert not r.ok, f"should fire on {param}"


def test_it_fires_on_an_internal_limit_call_even_with_no_limit_param(tmp_path: Path) -> None:
    # AD-20: a LIMIT applied to a set constructed exhaustive downgrades it — an INTERNAL .limit()
    # (no limit param) is exactly that, and the param-only anchor would miss it.
    src = (
        "from apx.core.domain.retrieval import ExhaustiveResultSet\n"
        "def search(tenant, scopes, query) -> ExhaustiveResultSet:\n"
        "    return build(q.limit(100))\n"
    )
    r = exhaustive_engine_takes_no_limit([_mod(tmp_path, "internal", src)])
    assert not r.ok


def test_it_catches_a_forward_ref_string_annotation(tmp_path: Path) -> None:
    src = (
        "from apx.core.domain.retrieval import ExhaustiveResultSet\n"
        "def search(tenant, scopes, query, *, limit=1) -> 'ExhaustiveResultSet': ...\n"
    )
    r = exhaustive_engine_takes_no_limit([_mod(tmp_path, "fwdref", src)])
    assert not r.ok


def test_it_passes_an_exhaustive_search_with_no_limit(tmp_path: Path) -> None:
    src = (
        "from apx.core.domain.retrieval import ExhaustiveResultSet\n"
        "def search(tenant, scopes, query) -> ExhaustiveResultSet: ...\n"
    )
    r = exhaustive_engine_takes_no_limit([_mod(tmp_path, "ok", src)])
    assert r.ok


def test_it_is_vacuous_when_nothing_produces_an_exhaustive_set(tmp_path: Path) -> None:
    r = exhaustive_engine_takes_no_limit([_mod(tmp_path, "plain", "def f(limit=10): ...\n")])
    assert r.ok and "vacuous" in r.detail


def test_the_real_tree_passes_the_exhaustive_engine_takes_no_limit() -> None:
    r = exhaustive_engine_takes_no_limit()
    assert r.ok


def test_it_fails_closed_on_an_unparseable_file(tmp_path: Path) -> None:
    r = exhaustive_engine_takes_no_limit([_mod(tmp_path, "broken", "def (:\n")])
    assert not r.ok
