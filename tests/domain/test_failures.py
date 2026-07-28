"""The failure register's domain layer (Story 2.6; FR-5, AD-28, AD-38).

The enumerated stable class set is present and append-only; the redacted diagnostic carries the
kind of failure but never a document fragment; cardinality is `unknown` only for an unopened
container.
"""

from __future__ import annotations

from apx.core.domain.failures import (
    CARDINALITY_ONE,
    CARDINALITY_UNKNOWN,
    ErrorClass,
    cardinality_for,
    redacted_diagnostic,
)


def test_error_class_carries_the_fr5_enumerated_stable_set() -> None:
    values = {e.value for e in ErrorClass}
    # FR-5's minimum enumerated set — every one must be present (the set is stable, append-only).
    required = {
        "unreadable-scan", "corrupt-file", "password-protected", "unsupported-format",
        "extraction-error", "extracted-empty", "container-unopenable", "resource-exhausted",
        "source-unavailable", "source-modified", "traversal-out-of-scope", "unknown",
    }
    assert required <= values


def test_redacted_diagnostic_keeps_the_kind_never_the_content() -> None:
    # a document name, a path, a client name in an exception message must NOT survive (AD-28)
    secret, path = "CONFIDENTIEL-CLIENT-DUPONT", "/matters/dupont/contrat-secret.pdf"
    exc = ValueError(f"could not parse {secret} at {path} — offset 4211")
    diag = redacted_diagnostic(exc)
    assert secret not in diag and path not in diag and "dupont" not in diag.lower()
    assert "4211" not in diag                 # no offsets, no fragments
    assert "ValueError" in diag               # the kind is kept — content-free triage


def test_redacted_diagnostic_qualifies_a_library_exception_but_not_a_builtin() -> None:
    assert redacted_diagnostic(KeyError("x")) == "KeyError"          # builtin stays bare

    class _LibError(Exception):
        pass

    _LibError.__module__ = "somelib.errors"
    assert redacted_diagnostic(_LibError("boom")) == "somelib.errors._LibError"


def test_redacted_diagnostic_cannot_inject_a_path_via_a_crafted_type() -> None:
    # defense in depth: a maliciously-constructed exception type whose __module__ is a PATH must
    # not inject it — the module is kept only when it is a valid dotted module name.
    class _Boom(Exception):
        pass

    _Boom.__module__ = "/matters/dupont/contrat-secret.pdf"  # not a dotted module name
    diag = redacted_diagnostic(_Boom("x"))
    assert "/matters" not in diag and "dupont" not in diag and diag == "_Boom"


def test_cardinality_is_unknown_only_for_an_unopened_container() -> None:
    assert cardinality_for(ErrorClass.CONTAINER_UNOPENABLE) == CARDINALITY_UNKNOWN
    for cls in (ErrorClass.PASSWORD_PROTECTED, ErrorClass.QUARANTINED, ErrorClass.EXTRACTED_EMPTY,
                ErrorClass.UNKNOWN):
        assert cardinality_for(cls) == CARDINALITY_ONE
