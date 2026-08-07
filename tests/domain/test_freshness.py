"""Freshness and staleness — the pure comparison (Story 4.13, FR-58/AD-23/AD-40).

Staleness is a comparison of stamps, not a flag anyone sets: every test here changes ONE observable
and asserts the assessment names THAT input and no other.
"""

from __future__ import annotations

import dataclasses

import pytest

from apx.core.domain.freshness import (
    ARTEFACT_KINDS,
    KIND_BOUND,
    KIND_LINE,
    KIND_RANKING,
    TRIGGER_KEYS,
    TRIGGERS,
    FreshnessStamp,
    assess_freshness,
    compare_stamps,
    config_digest,
    extraction_digest,
    inputs_for,
    trigger,
)

_STAMP = FreshnessStamp(
    ranking_version_no=3,
    line_seq=2,
    pin_ledger_seq=7,
    case_theory_version_no=1,
    config_digest="c" * 64,
    scope_identity="litige-x",
    corpus_count=1400,
    extraction_digest="e" * 64,
    discard_population="d" * 64,
)

# One *different* value per observable, so "changed" is unambiguous for each.
_MOVED: dict[str, object] = {
    "ranking_version_no": 4,
    "line_seq": 3,
    "pin_ledger_seq": 9,
    "case_theory_version_no": 2,
    "config_digest": "d" * 64,
    "scope_identity": "litige-y",
    "corpus_count": 1700,
    "extraction_digest": "f" * 64,
    "discard_population": "a" * 64,
}


def _assess(recorded=_STAMP, current=_STAMP, kind=KIND_RANKING):  # noqa: ANN001,ANN202
    return assess_freshness(
        kind=kind, artefact_id="art-1", recorded=recorded, current=current)


# ── the trigger list is closed and matches the stamp, both ways ─────────────────────────────────
def test_the_stamp_has_exactly_one_field_per_trigger_both_ways() -> None:
    fields = {f.name for f in dataclasses.fields(FreshnessStamp)}
    assert fields == set(TRIGGER_KEYS)
    # FR-58's seven, AD-40's eighth, FR-23's ninth (the population a bound was drawn from)
    assert len(TRIGGERS) == len(TRIGGER_KEYS) == 9


def test_every_trigger_names_a_french_phrase_and_a_source() -> None:
    for t in TRIGGERS:
        assert t.fr.strip() and t.source.strip()
        assert trigger(t.key) is t


def test_an_unknown_trigger_key_raises_rather_than_defaulting() -> None:
    with pytest.raises(ValueError, match="unknown staleness trigger"):
        trigger("whenever")
    with pytest.raises(ValueError, match="unknown staleness trigger"):
        _STAMP.value("whenever")


# ── the comparison ──────────────────────────────────────────────────────────────────────────────
def test_an_identical_stamp_is_fresh_and_names_nothing() -> None:
    assessment = _assess()
    assert assessment.fresh is True and assessment.stale is False
    assert assessment.changed == () and assessment.changed_fr == ()
    assert assessment.reason() == "à jour"


@pytest.mark.parametrize("key", TRIGGER_KEYS)
def test_each_trigger_alone_makes_the_bound_stale_and_names_itself(key: str) -> None:
    """The *confidence bound* depends on every observable (FR-58 and FR-23 are written about it),
    so it is where every trigger is exercised in isolation."""
    current = dataclasses.replace(_STAMP, **{key: _MOVED[key]})
    assessment = _assess(current=current, kind=KIND_BOUND)
    assert assessment.stale is True and assessment.fresh is False
    assert assessment.changed == (key,)                       # exactly one, and it is this one
    assert assessment.changed_fr == (trigger(key).fr,)
    assert trigger(key).fr in assessment.reason()


