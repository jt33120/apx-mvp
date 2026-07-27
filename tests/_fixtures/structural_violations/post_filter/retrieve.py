"""A retrieval post-filter: a result set AND a scope (FR-14/AD-14 violation). AST-scanned."""

from __future__ import annotations


def filter_by_scope(results: list, scopes: set) -> list:
    return [r for r in results if r.scope in scopes]  # scope applied AFTER the fetch
