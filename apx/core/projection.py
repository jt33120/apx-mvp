"""The one content-free projection primitive (story 1.10, AD-26/FR-31).

There is exactly ONE mechanism for emitting information *about* a *tenant*'s data without emitting
the data: a **registry of named projectors**. Each projector declares the **shape** of what it
emits — a value kind from a content-free set — and a text-deriving projector additionally declares
its **attestation floor** (min *pièces* AND min *matters*), so a value can never be traced to a
single *matter*. ``project_all`` is the one emit path; it constructs the sealed ``Projection``
result — a static check (``apx.checks.projection``) forbids constructing it anywhere else, so an
emission path outside the registry fails the build (a projector cannot be added by writing one).

Content-freedom is a **structural property**, not a promise: the seeded-token test runs every
registered projector (and the union of their output for one *tenant*) against a seeded content
token and a seeded secret value, and the two checks here fail the build on an out-of-registry
emission or an undeclared text-derived floor. The registry is **open by construction** (FR-31): the
next increment's on-premises style extractor registers a projector rather than forking the
primitive.

Pure core: no adapter import. The raw content-free facts a projector reads (counts, an error-class
histogram, distinct version identifiers) are gathered by the store into a ``Snapshot``; the
projectors are pure functions of that snapshot.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any


class ValueKind(Enum):
    """The content-free value kinds a projector may emit. A closed set of *kinds* (each provably
    content-free), but an OPEN set of *projectors* — the registry is not a closed list (FR-31)."""

    COUNT = "count"                          # a cardinality — how many, never which
    VERSION = "version"                      # a schema/extractor/model version identifier
    ERROR_CLASS = "error_class"              # an enumerated failure class, never its detail
    TIMING = "timing"                        # a duration / throughput figure
    REDACTED = "redacted"                    # a diagnostic string scrubbed of secrets (see redact)
    OPAQUE_ID = "opaque_id"                  # a correlation id, never a name
    ATTESTED_AGGREGATE = "attested_aggregate"  # derived from pièce/chunk text (needs a floor)


# The kinds whose value derives from *pièce*/*chunk* text and therefore require an attestation
# floor to be content-free (AD-26 iii). Today only the (future) style extractor's kind.
_TEXT_DERIVED = frozenset({ValueKind.ATTESTED_AGGREGATE})


@dataclass(frozen=True)
class Attestation:
    """A projector's declaration of what it emits and — for a text-derived value — the floor across
    which it is attested (min *pièces* AND min *matters*), so no value traces to one *matter*."""

    kinds: tuple[ValueKind, ...]
    min_pieces: int | None = None
    min_matters: int | None = None

    def requires_floor(self) -> bool:
        return any(k in _TEXT_DERIVED for k in self.kinds)

    def is_valid(self) -> bool:
        """A well-formed attestation: at least one kind, and a text-derived projector declares a
        real floor (≥ 1 *pièce* AND ≥ 1 *matter*). ``projectors_declare_attestation`` fails the
        build on an invalid one — the property is otherwise undecidable (AD-26 iii)."""
        if not self.kinds:
            return False
        if self.requires_floor():
            return (self.min_pieces or 0) >= 1 and (self.min_matters or 0) >= 1
        return True


@dataclass(frozen=True)
class Projection:
    """A content-free emission about a *tenant*'s data. SEALED: constructed ONLY by ``project_all``
    in this module — ``projection_emitted_only_by_registry`` (a static check) fails the build on a
    construction anywhere else, so every emission is a registered, seeded-token-tested projector."""

    projector: str
    kinds: tuple[str, ...]       # the declared value kinds (transparency)
    values: Mapping[str, Any]    # the emitted content-free values


# A projector is a pure function from the content-free Snapshot to its emitted values.
Projector = Callable[["Snapshot"], Mapping[str, Any]]


@dataclass(frozen=True)
class RegisteredProjector:
    name: str
    attestation: Attestation
    fn: Projector


@dataclass(frozen=True)
class Snapshot:
    """The content-free facts a projector may read — gathered by the store. By construction it holds
    NO names, paths, content or query text: only counts, an error-class histogram (enumerated
    classes → counts), and distinct version identifiers."""

    piece_count: int
    failure_count: int
    matter_count: int
    error_class_histogram: Mapping[str, int]
    schema_versions: tuple[str, ...]
    extractor_versions: tuple[str, ...]


# The ONE registry. A projector is added by registering it here (not by writing an emission path).
REGISTRY: dict[str, RegisteredProjector] = {}


def register(name: str, attestation: Attestation) -> Callable[[Projector], Projector]:
    """Register a named projector with its content-free attestation. The seeded-token test runs
    every registered projector automatically, so a new projector is covered without editing it."""
    def decorate(fn: Projector) -> Projector:
        if name in REGISTRY:
            raise ValueError(f"projector {name!r} is already registered")
        REGISTRY[name] = RegisteredProjector(name, attestation, fn)
        return fn
    return decorate


def project_all(snapshot: Snapshot) -> list[Projection]:
    """Run every registered projector over the snapshot — THE emission path (AD-26). Deterministic
    order (by name), reproducible output. This is the only place ``Projection`` is built."""
    return [
        Projection(p.name, tuple(k.value for k in p.attestation.kinds), dict(p.fn(snapshot)))
        for p in sorted(REGISTRY.values(), key=lambda p: p.name)
    ]


def projection_strings(projections: list[Projection]) -> list[str]:
    """Every string appearing anywhere in the projections' values — the union the seeded-token test
    scans (AD-26 i: the attestation floor is not composable, so the union is checked, not just each
    projector). Keys and stringified scalars are included."""
    out: list[str] = []

    def walk(value: Any) -> None:
        if isinstance(value, str):
            out.append(value)
        elif isinstance(value, Mapping):
            for k, v in value.items():
                out.append(str(k))
                walk(v)
        elif isinstance(value, list | tuple | set):
            for v in value:
                walk(v)
        else:
            out.append(str(value))

    for projection in projections:
        out.append(projection.projector)
        walk(projection.values)
    return out


def redact(text: str, secrets: list[str]) -> str:
    """Scrub configured secret VALUES from a diagnostic string (the REDACTED value kind, tying
    FR-31 to FR-51). Pure: the caller (the edge) supplies the secret values — core imports no
    logging/adapter. Longest-first so a value contained in another is masked whole."""
    for secret in sorted((s for s in secrets if s), key=len, reverse=True):
        if secret in text:
            text = text.replace(secret, "«redacted»")
    return text


# ── The registered projectors (story 1.10's first consumers — content-free by construction) ──
@register("corpus_counts", Attestation(kinds=(ValueKind.COUNT,)))
def _corpus_counts(s: Snapshot) -> Mapping[str, Any]:
    """How many *pièces*, failures and *matters* — cardinalities only, never which."""
    return {"pieces": s.piece_count, "failures": s.failure_count, "matters": s.matter_count}


@register("error_class_histogram", Attestation(kinds=(ValueKind.ERROR_CLASS, ValueKind.COUNT)))
def _error_class_histogram(s: Snapshot) -> Mapping[str, Any]:
    """Enumerated failure classes → counts (never a failure's detail, which is content)."""
    return {"by_class": dict(s.error_class_histogram)}


@register("versions", Attestation(kinds=(ValueKind.VERSION,)))
def _versions(s: Snapshot) -> Mapping[str, Any]:
    """The distinct schema/extractor version identifiers present — code identity, not data."""
    return {"schema": list(s.schema_versions), "extractor": list(s.extractor_versions)}
