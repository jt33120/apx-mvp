"""The frozen-payload-schema structural properties (story 1.3; AD-9, AD-40, AD-7).

Four static checks over the source tree — never runtime tests — each with a failure-path
fixture proving it fires (the 1.1/1.2 pattern). They defend the increment's one
irreversible decision at build time:

- **one_chunk_writer (AD-8/AD-9):** exactly one function persists a ``Chunk`` row — an
  ORM ``Chunk(...)`` construction OR an ``insert(Chunk)`` Core statement. Two writers would
  drift into two payload contracts.
- **scope_arg_required (AD-9/AD-13):** the writer takes ``rbac_scope`` as a required
  argument with **no default anywhere** — a chunk is never written under an unstated
  scope, and scope stays an argument, never a field.
- **chunk_columns_enumerated (AD-9):** the ``chunk`` model's columns are **exactly a subset
  of the enumerated permitted set** — "any other column fails the build". This is an
  allowlist, not a scope/custodian denylist: it reads the real **DB column name** (a
  positional ``mapped_column("scope")`` is caught even behind an innocent attribute), and
  so it also rejects the house alias *wall* and any stray column.
- **no_cascade_delete (AD-7):** no ``chunk``/``piece`` foreign key uses ``ON DELETE
  CASCADE`` / ``SET NULL`` / ``SET DEFAULT``. Deletion is a ``retired`` state.

Every check **fails closed**: a file it cannot parse is a failure, never a silent skip
that could hide a violation. Each accepts an explicit ``roots`` so a test can point it at a
violating fixture; the default is the shipped ``apx`` package.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path

from apx.checks.import_contracts import CheckResult

_APX_ROOT = Path(__file__).resolve().parent.parent  # the apx/ package
_FORBIDDEN_ONDELETE = {"CASCADE", "SET NULL", "SET DEFAULT"}

_Func = ast.FunctionDef | ast.AsyncFunctionDef

# The AD-9 enumeration — the ONLY columns a `chunk` may carry. The embedding trio
# (`vector`, `model_id`, `model_version`) is listed so the embedder story (2.8) adds them
# without touching this check; scope/custodian and anything else are absent by design.
_PERMITTED_CHUNK_COLUMNS = frozenset({
    "chunk_id",
    "piece_id",
    "tenant",
    "matter",
    "position",
    "full_text_version",
    "chunking_config_version",
    "schema_version",
    "model_id",
    "model_version",
    "vector",
    "external_ref",
})


def _iter_py(roots: Iterable[Path]) -> Iterable[Path]:
    for root in roots:
        base = root if root.is_dir() else root.parent
        for path in sorted(base.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            yield path


def _parse(path: Path) -> ast.Module | None:
    try:
        # ValueError catches source containing a NUL byte (not a SyntaxError).
        return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError, ValueError):
        return None


def _load_trees(roots: Iterable[Path]) -> tuple[list[tuple[Path, ast.Module]], list[str]]:
    """Parse every target file. Returns (parsed trees, names that would not parse). A guard
    that cannot read a file must fail closed, not skip it silently."""
    trees: list[tuple[Path, ast.Module]] = []
    unparseable: list[str] = []
    for path in _iter_py(roots):
        tree = _parse(path)
        if tree is None:
            unparseable.append(path.name)
        else:
            trees.append((path, tree))
    return trees, unparseable


def _fail_closed(name: str, ad: str, unparseable: list[str]) -> CheckResult:
    return CheckResult(
        name, ad, False, f"cannot parse (failing closed, cannot verify): {unparseable}"
    )


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


def _constructs_chunk(node: ast.AST) -> bool:
    """A node that persists a chunk ROW: an ORM ``Chunk(...)`` construction, or an
    ``insert(Chunk)`` / ``insert(chunk)`` Core statement (the natural bulk path)."""
    if _is_call_to(node, "Chunk"):
        return True
    if _is_call_to(node, "insert"):
        assert isinstance(node, ast.Call)
        for arg in node.args:
            if isinstance(arg, ast.Name) and arg.id in ("Chunk", "chunk"):
                return True
            if isinstance(arg, ast.Attribute) and arg.attr in ("Chunk", "chunk"):
                return True
    return False


def one_chunk_writer(roots: Iterable[Path] | None = None) -> CheckResult:
    """Exactly one function anywhere persists a ``Chunk`` row (AD-8/AD-9)."""
    name, ad = "one chunk writer", "AD-8/AD-9"
    roots = list(roots) if roots is not None else [_APX_ROOT]
    trees, unparseable = _load_trees(roots)
    if unparseable:
        return _fail_closed(name, ad, unparseable)
    writers: list[str] = []
    module_level = 0
    for path, tree in trees:
        parents = _parent_map(tree)
        for node in ast.walk(tree):
            if not _constructs_chunk(node):
                continue
            func = _enclosing_func(node, parents)
            if func is None:
                module_level += 1
            else:
                writers.append(f"{path}::{func.name}")  # full path — no basename collisions
    distinct = sorted(set(writers))
    if module_level:
        return CheckResult(name, ad, False, "a Chunk row is persisted at module scope "
                           f"({module_level}×) — the writer must be a single function")
    if len(distinct) == 0:
        return CheckResult(name, ad, False, "no chunk writer found — expected exactly one")
    if len(distinct) > 1:
        return CheckResult(name, ad, False, f"more than one chunk writer: {distinct}")
    return CheckResult(name, ad, True, f"the one chunk writer: {distinct[0].rsplit('/', 1)[-1]}")


def _param_has_default(func: _Func, param: str) -> tuple[bool, bool]:
    """Return (present, has_default) for ``param`` in ``func``'s signature."""
    a = func.args
    positional = list(a.posonlyargs) + list(a.args)
    n_def = len(a.defaults)
    for i, arg in enumerate(positional):
        if arg.arg == param:
            return True, i >= len(positional) - n_def
    for arg, default in zip(a.kwonlyargs, a.kw_defaults, strict=True):
        if arg.arg == param:
            return True, default is not None
    return False, False


