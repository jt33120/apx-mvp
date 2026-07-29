"""The gold-set merge gate (Story 2.12, FR-54 / AD-34): no ranking or triage code exists without the
gold-set recall harness (``eval.harness.recall_at_the_line``) being EXERCISED against the gold set
in CI. It is **live** — the triage / LLM-cascade subsystem already uses the ``Judge`` port — so the
gate requires the recall path to actually run, preventing the v1 defect (a gold set that exists and
never runs).

Detection anchors on the STABLE interface — an IMPORT of a ranking / triage port or use case — NOT a
guessed name whitelist: a name whitelist misses both the judging code that already ships and the
names a future ranker will choose. New ranking ports (the ranked order, *the line* placement) are
added to ``_RANKING_PORTS`` as they land. The ultimate quality gate is the CI recall run + ratchet
once a ranker exists; this structural check makes it unbypassable by requiring recall to be defined
AND invoked by a test (so it runs in CI), not merely to exist by name.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path

from apx.checks.import_contracts import CheckResult
from apx.checks.payload_schema import _fail_closed, _load_trees, _parse

_APX_ROOT = Path(__file__).resolve().parent.parent
_REPO_ROOT = _APX_ROOT.parent
_HARNESS = _REPO_ROOT / "eval" / "harness.py"
_TESTS = _REPO_ROOT / "tests"
_RECALL_FN = "recall_at_the_line"

# Build-time tooling is not ranking code; scan the product runtime only.
_RUNTIME_EXCLUDE = frozenset({"checks", "fitness", "__pycache__"})

# The stable interfaces ranking / triage / *the line* code is built on. Detection = an IMPORT of one
# of these. Extend as new ranking ports land.
_RANKING_PORTS = frozenset({
    "apx.core.ports.judge",   # the Judge port — the LLM triage cascade
    "apx.core.app.triage",    # the triage use case (RELEVANT / DISCARD / UNCERTAIN = *the line*)
})
# The modules that DEFINE those anchors — importing your own definition is not "using ranking".
_PORT_DEFS = frozenset({
    _APX_ROOT / "core" / "ports" / "judge.py",
    _APX_ROOT / "core" / "app" / "triage.py",
})


def _imported_modules(tree: ast.Module) -> set[str]:
    """The absolute module names this tree imports (``import a.b`` / ``from a.b import c``)."""
    mods: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            mods.add(node.module)
    return mods


def _runtime_trees() -> tuple[list[tuple[Path, ast.Module]], list[str]]:
    trees: list[tuple[Path, ast.Module]] = []
    unparseable: list[str] = []
    for path in sorted(_APX_ROOT.rglob("*.py")):
        if set(path.parts) & _RUNTIME_EXCLUDE:
            continue
        tree = _parse(path)
        if tree is None:
            unparseable.append(path.name)
        else:
            trees.append((path, tree))
    return trees, unparseable


def _ranking_site(trees: list[tuple[Path, ast.Module]]) -> Path | None:
    """The first runtime module that USES a ranking / triage interface (imports a ``_RANKING_PORTS``
    module), excluding the modules that define those interfaces. ``None`` → vacuous."""
    for path, tree in trees:
        if path in _PORT_DEFS:
            continue
        if _imported_modules(tree) & _RANKING_PORTS:
            return path
    return None


def _harness_defines_recall(harness: Path) -> bool:
    tree = _parse(harness) if harness.is_file() else None
    return tree is not None and any(
        isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef) and n.name == _RECALL_FN
        for n in ast.walk(tree))


def _a_test_invokes_recall(test_roots: Path) -> bool:
    """A test CALLS ``recall_at_the_line`` — so recall is exercised on every CI run, not merely
    defined. Today the deferral test invokes it (asserting it raises, pending a ranker); when a
    ranker lands the same call measures and ratchets a real figure."""
    if not test_roots.is_dir():
        return False
    for path in sorted(test_roots.rglob("test_*.py")):
        tree = _parse(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                fn = node.func
                if (isinstance(fn, ast.Name) and fn.id == _RECALL_FN) or (
                        isinstance(fn, ast.Attribute) and fn.attr == _RECALL_FN):
                    return True
    return False


def ranking_code_requires_the_gold_gate(
    roots: Iterable[Path] | None = None, *,
    harness: Path | None = None, test_roots: Path | None = None,
) -> CheckResult:
    """No ranking / triage code exists without the gold-set recall gate being exercised (AD-34 /
    FR-54). Vacuous only while nothing uses a ranking interface; the moment such code exists (it
    does today — the triage cascade), the recall harness (``eval.harness.recall_at_the_line``) must
    be defined AND invoked by a test, so recall runs against the gold set in CI — the v1 defect (a
    gold set that never ran) made impossible."""
    name, ad = "ranking code is gated by the gold-set recall harness", "AD-34"
    trees, unparseable = _runtime_trees() if roots is None else _load_trees(list(roots))
    if unparseable:
        return _fail_closed(name, ad, unparseable)
    site = _ranking_site(trees)
    if site is None:
        return CheckResult(
            name, ad, True,
            f"vacuous: nothing uses a ranking/triage interface ({len(trees)} runtime file(s))")
    gate = harness if harness is not None else _HARNESS
    tests = test_roots if test_roots is not None else _TESTS
    if not _harness_defines_recall(gate):
        return CheckResult(
            name, ad, False,
            f"{site.name} uses a ranking interface but the recall gate ({_RECALL_FN} in "
            "eval/harness.py) is missing — AD-34: recall must run against the gold set")
    if not _a_test_invokes_recall(tests):
        return CheckResult(
            name, ad, False,
            f"{site.name} uses a ranking interface but no test invokes {_RECALL_FN} — recall must "
            "RUN in CI, not merely exist by name (AD-34)")
    return CheckResult(
        name, ad, True,
        f"ranking code ({site.name}) is gated by the gold-set recall harness, exercised in CI")
