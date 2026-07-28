"""Ingestion error classes — FR-5's enumerated, stable set — and the redacted diagnostic.

A pièce that does not enter the corpus is enumerated here, never dropped (FR-5). The set is
**stable and append-only**: a value is never renamed or removed once shipped, because a persisted
`failure.error_class` string must always decode — a rename would orphan historical register rows.
An unclassified failure is recorded as `unknown` with a **redacted** diagnostic (never a document
fragment, a path, or a raw exception message — AD-28), so the register attributes it without ever
leaking content.
"""

from __future__ import annotations

import re
from enum import StrEnum

_SAFE_NAME = re.compile(r"[^A-Za-z0-9_]")
_DOTTED_MODULE = re.compile(r"[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)*")


class ErrorClass(StrEnum):
    # ── the extraction/read failures ──
    UNREADABLE = "unreadable"                    # an extractor could not read the file at all
    UNREADABLE_SCAN = "unreadable-scan"          # a scan/image OCR could not read (FR-5)
    CORRUPT_FILE = "corrupt-file"                # a damaged/truncated file (FR-5)
    PASSWORD_PROTECTED = "password-protected"    # encrypted; needs a credential to open (FR-5)
    UNSUPPORTED_FORMAT = "unsupported-format"    # a format not on the supported list
    EXTRACTION_ERROR = "extraction-error"        # the extractor raised
    EXTRACTED_EMPTY = "extracted-empty"          # extraction succeeded but yielded no text
    # ── the enumeration/source failures (FR-5); produced where their feature lands ──
    SOURCE_UNAVAILABLE = "source-unavailable"    # gone between enumeration and processing
    SOURCE_MODIFIED = "source-modified"          # changed between enumeration and processing
    TRAVERSAL_OUT_OF_SCOPE = "traversal-out-of-scope"  # a link pointing outside the subtree
    # ── the AD-17 operational classes (Story 2.2) ──
    RESOURCE_EXHAUSTED = "resource-exhausted"    # a unit over its configured memory/size bound
    QUARANTINED = "quarantined"                  # repeatedly killed the worker; quarantined
    # ── the AD-38 container class (Story 2.4): ONE entry of cardinality `unknown` ──
    CONTAINER_UNOPENABLE = "container-unopenable"
    # ── the catch-all: never dropped, always recorded with a redacted diagnostic (FR-5) ──
    UNKNOWN = "unknown"


# The register cardinality (AD-38): an ordinary pièce is `one`; a `container-unopenable` entry
# stands for an UNKNOWN number of pièces and is never summed into a total.
CARDINALITY_ONE = "one"
CARDINALITY_UNKNOWN = "unknown"


def cardinality_for(error_class: ErrorClass) -> str:
    """The cardinality an entry of this class carries (AD-38): `unknown` for an unopened
    container (it stands for an unknown number of pièces), else `one`."""
    if error_class is ErrorClass.CONTAINER_UNOPENABLE:
        return CARDINALITY_UNKNOWN
    return CARDINALITY_ONE


def redacted_diagnostic(exc: BaseException) -> str:
    """A **content-free** diagnostic for the register (AD-28): the exception's qualified type name
    ONLY — never ``str(exc)`` / ``args`` / ``__notes__`` / ``__cause__``, which may quote a path or
    a document fragment. It tells a reader *what kind* of failure occurred without leaking *what was
    in* the document. The name is scrubbed to identifier characters and length-capped, and the
    module is kept only when it is a valid dotted module name (never a path) — so even a
    maliciously-constructed exception type cannot inject a path or a structured fragment. (Real
    extraction exceptions have code-defined names; this is defense in depth, and ``failure.detail``
    is not surfaced on any register read.)"""
    cls = type(exc)
    name = _SAFE_NAME.sub("", cls.__name__)[:64] or "error"
    module = getattr(cls, "__module__", "") or ""
    if module in ("", "builtins") or not _DOTTED_MODULE.fullmatch(module):
        return name
    return f"{module}.{name}"
