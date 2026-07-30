"""The truth-status SURFACE gate (Story 3.4, FR-15): a response/export model carrying engine
results must serialise its truth status, and no model merges the two engines. Both pass the real
api tree, fire on fixtures, and fail closed."""

from __future__ import annotations

from pathlib import Path

from apx.checks.truth_status_surface import (
    no_response_merges_the_two_engines,
    result_set_response_serialises_truth_status,
)


def _mod(tmp_path: Path, name: str, src: str) -> Path:
    d = tmp_path / name
    d.mkdir()
    (d / f"{name}.py").write_text(src, encoding="utf-8")
    return d


def test_serialise_fires_on_a_results_model_without_truth_status(tmp_path: Path) -> None:
    src = (
        "from pydantic import BaseModel\n"
        "class SemanticResultOut(BaseModel):\n"
        "    piece_id: str\n"
        "class Leak(BaseModel):\n"
        "    results: list[SemanticResultOut]\n"   # engine results, but no truth_status
    )
    r = result_set_response_serialises_truth_status([_mod(tmp_path, "leak", src)])
    assert not r.ok and "truth_status" in r.detail


def test_serialise_passes_a_results_model_with_truth_status(tmp_path: Path) -> None:
    src = (
        "from pydantic import BaseModel\n"
        "class DeterministicResultOut(BaseModel):\n"
        "    piece_id: str\n"
        "class Ok(BaseModel):\n"
        "    truth_status: str\n"
        "    results: list[DeterministicResultOut]\n"
    )
    r = result_set_response_serialises_truth_status([_mod(tmp_path, "ok", src)])
    assert r.ok


def test_serialise_ignores_a_preview_model_that_is_not_an_engine_result_set(tmp_path: Path) -> None:
    # the bounded preview (SearchHitOut list) is deliberately not a truth-status set — not flagged
    src = (
        "from pydantic import BaseModel\n"
        "class SearchHitOut(BaseModel):\n"
        "    matter: str\n"
        "class SearchResultsOut(BaseModel):\n"
        "    hits: list[SearchHitOut]\n"
    )
    r = result_set_response_serialises_truth_status([_mod(tmp_path, "preview", src)])
    assert r.ok


def test_never_merge_fires_on_a_model_carrying_both_engines(tmp_path: Path) -> None:
    src = (
        "from pydantic import BaseModel\n"
        "class SemanticResultOut(BaseModel):\n    piece_id: str\n"
        "class DeterministicResultOut(BaseModel):\n    piece_id: str\n"
        "class Combined(BaseModel):\n"
        "    truth_status: str\n"
        "    suggestions: list[SemanticResultOut]\n"
        "    proofs: list[DeterministicResultOut]\n"   # both engines in one model — forbidden
    )
    r = no_response_merges_the_two_engines([_mod(tmp_path, "combined", src)])
    assert not r.ok and "both" in r.detail.lower()


def test_never_merge_passes_two_separate_models(tmp_path: Path) -> None:
    src = (
        "from pydantic import BaseModel\n"
        "from pydantic import BaseModel\n"
        "class SemanticResultOut(BaseModel):\n    piece_id: str\n"
        "class DeterministicResultOut(BaseModel):\n    piece_id: str\n"
        "class SuggestiveOut(BaseModel):\n    truth_status: str\n    r: list[SemanticResultOut]\n"
        "class ExhaustiveOut(BaseModel):\n"
        "    truth_status: str\n    r: list[DeterministicResultOut]\n"
    )
    r = no_response_merges_the_two_engines([_mod(tmp_path, "sep", src)])
    assert r.ok


def test_serialise_fires_on_an_untyped_results_container(tmp_path: Path) -> None:
    # a results field serialised as list[dict]/list (e.g. [r.model_dump() for r ...]) drops the
    # type anchor — the name convention still catches it (R2 HIGH-1).
    for i, ann in enumerate(["list[dict]", "list", "tuple[dict, ...]"]):
        src = ("from pydantic import BaseModel\n"
               f"class Leak(BaseModel):\n    results: {ann}\n")
        r = result_set_response_serialises_truth_status([_mod(tmp_path, f"unt{i}", src)])
        assert not r.ok, f"should fire on results: {ann}"


def test_serialise_is_inheritance_aware_both_ways(tmp_path: Path) -> None:
    # FALSE-POSITIVE guard (R2 HIGH-2): a DRY base carries truth_status; the subclass declares
    # results in its own body — this must PASS (the status is inherited).
    ok = ("from pydantic import BaseModel\n"
          "class TSBase(BaseModel):\n    truth_status: str\n"
          "class R(TSBase):\n    results: list[DeterministicResultOut]\n")
    assert result_set_response_serialises_truth_status([_mod(tmp_path, "dry", ok)]).ok
    # FALSE-NEGATIVE guard: results inherited from a base that has NO truth_status must FIRE.
    leak = ("from pydantic import BaseModel\n"
            "class Base(BaseModel):\n    results: list[SemanticResultOut]\n"
            "class Sub(Base):\n    header: str\n")
    assert not result_set_response_serialises_truth_status([_mod(tmp_path, "inh", leak)]).ok


def test_serialise_reads_forward_ref_string_annotations(tmp_path: Path) -> None:
    # both the whole-string and the nested-string forward ref (R2 MED-1)
    for i, ann in enumerate(["'list[SemanticResultOut]'", "list['DeterministicResultOut']"]):
        src = ("from pydantic import BaseModel\n"
               f"class Leak(BaseModel):\n    results: {ann}\n")
        assert not result_set_response_serialises_truth_status(
            [_mod(tmp_path, f"fwd{i}", src)]).ok


def test_never_merge_is_inheritance_aware(tmp_path: Path) -> None:
    # a model merging both engines via two bases must FIRE (R2 HIGH-2 FN)
    src = ("from pydantic import BaseModel\n"
           "class S(BaseModel):\n    truth_status: str\n    s: list[SemanticResultOut]\n"
           "class D(BaseModel):\n    d: list[DeterministicResultOut]\n"
           "class Merged(S, D):\n    header: str\n")
    assert not no_response_merges_the_two_engines([_mod(tmp_path, "merge2", src)]).ok


def test_both_pass_the_real_api_tree() -> None:
    assert result_set_response_serialises_truth_status().ok
    assert no_response_merges_the_two_engines().ok


def test_both_fail_closed_on_unparseable(tmp_path: Path) -> None:
    assert not result_set_response_serialises_truth_status([_mod(tmp_path, "b1", "def (:\n")]).ok
    assert not no_response_merges_the_two_engines([_mod(tmp_path, "b2", "def (:\n")]).ok
