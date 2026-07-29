"""The gold-set merge gate (Story 2.12, FR-54 / AD-34) is LIVE — it detects code that USES a
ranking / triage interface (an import of the Judge port or the triage use case, not a guessed name)
— and requires the recall harness to be defined AND invoked by a test, so recall RUNS in CI. It
fires when either half is missing; a function NAME alone never satisfies it.
"""

from __future__ import annotations

from pathlib import Path

from apx.checks.gold_gate import _HARNESS, _TESTS, ranking_code_requires_the_gold_gate

_NO_HARNESS = Path("/nonexistent/eval/harness.py")
_NO_TESTS = Path("/nonexistent/tests")
# a module that USES a ranking interface (imports the Judge port) — the stable anchor, not a name
_RANKING_IMPORT = "from apx.core.ports.judge import Judge\n\n\ndef use(j: Judge):\n    return j\n"


def _mod(tmp_path: Path, name: str, src: str) -> Path:
    (tmp_path / name).write_text(src, encoding="utf-8")
    return tmp_path


def test_it_is_live_on_the_real_tree_and_passes() -> None:
    # the triage cascade already uses the Judge port, so the gate is NOT vacuous; it passes only
    # because recall_at_the_line is defined AND invoked by the deferral test (exercised in CI)
    r = ranking_code_requires_the_gold_gate()
    assert r.ok and "exercised in CI" in r.detail


def test_ranking_code_without_the_recall_harness_fires(tmp_path: Path) -> None:
    root = _mod(tmp_path, "ranker.py", _RANKING_IMPORT)
    r = ranking_code_requires_the_gold_gate([root], harness=_NO_HARNESS, test_roots=_TESTS)
    assert not r.ok and "missing" in r.detail


def test_ranking_code_with_a_harness_no_test_invokes_fires(tmp_path: Path) -> None:
    # the recall harness EXISTS but no test invokes it → the gate fires: recall must RUN, not exist
    root = _mod(tmp_path, "ranker.py", _RANKING_IMPORT)
    r = ranking_code_requires_the_gold_gate([root], harness=_HARNESS, test_roots=_NO_TESTS)
    assert not r.ok and "invokes" in r.detail


def test_ranking_code_with_the_recall_harness_exercised_passes(tmp_path: Path) -> None:
    root = _mod(tmp_path, "ranker.py", _RANKING_IMPORT)
    r = ranking_code_requires_the_gold_gate([root], harness=_HARNESS, test_roots=_TESTS)
    assert r.ok


def test_code_using_no_ranking_interface_is_vacuous(tmp_path: Path) -> None:
    root = _mod(tmp_path, "helper.py", "def tidy(x):\n    return x\n")
    r = ranking_code_requires_the_gold_gate([root], harness=_NO_HARNESS, test_roots=_NO_TESTS)
    assert r.ok and "vacuous" in r.detail
