"""FR-19 / §0.2 — the priced move is a PROJECTION, never a sampling bound (Story 4.9).

The priced figure a lawyer sees while moving **the line** is a *projection from the ranking* — a
model estimate at a position where **nothing has been sampled**. A *confidence bound* is a different
kind of statement entirely: the hypergeometric statement a **completed** random sample produces
(``apx/core/domain/confidence.py::prevalence_upper_bound``). §0.2 makes the distinction
load-bearing: the two must never be computed by the same code and never shown in the same visual
register, because a projection can be wrong in a way a completed sample cannot.

The tractable static shadow, mirroring ``ranking_order_ignores_the_taxonomy_label``: the FR-19
projection module ``core/domain/line_projection.py`` must have **no dependency** on the
sampling-bound estimator — it must not import from ``apx.core.domain.confidence`` and must not
reference ``prevalence_upper_bound``. A future wiring of the bound into the projection fails the
build here, so the projection can never be silently computed by the bound. Fails closed if
unparseable.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path

from apx.checks.import_contracts import CheckResult
from apx.checks.payload_schema import _parse

_APX_ROOT = Path(__file__).resolve().parent.parent  # the apx/ package
_PROJECTION_MODULE = _APX_ROOT / "core" / "domain" / "line_projection.py"
_BOUND_MODULE = "confidence"           # the domain module holding the sampling bound
_BOUND_FN = "prevalence_upper_bound"   # the hypergeometric bound the projection must NOT use


def _references_the_sampling_bound(tree: ast.Module) -> str | None:
    """A reason string if the module imports/references the sampling-bound estimator, else None."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and (
                node.module.endswith(f".{_BOUND_MODULE}") or node.module == _BOUND_MODULE):
            return f"imports from {node.module}"
        if isinstance(node, ast.Name) and node.id == _BOUND_FN:
            return f"references {_BOUND_FN}"
        if isinstance(node, ast.Attribute) and node.attr == _BOUND_FN:
            return f"references {_BOUND_FN}"
    return None


def line_projection_is_not_a_sampling_bound(
    targets: Iterable[Path] | None = None,
) -> CheckResult:
    """The FR-19 priced projection has no dependency on the hypergeometric sampling bound (§0.2), so
    a projection can never be computed by the bound estimator or mistaken for it."""
    name, ad = "the priced move is a projection, not a sampling bound", "AD-20"
    modules = list(targets) if targets is not None else [_PROJECTION_MODULE]
    offenders: list[str] = []
    unparseable: list[str] = []
    for path in modules:
        if not path.exists():
            continue
        tree = _parse(path)
        if tree is None:
            unparseable.append(path.name)
            continue
        reason = _references_the_sampling_bound(tree)
        if reason is not None:
            offenders.append(
                f"{path.name}: the priced projection {reason} — a projection must not be computed "
                "by the sampling bound (FR-19/§0.2)")
    if unparseable:
        return CheckResult(
            name, ad, False, f"cannot parse (failing closed, cannot verify): {unparseable}")
    if offenders:
        return CheckResult(
            name, ad, False, f"the priced projection depends on the sampling bound: {offenders}")
    return CheckResult(
        name, ad, True,
        "the line-projection module does not import or reference the sampling-bound estimator")


def run() -> list[CheckResult]:
    return [line_projection_is_not_a_sampling_bound()]
