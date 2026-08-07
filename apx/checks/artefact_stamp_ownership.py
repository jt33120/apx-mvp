"""AD-37 / AD-7 — the freshness-stamp ledger is append-only, one owning module (Story 4.13, FR-58).

A stamp records **what the inputs were** when an artefact was produced. Updating one would rewrite
history so that a stale artefact reads fresh — the single most valuable row to tamper with in this
whole design, because staleness is decided by comparing against it. So the ledger is append-only
(AD-7) with one owning module (AD-37), the tractable static shadow mirroring
``line_placement_is_append_only`` / ``pin_ledger_is_append_only``:

- an ``ArtefactStamp(...)`` ORM construction may occur ONLY inside the store adapter
  (``adapters/store_postgres``) — a construction anywhere else is a second writer AD-37 forbids;
- the table is NEVER UPDATEd or DELETEd anywhere. Every reachable mutation idiom fails the build: a
  Core ``update(ArtefactStamp)`` / ``delete(ArtefactStamp)``; an ORM
  ``query(ArtefactStamp).update(...)`` / ``.delete()``; a raw ``UPDATE`` / ``DELETE …
  artefact_stamp``; a ``session.delete(row)`` of a locally-bound stamp; and an attribute assignment
  ``row.<col> = …`` to one. Re-producing an artefact mints a NEW artefact with a NEW stamp — FR-58's
  *"resolved only by an explicit user-initiated recomputation producing a new artefact"* — never a
  refreshed stamp on the old one.

The table is additionally evidential by default under Story 4.12's ``evidential_tables`` rule (every
mapped table minus the written transient allow-list), so the bounded runtime probe already fails on
any DELETE against it. This check adds what the probe cannot see: the UPDATE, and the second writer.

The same two residual idioms as the sibling checks are beyond AST-only static reach and are NOT
caught (an instance handed **across functions**, a construction under an **aliased import**). Also
NOT flagged: the migration's ``op.drop_table`` (a schema drop), or an ``ArtefactStamp(...)`` that
builds a NEW row (an append). Fails closed on an unparseable file.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path

from apx.checks.import_contracts import CheckResult
from apx.checks.payload_schema import _is_call_to, _iter_py, _parse

_APX_ROOT = Path(__file__).resolve().parent.parent  # the apx/ package
_STORE_DIR = _APX_ROOT / "adapters" / "store_postgres"
_MODEL = "ArtefactStamp"
_TABLE = "ARTEFACT_STAMP"


def _first_arg_is_model(node: ast.Call) -> bool:
    return bool(node.args) and isinstance(node.args[0], ast.Name) and node.args[0].id == _MODEL


def _mutates_stamp(node: ast.AST) -> bool:
    """A node that UPDATEs or DELETEs an existing ``artefact_stamp`` row. A construction
    ``ArtefactStamp(...)`` (an INSERT) is NOT a mutation and is not flagged here."""
    if not isinstance(node, ast.Call):
        return False
    if (_is_call_to(node, "update") or _is_call_to(node, "delete")) and _first_arg_is_model(node):
        return True  # update(ArtefactStamp) / delete(ArtefactStamp)
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


def _loaded_instance_names(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    """Local names bound to a LOADED ``ArtefactStamp`` — an assignment whose right side READS the
    model. A direct construction builds a NEW row (an append) and is deliberately excluded."""
    names: set[str] = set()
    for node in ast.walk(fn):
        if not isinstance(node, ast.Assign):
            continue
        rhs = node.value
        if isinstance(rhs, ast.Call) and _is_call_to(rhs, _MODEL):
            continue
        if any(isinstance(n, ast.Name) and n.id == _MODEL for n in ast.walk(rhs)):
            names.update(t.id for t in node.targets if isinstance(t, ast.Name))
    return names


def _mutates_a_loaded_instance(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """A ``session.delete(row)`` or an attribute assignment ``row.<col> = …`` where ``row`` is a
    local bound from a read of the model — the in-store way to rewrite a recorded stamp."""
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


def artefact_stamp_is_append_only(roots: Iterable[Path] | None = None) -> CheckResult:
    """The freshness-stamp ledger is append-only and single-owner (AD-37/AD-7). An
    ``ArtefactStamp(...)`` construction outside the store adapter, or ANY UPDATE/DELETE of the
    table, fails the build — so a stale artefact can never be made to read fresh (FR-58)."""
    name, ad = "artefact stamps are append-only, one owner", "AD-37"
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
            if _mutates_stamp(node):
                offenders.append(f"{path}: artefact_stamp UPDATE/DELETE-d (AD-7 append-only)")
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) \
                    and _mutates_a_loaded_instance(node):
                offenders.append(
                    f"{path}: a loaded ArtefactStamp is deleted/mutated in {node.name}() "
                    "(AD-7 append-only)")
    if unparseable:
        return CheckResult(
            name, ad, False, f"cannot parse (failing closed, cannot verify): {unparseable}")
    if offenders:
        return CheckResult(
            name, ad, False,
            f"artefact-stamp append-only / ownership violated: {offenders} — AD-37/AD-7 require one"
            " owning module and forbid rewriting the inputs an artefact was produced under")
    return CheckResult(
        name, ad, True,
        "artefact_stamp is constructed only in the store adapter and never UPDATE/DELETE-d")


def run() -> list[CheckResult]:
    return [artefact_stamp_is_append_only()]
