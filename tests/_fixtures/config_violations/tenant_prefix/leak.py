"""A core-like module that branches on a tenant PREFIX — the routing form a plain equality check
misses. Must be caught by the broadened check (AD-24). AST-scanned only, never imported."""

from __future__ import annotations


def route(tenant: str) -> str:
    if tenant.startswith("cabinet-dupont"):  # forbidden: a tenant is never a branch
        return "special"
    return "default"