def scope_arg_required(roots: Iterable[Path] | None = None) -> CheckResult:
    """The ``write_chunk`` writer takes ``rbac_scope`` as a required, defaultless
    argument (AD-9/AD-13)."""
    name, ad = "rbac_scope required, no default", "AD-9/AD-13"
    roots = list(roots) if roots is not None else [_APX_ROOT]
    trees, unparseable = _load_trees(roots)
    if unparseable:
        return _fail_closed(name, ad, unparseable)
    found_writer = False
    for path, tree in trees:
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


def _mapped_column_db_name(value: ast.AST, attr_name: str) -> str | None:
    """If ``value`` is a ``mapped_column(...)`` call, return the DB column name — its first
    string positional arg if present (``mapped_column("scope", ...)``), else the attribute
    name. Return None when ``value`` is not a mapped_column call (not a column)."""
    if not (isinstance(value, ast.Call) and _is_call_to(value, "mapped_column")):
        return None
    for arg in value.args:
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            return arg.value
    return attr_name


def _chunk_db_columns(cls: ast.ClassDef) -> list[str]:
    """The DB column names a model class declares (AnnAssign and plain Assign of a
    mapped_column), each resolved to its real DB name."""
    names: list[str] = []
    for stmt in cls.body:
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            db = _mapped_column_db_name(stmt.value, stmt.target.id) if stmt.value else None
            if db is not None:
                names.append(db)
        elif isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 \
                and isinstance(stmt.targets[0], ast.Name):
            db = _mapped_column_db_name(stmt.value, stmt.targets[0].id)
            if db is not None:
                names.append(db)
    return names


def chunk_columns_enumerated(roots: Iterable[Path] | None = None) -> CheckResult:
    """The ``Chunk`` model carries only columns in the AD-9 enumeration — any other
    (a scope/custodian, the house alias *wall*, or a stray field) fails the build."""
    name, ad = "chunk columns are exactly the AD-9 enumeration", "AD-9"
    roots = list(roots) if roots is not None else [_APX_ROOT]
    trees, unparseable = _load_trees(roots)
    if unparseable:
        return _fail_closed(name, ad, unparseable)
    seen = False
    for path, tree in trees:
        for node in ast.walk(tree):
            if not (isinstance(node, ast.ClassDef) and node.name == "Chunk"):
                continue
            seen = True
            for col in _chunk_db_columns(node):
                if col not in _PERMITTED_CHUNK_COLUMNS:
                    return CheckResult(name, ad, False,
                                       f"{path.name}: Chunk has column {col!r}, not in the "
                                       "AD-9 enumeration (scope/custodian and any other "
                                       "column are forbidden)")
    if not seen:
        return CheckResult(name, ad, False, "no Chunk model found to check")
    return CheckResult(name, ad, True, "Chunk carries only enumerated columns")


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
    trees, unparseable = _load_trees(roots)
    if unparseable:
        return _fail_closed(name, ad, unparseable)
    for path, tree in trees:
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
