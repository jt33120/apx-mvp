"""Tenant-isolation structural properties (story 1.4; AD-12). Two static checks that keep
the Chinese wall from regressing silently — the leak AD-12 exists to prevent has no error
message, so a build-time guard is the only reliable sentinel.

- **tenant_not_null_on_owned_tables (AD-12 write boundary):** every *tenant*-owned table
  carries a `tenant` column that is `NOT NULL`, so a record without a *tenant* cannot be
  written. Introspects the SQLAlchemy metadata (the real DDL nullability); a test passes a
  synthetic metadata to prove it fires.
- **scoped_access_carries_tenant (AD-12 tenant-first):** no store method applies an RBAC
  `scopes` filter without also taking a `tenant` — scope is applied *after* tenant, never
  instead of it, so a scope check can never straddle two tenants. This is the store-scoped
  slice of AD-14; the full single-read-path consolidation is a separate unit.

Both fail closed and follow the 1.1/1.2/1.3 registration pattern.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path

from sqlalchemy import MetaData

from apx.checks.import_contracts import CheckResult
from apx.checks.payload_schema import _fail_closed, _load_trees, _param_has_default

_STORE_DIR = Path(__file__).resolve().parent.parent / "adapters" / "store_postgres"

# Tables that own *tenant* data — each must carry a non-nullable `tenant` (AD-12).
# `user_scope` is excluded: it is keyed by the globally-unique `user_id` (itself
# tenant-bound) and carries no tenant of its own.
OWNED_TABLES = frozenset({
    "piece",
    "chunk",
    "failure",
    "matter_scope",
    "piece_label",
    "audit_record",
    "recall_review",
    "user_account",
})


def _base_metadata() -> MetaData:
    from apx.adapters.store_postgres.models import Base

    return Base.metadata


def tenant_not_null_on_owned_tables(metadata: MetaData | None = None) -> CheckResult:
    """Every tenant-owned table pins a non-nullable `tenant` (AD-12)."""
    name, ad = "tenant is NOT NULL on every tenant-owned table", "AD-12"
    tables = (metadata if metadata is not None else _base_metadata()).tables
    for owned in sorted(OWNED_TABLES):
        table = tables.get(owned)
        if table is None:
            continue  # absent from this metadata (e.g. a synthetic test metadata)
        col = table.columns.get("tenant")
        if col is None:
            return CheckResult(name, ad, False,
                               f"{owned} has no tenant column — a record could be written "
                               "without a tenant (AD-12)")
        if col.nullable:
            return CheckResult(name, ad, False,
                               f"{owned}.tenant is nullable — a record could be written "
                               "without a tenant")
    # any OTHER table that carries a tenant column must also make it non-nullable
    for tname, table in tables.items():
        col = table.columns.get("tenant")
        if col is not None and col.nullable:
            return CheckResult(name, ad, False, f"{tname}.tenant is nullable (AD-12)")
    return CheckResult(name, ad, True, "every tenant-owned table pins tenant NOT NULL")


def scoped_access_carries_tenant(roots: Iterable[Path] | None = None) -> CheckResult:
    """No store method applies an RBAC `scopes` filter without also taking a `tenant` —
    scope is applied after tenant, never instead of it (AD-12 tenant-first; the
    store-scoped slice of AD-14). A pure helper that merely names a matter (not a scoped
    read) is not flagged, because it takes no `scopes`."""
    name, ad = "scope is never applied without a tenant", "AD-12"
    roots = list(roots) if roots is not None else [_STORE_DIR]
    trees, unparseable = _load_trees(roots)
    if unparseable:
        return _fail_closed(name, ad, unparseable)
    offenders: list[str] = []
    for path, tree in trees:
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            has_scopes, _ = _param_has_default(node, "scopes")
            has_tenant, _ = _param_has_default(node, "tenant")
            if has_scopes and not has_tenant:
                offenders.append(f"{path.name}::{node.name}")
    if offenders:
        return CheckResult(name, ad, False,
                           f"method(s) take scopes without a tenant: {sorted(offenders)}")
    return CheckResult(name, ad, True, "every scoped access also carries a tenant")


def run() -> list[CheckResult]:
    """Both tenant-isolation checks, for the harness to fan out over."""
    return [tenant_not_null_on_owned_tables(), scoped_access_carries_tenant()]
