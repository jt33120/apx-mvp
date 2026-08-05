"""FR-17 — **the line** is stored by the identity of the last retained *pièce*, never a bare integer
position (Story 4.8).

FR-17's load-bearing failure path: an import that adds *pièces* must not silently move what the line
designates. It cannot, **because the line is stored against the last retained *pièce* — not
"position 180" that becomes position 180 of a larger set.** This makes "never a bare integer" a
shape, not a
discipline: there is no ordinal-position column for an import to invalidate.

The tractable static shadow, mirroring ``no_retained_or_discarded_set_column``: inspect the
``line_placement`` ORM model and assert (a) it declares the identity column
``last_retained_piece_id``, and (b) it declares NO bare-integer ordinal-position column (a DB column
whose name denotes a stored line position — ``position`` / ``ordinal`` / ``cut`` / ``offset``). The
append-only ``seq`` is the ledger's monotonic order (which placement), NOT where the line falls, and
is not an ordinal-position column. Fails closed on an unparseable file or a missing model."""

from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path

from apx.checks.import_contracts import CheckResult
from apx.checks.payload_schema import _APX_ROOT, _chunk_db_columns, _fail_closed, _load_trees

_TABLE = "line_placement"
_IDENTITY_COLUMN = "last_retained_piece_id"
# substrings that denote a STORED ordinal line position (the FR-17 anti-pattern — "position 180").
# `seq` (the ledger's append order) and the pièce-identity/version columns match none of these.
_ORDINAL_TOKENS = ("position", "ordinal", "cut", "offset")


def _assigns_tablename(target: ast.expr | None) -> bool:
    return isinstance(target, ast.Name) and target.id == "__tablename__"


def _tablename(cls: ast.ClassDef) -> str | None:
    for stmt in cls.body:
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 \
                and _assigns_tablename(stmt.targets[0]) \
                and isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str):
            return stmt.value.value
        if isinstance(stmt, ast.AnnAssign) and _assigns_tablename(stmt.target) \
                and isinstance(stmt.value, ast.Constant) \
                and isinstance(stmt.value.value, str):
            return stmt.value.value
    return None


def line_is_stored_by_piece_identity(roots: Iterable[Path] | None = None) -> CheckResult:
    """The line is stored by the identity of the last retained *pièce*, never a bare integer
    (FR-17). The ``line_placement`` model must declare ``last_retained_piece_id`` and must declare
    NO ordinal-position column — so an import that adds *pièces* can never silently move it."""
    name, ad = "the line is stored by pièce identity, not a bare integer", "AD-23"
    roots = list(roots) if roots is not None else [_APX_ROOT]
    trees, unparseable = _load_trees(roots)
    if unparseable:
        return _fail_closed(name, ad, unparseable)
    for path, tree in trees:
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef) or _tablename(node) != _TABLE:
                continue
            columns = _chunk_db_columns(node)
            if _IDENTITY_COLUMN not in columns:
                return CheckResult(
                    name, ad, False,
                    f"{path.name}: {node.name} does not store the line by "
                    f"{_IDENTITY_COLUMN!r} — its identity is the last retained pièce (FR-17)")
            for col in columns:
                lowered = col.lower()
                if any(token in lowered for token in _ORDINAL_TOKENS):
                    return CheckResult(
                        name, ad, False,
                        f"{path.name}: {node.name}.{col!r} is a bare ordinal line position — the "
                        "line must be stored by the last retained pièce identity, so an import "
                        "cannot silently move it (FR-17)")
            return CheckResult(
                name, ad, True,
                "the line is stored by last_retained_piece_id, with no ordinal-position column, so "
                "an import that adds pièces cannot move what the line designates (FR-17)")
    return _fail_closed(name, ad, [f"{_TABLE} model not found (cannot verify FR-17)"])


def run() -> list[CheckResult]:
    return [line_is_stored_by_piece_identity()]
