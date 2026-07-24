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

# The scope-mutating store methods — each must write an audit entry (FR-49/AC1).
_MUTATORS = frozenset({"grant_scope", "revoke_scope", "rescope_matter", "set_user_admin"})


def _calls_append_audit(func: ast.AST) -> bool:
    return any(_is_call_to(node, "_append_audit") for node in ast.walk(func))


def scope_mutations_are_audited(roots: Iterable[Path] | None = None) -> CheckResult:
    """Every scope-mutating store method (grant/revoke/re-scope/set-admin) calls the audit
    path — a wall is only ever moved on the record (FR-49/AC1)."""
    name, ad = "scope mutations are audited", "FR-49/AD-33"
    roots = list(roots) if roots is not None else [_STORE_DIR]
    trees, unparseable = _load_trees(roots)
    if unparseable:
        return _fail_closed(name, ad, unparseable)
    seen: list[str] = []
    for path, tree in trees:
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            if node.name not in _MUTATORS:
                continue
            seen.append(node.name)
            if not _calls_append_audit(node):
                return CheckResult(name, ad, False,
                                   f"{path.name}::{node.name} mutates scope without auditing it "
                                   "(FR-49 — a wall is only moved on the record)")
    return CheckResult(name, ad, True, f"every scope mutator audits: {sorted(set(seen))}")


def run() -> list[CheckResult]:
    return [scope_mutations_are_audited()]
