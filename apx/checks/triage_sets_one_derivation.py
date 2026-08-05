"""FR-16 / AD-39 — the retained/discarded sets have exactly ONE derivation (Story 4.7).

The *retained set* and *discarded set* are **views** computed at read time (AD-39), never stored
memberships. Their robust half: the view is produced by **one** implementation, so no surface can
hand-roll a divergent membership that quietly disagrees with the order + line + pins that define it.

The tractable static shadow, mirroring ``confidence_has_one_derivation`` /
``embedder_has_one_implementation``: the domain value object ``TriageSets`` (the only thing the sets
ARE) may be **constructed only inside ``apx/core/domain/triage_sets.py``** — the module that owns
``derive_triage_sets``. A ``TriageSets(...)`` construction anywhere else in the product runtime is a
second derivation FR-16/AD-39 forbid. (Callers such as ``store.read_triage_sets`` CALL
``derive_triage_sets`` — they never construct ``TriageSets`` — so they are not flagged.) Build-time
tooling and tests are not product runtime and are excluded. Fails closed on an unparseable file.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path

from apx.checks.import_contracts import CheckResult
from apx.checks.payload_schema import _is_call_to, _iter_py, _parse

_APX_ROOT = Path(__file__).resolve().parent.parent  # the apx/ package
_OWNER = _APX_ROOT / "core" / "domain" / "triage_sets.py"
_VALUE = "TriageSets"
# not product runtime — build tooling scans itself / the harness; tests build fixtures.
_EXCLUDE_DIRS = frozenset({"checks", "fitness", "__pycache__"})


def triage_sets_have_one_derivation(roots: Iterable[Path] | None = None) -> CheckResult:
    """The retained/discarded sets are derived by exactly one implementation (FR-16/AD-39): a
    ``TriageSets(...)`` construction outside ``core/domain/triage_sets.py`` is a second derivation
    and fails the build — so the sets stay a single auditable view, never a hand-rolled set."""
    name, ad = "the triage sets have one derivation", "AD-39"
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
            continue  # the one owning module may construct TriageSets
        for node in ast.walk(tree):
            if _is_call_to(node, _VALUE):
                offenders.append(
                    f"{path}: {_VALUE} constructed outside triage_sets.py (a second derivation of "
                    "the retained/discarded view — FR-16/AD-39)")
    if unparseable:
        return CheckResult(
            name, ad, False, f"cannot parse (failing closed, cannot verify): {unparseable}")
    if offenders:
        return CheckResult(
            name, ad, False,
            f"triage-set derivation is not single-implementation: {offenders} — AD-39 requires the "
            "sets be one auditable view over the order + line + pins")
    return CheckResult(
        name, ad, True,
        "the retained/discarded sets have one derivation (TriageSets is built only in "
        "core/domain/triage_sets.py)")


def run() -> list[CheckResult]:
    return [triage_sets_have_one_derivation()]
