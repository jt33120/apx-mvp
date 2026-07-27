"""A tenant identifier used as a branch, tree-wide (FR-30/AD-24 violation). AST-scanned."""

from __future__ import annotations


def route(tenant: str) -> str:
    if tenant == "cabinet-x":  # forbidden: a tenant is a filter argument, never a branch
        return "special"
    return "default"
