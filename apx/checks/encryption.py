"""Encryption structural properties (story 1.7; AD-31, AD-33). Two static checks:

- **sensitive_columns_are_encrypted:** every content-bearing model column uses the
  ``EncryptedText`` type, AND ``piece.full_text`` does **not** — it is the AD-31 named
  exception (the deterministic text index; you cannot ILIKE ciphertext). So a future edit can
  neither silently leave a new sensitive column plaintext (a name heuristic catches a reused
  sensitive name on any table) nor accidentally encrypt the search surface and break FR-13.
- **startup_gate_is_fail_closed:** the ``startup_gate`` covers BOTH layers — the application
  key (``load_key_from_env``) and the data volume (``APX_VOLUME_ENCRYPTED``) — and **raises**,
  so it cannot be silently downgraded to a warning-and-continue.

Both are AST-only (never import the target), and both fail closed on an unparseable file.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path

from apx.checks.import_contracts import CheckResult
from apx.checks.payload_schema import _fail_closed, _load_trees

_APX_ROOT = Path(__file__).resolve().parent.parent
_MODELS_FILE = _APX_ROOT / "adapters" / "store_postgres" / "models.py"
_STARTUP_FILE = _APX_ROOT / "api" / "startup.py"

_ENCRYPTED = "EncryptedText"

# The content-bearing columns that MUST be application-encrypted at rest (the AC1 set).
_REQUIRED_ENCRYPTED = {
    ("Piece", "provenance_path"), ("Piece", "custodian"),
    ("Failure", "filename"), ("Failure", "submitted_path"), ("Failure", "detail"),
    ("AuditRecord", "detail"),
    ("LabelRecord", "rationale"),
    ("User", "mfa_secret"),
}
# The AD-31 named exceptions — MUST NOT be application-encrypted (they are searchable surfaces
# protected by volume encryption; encrypting them would break exhaustive search / the index).
_FORBIDDEN_ENCRYPTED = {("Piece", "full_text")}
# Forward protection: a column with one of these names, on ANY table, must be encrypted — so a
# new table cannot reintroduce a known-sensitive column in the clear. `full_text` is not here.
_SENSITIVE_NAMES = {
    "provenance_path", "submitted_path", "custodian", "rationale", "filename", "mfa_secret",
}


def _column_type_name(value: ast.expr) -> str | None:
    """The type token of a ``mapped_column(TYPE, ...)`` call — the first positional arg's
    name (``EncryptedText``, ``Text``, ``String`` from ``String(64)``), or ``None`` when the
    assignment is not a ``mapped_column`` call or has no positional type."""
    if not (isinstance(value, ast.Call) and isinstance(value.func, ast.Name)
            and value.func.id == "mapped_column" and value.args):
        return None
    arg = value.args[0]
    if isinstance(arg, ast.Name):
        return arg.id
    if isinstance(arg, ast.Call) and isinstance(arg.func, ast.Name):
        return arg.func.id  # e.g. String(64)
    return None


def _mapped_columns(trees: Iterable[tuple[Path, ast.Module]]) -> dict[tuple[str, str], str | None]:
    """Map ``(class_name, attr_name) -> type token`` for every ``mapped_column`` assignment."""
    columns: dict[tuple[str, str], str | None] = {}
    for _path, tree in trees:
        for cls in ast.walk(tree):
            if not isinstance(cls, ast.ClassDef):
                continue
            for stmt in cls.body:
                if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                    tname = _column_type_name(stmt.value) if stmt.value is not None else None
                    if tname is not None:
                        columns[(cls.name, stmt.target.id)] = tname
    return columns


def sensitive_columns_are_encrypted(roots: Iterable[Path] | None = None) -> CheckResult:
    """Content-bearing columns are EncryptedText; the named searchable surfaces are not."""
    name, ad = "content-bearing columns are application-encrypted", "AD-31"
    roots = list(roots) if roots is not None else [_MODELS_FILE]
    trees, unparseable = _load_trees(roots)
    if unparseable:
        return _fail_closed(name, ad, unparseable)
    columns = _mapped_columns(trees)

    for key in sorted(_REQUIRED_ENCRYPTED):
        if key not in columns:
            continue  # the class/column is not in this (possibly fixture) tree — nothing to assert
        if columns[key] != _ENCRYPTED:
            return CheckResult(name, ad, False,
                               f"{key[0]}.{key[1]} is {columns[key]}, not {_ENCRYPTED} — a "
                               "content-bearing column must be application-encrypted (AD-31)")
    for key in sorted(_FORBIDDEN_ENCRYPTED):
        if columns.get(key) == _ENCRYPTED:
            return CheckResult(name, ad, False,
                               f"{key[0]}.{key[1]} is {_ENCRYPTED} — it is an AD-31 named "
                               "exception (the searchable text index) and must stay plaintext; "
                               "encrypting it breaks exhaustive search (FR-13)")
    for (cls, attr), tname in sorted(columns.items()):
        if attr in _SENSITIVE_NAMES and tname != _ENCRYPTED:
            return CheckResult(name, ad, False,
                               f"{cls}.{attr} is {tname}, not {_ENCRYPTED} — a column with a "
                               "known-sensitive name must be application-encrypted (AD-31)")
    return CheckResult(name, ad, True,
                       "content-bearing columns are EncryptedText; the text index is not")


def _find_function(trees: Iterable[tuple[Path, ast.Module]], fn: str) -> ast.FunctionDef | None:
    for _path, tree in trees:
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == fn:
                return node
    return None


def _names_and_strings(tree: ast.Module) -> set[str]:
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            out.add(node.id)
        elif isinstance(node, ast.Attribute):
            out.add(node.attr)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            out.add(node.value)
    return out


def startup_gate_is_fail_closed(roots: Iterable[Path] | None = None) -> CheckResult:
    """``startup_gate`` names both encryption layers and raises (never a bare warning)."""
    name, ad = "the start-up gate fails closed on both layers", "AD-31"
    roots = list(roots) if roots is not None else [_STARTUP_FILE]
    trees, unparseable = _load_trees(roots)
    if unparseable:
        return _fail_closed(name, ad, unparseable)

    gate = None
    gate_tree = None
    for _path, tree in trees:
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "startup_gate":
                gate, gate_tree = node, tree
    if gate is None or gate_tree is None:
        return CheckResult(name, ad, False, "no startup_gate function found (AD-31 gate absent)")

    tokens = _names_and_strings(gate_tree)
    if "load_key_from_env" not in tokens:
        return CheckResult(name, ad, False,
                           "startup_gate does not check the application key layer "
                           "(load_key_from_env) — AD-31 requires both layers")
    if "APX_VOLUME_ENCRYPTED" not in tokens:
        return CheckResult(name, ad, False,
                           "startup_gate does not check the data-volume layer "
                           "(APX_VOLUME_ENCRYPTED) — AD-31 requires both layers")
    if not any(isinstance(n, ast.Raise) for n in ast.walk(gate)):
        return CheckResult(name, ad, False,
                           "startup_gate never raises — a warning-and-continue is not a "
                           "fail-closed gate (AD-31: no permissive default)")
    return CheckResult(name, ad, True,
                       "startup_gate checks the key and the volume layers, and raises")


def run() -> list[CheckResult]:
    return [sensitive_columns_are_encrypted(), startup_gate_is_fail_closed()]
