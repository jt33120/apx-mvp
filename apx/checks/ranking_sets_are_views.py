"""AD-39 — the *retained set* and the *discarded set* are views, never stored memberships (Story
4.3).

AD-39: *"the retained set and the discarded set are views computed over one ranked order plus pins …
never stored memberships, never a column, never a materialised table. Enforced as a structural
property: no table and no column names a retained or discarded set."* A stored membership would
drift
from the order + **the line** + pins that define it, after which "reversible labelling" becomes a
promise somebody has to keep rather than a shape in which irreversibility is unrepresentable.

The tractable static shadow: scan every ORM model (a class with a ``__tablename__``) and flag a
table
name OR a DB column name that names a retained/discarded set (contains ``retained`` or
``discarded``).
It reads the REAL DB column name (via ``payload_schema._chunk_db_columns``), so a positional
``mapped_column("discarded_set")`` behind an innocent attribute is still caught. Zero offenders
today
(the ranked order stores rank + rejection class + family, never a set membership). Fails closed on
an
unparseable file.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path

from apx.checks.import_contracts import CheckResult
from apx.checks.payload_schema import _APX_ROOT, _chunk_db_columns, _fail_closed, _load_trees

# A name that denotes a stored retained/discarded SET membership (AD-39). Matched as a substring of
# a
# lower-cased table or column name — the sets are named exactly these words in the PRD/spine.
_FORBIDDEN_TOKENS = ("retained", "discarded")

# Boundary-identity columns that legitimately contain a forbidden token but are NOT a set membership
# (Story 4.8, FR-17): the line is stored by the identity of the LAST RETAINED *pièce* — a single
# pièce id (the ordinal cut), the opposite of a stored set. AD-39 forbids materialising the
# retained/discarded SETS; it does not forbid naming the cut that DERIVES them. Exact column names
# only, so the exemption cannot be widened to a membership column by accident.
_BOUNDARY_IDENTITY_COLUMNS = frozenset({"last_retained_piece_id"})


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


def _names_a_forbidden_set(name: str) -> bool:
    lowered = name.lower()
    return any(token in lowered for token in _FORBIDDEN_TOKENS)


def no_retained_or_discarded_set_column(roots: Iterable[Path] | None = None) -> CheckResult:
    """No ORM table or column names a *retained*/*discarded* set (AD-39) — those sets are views over
    the ranked order + **the line** + pins, never a stored membership. Fails the build on a table or
    column whose name denotes such a set. The line's boundary identity
    ``last_retained_piece_id`` (a single *pièce*, FR-17 — the cut that DERIVES the sets, not a
    membership) is exempt (``_BOUNDARY_IDENTITY_COLUMNS``)."""
    name, ad = "no retained/discarded set is stored (they are views)", "AD-39"
    roots = list(roots) if roots is not None else [_APX_ROOT]
    trees, unparseable = _load_trees(roots)
    if unparseable:
        return _fail_closed(name, ad, unparseable)
    for path, tree in trees:
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            table = _tablename(node)
            if table is None:
                continue  # not an ORM model (a model declares __tablename__)
            if _names_a_forbidden_set(table):
                return CheckResult(
                    name, ad, False,
                    f"{path.name}: table {table!r} names a retained/discarded set — those sets are "
                    "views over the order + the line + pins, never a stored membership (AD-39)")
            for col in _chunk_db_columns(node):
                if col in _BOUNDARY_IDENTITY_COLUMNS:
                    continue  # the line's boundary identity (one pièce, FR-17) — not a set (AD-39)
                if _names_a_forbidden_set(col):
                    return CheckResult(
                        name, ad, False,
                        f"{path.name}: {node.name}.{col!r} names a retained/discarded set — a "
                        "membership must not be stored (AD-39)")
    return CheckResult(
        name, ad, True,
        "no table or column names a retained/discarded set (they are views over the order + the "
        "line + pins)")


def run() -> list[CheckResult]:
    return [no_retained_or_discarded_set_column()]
