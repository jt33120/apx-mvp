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
import dataclasses
from collections.abc import Iterable, Mapping
from pathlib import Path

from apx.checks.import_contracts import CheckResult
from apx.checks.payload_schema import _fail_closed, _is_call_to, _parse
from apx.core.projection import REGISTRY, RegisteredProjector, Snapshot

_APX_DIR = Path(__file__).resolve().parent.parent
_REGISTRY_FILE = _APX_DIR / "core" / "projection.py"
_REPO_ROOT = _APX_DIR.parent
_EXCLUDE_PARTS = frozenset({"web", "node_modules", "__pycache__"})
_EMISSION_TYPE = "Projection"

# The vetted content-free fields the projector input (Snapshot) may carry — a count, an enumerated
# error-class histogram, or version identifiers. A NEW field must be added here consciously (is it
# a name / path / content?), so a projector can never RECEIVE tenant content — its input cannot
# carry any. Mirrors AD-31's encrypted-column allowlist (a deliberate, small, reviewed list).
_CONTENT_FREE_SNAPSHOT_FIELDS = frozenset({
    "piece_count", "failure_count", "matter_count",
    "error_class_histogram", "schema_versions", "extractor_versions",
})


def _scannable_files(roots: Iterable[Path]) -> list[Path]:
    """Every ``*.py`` under the roots, EXCLUDING the registry file and vendored/generated trees —
    applied BEFORE parsing, so a non-UTF8 file inside an excluded tree cannot fail the check
    closed (honouring ``_EXCLUDE_PARTS``, not just skipping post-parse)."""
    out: list[Path] = []
    for root in roots:
        base = root if root.is_dir() else root.parent
        for path in sorted(base.rglob("*.py")):
            if path == _REGISTRY_FILE or set(path.parts) & _EXCLUDE_PARTS:
                continue
            out.append(path)
    return out


def projection_emitted_only_by_registry(roots: Iterable[Path] | None = None) -> CheckResult:
    """The ``Projection`` result type is constructed only by the registry (AD-26/FR-31 ii). Catches
    a bare ``Projection(...)`` AND an attribute-form ``proj.Projection(...)`` (via ``_is_call_to``,
    the same matcher the one-chunk-writer check uses) — a runtime seal on the type closes the rest
    (alias/``getattr``/subclass). Fails closed on an unparseable non-excluded file."""
    name, ad = "projections are emitted only by the registry", "AD-26"
    files = _scannable_files(list(roots) if roots is not None else [_APX_DIR])
    for path in files:
        tree = _parse(path)
        if tree is None:
            return _fail_closed(name, ad, [path.name])
        for node in ast.walk(tree):
            if _is_call_to(node, _EMISSION_TYPE):
                where = path.relative_to(_REPO_ROOT) if path.is_relative_to(_REPO_ROOT) else path
                return CheckResult(
                    name, ad, False,
                    f"{where}:{node.lineno} constructs {_EMISSION_TYPE}() outside the registry — "
                    "an emission path outside the registry fails the build; a consumer receives a "
                    "Projection from project_all, it never fabricates one (AD-26/FR-31)")
    return CheckResult(name, ad, True,
                       f"the {_EMISSION_TYPE} type is constructed only by the registry "
                       f"({len(files)} file(s) scanned)")


def snapshot_fields_are_content_free(snapshot_type: type | None = None) -> CheckResult:
    """Every field of the projector input ``Snapshot`` is a vetted content-free fact (AD-26): a new
    field must be declared on the allowlist, so a projector can never RECEIVE *tenant* content — its
    only input cannot carry a name, a path or document text. This is the structural chokepoint the
    seeded-token test alone does not give (that test proves selectivity of today's fields; this
    makes widening the input to carry content a build failure)."""
    name, ad = "the projector input Snapshot is content-free", "AD-26"
    st = Snapshot if snapshot_type is None else snapshot_type
    extra = {f.name for f in dataclasses.fields(st)} - _CONTENT_FREE_SNAPSHOT_FIELDS
    if extra:
        return CheckResult(
            name, ad, False,
            f"Snapshot carries un-vetted field(s) {sorted(extra)} — a new projector-input field "
            "must be declared content-free (a count / enum / version identifier), never a name, "
            "path or document content (AD-26/FR-31)")
    return CheckResult(name, ad, True, "the projector input carries only vetted content-free facts")


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
        snapshot_fields_are_content_free(),
        projectors_declare_attestation(),
    ]
