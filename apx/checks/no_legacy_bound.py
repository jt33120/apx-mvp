"""FR-23 / AD-7 — the legacy bound writer is superseded and cannot come back (Story 5.1).

Before Epic 5 the *confidence bound* was written by ``record_recall_review`` over the Story-2.x
label pile. Planning decision A1 replaced that population with the Epic-4 derived discarded view, so
the legacy pair is **superseded**. Superseded is not deleted (AD-7): every ``recall_review`` row
stays readable forever with its bound, its population, its reviewer and its date, and
``read_current_bound`` still falls back to them for a *matter* that has no *sampling run*.

What must not happen is a **second live writer**. Two bound-producing paths over two different
populations, both called "the discarded set", both rendered on the same surface, is the
ambiguous-referent defect the Epic 4 retrospective identified as this build's recurring failure —
installed at the one place where being wrong is said out loud to a court.

So: **zero constructions of ``RecallReview(...)`` anywhere under ``apx/``.** Reading the table is
free (history is readable), writing to it is not. Test fixtures are outside ``apx/`` and are
untouched by this check — they are allowed to seed a legacy row precisely so the fallback path
stays tested.

Reads the SOURCE of every module under ``apx/``; fails closed on an unparseable file.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path

from apx.checks.import_contracts import CheckResult
from apx.checks.payload_schema import _parse

_APX_ROOT = Path(__file__).resolve().parent.parent
_LEGACY_MODEL = "RecallReview"


def _construction_sites(tree: ast.Module) -> list[int]:
    """The line numbers where ``RecallReview(...)`` is CALLED — a construction, not a read.

    Both call shapes count: the bare name ``RecallReview(...)`` and the qualified
    ``models.RecallReview(...)``. Catching only the first would leave the writer one import style
    away from coming back, which is not a property — it is a habit."""
    sites: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        named = (isinstance(func, ast.Name) and func.id == _LEGACY_MODEL) or (
            isinstance(func, ast.Attribute) and func.attr == _LEGACY_MODEL)
        if named:
            sites.append(node.lineno)
    return sites


def no_new_legacy_bound_is_written(targets: Iterable[Path] | None = None) -> CheckResult:
    """No code path under ``apx/`` constructs a ``recall_review`` row. The legacy bound is history a
    reader can still read, never a second live writer over a second population (FR-23/AD-7)."""
    name, ad = "no new legacy bound is written", "AD-7"
    modules = sorted(targets) if targets is not None else sorted(_APX_ROOT.rglob("*.py"))
    offenders: list[str] = []
    unparseable: list[str] = []
    scanned = 0
    for path in modules:
        if not path.is_file():
            continue
        scanned += 1
        tree = _parse(path)
        if tree is None:
            unparseable.append(path.name)
            continue
        for line in _construction_sites(tree):
            offenders.append(f"{path.name}:{line}")
    if unparseable:
        return CheckResult(
            name, ad, False, f"cannot parse (failing closed, cannot verify): {unparseable}")
    if offenders:
        return CheckResult(
            name, ad, False,
            f"{_LEGACY_MODEL}(...) is constructed at {offenders} — the legacy bound was computed "
            "over the Story-2.x label pile, and Epic 5's discarded set is the derived view "
            "(decision A1). Two live bound writers over two populations is the ambiguous referent "
            "this build keeps being bitten by; the rows stay readable, the writer does not come "
            "back")
    return CheckResult(
        name, ad, True,
        f"{scanned} modules scanned; no {_LEGACY_MODEL} row is constructed anywhere in the product "
        "runtime — the legacy bound is readable history, superseded by the sampling run")


def run() -> list[CheckResult]:
    return [no_new_legacy_bound_is_written()]
