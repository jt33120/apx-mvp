"""The constant-truth-status gate (Story 3.1, AD-20 / FR-12 / FR-56).

*Truth status* is a property of the result set, set at **exactly one construction site per engine**
and a **constant** there — no threshold in any configuration can produce an **exhaustive** label
(AD-20). This check makes that mechanical, anchored on the ``TruthStatus`` **type** (not a guessed
field name): a ``TruthStatus`` member may appear only as a **constant, non-overridable** data slot —
``field(default=<member>, init=False)`` or a ``ClassVar`` — or in read comparisons. It **fires** on:

- a ``TruthStatus`` member SELECTED by a condition anywhere — an ``IfExp``/``BoolOp`` of members
  (the v1 defect: *a similarity threshold in the costume of a proof*);
- a ``@property``/method that RETURNS a member (a computed status is not "carried in data");
- a status field that is init-able or non-constant (a caller could override it);
- a runtime relabel via ``object.__setattr__(self, "…", <member>)`` (bypasses ``frozen``);
- a **suggestive** result-set type that carries a completeness-shaped (denominator) field — a
  suggestive set can never express completeness (AD-20).

It is vacuous only when NO ``TruthStatus`` member appears at all, and admits a second engine's
``EXHAUSTIVE`` type (3.2) unchanged. Detection is by name for the denominator field (best-effort);
the constant/selection anchor is on the type. Fails closed on an unparseable file; injectable
``roots``. The shipped set also blocks a relabel at runtime (frozen + init=False) short of a
deliberate ``object.__setattr__``.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path

from apx.checks.import_contracts import CheckResult
from apx.checks.payload_schema import _fail_closed, _load_trees, _parse

_APX_ROOT = Path(__file__).resolve().parent.parent
_RUNTIME_EXCLUDE = frozenset({"checks", "fitness", "timedrun", "__pycache__"})
_MEMBERS = frozenset({"SUGGESTIVE", "EXHAUSTIVE"})
# Completeness-shaped field names a suggestive set must never carry (AD-20). Best-effort by token.
_DENOMINATOR_TOKENS = (
    "total", "denominator", "population", "cardinality", "corpus_size", "count_of",
)


def _runtime_trees() -> tuple[list[tuple[Path, ast.Module]], list[str]]:
    trees: list[tuple[Path, ast.Module]] = []
    unparseable: list[str] = []
    for path in sorted(_APX_ROOT.rglob("*.py")):
        if set(path.parts) & _RUNTIME_EXCLUDE:
            continue
        tree = _parse(path)
        if tree is None:
            unparseable.append(path.name)
        else:
            trees.append((path, tree))
    return trees, unparseable


def _is_member(node: ast.AST | None) -> bool:
    """A ``TruthStatus`` member access — ``TruthStatus.SUGGESTIVE``, an alias ``TS.SUGGESTIVE``, or
    a qualified ``m.TruthStatus.SUGGESTIVE``. Matched by the member attr name (alias-tolerant)."""
    return isinstance(node, ast.Attribute) and node.attr in _MEMBERS


def _mentions_member(node: ast.AST) -> bool:
    return any(_is_member(n) for n in ast.walk(node))


def _selects_member(node: ast.AST) -> bool:
    """A member SELECTED by a condition — an ``IfExp`` or ``BoolOp`` whose branches yield a member.
    This is the threshold-derived-label anti-pattern, fired wherever it appears."""
    if isinstance(node, ast.IfExp):
        return _mentions_member(node.body) or _mentions_member(node.orelse)
    if isinstance(node, ast.BoolOp):
        return any(_mentions_member(v) for v in node.values)
    return False


def _is_setattr_relabel(node: ast.AST) -> bool:
    """``object.__setattr__(x, "…", <member>)`` — a runtime relabel bypassing ``frozen``."""
    if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
        return False
    if node.func.attr != "__setattr__":
        return False
    return any(_is_member(arg) or _selects_member(arg) for arg in node.args)


def _annotation_is_truthstatus(ann: ast.expr | None) -> bool:
    if isinstance(ann, ast.Name):
        return ann.id == "TruthStatus"
    if isinstance(ann, ast.Attribute):
        return ann.attr == "TruthStatus"
    if isinstance(ann, ast.Subscript):          # ClassVar[TruthStatus] / Final[TruthStatus]
        return _annotation_is_truthstatus(ann.slice)
    return False


def _is_classvar(ann: ast.expr | None) -> bool:
    if isinstance(ann, ast.Subscript):
        base = ann.value
        return (isinstance(base, ast.Name) and base.id in {"ClassVar", "Final"}) or (
            isinstance(base, ast.Attribute) and base.attr in {"ClassVar", "Final"})
    return False


def _kw(call: ast.Call, name: str) -> ast.expr | None:
    for kw in call.keywords:
        if kw.arg == name:
            return kw.value
    return None


def _constant_member_from(value: ast.expr | None, annotation: ast.expr | None) -> str | None:
    """The member name if ``value`` is a constant, non-overridable ``TruthStatus`` slot, else None.
    Accepted: ``field(default=<member>, init=False)``; or a ``ClassVar``/``Final`` with a bare
    member. A bare member with a plain annotation is init-able (overridable) → not accepted."""
    if _is_classvar(annotation) and _is_member(value):
        return value.attr  # type: ignore[union-attr]
    is_field = (
        isinstance(value, ast.Call) and isinstance(value.func, ast.Name)
        and value.func.id == "field"
    )
    if is_field:
        default = _kw(value, "default")
        init = _kw(value, "init")
        init_false = isinstance(init, ast.Constant) and init.value is False
        if _is_member(default) and init_false:
            return default.attr  # type: ignore[union-attr]
    return None


def _completeness_field(cls: ast.ClassDef) -> str | None:
    for stmt in cls.body:
        target = None
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            target = stmt.target.id
        elif isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 \
                and isinstance(stmt.targets[0], ast.Name):
            target = stmt.targets[0].id
        if target and any(tok in target.lower() for tok in _DENOMINATOR_TOKENS):
            return target
    return None


def _class_status_finding(cls: ast.ClassDef) -> tuple[int, str | None]:
    """(status sites in this class, first offence detail or None). A status site is a field whose
    annotation is ``TruthStatus`` or whose value mentions a member, or a member-returning method."""
    sites = 0
    for stmt in cls.body:
        if isinstance(stmt, ast.FunctionDef | ast.AsyncFunctionDef):
            for sub in ast.walk(stmt):
                if isinstance(sub, ast.Return) and sub.value is not None and _is_member(sub.value):
                    sites += 1
                    return sites, f"{cls.name}.{stmt.name} computes truth status; it must be data"
            continue
        if not isinstance(stmt, ast.AnnAssign | ast.Assign):
            continue
        annotation = stmt.annotation if isinstance(stmt, ast.AnnAssign) else None
        value = stmt.value
        is_status = _annotation_is_truthstatus(annotation) or (value is not None
                                                               and _mentions_member(value))
        if not is_status:
            continue
        sites += 1
        member = _constant_member_from(value, annotation)
        if member is None:
            return sites, f"{cls.name} truth status is overridable or non-constant"
        if member == "SUGGESTIVE":
            bad = _completeness_field(cls)
            if bad is not None:
                return sites, f"{cls.name} is suggestive yet carries completeness field {bad!r}"
    return sites, None


def truth_status_is_constant_per_engine(roots: Iterable[Path] | None = None) -> CheckResult:
    """Every result-set type sets ``truth_status`` to a constant ``TruthStatus`` member a caller/
    config cannot override (AD-20). Vacuous until a member appears; fires on a derived/computed/
    overridable status or a suggestive set that carries a denominator."""
    name, ad = "truth status is a constant construction site per engine", "AD-20"
    trees, unparseable = _runtime_trees() if roots is None else _load_trees(list(roots))
    if unparseable:
        return _fail_closed(name, ad, unparseable)
    sites = 0
    for path, tree in trees:
        for node in ast.walk(tree):
            if _selects_member(node):
                return CheckResult(
                    name, ad, False,
                    f"{path.name}: a truth status selected by a condition — a threshold-derived "
                    "label; no config may produce it (AD-20)")
            if _is_setattr_relabel(node):
                return CheckResult(
                    name, ad, False,
                    f"{path.name}: truth status relabelled via object.__setattr__ (AD-20)")
        for cls in [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]:
            found, detail = _class_status_finding(cls)
            sites += found
            if detail is not None:
                return CheckResult(name, ad, False, f"{path.name}:{detail} (AD-20)")
    if sites == 0:
        return CheckResult(name, ad, True,
                           f"vacuous: no result-set type carries a truth status ({len(trees)} f.)")
    return CheckResult(name, ad, True,
                       f"every truth status site ({sites}) is a non-overridable constant (AD-20)")
