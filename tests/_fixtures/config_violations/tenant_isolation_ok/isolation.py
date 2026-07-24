"""A legitimate tenant-vs-tenant isolation comparison — both operands are tenant values, neither
is a literal, so this is NOT a branch on a tenant identity and must NOT be flagged. Scanned by
AST only, never imported."""

from __future__ import annotations


def same_tenant(piece, ident):
    return piece.tenant == ident.tenant  # isolation logic, not per-tenant behaviour
