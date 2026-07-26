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


# String methods that turn a *tenant* into a prefix/pattern branch (``tenant.startswith("x-")``).
_TENANT_BRANCH_METHODS = frozenset({"startswith", "endswith", "match", "search", "fullmatch"})


def _is_tenant_expr(node: ast.expr) -> bool:
    if isinstance(node, ast.Name):
        return node.id in _TENANT_NAMES
    if isinstance(node, ast.Attribute):
        return node.attr in _TENANT_NAMES
    return False


def _module_string_consts(tree: ast.Module) -> dict[str, str]:
    """Top-level ``NAME = "literal"`` string constants, so a branch that hides the literal behind
    a module constant (``SPECIAL = "cabinet-x"`` … ``if tenant == SPECIAL``) is still caught."""
    consts: dict[str, str] = {}
    for node in tree.body:
        targets = node.targets if isinstance(node, ast.Assign) else (
            [node.target] if isinstance(node, ast.AnnAssign) and node.value is not None else [])
        if (isinstance(node, ast.Assign | ast.AnnAssign) and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)):
            for t in targets:
                if isinstance(t, ast.Name):
                    consts[t.id] = node.value.value
    return consts


def _is_literal_operand(node: ast.expr, consts: dict[str, str]) -> bool:
    """A NON-EMPTY literal a tenant could be branched against — a non-empty constant, a non-empty
    container/dict of constants, or a Name resolving to a non-empty module string constant. An
    EMPTY string, ``None`` or an empty container is a sentinel/defensive guard and is NOT a branch
    on a tenant identity (so ``if row.tenant == "":`` is allowed, the MED-5 false positive)."""
    if isinstance(node, ast.Constant):
        return node.value not in ("", None, b"")
    if isinstance(node, ast.List | ast.Tuple | ast.Set):
        return bool(node.elts) and all(isinstance(e, ast.Constant) for e in node.elts)
    if isinstance(node, ast.Dict):  # `tenant in {"cabinet-x": handler}` — dispatch by literal key
        return bool(node.keys)
    if isinstance(node, ast.Name):
        return bool(consts.get(node.id))
    return False


def _tenant_vs_literal(compare: ast.Compare, consts: dict[str, str]) -> bool:
    """A *tenant* expression tested (==/!=/in/not in) against a non-empty literal — a branch on a
    specific tenant identity. Tenant-vs-tenant (both operands tenant expressions) is the legitimate
    isolation comparison and is NOT flagged; nor is tenant-vs-empty/None (a sentinel guard)."""
    operands = [compare.left, *compare.comparators]
    for i, op in enumerate(compare.ops):
        if not isinstance(op, _BRANCH_OPS):
            continue
        a, b = operands[i], operands[i + 1]
        if _is_tenant_expr(a) and not _is_tenant_expr(b) and _is_literal_operand(b, consts):
            return True
        if _is_tenant_expr(b) and not _is_tenant_expr(a) and _is_literal_operand(a, consts):
            return True
    return False


def _tenant_prefix_call(node: ast.Call, consts: dict[str, str]) -> bool:
    """A ``tenant.startswith("cabinet-")`` / ``.endswith`` / ``re.match``-style branch — the
    prefix-routing form that a plain equality check misses."""
    func = node.func
    if not (isinstance(func, ast.Attribute) and func.attr in _TENANT_BRANCH_METHODS):
        return False
    # `tenant.startswith(...)` (method on the tenant) OR `re.match(pat, tenant)` (tenant as arg)
    subject_is_tenant = _is_tenant_expr(func.value)
    tenant_arg = any(_is_tenant_expr(a) for a in node.args)
    if not (subject_is_tenant or tenant_arg):
        return False
    return any(_is_literal_operand(a, consts) for a in node.args)


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
    """No conditional under ``core/`` branches on a *tenant* identifier (AD-24). Catches equality /
    membership against a literal (incl. one hidden behind a module constant or a dict-literal), a
    ``.startswith``/``.endswith``/``re.match`` prefix branch, and a ``match`` on a tenant. It does
    NOT flag tenant-vs-tenant isolation checks, sentinel/empty guards, or a data structure *keyed*
    by tenant (``config[tenant]`` — the correct configuration-as-data pattern)."""
    name, ad = "no tenant identifier is a branch in core", "AD-24"
    roots = list(roots) if roots is not None else [_CORE_DIR]
    trees, unparseable = _load_trees(roots)
    if unparseable:
        return _fail_closed(name, ad, unparseable)
    for path, tree in trees:
        consts = _module_string_consts(tree)
        for node in ast.walk(tree):
            hit = (
                (isinstance(node, ast.Compare) and _tenant_vs_literal(node, consts))
                or (isinstance(node, ast.Call) and _tenant_prefix_call(node, consts))
                or (isinstance(node, ast.Match) and _match_on_tenant(node)))
            if hit:
                where = path.relative_to(_REPO_ROOT) if path.is_relative_to(_REPO_ROOT) else path
                return CheckResult(
                    name, ad, False,
                    f"{where}:{node.lineno} a tenant identifier is used as a branch — a tenant is "
                    "a filter argument and a row key, never a branch (AD-24)")
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
_README = _REPO_ROOT / "README.md"


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


