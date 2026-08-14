"""The three continuity structural checks fire on the defect and pass on the real tree (5.9).

Each fixture commits exactly the shape the shipped code was found in: a store built without the
head journal (the import worker, which writes most of the record), a continuity claim about the
READER's bytes handed over by the adapter from a fact about its own database, and an audit append
wrapped in a handler that logs and continues.
"""

from __future__ import annotations

from pathlib import Path

from apx.checks.continuity import (
    an_audit_write_failure_is_never_swallowed,
    the_continuity_claim_is_derived_from_the_document,
    the_store_has_one_door,
)

_FIXTURES = Path(__file__).resolve().parents[1] / "_fixtures" / "continuity_violations"
_CHECKS = (
    the_store_has_one_door,
    the_continuity_claim_is_derived_from_the_document,
    an_audit_write_failure_is_never_swallowed,
)


def _fixture(name: str) -> list[Path]:
    return [_FIXTURES / name]


# ── on the real tree ──────────────────────────────────────────────────────────────────────────

def test_all_three_pass_on_the_real_runtime() -> None:
    for check in _CHECKS:
        result = check()
        assert result.ok, f"{result.name}: {result.detail}"


def test_the_clean_fixture_passes_all_three() -> None:
    """The shape a correct wiring has — so the failures below are about the defect and not about
    the fixture being unlike real code."""
    for check in _CHECKS:
        assert check(_fixture("clean")).ok, check.__name__


# ── one door onto the store (FR-53/AD-35) ─────────────────────────────────────────────────────

def test_a_store_built_without_the_journal_fails_the_build() -> None:
    """The shipped import worker, until this story. Every act it wrote advanced the chain head with
    nothing recorded outside the restorable store — so a truncation back to the last head the API
    happened to record was undetectable, on the half of the record the worker produces."""
    result = the_store_has_one_door(_fixture("unjournalled_store"))
    assert not result.ok
    assert "open_store()" in result.detail and "AD-35" in result.detail


# ── the claim is about the document (FR-53) ───────────────────────────────────────────────────

def test_a_caller_that_asserts_the_continuity_claim_fails_the_build() -> None:
    """``recomputable_from_this_document`` asserts a property of the bytes the reader holds. Handed
    over by the adapter it carried a fact about the server's own storage instead — and printed
    **true** on a court document that carried no audit entries at all."""
    result = the_continuity_claim_is_derived_from_the_document(_fixture("claim_from_the_caller"))
    assert not result.ok
    assert "recomputable_from_this_document" in result.detail
    assert "derived from the document" in result.detail


# ── the act fails, or the record is a lie (FR-53/AD-22) ───────────────────────────────────────

def test_an_audit_append_that_is_caught_and_continued_fails_the_build() -> None:
    """FR-53's first consequence is one sentence, and it is defeated by one handler. What that
    handler produces is an act that happened beside a record saying it did not — which is, after
    the fact, indistinguishable from an act that never happened."""
    result = an_audit_write_failure_is_never_swallowed(_fixture("swallowed_audit_write"))
    assert not result.ok
    assert "must fail" in result.detail and "unaudited" in result.detail


def test_the_pass_message_counts_what_it_actually_inspected() -> None:
    """A check whose success message says nothing about its coverage is one nobody notices has
    stopped finding anything."""
    detail = an_audit_write_failure_is_never_swallowed().detail
    assert "try-block(s) contain an audit append" in detail
    assert not detail.startswith("0 "), "a check that guarded nothing must not read as a pass"
