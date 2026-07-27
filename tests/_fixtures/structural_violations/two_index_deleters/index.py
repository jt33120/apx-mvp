"""Two call sites for a destructive index op (FR-10/AD-7 violation). AST-scanned."""

from __future__ import annotations


def rebuild(store: object) -> None:
    store.drop_collection()  # destructive index op — call site 1


def repair(store: object) -> None:
    store.drop_collection()  # destructive index op — call site 2