def _read_block(path: Path) -> tuple[str | None, str | None]:
    """Return (block-text, error). The block is between the two markers; a missing marker yields
    (None, None) — 'no block here'. An unreadable file yields (None, <error>) — fail closed."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None, f"cannot read {path.name} (failing closed, cannot verify)"
    start, end = text.find(_DOC_START), text.find(_DOC_END)
    if start == -1 or end == -1 or end < start:
        return None, None
    return text[start + len(_DOC_START):end], None


def documented_config_keys_exist(
    doc_paths: Iterable[Path] | None = None, schema: Mapping[str, ConfigKey] | None = None
) -> CheckResult:
    """Every configuration key named in the documentation's config-reference block exists in the
    schema (AD-24/FR-56). When scanning the shipped README (the default), a MISSING or mis-marked
    block is itself a failure — the every-install artefact cannot be silently neutered by a doc
    edit. Fails closed on an unreadable file."""
    name, ad = "every documented config key exists", "AD-24"
    schema = CONFIG_SCHEMA if schema is None else schema
    scanning_readme = doc_paths is None
    paths = list(doc_paths) if doc_paths is not None else [_README]
    for path in paths:
        block, error = _read_block(path)
        if error is not None:
            return CheckResult(name, ad, False, error)
        if block is None:
            if scanning_readme:  # the README MUST carry the block — a missing one is not a pass
                return CheckResult(name, ad, False,
                                   "README.md has no config-keys block (the documented-keys guard "
                                   "would be silently neutered) — restore the markers (AD-24)")
            continue
        for key in _documented_keys(block):
            if key not in schema:
                return CheckResult(
                    name, ad, False,
                    f"{path.name} documents config key `{key}` with no backing schema entry "
                    "— a documented key that exists in zero source files (AD-24)")
    return CheckResult(name, ad, True, "every documented config key exists in the schema")


def config_reference_is_complete(
    schema: Mapping[str, ConfigKey] | None = None, readme: Path | None = None
) -> CheckResult:
    """Every schema key appears in the README config-reference block (AD-24/FR-56) — the reverse
    of ``documented_config_keys_exist``, shipped as its own build gate so a new key can never be
    added without documenting it (the two directions together keep schema and docs in lock-step).
    Fails closed on a missing block or an unreadable README."""
    name, ad = "every config key is documented", "AD-24"
    schema = CONFIG_SCHEMA if schema is None else schema
    block, error = _read_block(readme if readme is not None else _README)
    if error is not None:
        return CheckResult(name, ad, False, error)
    if block is None:
        return CheckResult(name, ad, False, "README.md has no config-keys block (AD-24/FR-56)")
    documented = set(_documented_keys(block))
    missing = [k for k in schema if k not in documented]
    if missing:
        return CheckResult(name, ad, False,
                           f"schema key(s) not documented in the README block: {sorted(missing)} "
                           "— every key must be documented (AD-24)")
    return CheckResult(name, ad, True, f"every schema key is documented ({len(schema)} key(s))")


def run() -> list[CheckResult]:
    """The configuration-as-data checks, for the harness to fan out over."""
    return [
        no_tenant_conditional_in_core(),
        config_defaults_preserve_guarantees(),
        documented_config_keys_exist(),
        config_reference_is_complete(),
    ]
