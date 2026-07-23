"""The frozen-payload-schema structural properties (story 1.3; AD-9, AD-40, AD-7).

Four static checks over the source tree — never runtime tests — each with a failure-path
fixture proving it fires (the 1.1/1.2 pattern). They defend the increment's one
irreversible decision at build time:

- **one_chunk_writer (AD-8/AD-9):** exactly one function constructs a ``Chunk`` row. Two
  writers would drift into two payload contracts.
- **scope_arg_required (AD-9/AD-13):** the writer takes ``rbac_scope`` as a required
  argument with **no default anywhere** — a chunk is never written under an unstated
  scope, and scope stays an argument, never a field.
- **chunk_columns_enumerated (AD-9):** the ``chunk`` model carries no column named or
  aliased as a *scope* or a *custodian*. Those are write-time inputs resolved by join,
  never denormalised onto the row (the stale-wall / blind-reindex defect).
- **no_cascade_delete (AD-7):** no ``chunk``/``piece`` foreign key uses ``ON DELETE
  CASCADE`` / ``SET NULL`` / ``SET DEFAULT``. Deletion is a ``retired`` state, never a
  cascade that removes a chunk out from under an audit trail.

Each check accepts an explicit ``roots`` so a test can point it at a violating fixture;
the default is the shipped ``apx`` package.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable, Iterator
from pathlib import Path

from apx.checks.import_contracts import CheckResult

_APX_ROOT = Path(__file__).resolve().parent.parent  # the apx/ package
_FORBIDDEN_TOKENS = ("scope", "custodian")  # "named or aliased as a scope or a custodian"
_FORBIDDEN_ONDELETE = {"CASCADE", "SET NULL", "SET DEFAULT"}

_Func = ast.FunctionDef | ast.AsyncFunctionDef


def _iter_py(roots: Iterable[Path]) -> Iterator[Path]:
    for root in roots:
        base = root if root.is_dir() else root.parent
        for path in sorted(base.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            yield path


def _parse(path: Path) -> ast.Module | None:
    try:
        return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError):
        return None


def _parent_map(tree: ast.AST) -> dict[int, ast.AST]:
    parents: dict[int, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[id(child)] = node
    return parents


def _enclosing_func(node: ast.AST, parents: dict[int, ast.AST]) -> ast.AST | None:
    cur = parents.get(id(node))
    while cur is not None:
        if isinstance(cur, ast.FunctionDef | ast.AsyncFunctionDef):
            return cur
        cur = parents.get(id(cur))
    return None


def _is_call_to(node: ast.AST, name: str) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Name):
        return func.id == name
    if isinstance(func, ast.Attribute):
        return func.attr == name
    return False


def one_chunk_writer(roots: Iterable[Path] | None = None) -> CheckResult:
    """Exactly one function anywhere constructs a ``Chunk`` (AD-8/AD-9)."""
    name, ad = "one chunk writer", "AD-8/AD-9"
    roots = list(roots) if roots is not None else [_APX_ROOT]
    writers: list[str] = []
    module_level = 0
    for path in _iter_py(roots):
        tree = _parse(path)
        if tree is None:
            continue
        parents = _parent_map(tree)
        for node in ast.walk(tree):
            if not _is_call_to(node, "Chunk"):
                continue
            func = _enclosing_func(node, parents)
            if func is None:
                module_level += 1
            else:
                writers.append(f"{path.name}::{func.name}")  # type: ignore[attr-defined]
    distinct = sorted(set(writers))
    if module_level:
        return CheckResult(name, ad, False, f"a Chunk row is constructed at module scope "
                           f"({module_level}×) — the writer must be a single function")
    if len(distinct) == 0:
        return CheckResult(name, ad, False, "no chunk writer found — expected exactly one")
    if len(distinct) > 1:
        return CheckResult(name, ad, False, f"more than one chunk writer: {distinct}")
    return CheckResult(name, ad, True, f"the one chunk writer: {distinct[0]}")


def _param_has_default(func: _Func, param: str) -> tuple[bool, bool]:
    """Return (present, has_default) for ``param`` in ``func``'s signature."""
    a = func.args
    # positional / positional-only: defaults align to the tail of (posonly + args)
    positional = list(a.posonlyargs) + list(a.args)
    n_def = len(a.defaults)
    for i, arg in enumerate(positional):
        if arg.arg == param:
            has_default = i >= len(positional) - n_def
            return True, has_default
    # keyword-only: kw_defaults is positionally aligned, None means no default
    for arg, default in zip(a.kwonlyargs, a.kw_defaults, strict=True):
        if arg.arg == param:
            return True, default is not None
    return False, False