# ── each artefact depends on the inputs it actually has ─────────────────────────────────────────
def test_the_bound_depends_on_every_observable_and_the_others_narrow_with_a_reason() -> None:
    assert inputs_for(KIND_BOUND) == TRIGGER_KEYS
    # a line move / a pin touch only their own ledgers; the ranked order is unchanged, so claiming
    # it is out of date would be false — and a banner that cries wolf is one nobody reads.
    assert set(TRIGGER_KEYS) - set(inputs_for(KIND_RANKING)) == {
        "line_seq", "pin_ledger_seq", "discard_population"}
    # a pin overrides the line for one pièce (FR-43); it does not move the cut. The relevance
    # verdict is downstream of the order, never an input to it (label_not_a_ranking_input).
    assert set(TRIGGER_KEYS) - set(inputs_for(KIND_LINE)) == {
        "pin_ledger_seq", "discard_population"}
    # every narrowing is a SUBSET, and together they cover the whole enumeration
    covered: set[str] = set()
    for kind in ARTEFACT_KINDS:
        assert set(inputs_for(kind)) <= set(TRIGGER_KEYS)
        covered |= set(inputs_for(kind))
    assert covered == set(TRIGGER_KEYS)
    # an unknown kind depends on EVERYTHING — over-invalidated, never under-invalidated
    assert inputs_for("an-artefact-nobody-declared") == TRIGGER_KEYS


@pytest.mark.parametrize("key", ["line_seq", "pin_ledger_seq", "discard_population"])
def test_an_input_the_ranked_order_does_not_have_leaves_it_fresh(key: str) -> None:
    current = dataclasses.replace(_STAMP, **{key: _MOVED[key]})
    assert _assess(current=current, kind=KIND_RANKING).fresh is True
    assert _assess(current=current, kind=KIND_BOUND).stale is True   # but the bound IS affected


def test_an_ingestion_is_not_reported_as_a_re_extraction() -> None:
    """The extraction digest covers every pièce, so an ingestion moves it too — but nobody re-read
    anything. Naming both would be a false statement, and the whole product argues it makes none."""
    current = dataclasses.replace(
        _STAMP, corpus_count=1700, extraction_digest="f" * 64)
    assessment = _assess(current=current, kind=KIND_BOUND)
    assert assessment.changed == ("corpus_count",)          # the implied name is dropped
    # and a re-extraction ALONE is still named — the subsumption only ever removes a redundant
    # name from an already non-empty set, so no staleness can hide behind it
    only_re_extracted = dataclasses.replace(_STAMP, extraction_digest="f" * 64)
    assert _assess(current=only_re_extracted, kind=KIND_BOUND).changed == ("extraction_digest",)


def test_an_unplaced_line_differs_from_a_placed_one() -> None:
    # None is a real observable value, not a missing one: placing the first line IS a change.
    unplaced = dataclasses.replace(_STAMP, line_seq=None)
    assert compare_stamps(unplaced, _STAMP) == ("line_seq",)


def test_two_changed_inputs_are_both_named_in_trigger_order() -> None:
    current = dataclasses.replace(_STAMP, corpus_count=1700, ranking_version_no=4)
    assessment = _assess(current=current)
    assert assessment.changed == ("ranking_version_no", "corpus_count")  # TRIGGERS order
    assert len(assessment.changed_fr) == 2


def test_fresh_is_derived_from_changed_and_cannot_disagree_with_it() -> None:
    # There is no constructor path producing fresh=True beside a non-empty changed list.
    for key in TRIGGER_KEYS:
        current = dataclasses.replace(_STAMP, **{key: _MOVED[key]})
        assessment = _assess(current=current)
        assert assessment.fresh == (not assessment.changed)


def test_every_artefact_kind_assesses_and_an_unknown_one_raises() -> None:
    for kind in ARTEFACT_KINDS:
        assert _assess(kind=kind).kind == kind
    assert set(ARTEFACT_KINDS) == {KIND_RANKING, KIND_LINE, KIND_BOUND}
    with pytest.raises(ValueError, match="unknown artefact kind"):
        _assess(kind="estimate")


# ── no clock is an input ────────────────────────────────────────────────────────────────────────
def test_no_observable_is_a_timestamp() -> None:
    # A clock as an input is how staleness resolves itself by the passage of time (FR-58 forbids
    # it). The structural check asserts this over the source; this asserts it over the values.
    for field in dataclasses.fields(FreshnessStamp):
        assert field.type in {"int", "int | None", "str"}, field


