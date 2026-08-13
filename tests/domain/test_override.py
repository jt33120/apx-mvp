"""The *override* — its grounds, its one validator, and the reason's exact round trip
(Story 5.6, FR-25).

Pure: no clock, no store. Three things are asserted here, and each is one of FR-25's own testable
consequences: an override names which ground makes it one, a blank reason is refused by exactly one
rule, and the reason survives the record verbatim — including a reason written to break the
renderer."""

from __future__ import annotations

import pytest

from apx.core.domain import audit
from apx.core.domain.override import (
    GROUND_CONTRADICTS_MACHINE,
    GROUND_GUARD_BYPASS,
    GROUND_REGISTER_EXIT,
    GROUNDS,
    REASON_MARK,
    MissingOverrideReason,
    ReasonMarkInAField,
    UnknownOverrideGround,
    check_ground,
    ground_label_fr,
    override_detail,
    reason_from_detail,
    validate_override_reason,
)

# ── the grounds ───────────────────────────────────────────────────────────────────────────────


def test_fr25_names_three_grounds_and_only_three() -> None:
    assert GROUNDS == (
        GROUND_CONTRADICTS_MACHINE, GROUND_REGISTER_EXIT, GROUND_GUARD_BYPASS)


def test_a_fourth_ground_is_refused_rather_than_invented() -> None:
    with pytest.raises(UnknownOverrideGround):
        check_ground("because-the-user-insisted")


def test_every_ground_says_itself_in_the_lawyers_language() -> None:
    for ground in GROUNDS:
        assert ground_label_fr(ground) != ground  # a French sentence, not the slug
    # an unknown ground shows as ITSELF rather than as blank — a reader is never shown nothing
    assert ground_label_fr("not-a-ground") == "not-a-ground"


# ── the one validator ─────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("blank", ["", "   ", "\t\n", "  ", None])
def test_a_blank_reason_is_refused(blank: str | None) -> None:
    with pytest.raises(MissingOverrideReason):
        validate_override_reason(blank)


def test_the_refusal_is_still_a_value_error() -> None:
    # the shipped paths raised ValueError before this type existed; every caller catching it,
    # including the API's own 400 handler, must keep working
    assert issubclass(MissingOverrideReason, ValueError)


def test_a_real_reason_passes_and_is_returned_unstripped() -> None:
    reason = "  aveu implicite au §4 — décisif malgré le rang  "
    assert validate_override_reason(reason) == reason  # verbatim: the record keeps what was typed


# ── the reason, verbatim, in the record ───────────────────────────────────────────────────────


def test_the_detail_carries_the_fields_then_the_reason() -> None:
    detail = override_detail("source disparue", entry="abc123", error_class="unreadable")
    assert detail == f"entry=abc123 error_class=unreadable {REASON_MARK}source disparue"


def test_a_detail_with_no_fields_is_still_a_reason() -> None:
    assert override_detail("parce que") == f"{REASON_MARK}parce que"


@pytest.mark.parametrize("reason", [
    "source disparue, jamais rendue lisible",
    "reason=quelque chose",                       # contains the mark itself
    "a=b c=d reason=e reason=f",                  # contains it twice, after other pairs
    "ligne 1\nligne 2\nligne 3",                  # newlines
    'il a dit « = » et "reason=" au §4',          # quotes, guillemets, an equals sign
    "  espaces autour  ",                         # leading/trailing whitespace
    "北京 — 東京 · Ω ≥ 3",                          # non-latin, symbols
    "x" * 4000,                                   # long
])
def test_the_reason_round_trips_byte_for_byte(reason: str) -> None:
    detail = override_detail(reason, entry="abc123", seq=7)
    assert reason_from_detail(detail) == reason


def test_a_detail_that_carries_no_reason_reads_as_none_not_as_empty() -> None:
    # None and "" must stay distinguishable: "this entry carries no reason" is an ordinary
    # non-override entry, while "this entry's reason is empty" cannot happen and would be a defect
    # worth seeing rather than smoothing over
    assert reason_from_detail("piece=abc action=retain seq=3") is None


def test_the_renderer_is_the_last_place_a_blank_reason_could_slip_in() -> None:
    with pytest.raises(MissingOverrideReason):
        override_detail("   ", entry="abc123")


def test_a_field_carrying_the_mark_is_refused_rather_than_rendered() -> None:
    # reachable from CLIENT DATA, not only from a typo: a firm names its own matters. A field with
    # the mark ahead of the reason would make the extractor hand back that field's tail — and it
    # would look like a reason, count as one and read as one.
    with pytest.raises(ReasonMarkInAField):
        override_detail("le vrai motif", matter="dossier x reason=faux motif")
    with pytest.raises(ReasonMarkInAField):
        override_detail("le vrai motif", **{"reason=x": "y"})


def test_without_that_guard_the_extractor_would_return_the_wrong_sentence() -> None:
    # the guard is not decoration: this is what the record would say if the field were rendered
    forged = f"matter=dossier x {REASON_MARK}faux motif {REASON_MARK}le vrai motif"
    assert reason_from_detail(forged) == "faux motif reason=le vrai motif"


# ── the catalogue's override axis ─────────────────────────────────────────────────────────────


def test_the_three_shipped_overrides_each_name_a_ground() -> None:
    assert audit.override_ground(audit.ACT_PIN_OVERRIDE) == GROUND_CONTRADICTS_MACHINE
    assert audit.override_ground(audit.ACT_REGISTER_OVERRIDE) == GROUND_REGISTER_EXIT
    assert audit.override_ground(audit.ACT_TRUNCATION_OVERRIDE) == GROUND_GUARD_BYPASS


def test_a_pin_is_an_override_although_its_fr24_class_is_pin() -> None:
    # the whole reason the override is a second axis: FR-24 requires "every *pin*" recorded as a
    # pin, FR-25 requires it counted as an override, and an act has one class
    assert audit.ACTS[audit.ACT_PIN_OVERRIDE].act_class == audit.CLASS_PIN
    assert audit.is_override(audit.ACT_PIN_OVERRIDE)


def test_counting_by_class_would_miss_the_pins() -> None:
    by_flag = set(audit.override_verbs())
    by_class = set(audit.verbs_for(audit.CLASS_OVERRIDE))
    assert audit.ACT_PIN_OVERRIDE in by_flag
    assert audit.ACT_PIN_OVERRIDE not in by_class
    assert by_class < by_flag


def test_lifting_a_contradiction_is_not_making_one() -> None:
    # removing a pin costs no reason: it puts the *pièce* back where the tool had it
    assert not audit.is_override(audit.ACT_PIN_REMOVED)
    assert audit.override_ground(audit.ACT_PIN_REMOVED) is None


def test_an_ordinary_modification_is_never_an_override() -> None:
    for verb in audit.verbs_for(audit.CLASS_VALUE_MODIFIED):
        assert not audit.is_override(verb), verb


def test_an_uncatalogued_verb_is_not_an_override_and_does_not_raise() -> None:
    # the predicate stays total so a read over historical rows can never blow up
    assert audit.is_override("piece_labeled") is False
    assert audit.override_ground("piece_labeled") is None


def test_the_override_class_is_no_longer_pending() -> None:
    assert audit.CLASS_OVERRIDE not in audit.PENDING_CLASSES
    assert audit.CLASS_OVERRIDE in audit.covered_classes()
