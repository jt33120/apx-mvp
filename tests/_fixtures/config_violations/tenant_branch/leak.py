"""A core-like module that BRANCHES on a specific tenant identity — the AD-24 violation
(``no_tenant_conditional_in_core``). Scanned by AST only, never imported."""

from __future__ import annotations


def route(tenant: str) -> str:
    if tenant == "cabinet-dupont":  # forbidden: a tenant is a filter argument, never a branch
        return "special"
    return "default"
