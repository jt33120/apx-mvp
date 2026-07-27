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

import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
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
        real floor. AD-26(iii)/FR-31: a value must be attested across a minimum number of *pièces*
        AND *matters* and be **never traceable to one** — so the floor must span **≥ 2 *matters***
        (and ≥ 2 *pièces*); a floor of 1 would bless a value quotable from a single *matter*, the
        exact leak the floor exists to prevent. ``projectors_declare_attestation`` fails the build
        on an invalid one — the property is otherwise undecidable (AD-26 iii)."""
        if not self.kinds:
            return False
        if self.requires_floor():
            return (self.min_pieces or 0) >= 2 and (self.min_matters or 0) >= 2
        return True


# A module-private seal only ``project_all`` holds. ``Projection.__post_init__`` refuses any
# construction that does not present it — so alias / ``getattr`` / subclass / attribute-form
# construction all fail at RUNTIME, making "built only by the registry" literally true, not just a
# name-pattern the static check can be aliased around.
_REGISTRY_SEAL = object()


@dataclass(frozen=True)
class Projection:
    """A content-free emission about a *tenant*'s data. SEALED two ways: (1) at RUNTIME —
    ``__post_init__`` refuses construction without the registry's private seal, so ``project_all``
    is the only route that can build one (alias/``getattr``/subclass/attribute-form all raise);
    (2) at BUILD time — ``projection_emitted_only_by_registry`` fails the build on a bare- or
    attribute-form ``Projection(...)`` anywhere outside this module, for a clear compile-time error.
    A consumer RECEIVES a projection from ``project_all``; it never constructs one."""

    projector: str
    kinds: tuple[str, ...]       # the declared value kinds (transparency)
    values: Mapping[str, Any]    # the emitted content-free values
    _seal: object = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self._seal is not _REGISTRY_SEAL:
            raise RuntimeError(
                "Projection is constructed only by the registry (project_all) — an emission path "
                "outside the registry is a defect (AD-26/FR-31)")


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


def project_all(
    snapshot: Snapshot, registry: Mapping[str, RegisteredProjector] | None = None
) -> list[Projection]:
    """Run every registered projector over the snapshot — THE emission path (AD-26). Deterministic
    order (by name), reproducible output. This is the only place ``Projection`` is built (it holds
    the registry seal). ``registry`` is injectable so a test can run an isolated set without
    mutating the module global."""
    reg = REGISTRY if registry is None else registry
    return [
        Projection(p.name, tuple(k.value for k in p.attestation.kinds), dict(p.fn(snapshot)),
                   _seal=_REGISTRY_SEAL)
        for p in sorted(reg.values(), key=lambda p: p.name)
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
        elif isinstance(value, bytes | bytearray):
            out.append(str(value))  # str(b"…") exposes the bytes' content to the scan
        elif isinstance(value, Iterable):
            for v in list(value):  # materialise a lazy iterator so its contents cannot hide
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


# A version identifier is CODE identity (schema/extractor/chunking version — AD-23), set by APX's
# own code to a version constant, architecturally independent of *tenant* content. This bound is
# defence-in-depth against an extractor that violates that contract and derives its version string
# from file/tool metadata: an identifier is a short machine token (no whitespace, bounded), so a
# path, a sentence or a client name embedded in a version is replaced by a non-content marker
# rather than emitted verbatim.
_SAFE_VERSION = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9._+/-]{0,23}\Z")


def _safe_version(value: str) -> str:
    return value if _SAFE_VERSION.match(value) else "«non-conforming»"


@register("versions", Attestation(kinds=(ValueKind.VERSION,)))
def _versions(s: Snapshot) -> Mapping[str, Any]:
    """The distinct schema/extractor version identifiers present — code identity, not data. Each is
    bounded to a machine-token shape (``_safe_version``) so a version that smuggled content is not
    emitted verbatim."""
    return {
        "schema": [_safe_version(v) for v in s.schema_versions],
        "extractor": [_safe_version(v) for v in s.extractor_versions],
    }
