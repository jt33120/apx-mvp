"""The no-truncation gate (Story 3.2, AD-20): an **exhaustive** result set is never truncated.

AD-20: "a ``LIMIT``, a ``top_k`` or a page size applied to a set constructed exhaustive downgrades
its status to *suggestive* at the same construction site, and no configuration can prevent the
downgrade. Enforced as a structural property: the deterministic engine accepts no limit
parameter." This check makes that mechanical, anchored on the **type** (not a guessed name): any
function whose return annotation is an exhaustive result set (``ExhaustiveResultSet`` / the port's
``ExactSearch`` bundle) must take **no** ``limit`` / ``top_k`` / ``page_size`` / ``max_results`` /
``cap`` parameter. Vacuous until such a function exists; fires on a truncating one. Fails closed on
an unparseable file; injectable ``roots``.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path

from apx.checks.import_contracts import CheckResult
from apx.checks.payload_schema import _fail_closed, _load_trees, _parse

_APX_ROOT = Path(__file__).resolve().parent.parent
_RUNTIME_EXCLUDE = frozenset({"checks", "fitness", "timedrun", "__pycache__"})
_EXHAUSTIVE_TYPES = frozenset({"ExhaustiveResultSet", "ExactSearch"})
_LIMIT_PARAMS = frozenset({
    "limit", "top_k", "topk", "page_size", "pagesize", "max_results", "maxresults", "cap",
})


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


def _returns_exhaustive(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """The function's return annotation names an exhaustive result-set type — a ``Name``
    or a forward-ref string annotation (``-> "ExhaustiveResultSet"``)."""
    ann = fn.returns
    if ann is None:
        return False
    if isinstance(ann, ast.Constant) and isinstance(ann.value, str):
        return any(t in ann.value for t in _EXHAUSTIVE_TYPES)
    return any(isinstance(n, ast.Name) and n.id in _EXHAUSTIVE_TYPES for n in ast.walk(ann))


def _limit_params(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    args = fn.args
    names = {a.arg for a in (*args.posonlyargs, *args.args, *args.kwonlyargs)}
    return names & _LIMIT_PARAMS


def _internal_truncation(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """A ``.limit(...)`` call in the body — a query truncation applied to the set being constructed
    exhaustive (AD-20), which the param-only anchor misses. (A ``[:n]`` slice is deliberately not
    flagged: it is ambiguous with a snippet truncation.)"""
    return any(
        isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "limit"
        for n in ast.walk(fn)
    )


def exhaustive_engine_takes_no_limit(roots: Iterable[Path] | None = None) -> CheckResult:
    """No function producing an exhaustive result set takes a limit/top-k/page-size (AD-20).
    Vacuous until such a function exists; fires the moment a truncating one appears."""
    name, ad = "an exhaustive engine takes no limit", "AD-20"
    trees, unparseable = _runtime_trees() if roots is None else _load_trees(list(roots))
    if unparseable:
        return _fail_closed(name, ad, unparseable)
    sites = 0
    for path, tree in trees:
        for node in ast.walk(tree):
            is_fn = isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
            if is_fn and _returns_exhaustive(node):
                sites += 1
                bad = _limit_params(node)
                if bad:
                    return CheckResult(
                        name, ad, False,
                        f"{path.name}:{node.name} takes {sorted(bad)} — an exhaustive set is never "
                        "truncated; a limit downgrades it to suggestive (AD-20)")
                if _internal_truncation(node):
                    return CheckResult(
                        name, ad, False,
                        f"{path.name}:{node.name} applies a .limit() to a set it constructs "
                        "exhaustive — a truncation downgrades it to suggestive (AD-20)")
    if sites == 0:
        return CheckResult(name, ad, True,
                           f"vacuous: no function produces an exhaustive set ({len(trees)} files)")
    return CheckResult(name, ad, True,
                       f"every exhaustive-search function ({sites}) takes no limit/top-k (AD-20)")
