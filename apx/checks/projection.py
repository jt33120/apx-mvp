"""Content-free projection structural properties (story 1.10; AD-26/FR-31). Two static checks:

- **projection_emitted_only_by_registry (AD-26/FR-31 ii):** the sealed ``Projection`` result type
  is constructed ONLY inside ``apx/core/projection.py`` (the registry) — an emission path anywhere
  else fails the build, so a projector cannot be added by writing one; every emission is a
  registered, seeded-token-tested projector. A consumer (the diagnostic endpoint, later the 6.2
  export) RECEIVES a ``Projection`` from ``project_all``; it never fabricates one.
- **projectors_declare_attestation (AD-26/FR-31 iii):** every registered projector declares a valid
  content-free attestation — at least one value kind, and a text-deriving projector declares its
  floor (min *pièces* AND *matters*). A projected value without an attestation turns the build red,
  because the property is otherwise undecidable.

The *no-fourth-egress-path* check (AD-45) deliberately lives elsewhere (``import_contracts``, in the
checks harness), NOT here — dropping this projection unit must not drop that guarantee (the AD-26 →
AD-45 split). Both checks fail closed and follow the 1.3–1.9 registration pattern.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable, Mapping
from pathlib import Path

from apx.checks.import_contracts import CheckResult
from apx.checks.payload_schema import _fail_closed, _load_trees
from apx.core.projection import REGISTRY, RegisteredProjector

_APX_DIR = Path(__file__).resolve().parent.parent
_REGISTRY_FILE = _APX_DIR / "core" / "projection.py"
_REPO_ROOT = _APX_DIR.parent
_EXCLUDE_PARTS = frozenset({"web", "node_modules", "__pycache__"})
_EMISSION_TYPE = "Projection"


def projection_emitted_only_by_registry(roots: Iterable[Path] | None = None) -> CheckResult:
    """The ``Projection`` result type is constructed only by the registry (AD-26/FR-31 ii)."""
    name, ad = "projections are emitted only by the registry", "AD-26"
    roots = list(roots) if roots is not None else [_APX_DIR]
    trees, unparseable = _load_trees(roots)
    if unparseable:
        return _fail_closed(name, ad, unparseable)
    scanned = 0
    for path, tree in trees:
        if path == _REGISTRY_FILE or set(path.parts) & _EXCLUDE_PARTS:
            continue  # the registry itself is the one place; skip vendored/generated trees
        scanned += 1
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == _EMISSION_TYPE):
                where = path.relative_to(_REPO_ROOT) if path.is_relative_to(_REPO_ROOT) else path
                return CheckResult(
                    name, ad, False,
                    f"{where}:{node.lineno} constructs {_EMISSION_TYPE}() outside the registry — "
                    "an emission path outside the registry fails the build; a consumer receives a "
                    "Projection from project_all, it never fabricates one (AD-26/FR-31)")
    return CheckResult(name, ad, True,
                       f"the {_EMISSION_TYPE} type is constructed only by the registry "
                       f"({scanned} file(s) scanned)")


def projectors_declare_attestation(
    registry: Mapping[str, RegisteredProjector] | None = None
) -> CheckResult:
    """Every registered projector declares a valid content-free attestation (AD-26/FR-31 iii)."""
    name, ad = "every projector declares a content-free attestation", "AD-26"
    registry = REGISTRY if registry is None else registry
    for pname, projector in registry.items():
        if not projector.attestation.is_valid():
            reason = ("no value kind" if not projector.attestation.kinds
                      else "a text-derived value with no attestation floor (min pièces + matters)")
            return CheckResult(
                name, ad, False,
                f"projector {pname!r} has {reason} — a projected value without a content-free "
                "attestation turns the build red (AD-26/FR-31)")
    return CheckResult(name, ad, True,
                       f"every registered projector declares a content-free attestation "
                       f"({len(registry)} projector(s))")


def run() -> list[CheckResult]:
    """The content-free projection checks, for the harness to fan out over."""
    return [
        projection_emitted_only_by_registry(),
        projectors_declare_attestation(),
    ]
