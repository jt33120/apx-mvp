"""FR-42 / FR-56 — the per-pièce confidence has exactly ONE derivation (Story 4.4).

FR-42's robust half (the counterpart to ``no_model_reported_confidence``): the confidence a *pièce*
carries is produced by **one** implementation, so a second, divergent formula cannot slip in and
quietly disagree — the derivation is auditable and reproducible from the recorded method (AD-23).

The tractable static shadow, mirroring ``embedder_has_one_implementation`` /
``ranking_ownership``: the domain value object ``Confidence`` (the only thing a confidence IS) may
be
**constructed only inside ``apx/core/domain/piece_confidence.py``** — the module that owns
``derive_confidence``. A ``Confidence(...)`` construction anywhere else in the product runtime is a
second derivation FR-42 forbids. (Callers such as ``ranking.rank_cascade`` CALL
``derive_confidence``
— they never construct ``Confidence`` — so they are not flagged.) Build-time tooling and tests are
not product runtime and are excluded. Fails closed on an unparseable file.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path

from apx.checks.import_contracts import CheckResult
from apx.checks.payload_schema import _is_call_to, _iter_py, _parse

_APX_ROOT = Path(__file__).resolve().parent.parent  # the apx/ package
_OWNER = _APX_ROOT / "core" / "domain" / "piece_confidence.py"
_VALUE = "Confidence"
# not product runtime — build tooling scans itself / the harness; tests build fixtures.
_EXCLUDE_DIRS = frozenset({"checks", "fitness", "__pycache__"})


def confidence_has_one_derivation(roots: Iterable[Path] | None = None) -> CheckResult:
    """The per-pièce confidence is derived by exactly one implementation (FR-42/FR-56): a
    ``Confidence(...)`` construction outside ``core/domain/piece_confidence.py`` is a second
    derivation and fails the build."""
    name, ad = "confidence has one derivation", "AD-19"
    roots = list(roots) if roots is not None else [_APX_ROOT]
    offenders: list[str] = []
    unparseable: list[str] = []
    owner_resolved = _OWNER.resolve()
    for path in _iter_py(roots):
        if set(path.parts) & _EXCLUDE_DIRS:
            continue
        tree = _parse(path)
        if tree is None:
            unparseable.append(path.name)
            continue
        if path.resolve() == owner_resolved:
            continue  # the one owning module may construct Confidence
        for node in ast.walk(tree):
            if _is_call_to(node, _VALUE):
                offenders.append(
                    f"{path}: {_VALUE} constructed outside piece_confidence.py (a second "
                    "derivation — FR-42)")
    if unparseable:
        return CheckResult(
            name, ad, False, f"cannot parse (failing closed, cannot verify): {unparseable}")
    if offenders:
        return CheckResult(
            name, ad, False,
            f"confidence derivation is not single-implementation: {offenders} — FR-42 requires one "
            "auditable derivation")
    return CheckResult(
        name, ad, True,
        "confidence is derived by one implementation (Confidence is built only in "
        "core/domain/piece_confidence.py)")


def run() -> list[CheckResult]:
    return [confidence_has_one_derivation()]
