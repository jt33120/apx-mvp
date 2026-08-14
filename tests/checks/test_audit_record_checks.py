"""The three audit structural checks fire on the defect and pass on the real tree (Story 5.5).

A check that only ever passes proves nothing, so each one is driven against a fixture that commits
exactly the defect it exists to catch. The fixtures live under ``tests/_fixtures`` rather than being
written at runtime, so what the check reads is the same kind of file the runtime scan reads.
"""

from __future__ import annotations

from pathlib import Path

from apx.checks.audit_record import (
    APPEND_ONLY_MODELS,
    EVIDENTIAL_MODELS,
    audit_catalogue_is_complete,
    audit_record_is_append_only,
    audit_sequence_is_not_generated,
)
from apx.core.domain import audit

_FIXTURES = Path(__file__).resolve().parents[1] / "_fixtures" / "audit_violations"


def _fixture(name: str) -> list[Path]:
    return [_FIXTURES / name]


# ── on the real tree ──────────────────────────────────────────────────────────────────────────

def test_all_three_pass_on_the_real_runtime() -> None:
    for check in (audit_catalogue_is_complete, audit_sequence_is_not_generated,
                  audit_record_is_append_only):
        result = check()
        assert result.ok, f"{result.name}: {result.detail}"


# ── the catalogue ─────────────────────────────────────────────────────────────────────────────

def test_a_literal_verb_at_a_call_site_fails_the_build() -> None:
    result = audit_catalogue_is_complete(_fixture("literal_verb"))
    assert not result.ok
    assert "piece_labeled" in result.detail and "never a string at the call site" in result.detail


def test_a_named_verb_the_catalogue_does_not_define_fails_the_build() -> None:
    result = audit_catalogue_is_complete(_fixture("unknown_constant"))
    assert not result.ok
    assert "ACT_INVENTED" in result.detail


def test_the_catalogue_leg_is_independent_of_the_scanned_tree() -> None:
    """Legs 3 reads the catalogue itself, so it holds whatever tree is scanned: an FR-24 class
    with no writer and no owning story fails even when every call site is clean."""
    clean = audit_catalogue_is_complete(_fixture("clean"))
    assert clean.ok, clean.detail
    # Every FR-24 class has a writer as of Story 5.8, so the "no writer, no owner" leg is exercised
    # by introducing a class nothing writes rather than by un-declaring a pending one. That is also
    # the shape the leg exists to catch: a requirement gains a class, and nobody notices it has no
    # writer until an export prints a section that can only ever be empty.
    original = audit.FR24_CLASSES
    try:
        audit.FR24_CLASSES = (*original, "a_class_nothing_writes")
        broken = audit_catalogue_is_complete(_fixture("clean"))
        assert not broken.ok
        assert "no writer and no story that owns it" in broken.detail
    finally:
        audit.FR24_CLASSES = original


def test_a_pending_class_that_something_writes_fails_the_build() -> None:
    """The fitness driver's rule: a thing is asserted with something behind it or pending with a
    name on it, and never both. A class claimed as pending while a verb writes it would let a
    half-built capability read as deliberately deferred."""
    original = dict(audit.PENDING_CLASSES)
    try:
        audit.PENDING_CLASSES[audit.CLASS_PIN] = "9.9"
        result = audit_catalogue_is_complete(_fixture("clean"))
        assert not result.ok
        assert "cannot also be declared pending" in result.detail
    finally:
        audit.PENDING_CLASSES.clear()
        audit.PENDING_CLASSES.update(original)


# ── the sequence authority ────────────────────────────────────────────────────────────────────

def test_a_sequence_generator_fails_the_build() -> None:
    result = audit_sequence_is_not_generated(_fixture("generated_sequence"))
    assert not result.ok
    assert "Sequence()" in result.detail


def test_nextval_in_raw_sql_fails_the_build_while_a_docstring_may_quote_it() -> None:
    """AD-43 has to be quotable by the module that obeys it — the 0033 migration explains at
    length why nextval is banned. The exemption is subtractive, so raw SQL beside such a docstring
    still fails."""
    assert not audit_sequence_is_not_generated(_fixture("nextval_sql")).ok
    assert audit_sequence_is_not_generated(_fixture("nextval_docstring")).ok


def test_an_unlocked_allocation_fails_the_build() -> None:
    """The check that only banned the generator would pass happily on the unlocked
    read-modify-write this story replaced."""
    result = audit_sequence_is_not_generated(_fixture("unlocked_head"))
    assert not result.ok
    assert "row lock" in result.detail


# ── append-only ───────────────────────────────────────────────────────────────────────────────

def test_deleting_an_evidential_row_fails_the_build() -> None:
    result = audit_record_is_append_only(_fixture("evidential_delete"))
    assert not result.ok
    assert "AuditRecord" in result.detail


def test_updating_an_evidential_row_fails_the_build() -> None:
    result = audit_record_is_append_only(_fixture("evidential_update"))
    assert not result.ok
    assert "LinePlacement" in result.detail


def test_the_head_row_is_deliberately_not_evidential() -> None:
    """It is the allocator, not the record: it exists to be updated in place. Listing it would
    forbid the very mechanism AD-43 requires."""
    assert "AuditChainHead" not in EVIDENTIAL_MODELS
    assert audit_record_is_append_only(_fixture("head_row_update")).ok


def test_editing_a_loaded_evidential_row_in_place_fails_the_build() -> None:
    """CONFIRMED BY REVIEW. The check's docstring promised this leg and the implementation did not
    deliver it: it inspected only delete()/update() statement builders, so
    `row = session.scalars(select(AuditRecord)...).one(); row.detail = 'corrected'` passed a green
    build. Five sibling checks already implemented exactly this idiom."""
    result = audit_record_is_append_only(_fixture("in_place_edit"))
    assert not result.ok
    assert "row.detail" in result.detail and "append-only" in result.detail


def test_a_lifecycle_transition_on_a_sampling_run_is_not_an_edit_of_the_record() -> None:
    """The distinction the strengthened leg had to make. A run is an entity with a lifecycle —
    open, then completed or abandoned — and each transition writes its own audit entry. Its
    history lives on the chain, which IS append-only in the strict sense."""
    assert "SamplingRun" in EVIDENTIAL_MODELS        # no statement may remove or bulk-update it
    assert "SamplingRun" not in APPEND_ONLY_MODELS   # ... but closing it is not a rewrite
    assert audit_record_is_append_only(_fixture("lifecycle_transition")).ok
