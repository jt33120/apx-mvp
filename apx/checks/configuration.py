"""Configuration-as-data structural properties (story 1.9; AD-24/AD-25). Three static checks
over source, each with a failure fixture that fires:

- **no_tenant_conditional_in_core (AD-24):** no conditional anywhere under ``core/`` reads a
  *tenant* identifier — a *tenant* is a filter argument and a row key, never a branch. Catches
  ``if tenant == "cabinet-x"`` / ``tenant in (...)`` / ``match tenant: case "x"``, but not the
  legitimate isolation comparison of two *tenant* values (``piece.tenant == ident.tenant``),
  whose operands are both non-constant. This is AD-24's own resolved, greppable check.
- **config_defaults_preserve_guarantees (AD-24):** every configuration key has a defined default,
  and no default disables the guarantee its key governs — the v1 defect was the off-corpus gate
  shipped *disabled by default*. Reads the declared schema (``apx.core.domain.config``).
- **documented_config_keys_exist (AD-24, FR-56):** every configuration key named in the
  documentation (the README config-reference block) exists in the schema — the v1 defect was
  documented keys that appeared in zero source files.

All three fail closed and follow the 1.3–1.8 registration pattern.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterable, Mapping
from pathlib import Path

from apx.checks.import_contracts import CheckResult
from apx.checks.payload_schema import _fail_closed, _load_trees
from apx.core.domain.config import CONFIG_SCHEMA, ConfigKey

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CORE_DIR = Path(__file__).resolve().parent.parent / "core"

# Identifiers that name a *tenant* — a value that flows as an argument / row key, never a branch.
_TENANT_NAMES = frozenset({
    "tenant", "tenant_id", "tenant_key", "tenant_name", "tenantid", "tenant_slug",
})
# Comparison operators that make a *tenant* a branch (equality / membership). Ordering ops are
# meaningless on a tenant identity and are not the failure this guards.
_BRANCH_OPS = (ast.Eq, ast.NotEq, ast.In, ast.NotIn)


def _is_tenant_expr(node: ast.expr) -> bool:
    if isinstance(node, ast.Name):
        return node.id in _TENANT_NAMES
    if isinstance(node, ast.Attribute):
        return node.attr in _TENANT_NAMES
    return False


def _is_constant_operand(node: ast.expr) -> bool:
    """A literal the code could branch a tenant against — a constant, or a container of them."""
    if isinstance(node, ast.Constant):
        return True
    if isinstance(node, ast.List | ast.Tuple | ast.Set):
        return bool(node.elts) and all(isinstance(e, ast.Constant) for e in node.elts)
    return False


def _tenant_vs_constant(compare: ast.Compare) -> bool:
    """True if the comparison pits a *tenant* expression against a constant with an equality /
    membership op — i.e. a branch on a specific tenant identity. A tenant-vs-tenant comparison
    (both operands non-constant) is the legitimate isolation check and is NOT flagged."""
    operands = [compare.left, *compare.comparators]
    for i, op in enumerate(compare.ops):
        if not isinstance(op, _BRANCH_OPS):
            continue
        a, b = operands[i], operands[i + 1]
        if (_is_tenant_expr(a) and _is_constant_operand(b)) or (
            _is_tenant_expr(b) and _is_constant_operand(a)
        ):
            return True
    return False


def _match_on_tenant(node: ast.Match) -> bool:
    """A ``match`` whose subject is a tenant expression and whose cases test constant values."""
    if not _is_tenant_expr(node.subject):
        return False
    return any(
        isinstance(p, ast.MatchValue | ast.MatchSingleton)
        for case in node.cases
        for p in ast.walk(case.pattern)
    )


def no_tenant_conditional_in_core(roots: Iterable[Path] | None = None) -> CheckResult:
    """No conditional under ``core/`` reads a *tenant* identifier (AD-24)."""
    name, ad = "no tenant identifier is a branch in core", "AD-24"
    roots = list(roots) if roots is not None else [_CORE_DIR]
    trees, unparseable = _load_trees(roots)
    if unparseable:
        return _fail_closed(name, ad, unparseable)
    for path, tree in trees:
        for node in ast.walk(tree):
            hit = (isinstance(node, ast.Compare) and _tenant_vs_constant(node)) or (
                isinstance(node, ast.Match) and _match_on_tenant(node))
            if hit:
                where = path.relative_to(_REPO_ROOT) if path.is_relative_to(_REPO_ROOT) else path
                return CheckResult(
                    name, ad, False,
                    f"{where}:{node.lineno} a tenant identifier is compared to a literal — a "
                    "tenant is a filter argument and a row key, never a branch (AD-24)")
    return CheckResult(name, ad, True, f"no tenant branch in {len(trees)} core module(s)")


def config_defaults_preserve_guarantees(
    schema: Mapping[str, ConfigKey] | None = None
) -> CheckResult:
    """Every key has a default, and no default disables the guarantee it governs (AD-24)."""
    name, ad = "no config default disables its guarantee", "AD-24"
    schema = CONFIG_SCHEMA if schema is None else schema
    for key, spec in schema.items():
        if spec.default is None:
            return CheckResult(name, ad, False, f"{key} has no default (AD-24: every key has one)")
        try:
            ok = spec.default_preserves_guarantee()
        except Exception as exc:  # noqa: BLE001 — a predicate that explodes fails closed
            return CheckResult(name, ad, False, f"{key}: default-guarantee check raised {exc!r}")
        if not ok:
            return CheckResult(
                name, ad, False,
                f"{key} default {spec.default!r} disables the guarantee it governs "
                f"({spec.governs}) — the v1 off-corpus-gate defect (AD-24)")
    return CheckResult(name, ad, True,
                       f"every default preserves its guarantee ({len(schema)} key(s))")


_DOC_START = "<!-- config-keys:start -->"
_DOC_END = "<!-- config-keys:end -->"
_BACKTICKED = re.compile(r"`([a-z][a-z0-9_]+)`")


def _documented_keys(block: str) -> list[str]:
    """The config keys named in a config-reference block: the backticked token in the FIRST cell
    of each markdown table row. Reading only the first column keeps default *values* elsewhere in
    the row (``fr``, ``v1``, ``true``) from being mistaken for keys."""
    keys: list[str] = []
    for line in block.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        first_cell = stripped.strip("|").split("|", 1)[0]
        match = _BACKTICKED.search(first_cell)
        if match is not None:  # the header ("Key") and separator ("---") rows carry no backticks
            keys.append(match.group(1))
    return keys


def documented_config_keys_exist(
    doc_paths: Iterable[Path] | None = None, schema: Mapping[str, ConfigKey] | None = None
) -> CheckResult:
    """Every configuration key named in the documentation's config-reference block exists in the
    schema (AD-24/FR-56). Fails closed on an unreadable documentation file."""
    name, ad = "every documented config key exists", "AD-24"
    schema = CONFIG_SCHEMA if schema is None else schema
    paths = list(doc_paths) if doc_paths is not None else [_REPO_ROOT / "README.md"]
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            return CheckResult(name, ad, False,
                               f"cannot read {path.name} (failing closed, cannot verify)")
        start = text.find(_DOC_START)
        end = text.find(_DOC_END)
        if start == -1 or end == -1 or end < start:
            continue  # no config-reference block in this doc — nothing documented to check
        for key in _documented_keys(text[start + len(_DOC_START):end]):
            if key not in schema:
                return CheckResult(
                    name, ad, False,
                    f"{path.name} documents config key `{key}` with no backing schema entry "
                    "— a documented key that exists in zero source files (AD-24)")
    return CheckResult(name, ad, True, "every documented config key exists in the schema")


def run() -> list[CheckResult]:
    """The configuration-as-data checks, for the harness to fan out over."""
    return [
        no_tenant_conditional_in_core(),
        config_defaults_preserve_guarantees(),
        documented_config_keys_exist(),
    ]