# ── the digests ─────────────────────────────────────────────────────────────────────────────────
def test_the_config_digest_is_insertion_order_independent() -> None:
    a = config_digest({"similarity_threshold": 0.3, "model_name": "m"})
    b = config_digest({"model_name": "m", "similarity_threshold": 0.3})
    assert a == b
    assert config_digest({"similarity_threshold": 0.4, "model_name": "m"}) != a


def test_the_extraction_digest_moves_when_any_text_identity_moves() -> None:
    base = [("a" * 64, "1" * 64), ("b" * 64, "2" * 64), ("c" * 64, "3" * 64)]
    assert extraction_digest(base) == extraction_digest(list(base))
    # a re-extraction of the MIDDLE pièce — the case a min/max/count aggregate would miss
    moved = [base[0], (base[1][0], "9" * 64), base[2]]
    assert extraction_digest(moved) != extraction_digest(base)
    # a new pièce moves it too
    assert extraction_digest([*base, ("d" * 64, "4" * 64)]) != extraction_digest(base)
    assert extraction_digest([]) == extraction_digest([])


def test_the_extraction_digest_is_not_a_plain_concatenation() -> None:
    # The \x00 / \n framing must make ("ab","c") and ("a","bc") distinct, so a boundary shift
    # cannot masquerade as the same corpus.
    assert extraction_digest([("ab", "c")]) != extraction_digest([("a", "bc")])


# ── the stamp round-trips, and fails closed ─────────────────────────────────────────────────────
def test_the_stamp_round_trips_through_canonical_json() -> None:
    assert FreshnessStamp.from_json(_STAMP.to_json()) == _STAMP
    unplaced = dataclasses.replace(_STAMP, line_seq=None)
    assert FreshnessStamp.from_json(unplaced.to_json()) == unplaced
    # canonical: sorted keys, so the same stamp is the same bytes on any machine
    assert _STAMP.to_json() == _STAMP.to_json()
    assert _STAMP.to_json().index('"config_digest"') < _STAMP.to_json().index('"corpus_count"')


def test_a_stamp_missing_a_field_is_refused_not_defaulted() -> None:
    payload = _STAMP.to_json().replace('"corpus_count":1400,', "")
    with pytest.raises(ValueError, match="missing"):
        FreshnessStamp.from_json(payload)


def test_a_stamp_with_an_extra_field_is_refused() -> None:
    payload = _STAMP.to_json()[:-1] + ',"invented":1}'
    with pytest.raises(ValueError, match="unknown"):
        FreshnessStamp.from_json(payload)


def test_an_unreadable_stamp_raises_rather_than_reading_as_fresh() -> None:
    with pytest.raises(ValueError, match="unreadable freshness stamp"):
        FreshnessStamp.from_json("{not json")
    with pytest.raises(ValueError, match="must be a JSON object"):
        FreshnessStamp.from_json("[]")


# ── a superseded artefact keeps its verdict but is not work ─────────────────────────────────────
def test_a_superseded_artefact_is_still_assessed_but_is_not_work() -> None:
    """It is still readable and the verdict is still true of it (AD-7), but the recomputation its
    worklist line would offer has already been performed — so offering it again would mean the offer
    never discharges."""
    from apx.core.domain.worklist import worklist_lines

    current = dataclasses.replace(_STAMP, corpus_count=1700)
    live = assess_freshness(
        kind=KIND_RANKING, artefact_id="v2", recorded=_STAMP, current=current)
    dead = assess_freshness(
        kind=KIND_RANKING, artefact_id="v1", recorded=_STAMP, current=current, superseded=True)
    assert live.stale and dead.stale                       # both verdicts stand
    assert live.superseded is False and dead.superseded is True
    lines = worklist_lines([dead, live])
    assert [line.artefact_id for line in lines] == ["v2"]  # only the live one is work
    assert worklist_lines([dead]) == ()
