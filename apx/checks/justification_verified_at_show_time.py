"""FR-11 / FR-41 — a justification is verified by exact containment at SHOW time (Story 4.6).

Every *retained extract* shown with a justification passes exact-containment verification against
its source at the moment it is shown; a justification whose extracts do not resolve is shown as
**unverified**, never as ordinary (FR-41/FR-11). The structural guarantee behind that promise: the
store's justification **read seam** cannot return a justification's evidence WITHOUT routing every
extract through the containment resolver.

This asserts that ``SqlStore.read_justification`` (the one read path) references BOTH the show-time
containment resolver (``resolve_chunk`` — the FR-11 primitive, scope-gated, re-verifying
containment) AND ``verify_justification`` (the domain check that turns each resolution into a
verified/unverified
verdict and sets ``is_unverified``). A read that stopped calling either could surface an unverified
extract as ordinary, so its absence fails the build. Fails closed on an unparseable/missing file.
"""

from __future__ import annotations

import ast
from pathlib import Path

from apx.checks.import_contracts import CheckResult
from apx.checks.payload_schema import _parse

_APX_ROOT = Path(__file__).resolve().parent.parent  # the apx/ package
_STORE_FILE = _APX_ROOT / "adapters" / "store_postgres" / "store.py"
_READ_FN = "read_justification"
_RESOLVER = "resolve_chunk"          # the FR-11 show-time containment primitive (scope-gated)
_VERIFIER = "verify_justification"   # the domain check that marks each extract verified/unverified


def _fn_named(tree: ast.Module, wanted: str) -> ast.FunctionDef | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == wanted:
            return node
    return None


def _references(fn: ast.FunctionDef, wanted: str) -> bool:
    """True if ``fn`` references a name/attribute ``wanted`` anywhere in its body (a call to
    ``self.resolve_chunk`` is an ``Attribute``; ``verify_justification`` is a ``Name``)."""
    for node in ast.walk(fn):
        if isinstance(node, ast.Attribute) and node.attr == wanted:
            return True
        if isinstance(node, ast.Name) and node.id == wanted:
            return True
    return False


def justification_verified_at_show_time(target: Path | None = None) -> CheckResult:
    """The justification read seam verifies every extract by exact containment at show time
    (FR-11/FR-41): ``read_justification`` routes evidence through both ``resolve_chunk`` and
    ``verify_justification``, so an unresolved extract can only ever be surfaced as unverified."""
    name, ad = "a justification is containment-verified at show time", "AD-10"
    path = target if target is not None else _STORE_FILE
    if not path.exists():
        return CheckResult(name, ad, False, f"the justification read seam is missing: {path.name}")
    tree = _parse(path)
    if tree is None:
        return CheckResult(name, ad, False, f"cannot parse (failing closed): {path.name}")
    fn = _fn_named(tree, _READ_FN)
    if fn is None:
        return CheckResult(
            name, ad, False,
            f"{path.name}: no {_READ_FN} — the justification read seam must verify at show time")
    missing = [w for w in (_RESOLVER, _VERIFIER) if not _references(fn, w)]
    if missing:
        return CheckResult(
            name, ad, False,
            f"{_READ_FN} does not reference {missing} — an extract could be shown without "
            "containment verification (FR-11/FR-41)")
    return CheckResult(
        name, ad, True,
        f"{_READ_FN} routes every extract through {_RESOLVER} + {_VERIFIER} — an unresolved "
        "extract is surfaced as unverified, never ordinary")


def run() -> list[CheckResult]:
    return [justification_verified_at_show_time()]
