"""FR-41 — a justification's checkable part is its NAMED evidence, never the sentence alone (Story
4.6).

The R-11 mitigation made structural: the one-line justification is a model **summary**, and the
control a reader checks is the **named evidence** — the *retained extracts* (a chunk id + quoted
passage) or the named intrinsic signals. The domain value object ``Justification`` enforces this in
``__post_init__`` (it cannot be constructed without named evidence). The tractable static shadow —
mirroring ``confidence_has_one_derivation`` — keeps that invariant unbypassable: the
``Justification`` value object may be **constructed only inside
``apx/core/domain/justification.py``** (which also owns ``build_justification`` and
``rebuild_justification``). A ``Justification(...)`` construction anywhere else in the product
runtime could evade the evidence invariant, so it fails the build.

**Second leg (a review finding).** The invariant must also run at the PERSISTENCE seam: the read
path rebuilds the value object, so a row written without the invariant would raise on every read —
and since recording is write-once and AD-7 forbids a delete, that justification would be unreadable
forever. So ``SqlStore.record_justification`` must call ``validate_named_evidence`` before writing.
Build-time
tooling and tests are not product runtime and are excluded. Fails closed on an unparseable file.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path

from apx.checks.import_contracts import CheckResult
from apx.checks.payload_schema import _is_call_to, _iter_py, _parse

_APX_ROOT = Path(__file__).resolve().parent.parent  # the apx/ package
_OWNER = _APX_ROOT / "core" / "domain" / "justification.py"
_VALUE = "Justification"
# not product runtime — build tooling scans itself / the harness; tests build fixtures.
_EXCLUDE_DIRS = frozenset({"checks", "fitness", "__pycache__"})
# the SECOND leg (a review finding): the persistence seam must re-run the invariant BEFORE writing.
# A row accepted without it is unreadable forever — the read rebuilds the value object, recording is
# write-once and AD-7 forbids a delete. Naming the validator here keeps that regression from
# silently returning.
_STORE_FILE = _APX_ROOT / "adapters" / "store_postgres" / "store.py"
_WRITE_FN = "record_justification"
_VALIDATOR = "validate_named_evidence"


def _fn_named(tree: ast.Module, wanted: str) -> ast.FunctionDef | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == wanted:
            return node
    return None


def _write_seam_validates(target: Path) -> str | None:
    """A reason string if the persistence seam does NOT re-run the invariant, else None."""
    if not target.exists():
        return f"the justification write seam is missing: {target.name}"
    tree = _parse(target)
    if tree is None:
        return f"cannot parse (failing closed): {target.name}"
    fn = _fn_named(tree, _WRITE_FN)
    if fn is None:
        return f"{target.name}: no {_WRITE_FN} — the write seam must validate before persisting"
    for node in ast.walk(fn):
        if isinstance(node, ast.Name) and node.id == _VALIDATOR:
            return None
        if isinstance(node, ast.Attribute) and node.attr == _VALIDATOR:
            return None
    return (
        f"{_WRITE_FN} does not call {_VALIDATOR} — a justification with no named evidence could be "
        "persisted and then be unreadable forever (write-once, AD-7 forbids a delete)")


def justification_names_its_evidence(
    roots: Iterable[Path] | None = None, write_seam: Path | None = None
) -> CheckResult:
    """A justification names checkable evidence, never the sentence alone (FR-41). Two legs: the
    ``Justification`` value object is constructed only inside ``core/domain/justification.py`` — the
    module whose ``__post_init__`` enforces that evidence-or-signals is present — so the invariant
    cannot be bypassed by a construction elsewhere; AND the persistence seam re-runs that invariant
    (``validate_named_evidence``) before writing, so a justification that could never be read back
    is never persisted."""
    name, ad = "a justification names its evidence, not just a sentence", "AD-19"
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
            continue  # the one owning module may construct Justification
        for node in ast.walk(tree):
            if _is_call_to(node, _VALUE):
                offenders.append(
                    f"{path}: {_VALUE} constructed outside justification.py (could evade the "
                    "named-evidence invariant — FR-41)")
    if unparseable:
        return CheckResult(
            name, ad, False, f"cannot parse (failing closed, cannot verify): {unparseable}")
    if offenders:
        return CheckResult(
            name, ad, False,
            f"a justification is built outside its owning module: {offenders} — FR-41 requires the "
            "named-evidence invariant hold everywhere")
    unvalidated = _write_seam_validates(write_seam if write_seam is not None else _STORE_FILE)
    if unvalidated is not None:
        return CheckResult(name, ad, False, unvalidated)
    return CheckResult(
        name, ad, True,
        "a justification names checkable evidence (Justification is built only in "
        f"core/domain/justification.py, and {_WRITE_FN} re-runs {_VALIDATOR} before persisting)")


def run() -> list[CheckResult]:
    return [justification_names_its_evidence()]
