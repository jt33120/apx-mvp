"""AD-37 / AD-7 — the taxonomy-label ledger is append-only, one owning module (Story 4.5, FR-40).

FR-40 makes a per-*pièce* taxonomy label an ordinary, **reversible** cell edit: a change and its
reversal are BOTH new entries, never an overwrite. AD-7 forbids a hard delete; AD-37 requires one
owning use case per write. The tractable static shadow, mirroring the sibling append-only checks
(``case_theory_version_is_append_only`` / ``ranking_version_is_append_only``):

- a ``TaxonomyLabelEntry(...)`` ORM construction may occur ONLY inside the store adapter
  (``adapters/store_postgres``) — a construction anywhere else is a second writer AD-37 forbids;
- the table is NEVER UPDATEd or DELETEd anywhere (append-only, AD-7). Every reachable mutation idiom
  fails the build: a Core ``update(TaxonomyLabelEntry)`` / ``delete(TaxonomyLabelEntry)``; an ORM
  ``query(TaxonomyLabelEntry).update(...)`` / ``.delete()``; a raw ``UPDATE`` / ``DELETE …
  taxonomy_label_entry``; **a ``session.delete(row)`` of a locally-bound entry instance**; and **an
  attribute assignment ``row.label = …`` to one**. A reversal is an INSERT of a new entry restoring
  a prior value — never an UPDATE of the current one — so append-only is preserved and the change
  log is complete.

Instance-level ops are caught when ``row`` is a same-function local bound from a **read** of the
model. The same two residual idioms as the sibling checks are beyond AST-only static reach and are
NOT caught (an instance handed **across functions**, and a construction under an **aliased
import**). Also NOT flagged: the migration's ``op.drop_table`` (a schema drop, not a row DELETE), or
a direct
``TaxonomyLabelEntry(...)`` that builds a NEW row (an append). Fails closed on an unparseable file.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path

from apx.checks.import_contracts import CheckResult
from apx.checks.payload_schema import _is_call_to, _iter_py, _parse

_APX_ROOT = Path(__file__).resolve().parent.parent  # the apx/ package
_STORE_DIR = _APX_ROOT / "adapters" / "store_postgres"
_MODEL = "TaxonomyLabelEntry"
_TABLE = "TAXONOMY_LABEL_ENTRY"


def _first_arg_is_model(node: ast.Call) -> bool:
    return bool(node.args) and isinstance(node.args[0], ast.Name) and node.args[0].id == _MODEL


def _mutates_taxonomy_label(node: ast.AST) -> bool:
    """A node that UPDATEs or DELETEs an existing ``taxonomy_label_entry`` row — every idiom a
    second owner could use to break append-only. A construction ``TaxonomyLabelEntry(...)`` (an
    INSERT) is
    NOT a mutation and is not flagged here."""
    if not isinstance(node, ast.Call):
        return False
    if (_is_call_to(node, "update") or _is_call_to(node, "delete")) and _first_arg_is_model(node):
        return True  # update(TaxonomyLabelEntry) / delete(TaxonomyLabelEntry)
    if isinstance(node.func, ast.Attribute) and node.func.attr in {"update", "delete"} and any(
            isinstance(n, ast.Name) and n.id == _MODEL for n in ast.walk(node.func)):
        return True  # .update({...})/.delete() on a query/select of the model
    if _is_call_to(node, "text") or _is_call_to(node, "execute"):
        for a in node.args:  # raw SQL that UPDATEs/DELETEs the table by literal name
            if isinstance(a, ast.Constant) and isinstance(a.value, str):
                up = a.value.upper()
                if _TABLE in up and ("UPDATE" in up or "DELETE" in up):
                    return True
    return False


def _loaded_instance_names(fn: ast.FunctionDef) -> set[str]:
    """Local names in ``fn`` bound to a LOADED ``TaxonomyLabelEntry`` instance — an assignment whose
    right side READS the model. A direct construction ``x = TaxonomyLabelEntry(...)`` builds a NEW
    row (an append) and is deliberately excluded."""
    names: set[str] = set()
    for node in ast.walk(fn):
        if not isinstance(node, ast.Assign):
            continue
        rhs = node.value
        if isinstance(rhs, ast.Call) and _is_call_to(rhs, _MODEL):
            continue  # a construction builds a new row, not a loaded instance
        if any(isinstance(n, ast.Name) and n.id == _MODEL for n in ast.walk(rhs)):
            names.update(t.id for t in node.targets if isinstance(t, ast.Name))
    return names


def _mutates_a_loaded_instance(fn: ast.FunctionDef) -> bool:
    """Within ``fn``, a ``session.delete(row)`` or an attribute assignment ``row.<col> = …`` where
    ``row`` is a local bound from a read of the model — the in-store way to hard-delete or edit an
    existing entry, which append-only (AD-7) forbids."""
    loaded = _loaded_instance_names(fn)
    if not loaded:
        return False
    for node in ast.walk(fn):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "delete" and len(node.args) == 1
                and isinstance(node.args[0], ast.Name) and node.args[0].id in loaded):
            return True  # session.delete(row)
        if isinstance(node, ast.Assign | ast.AugAssign):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name)
                   and t.value.id in loaded for t in targets):
                return True  # row.<col> = …
    return False


def taxonomy_label_is_append_only(roots: Iterable[Path] | None = None) -> CheckResult:
    """The taxonomy-label ledger is append-only and single-owner (AD-37/AD-7). A
    ``TaxonomyLabelEntry(...)`` construction outside the store adapter, or ANY UPDATE/DELETE of the
    table, fails the build — so a label edit and its reversal are always new entries (FR-40)."""
    name, ad = "taxonomy labels are append-only, one owner", "AD-37"
    roots = list(roots) if roots is not None else [_APX_ROOT]
    offenders: list[str] = []
    unparseable: list[str] = []
    for path in _iter_py(roots):
        tree = _parse(path)
        if tree is None:
            unparseable.append(path.name)
            continue
        resolved = path.resolve()
        in_store = _STORE_DIR in resolved.parents or resolved == _STORE_DIR
        for node in ast.walk(tree):
            if _is_call_to(node, _MODEL) and not in_store:
                offenders.append(f"{path}: {_MODEL} constructed outside the store adapter (AD-37)")
            if _mutates_taxonomy_label(node):
                offenders.append(f"{path}: taxonomy_label_entry UPDATE/DELETE-d (AD-7 append-only)")
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) \
                    and _mutates_a_loaded_instance(node):
                offenders.append(
                    f"{path}: a loaded TaxonomyLabelEntry is deleted/mutated in {node.name}() "
                    "(AD-7 append-only)")
    if unparseable:
        return CheckResult(
            name, ad, False, f"cannot parse (failing closed, cannot verify): {unparseable}")
    if offenders:
        return CheckResult(
            name, ad, False,
            f"taxonomy-label append-only / ownership violated: {offenders} — AD-37/AD-7 require one"
            " owning module and forbid mutating or deleting an existing label entry")
    return CheckResult(
        name, ad, True,
        "taxonomy_label_entry is constructed only in the store adapter and never UPDATE/DELETE-d")


def run() -> list[CheckResult]:
    return [taxonomy_label_is_append_only()]
