"""Scope-administration structural property (story 1.6; FR-49, AD-33). Every scope-mutating
store method audits its act — a wall may only be moved **on the record**. A mutator that skips
the audit fails the build. AST over the store adapter; fails closed on an unparseable file;
carries a failure fixture.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path

from apx.checks.import_contracts import CheckResult
from apx.checks.payload_schema import _fail_closed, _is_call_to, _load_trees

_STORE_DIR = Path(__file__).resolve().parent.parent / "adapters" / "store_postgres"

# The scope/authority-mutating store methods — each must write an audit entry (FR-49/AC1),
# including create_user (it grants scopes and, possibly, the administrative authority).
_MUTATORS = frozenset({
    "grant_scope", "revoke_scope", "rescope_matter", "set_user_admin", "create_user",
})


def _calls_append_audit(func: ast.AST) -> bool:
    # A lexical match (the token appears in the body). Documented limitation: it does not prove
    # the call is on every path (a dead branch would pass) — path-sensitivity is dataflow, out
    # of scope for a static check; the runtime tests cover the actual audit content.
    return any(_is_call_to(node, "_append_audit") for node in ast.walk(func))


def scope_mutations_are_audited(roots: Iterable[Path] | None = None) -> CheckResult:
    """Every scope/authority-mutating store method audits its act — a wall is only ever moved
    on the record (FR-49/AC1). On the real tree the known mutators must all be **present**
    (a rename or deletion fails the build, rather than passing vacuously)."""
    name, ad = "scope mutations are audited", "FR-49/AD-33"
    real_tree = roots is None
    roots = list(roots) if roots is not None else [_STORE_DIR]
    trees, unparseable = _load_trees(roots)
    if unparseable:
        return _fail_closed(name, ad, unparseable)
    seen: set[str] = set()
    for path, tree in trees:
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            if node.name not in _MUTATORS:
                continue
            seen.add(node.name)
            if not _calls_append_audit(node):
                return CheckResult(name, ad, False,
                                   f"{path.name}::{node.name} mutates scope without auditing it "
                                   "(FR-49 — a wall is only moved on the record)")
    missing = _MUTATORS - seen
    if real_tree and missing:
        return CheckResult(name, ad, False,
                           f"expected scope mutators are missing or renamed (each must audit): "
                           f"{sorted(missing)}")
    return CheckResult(name, ad, True, f"every scope mutator audits: {sorted(seen)}")


def run() -> list[CheckResult]:
    return [scope_mutations_are_audited()]
