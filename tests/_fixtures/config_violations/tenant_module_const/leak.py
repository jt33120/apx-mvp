"""A core-like module that hides the tenant literal behind a module constant — the check resolves
top-level string constants, so this is still caught (AD-24). AST-scanned only, never imported."""

from __future__ import annotations

SPECIAL_TENANT = "cabinet-dupont"


def route(tenant: str) -> str:
    if tenant == SPECIAL_TENANT:  # forbidden even via a constant — a tenant is never a branch
        return "special"
    return "default"
