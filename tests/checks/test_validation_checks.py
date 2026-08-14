"""The three validation structural checks fire on the defect and pass on the real tree (5.8).

A check that only ever passes proves nothing, so each is driven against a fixture committing
exactly the defect it exists to catch: a second writer of the acceptance (which is a *default*, not
a duplicate), an acceptance written with no gesture behind it, a batch stamping its provenance
instead of reading it, a dwell-time path to an acceptance, and a second spelling of the sentence the
record attributes to a lawyer.
"""

from __future__ import annotations

from pathlib import Path

from apx.checks.matter_export import a_pending_section_is_not_a_zero
from apx.checks.validation import (
    acceptance_is_never_manufactured,
    only_the_validation_act_accepts,
    the_opened_fact_is_never_a_literal,
)
from apx.core.domain import audit, matter_record

_FIXTURES = Path(__file__).resolve().parents[1] / "_fixtures" / "validation_violations"


def _fixture(name: str) -> list[Path]:
    return [_FIXTURES / name]


# ── on the real tree ──────────────────────────────────────────────────────────────────────────

def test_all_three_pass_on_the_real_runtime() -> None:
    for check in (only_the_validation_act_accepts, the_opened_fact_is_never_a_literal,
                  acceptance_is_never_manufactured):
        result = check()
        assert result.ok, f"{result.name}: {result.detail}"


def test_the_clean_fixture_passes_all_three() -> None:
    # the shape a correct write path has, so the failures below are about the defect and not about
    # the fixture being unlike real code
    for check in (only_the_validation_act_accepts, the_opened_fact_is_never_a_literal,
                  acceptance_is_never_manufactured):
        assert check(_fixture("clean")).ok, check.__name__


# ── one origin for an acceptance (FR-45/FR-24 §614) ───────────────────────────────────────────

def test_a_second_writer_of_the_acceptance_fails_the_build() -> None:
    """The nightly sweep that marks untouched values accepted. It is not a duplicate of the
    validation act — it is the **default** FR-45 forbids by name, and every entry it writes is
    indistinguishable from a gesture a lawyer performed."""
    result = only_the_validation_act_accepts(_fixture("two_acceptors"))
    assert not result.ok
    assert "FR-45 allows one" in result.detail


def test_an_acceptance_with_no_gesture_behind_it_fails_the_build() -> None:
    result = only_the_validation_act_accepts(_fixture("acceptance_alone"))
    assert not result.ok
    assert "without the validation act" in result.detail


def test_the_accepted_class_has_exactly_one_verb() -> None:
    """The catalogue leg, independent of the scanned tree: a second verb carrying `value_accepted`
    would make the export's count mean two different things."""
    assert list(audit.verbs_for(audit.CLASS_VALUE_ACCEPTED)) == [audit.ACT_VALUES_ACCEPTED]


# ── the provenance is read, never asserted (FR-45(c)/FR-44) ───────────────────────────────────

def test_a_batch_stamping_its_provenance_fails_the_build() -> None:
    """FR-45(c)'s defect exactly: *records for each pièce that it was not opened, unless it was* —
    and here a loop writes `opened_at=None` for every pièce in the selection, including the ones
    the lawyer had opened. It looks perfectly reasonable in review, which is why it is checked."""
    result = the_opened_fact_is_never_a_literal(_fixture("literal_provenance"))
    assert not result.ok
    assert "blanket stamp over a batch" in result.detail


def test_the_withdrawal_exemption_is_judged_per_call_not_per_function() -> None:
    """A withdrawal legitimately passes `None` — it accepts nothing and has no provenance. The
    exemption is granted by the call's own `action` argument, so a validate call sitting in the
    same module cannot borrow it."""
    assert the_opened_fact_is_never_a_literal(_fixture("clean")).ok
    assert not the_opened_fact_is_never_a_literal(_fixture("literal_provenance")).ok


# ── nothing manufactures an acceptance (FR-45) ────────────────────────────────────────────────

def test_a_dwell_time_path_to_an_acceptance_fails_the_build() -> None:
    result = acceptance_is_never_manufactured(_fixture("manufactured"))
    assert not result.ok
    assert "elapsed time" in result.detail or "presence" in result.detail


def test_a_second_spelling_of_the_assertion_fails_the_build() -> None:
    """One home for the sentence. A second control with different words would attribute to her a
    claim she never made in the terms that were recorded."""
    result = acceptance_is_never_manufactured(_fixture("second_assertion"))
    assert not result.ok
    assert "spells the assertion again" in result.detail


# ── the pending-section biconditional (FR-26, strengthened by 5.8) ────────────────────────────

def test_a_pending_section_is_declared_exactly_when_its_act_is_uncatalogued() -> None:
    """Story 5.7's leg was a one-shot tripwire — *at least one section must be pending* — which was
    true until 5.8 built both and then failed **on success**. The durable rule is the
    biconditional, and it fails in both directions."""
    assert a_pending_section_is_not_a_zero().ok
    assert matter_record.PENDING_SECTIONS == {}

    original = dict(matter_record.PENDING_SECTIONS)
    try:
        # a section declared pending while its act exists: it would print "not built" over a
        # matter where a lawyer really did validate forty pièces
        matter_record.PENDING_SECTIONS["validation_acts"] = "5.8"
        stale = a_pending_section_is_not_a_zero()
        assert not stale.ok
        assert "is catalogued" in stale.detail
    finally:
        matter_record.PENDING_SECTIONS.clear()
        matter_record.PENDING_SECTIONS.update(original)


def test_a_section_whose_act_vanishes_must_be_declared_pending_again() -> None:
    """The other direction: a section printing a count for an act nobody can perform. That zero
    reads as a finding about the firm, which is the misreading this whole rule exists to stop."""
    original = dict(matter_record.SECTION_ACTS)
    try:
        matter_record.SECTION_ACTS["a_section_with_no_act"] = "an_uncatalogued_verb"
        broken = a_pending_section_is_not_a_zero()
        assert not broken.ok
        assert "would print a zero" in broken.detail
    finally:
        matter_record.SECTION_ACTS.clear()
        matter_record.SECTION_ACTS.update(original)
