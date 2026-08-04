"""AD-37 / AD-7 — the ranking version + ranked entry tables are append-only, one owning module
(Story 4.3).

FR-39 makes a *ranking version* the immutable identity of a produced order, retained and
referenceable; AD-7 forbids a hard delete; AD-37 requires one owning use case per write ("ranking
version | created | never mutated after creation"). The tractable static shadow, mirroring
``case_theory_ownership`` and generalised over BOTH ranking tables (``RankingVersion``,
``RankedEntry``):

- a ``RankingVersion(...)`` / ``RankedEntry(...)`` ORM construction may occur ONLY inside the store
  adapter (``adapters/store_postgres``) — a construction elsewhere is a second writer AD-37 forbids;
- neither table is ever UPDATEd or DELETEd anywhere (append-only, AD-7). Every reachable mutation
  idiom fails the build: a Core ``update(RankingVersion)`` / ``delete(RankedEntry)``; an ORM
  ``query(...).update(...)`` / ``.delete()``; a raw ``UPDATE`` / ``DELETE … ranking_version`` /
  ``ranked_entry``; **a ``session.delete(row)`` of a locally-bound instance**; and **an attribute
  assignment ``row.rank = …`` to one**. A re-ranking is a NEW version (new rows) — never an edit.

Instance-level ops are caught when the instance is a same-function local bound from a **read** of
the
model. Two residual idioms are beyond AST-only reach and NOT caught: an instance handed **across
functions**, and a construction under an **aliased import**. Also NOT flagged: the migration's
``op.drop_table`` (a schema drop, not a row DELETE) and a direct construction that builds a NEW row
(an append). Note the store imports ``RankingVersion as RankingVersionRow`` — the check matches the
model class name at its construction/read site, which is the real one (``RankingVersion``), because
a
NAMED alias rebinds only the local name while the check anchors on the model identifier as written;
the store's ``RankingVersionRow(...)`` construction is inside the store adapter and thus allowed
regardless. Fails closed on an unparseable file.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path

from apx.checks.import_contracts import CheckResult
from apx.checks.payload_schema import _is_call_to, _iter_py, _parse

_APX_ROOT = Path(__file__).resolve().parent.parent  # the apx/ package
_STORE_DIR = _APX_ROOT / "adapters" / "store_postgres"
# (model class name as written at the construction/read site, table name for raw-SQL detection).
# The store aliases the model as ``RankingVersionRow`` on import; both names are matched so an
# aliased construction/mutation is still flagged when it appears outside the store adapter.
_MODELS = ("RankingVersion", "RankingVersionRow", "RankedEntry")
_TABLES = ("RANKING_VERSION", "RANKED_ENTRY")


def _first_arg_is_a_model(node: ast.Call) -> bool:
    return bool(node.args) and isinstance(node.args[0], ast.Name) and node.args[0].id in _MODELS


def _mutates_a_ranking_table(node: ast.AST) -> bool:
    """A node that UPDATEs or DELETEs an existing ranking row — Core ``update/delete(Model)``, an
    ORM
    ``query(Model).update/delete``, or a raw ``UPDATE``/``DELETE`` naming either table by
    literal."""
    if not isinstance(node, ast.Call):
        return False
    if (_is_call_to(node, "update") or _is_call_to(node, "delete")) and _first_arg_is_a_model(node):
        return True
    if isinstance(node.func, ast.Attribute) and node.func.attr in {"update", "delete"} and any(
            isinstance(n, ast.Name) and n.id in _MODELS for n in ast.walk(node.func)):
        return True
    if _is_call_to(node, "text") or _is_call_to(node, "execute"):
        for a in node.args:
            if isinstance(a, ast.Constant) and isinstance(a.value, str):
                up = a.value.upper()
                if any(t in up for t in _TABLES) and ("UPDATE" in up or "DELETE" in up):
                    return True
    return False


def _constructs_a_model(node: ast.AST) -> bool:
    return isinstance(node, ast.Call) and any(_is_call_to(node, m) for m in _MODELS)


def _loaded_instance_names(fn: ast.FunctionDef) -> set[str]:
    """Local names in ``fn`` bound to a LOADED ranking instance — an assignment whose right side
    READS a ranking model (``session.get(RankingVersion, …)``, ``select(RankedEntry)``). A direct
    construction builds a NEW row (an append) and is excluded."""
    names: set[str] = set()
    for node in ast.walk(fn):
        if not isinstance(node, ast.Assign):
            continue
        rhs = node.value
        if isinstance(rhs, ast.Call) and any(_is_call_to(rhs, m) for m in _MODELS):
            continue  # a construction builds a new row, not a loaded instance
        if any(isinstance(n, ast.Name) and n.id in _MODELS for n in ast.walk(rhs)):
            names.update(t.id for t in node.targets if isinstance(t, ast.Name))
    return names


def _mutates_a_loaded_instance(fn: ast.FunctionDef) -> bool:
    """A ``session.delete(row)`` or an attribute assignment ``row.<col> = …`` where ``row`` is a
    local bound from a read of a ranking model — the in-store way to hard-delete or edit an existing
    row, which append-only (AD-7) forbids."""
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


def ranking_version_is_append_only(roots: Iterable[Path] | None = None) -> CheckResult:
    """The ranking version + ranked entry tables are append-only and single-owner (AD-37/AD-7). A
    construction outside the store adapter, or ANY UPDATE/DELETE of either table, fails the
    build."""
    name, ad = "ranking versions are append-only, one owner", "AD-37"
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
            if _constructs_a_model(node) and not in_store:
                offenders.append(
                    f"{path}: a ranking model is constructed outside the store adapter (AD-37)")
            if _mutates_a_ranking_table(node):
                offenders.append(
                    f"{path}: ranking_version/ranked_entry UPDATE/DELETE-d (AD-7 append-only)")
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) \
                    and _mutates_a_loaded_instance(node):
                offenders.append(
                    f"{path}: a loaded ranking row is deleted/mutated in {node.name}() "
                    "(AD-7 append-only)")
    if unparseable:
        return CheckResult(
            name, ad, False, f"cannot parse (failing closed, cannot verify): {unparseable}")
    if offenders:
        return CheckResult(
            name, ad, False,
            f"ranking append-only / ownership violated: {offenders} — AD-37/AD-7 require one "
            "owning module and forbid mutating or deleting an existing ranking row")
    return CheckResult(
        name, ad, True,
        "ranking_version/ranked_entry are constructed only in the store adapter and never "
        "UPDATE/DELETE-d")


def run() -> list[CheckResult]:
    return [ranking_version_is_append_only()]
