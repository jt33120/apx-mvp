"""FR-43 / AD-39 — the ranked order ignores the pin (Story 4.11).

A *pin* moves exactly one *pièce* across **the line** without moving the line and **without changing
the ranked order** (FR-43): the *retained*/*discarded* sets are views over the order + the line +
pins (AD-39), and a pin shifts only that one *pièce*'s membership in the VIEW, never its rank. The
structural guarantee behind that promise is that the ranked-order computation has **no dependency**
on the pin axis — so a pin can never become an ordering input.

This asserts the two modules that COMPUTE the order — ``core/domain/ranking.py``
(``RankingIdentity`` + ``rank_cascade``) and ``core/app/rank.py`` (``produce_ranking``) — neither
imports from ``apx.core.domain.pin`` nor references the ``PinEntry`` ledger by name. A future wiring
of a pin into the order fails the build here. Fails closed on an unparseable file.
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
_PIN_MODULE = "pin"        # the domain module the order must NOT depend on
_PIN_TABLE = "PinEntry"    # the ledger ORM model the order must NOT reference


def _imports_module_named(node: ast.AST, wanted: str) -> str | None:
    """A reason string if ``node`` is an import of a module whose final component is ``wanted``."""
    if isinstance(node, ast.ImportFrom) and node.module and (
            node.module == wanted or node.module.endswith(f".{wanted}")):
        return f"imports from {node.module}"
    if isinstance(node, ast.Import):
        for alias in node.names:
            if alias.name == wanted or alias.name.endswith(f".{wanted}"):
                return f"imports {alias.name}"
    return None


def _references_the_pin_axis(tree: ast.Module) -> str | None:
    """A reason string if the module imports/references the pin axis, else None."""
    for node in ast.walk(tree):
        reason = _imports_module_named(node, _PIN_MODULE)
        if reason is not None:
            return reason
        if isinstance(node, ast.Name) and node.id == _PIN_TABLE:
            return f"references {_PIN_TABLE}"
        if isinstance(node, ast.Attribute) and node.attr == _PIN_TABLE:
            return f"references {_PIN_TABLE}"
    return None


def ranking_order_ignores_the_pin(targets: Iterable[Path] | None = None) -> CheckResult:
    """The ranked-order computation has no dependency on the pin axis (FR-43/AD-39), so a pin can
    never move a *pièce* in the order — it moves exactly one *pièce* in the VIEW only."""
    name, ad = "the ranked order ignores the pin", "AD-39"
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
        reason = _references_the_pin_axis(tree)
        if reason is not None:
            offenders.append(
                f"{path.name}: the ranked order {reason} — a pin must not be an ordering input "
                "(FR-43/AD-39)")
    if unparseable:
        return CheckResult(
            name, ad, False, f"cannot parse (failing closed, cannot verify): {unparseable}")
    if offenders:
        return CheckResult(name, ad, False, f"ranked order depends on the pin axis: {offenders}")
    return CheckResult(
        name, ad, True, "the ranked-order modules do not import or reference the pin axis")


def run() -> list[CheckResult]:
    return [ranking_order_ignores_the_pin()]