def scope_arg_required(roots: Iterable[Path] | None = None) -> CheckResult:
    """The ``write_chunk`` writer takes ``rbac_scope`` as a required, defaultless
    argument (AD-9/AD-13)."""
    name, ad = "rbac_scope required, no default", "AD-9/AD-13"
    roots = list(roots) if roots is not None else [_APX_ROOT]
    found_writer = False
    for path in _iter_py(roots):
        tree = _parse(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            if node.name != "write_chunk":
                continue
            found_writer = True
            present, has_default = _param_has_default(node, "rbac_scope")
            if not present:
                return CheckResult(name, ad, False,
                                   f"{path.name}::write_chunk has no rbac_scope parameter")
            if has_default:
                return CheckResult(name, ad, False,
                                   f"{path.name}::write_chunk gives rbac_scope a default — "
                                   "scope must be a required argument")
    if not found_writer:
        return CheckResult(name, ad, False, "no write_chunk found to check")
    return CheckResult(name, ad, True, "rbac_scope is required with no default")


def _class_column_names(cls: ast.ClassDef) -> list[str]:
    """The mapped column names declared on a model class body (AnnAssign targets)."""
    names: list[str] = []
    for stmt in cls.body:
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            names.append(stmt.target.id)
    return names


def chunk_columns_enumerated(roots: Iterable[Path] | None = None) -> CheckResult:
    """The ``Chunk`` model carries no scope- or custodian-named/aliased column (AD-9)."""
    name, ad = "chunk carries no scope/custodian column", "AD-9"
    roots = list(roots) if roots is not None else [_APX_ROOT]
    seen = False
    for path in _iter_py(roots):
        tree = _parse(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if not (isinstance(node, ast.ClassDef) and node.name == "Chunk"):
                continue
            seen = True
            for col in _class_column_names(node):
                low = col.lower()
                if any(tok in low for tok in _FORBIDDEN_TOKENS) or low == "rbac":
                    return CheckResult(name, ad, False,
                                       f"{path.name}: Chunk has forbidden column {col!r} "
                                       "(scope/custodian are write-time inputs, never columns)")
    if not seen:
        return CheckResult(name, ad, False, "no Chunk model found to check")
    return CheckResult(name, ad, True, "Chunk carries no scope/custodian column")


def _ondelete_value(call: ast.Call) -> str | None:
    for kw in call.keywords:
        if kw.arg == "ondelete" and isinstance(kw.value, ast.Constant):
            return str(kw.value.value).upper()
    return None


def _sql_string_args(call: ast.Call) -> list[str]:
    """String-constant positional args of a call (an ``op.execute``/``text`` DDL)."""
    return [a.value for a in call.args if isinstance(a, ast.Constant) and isinstance(a.value, str)]


def no_cascade_delete(roots: Iterable[Path] | None = None) -> CheckResult:
    """No chunk/piece FK uses ON DELETE CASCADE / SET NULL / SET DEFAULT (AD-7). Precise
    by design: it inspects only real ``ForeignKey``/``ForeignKeyConstraint`` calls and the
    SQL strings passed to ``execute``/``text`` — never comments or prose (so a docstring
    that *names* the forbidden clause, like this one, is not a false positive)."""
    name, ad = "no cascade delete on chunk/piece", "AD-7"
    roots = list(roots) if roots is not None else [_APX_ROOT]
    for path in _iter_py(roots):
        tree = _parse(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if _is_call_to(node, "ForeignKey") or _is_call_to(node, "ForeignKeyConstraint"):
                assert isinstance(node, ast.Call)
                od = _ondelete_value(node)
                if od in _FORBIDDEN_ONDELETE:
                    return CheckResult(name, ad, False,
                                       f"{path.name}: ForeignKey ondelete={od!r} (AD-7)")
            if _is_call_to(node, "execute") or _is_call_to(node, "text"):
                assert isinstance(node, ast.Call)
                for sql in _sql_string_args(node):
                    up = sql.upper()
                    hit = next((f for f in _FORBIDDEN_ONDELETE if f"ON DELETE {f}" in up), None)
                    if hit is not None:
                        return CheckResult(name, ad, False,
                                           f"{path.name}: raw SQL 'ON DELETE {hit}' (AD-7)")
    return CheckResult(name, ad, True, "no cascade/set-null/set-default delete on FKs")


def run() -> list[CheckResult]:
    """All four frozen-schema checks, for the harness to fan out over."""
    return [
        one_chunk_writer(),
        scope_arg_required(),
        chunk_columns_enumerated(),
        no_cascade_delete(),
    ]
