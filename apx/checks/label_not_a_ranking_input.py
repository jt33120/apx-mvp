"""FR-40 / FR-43 / AD-39 — the ranked order ignores the taxonomy label (Story 4.5).

A label is a *label*, not a rank: changing a taxonomy label must never move a *pièce* in the ranked
order nor across **the line** (FR-40). The structural guarantee behind that promise is that the
ranked-order computation has **no dependency** on the taxonomy-label axis — so a label cannot be an
ordering input, and the *retained*/*discarded* sets (views over the order + the line + pins, AD-39)
never shift because a label changed.

This asserts the two modules that COMPUTE the order — ``core/domain/ranking.py`` (the
``RankingIdentity`` + ``rank_cascade``) and ``core/app/rank.py`` (``produce_ranking``) — neither
imports from ``apx.core.domain.taxonomy_label`` nor references the ``TaxonomyLabelEntry`` ledger by
name. A future wiring of the label into the order fails the build here. Fails closed on an
unparseable file.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path

from apx.checks.import_contracts import CheckResult
from apx.checks.payload_schema import _parse

_APX_ROOT = Path(__file__).resolve().parent.parent  # the apx/ package
_RANKING_MODULES = (
    _APX_ROOT / "core" / "domain" / "ranking.py",
    _APX_ROOT / "core" / "app" / "rank.py",
)
_LABEL_MODULE = "taxonomy_label"      # the domain module the order must NOT depend on
_LABEL_TABLE = "TaxonomyLabelEntry"   # the ledger ORM model the order must NOT reference


def _references_the_label_axis(tree: ast.Module) -> str | None:
    """A reason string if the module imports/references the taxonomy-label axis, else None."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and _LABEL_MODULE in node.module:
            return f"imports from {node.module}"
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _LABEL_MODULE in alias.name:
                    return f"imports {alias.name}"
        if isinstance(node, ast.Name) and node.id == _LABEL_TABLE:
            return f"references {_LABEL_TABLE}"
        if isinstance(node, ast.Attribute) and node.attr == _LABEL_TABLE:
            return f"references {_LABEL_TABLE}"
    return None


def ranking_order_ignores_the_taxonomy_label(
    targets: Iterable[Path] | None = None,
) -> CheckResult:
    """The ranked-order computation has no dependency on the taxonomy-label axis (FR-43/AD-39), so a
    label can never move a *pièce* or the line."""
    name, ad = "the ranked order ignores the taxonomy label", "AD-39"
    modules = list(targets) if targets is not None else list(_RANKING_MODULES)
    offenders: list[str] = []
    unparseable: list[str] = []
    for path in modules:
        if not path.exists():
            continue
        tree = _parse(path)
        if tree is None:
            unparseable.append(path.name)
            continue
        reason = _references_the_label_axis(tree)
        if reason is not None:
            offenders.append(
                f"{path.name}: the ranked order {reason} — a label must not be an ordering input "
                "(FR-43/AD-39)")
    if unparseable:
        return CheckResult(
            name, ad, False, f"cannot parse (failing closed, cannot verify): {unparseable}")
    if offenders:
        return CheckResult(name, ad, False, f"ranked order depends on the label axis: {offenders}")
    return CheckResult(
        name, ad, True,
        "the ranked-order modules do not import or reference the taxonomy-label axis")


def run() -> list[CheckResult]:
    return [ranking_order_ignores_the_taxonomy_label()]
