"""Structural properties that guard the runtime boundary NOW (story 1.12; AD-16/AD-45/AD-24).

Three static checks over the **product runtime** — apx/ minus the build-time tooling (the harness
itself, ``checks/``, and the offline fitness driver, ``fitness/``) and the test tree — each with a
failure-path fixture that fires:

- **no_runtime_import_from_tests (FR-33/AD-16):** no runtime module imports the test tree
  (``tests``, ``conftest``, a ``_fixtures`` package). The v1 defect was a demo layer that overrode
  the real product; a corpus is a data source, never a fixture reached from runtime code.
- **no_egress_call_site_outside_adapters (FR-32/AD-45):** a source-level network call site
  (``urllib.request``, ``socket``, ``httpx``, ``requests``, ``aiohttp``, ``http.client``) appears
  ONLY inside an enumerated egress adapter — the model provider, the embedder, the OCR service —
  and nowhere else. This is the call-site leg AD-45 demands alongside the import deny-list.
- **no_tenant_identifier_in_source (FR-30/AD-24):** the tree-wide extension of the core-only
  no-tenant-branch check — a *tenant* branched against a literal anywhere in the runtime. *Tenant*
  behaviour that is not greppable is NOT claimed here; the one-artefact rule (AD-3) covers it.

Each fails closed on an unparseable file and accepts an injectable ``roots`` so a test can aim it at
a violating fixture; the default is the shipped runtime tree.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path

from apx.checks.configuration import (
    _match_on_tenant,
    _module_string_consts,
    _tenant_prefix_call,
    _tenant_vs_literal,
)
from apx.checks.import_contracts import CheckResult
from apx.checks.payload_schema import _fail_closed, _load_trees, _parse

_APX_ROOT = Path(__file__).resolve().parent.parent      # the apx/ package
_REPO_ROOT = _APX_ROOT.parent

# The product runtime = apx/ minus the build-time tooling. FR-33/AD-16 is about the product's
# request/ingestion data path — the harness (checks/) legitimately names "_fixtures"/"tests" in its
# own scanning logic, and the fitness driver (fitness/) is CI tooling, so neither is the runtime.
_RUNTIME_EXCLUDE = frozenset({"checks", "fitness", "__pycache__"})


def _runtime_trees() -> tuple[list[tuple[Path, ast.Module]], list[str]]:
    """Parse every ``.py`` in the product runtime (apx/ minus checks/, fitness/). Returns
    (parsed trees, names that would not parse) — an unparseable file fails closed, never skips."""
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


def _trees(roots: Iterable[Path] | None) -> tuple[list[tuple[Path, ast.Module]], list[str]]:
    """The runtime tree by default, or the injected ``roots`` (a fixture) for a test."""
    return _runtime_trees() if roots is None else _load_trees(list(roots))


def _where(path: Path) -> Path | str:
    return path.relative_to(_REPO_ROOT) if path.is_relative_to(_REPO_ROOT) else path


# ── FR-33 / AD-16: no runtime import from the test tree ──────────────────────────────────────
def _import_modules(node: ast.AST) -> list[str]:
    """The dotted module name(s) an import node names (empty for a relative ``from . import x``)."""
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    if isinstance(node, ast.ImportFrom):
        return [node.module] if (node.module and node.level == 0) else []
    return []


def _is_test_tree_module(module: str) -> bool:
    parts = module.split(".")
    return parts[0] == "tests" or "conftest" in parts or "_fixtures" in parts


def no_runtime_import_from_tests(roots: Iterable[Path] | None = None) -> CheckResult:
    """No runtime module imports the test tree (FR-33/AD-16): ``tests``, ``conftest`` or a
    ``_fixtures`` package. Test fixtures exist only inside the test suite and are unreachable from
    any runtime code path — the v1 demo layer that overrode the real product is deleted, not hidden.
    """
    name, ad = "no runtime import from the test tree", "AD-16"
    trees, unparseable = _trees(roots)
    if unparseable:
        return _fail_closed(name, ad, unparseable)
    for path, tree in trees:
        for node in ast.walk(tree):
            for module in _import_modules(node):
                if _is_test_tree_module(module):
                    return CheckResult(
                        name, ad, False,
                        f"{_where(path)}:{node.lineno} imports the test tree ({module!r}) — a "
                        "runtime module may never reach the test suite or a fixture (FR-33/AD-16)")
    return CheckResult(name, ad, True,
                       f"no runtime module imports the test tree ({len(trees)} file(s))")


# ── FR-32 / AD-45: no outbound call site outside the enumerated egress adapters ───────────────
# The enumerated egress adapter families (AD-45): the model provider, the embedder, the OCR service.
# A source-level network call site may appear ONLY inside one of these; anywhere else is a fourth
# egress path. (The DB driver opens its socket inside psycopg, not at an apx source call site, so it
# is not a source-level network call and is not — and must not be — flagged.)
_EGRESS_ADAPTER_DIRS = frozenset({"llm_openai_compat", "embedder_bgem3", "ocr_tesseract"})


def _call_dotted(node: ast.Call) -> str | None:
    """The dotted attribute chain of a call target — ``urllib.request.urlopen`` → that string,
    ``requests.get`` → ``requests.get`` — or None when the target is not a simple name/attr chain
    (``client.get(...)`` on a variable, ``session.get(...)`` on an ORM object: not flagged)."""
    parts: list[str] = []
    cur: ast.expr = node.func
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
        return ".".join(reversed(parts))
    return None


def _is_network_call(dotted: str) -> bool:
    """A source-level socket-opening / HTTP call. Precise on purpose: ``urllib.request.*`` (not
    ``urllib.parse.*``), ``http.client.*``, ``socket.*``, and the ``httpx``/``requests``/``aiohttp``
    clients — never a bare ``.get``/``.post`` on a variable (which is dict/ORM, not egress)."""
    root = dotted.split(".")[0]
    return (
        root in ("httpx", "requests", "aiohttp")
        or dotted.startswith("urllib.request")
        or dotted.startswith("http.client")
        or root == "socket")


def no_egress_call_site_outside_adapters(roots: Iterable[Path] | None = None) -> CheckResult:
    """A source-level network call site appears only inside an enumerated egress adapter (FR-32/
    AD-45) — the model provider, the embedder, the OCR service. Any outbound call site elsewhere is
    a fourth egress path (telemetry, a crash reporter, an update check), the defect this forbids."""
    name, ad = "no outbound call site outside the enumerated adapters", "AD-45"
    trees, unparseable = _trees(roots)
    if unparseable:
        return _fail_closed(name, ad, unparseable)
    for path, tree in trees:
        in_egress_adapter = bool(set(path.parts) & _EGRESS_ADAPTER_DIRS)
        if in_egress_adapter:
            continue  # the enumerated set may open sockets; the point is that nothing else may
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                dotted = _call_dotted(node)
                if dotted is not None and _is_network_call(dotted):
                    return CheckResult(
                        name, ad, False,
                        f"{_where(path)}:{node.lineno} an outbound network call ({dotted}) outside "
                        "the enumerated egress adapters — a fourth egress path is a defect (AD-45)")
    return CheckResult(name, ad, True,
                       f"no outbound call site outside the egress adapters ({len(trees)} file(s))")


# ── FR-30 / AD-24: no tenant identifier is a branch, anywhere in the runtime ──────────────────
def no_tenant_identifier_in_source(roots: Iterable[Path] | None = None) -> CheckResult:
    """No conditional anywhere in the runtime branches on a *tenant* identifier (FR-30/AD-24) — the
    tree-wide extension of the core-only ``no_tenant_conditional_in_core``. Catches equality /
    membership against a literal (incl. one behind a module constant or a dict literal), a
    ``.startswith``/``.endswith``/``re.match`` prefix branch, and a ``match`` on a tenant. It does
    NOT flag tenant-vs-tenant isolation checks, sentinel/empty guards, or a structure keyed by
    tenant. *Tenant behaviour* that is not greppable is not claimed — the one-artefact rule (AD-3)
    covers it — so this is exactly the greppable half FR-30 promises."""
    name, ad = "no tenant identifier is a branch in source", "AD-24"
    trees, unparseable = _trees(roots)
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
                return CheckResult(
                    name, ad, False,
                    f"{_where(path)}:{node.lineno} a tenant identifier is used as a branch — a "
                    "tenant is a filter argument and a row key, never a branch (FR-30/AD-24)")
    return CheckResult(name, ad, True,
                       f"no tenant branch in {len(trees)} runtime module(s)")


def run() -> list[CheckResult]:
    return [
        no_runtime_import_from_tests(),
        no_egress_call_site_outside_adapters(),
        no_tenant_identifier_in_source(),
    ]
