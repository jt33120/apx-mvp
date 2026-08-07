"""The pure vocabulary of the *sampling run* (Story 5.1, FR-22)."""

from __future__ import annotations

import pytest

from apx.core.domain.sampling import (
    STATE_INVALIDATED,
    STATUS_ABANDONED,
    STATUS_COMPLETED,
    STATUS_OPEN,
    SamplingUnit,
    bound_for_run,
    census_statement_fr,
    derive_run_state,
    draw_families,
    group_discarded_families,
    is_census,
    size_for_target,
)

# ── the unit of the draw is the family, restricted to the discarded set ─────────────────────────

def test_a_family_is_one_unit_and_its_proxy_is_its_lowest_ranked_discarded_member() -> None:
    units = group_discarded_families(
        [("p3", "fam-a"), ("p4", "fam-a"), ("p5", "fam-b"), ("p6", "fam-a")])
    assert [u.family_id for u in units] == ["fam-a", "fam-b"]
    assert units[0].proxy_piece_id == "p3"          # first seen = lowest rank
    assert units[0].member_piece_ids == ("p3", "p4", "p6")
    assert units[0].member_count == 3
    assert units[1].member_piece_ids == ("p5",)


def test_forty_copies_of_one_email_are_one_draw_not_forty() -> None:
    """FR-38 / epics.md 5.2 — a family counts as it should, not as its member count."""
    units = group_discarded_families([(f"copy-{i}", "fam-x") for i in range(40)])
    assert len(units) == 1
    assert units[0].member_count == 40


def test_a_retained_member_of_a_straddling_family_is_not_in_the_population() -> None:
    """Only the DISCARDED members reach the unit — the caller restricts to the derived view, and
    the unit carries exactly what it was given. A retained member counted into the discarded
    population would inflate the denominator of a bound quoted to a court."""
    units = group_discarded_families([("p9", "fam-straddle")])  # p8 retained, above the line
    assert units[0].member_piece_ids == ("p9",)
    assert units[0].proxy_piece_id == "p9"


def test_a_piece_appearing_twice_fails_loudly() -> None:
    with pytest.raises(ValueError, match="twice"):
        group_discarded_families([("p1", "fam-a"), ("p1", "fam-b")])


def test_an_empty_discarded_set_groups_to_nothing() -> None:
    assert group_discarded_families([]) == ()


# ── the draw ────────────────────────────────────────────────────────────────────────────────────

def _units(n: int) -> tuple[SamplingUnit, ...]:
    return tuple(
        SamplingUnit(family_id=f"f{i}", proxy_piece_id=f"p{i}", member_piece_ids=(f"p{i}",))
        for i in range(n))


def test_the_draw_is_without_replacement() -> None:
    drawn = draw_families(_units(10), 6, seed=7)
    assert len(drawn) == 6
    assert len({u.family_id for u in drawn}) == 6


def test_the_draw_is_reproducible_from_its_seed_but_the_seed_is_not_the_record() -> None:
    a = draw_families(_units(20), 5, seed=42)
    b = draw_families(_units(20), 5, seed=42)
    assert [u.family_id for u in a] == [u.family_id for u in b]
    # FR-22: "a seed alone is insufficient" — the function hands back the units themselves, so the
    # caller has identifiers to freeze and never has to re-derive the draw from the seed.
    assert all(isinstance(u, SamplingUnit) for u in a)


def test_a_different_seed_draws_a_different_sample() -> None:
    a = {u.family_id for u in draw_families(_units(50), 5, seed=1)}
    b = {u.family_id for u in draw_families(_units(50), 5, seed=2)}
    assert a != b


def test_the_draw_is_not_returned_in_rank_order() -> None:
    """Presenting the sample sorted by rank tells the lawyer which pièces sit nearest the line
    before she has judged them — precisely the information that would bias the verdicts."""
    drawn = draw_families(_units(60), 40, seed=3)
    ranks = [int(u.family_id[1:]) for u in drawn]
    assert ranks != sorted(ranks)


def test_asking_for_more_than_exists_is_a_census_not_an_error() -> None:
    drawn = draw_families(_units(4), 99, seed=1)
    assert len(drawn) == 4


def test_a_draw_of_nothing_is_refused() -> None:
    with pytest.raises(ValueError, match="at least one"):
        draw_families(_units(4), 0, seed=1)


def test_drawing_from_an_empty_population_is_refused() -> None:
    with pytest.raises(ValueError, match="empty"):
        draw_families((), 3, seed=1)


# ── sizing for a target bound, and the census crossover ─────────────────────────────────────────

def test_a_target_inside_the_population_gives_a_sample_size_below_the_census() -> None:
    sizing = size_for_target(population=1400, target_prevalence=0.05, confidence=0.95)
    assert sizing.size is not None
    assert 0 < sizing.size < 1400
    assert not sizing.is_census
    assert sizing.achievable_prevalence_upper <= 0.05
    assert "familles sur 1400" in sizing.reason_fr


def test_the_size_returned_is_the_smallest_that_reaches_the_target() -> None:
    sizing = size_for_target(population=200, target_prevalence=0.05, confidence=0.95)
    assert sizing.size is not None
    one_fewer = bound_for_run(
        population=200, sample_size=sizing.size - 1, relevant_found=0, confidence=0.95)
    assert one_fewer.prevalence_upper > 0.05


def test_a_tight_target_crosses_over_into_a_census_and_is_labelled_as_one() -> None:
    """On a small pile, leaving even one family unread admits one relevant family, so a target of
    "none at all" is only reachable by reading everything — the census crossover FR-22 names."""
    sizing = size_for_target(population=10, target_prevalence=0.0, confidence=0.95)
    assert sizing.size == 10
    assert sizing.is_census
    assert sizing.achievable_prevalence_upper == 0.0
    assert "recensement" in sizing.reason_fr
    # the crossover is real: one family short of the census does NOT reach the target
    assert bound_for_run(
        population=10, sample_size=9, relevant_found=0, confidence=0.95).prevalence_upper > 0.0


def test_a_target_beyond_what_a_human_will_read_is_unreachable_and_offers_the_best() -> None:
    sizing = size_for_target(
        population=5000, target_prevalence=0.001, confidence=0.95, max_size=100)
    assert sizing.size is None
    assert not sizing.is_census
    assert sizing.achievable_prevalence_upper > 0.001
    assert "inatteignable" in sizing.reason_fr


def test_an_empty_discarded_set_has_no_bound_never_a_flattering_zero() -> None:
    sizing = size_for_target(population=0, target_prevalence=0.05)
    assert sizing.size is None
    assert "aucune borne" in sizing.reason_fr


def test_the_bound_at_zero_found_is_monotone_in_the_draw_size() -> None:
    """The binary search in size_for_target is only valid because of this."""
    bounds = [
        bound_for_run(population=60, sample_size=n, relevant_found=0, confidence=0.95)
        .prevalence_upper
        for n in range(1, 61)
    ]
    assert bounds == sorted(bounds, reverse=True)


@pytest.mark.parametrize("target", [-0.01, 1.0, 1.5])
def test_a_target_outside_zero_to_one_is_refused(target: float) -> None:
    with pytest.raises(ValueError, match="target prevalence"):
        size_for_target(population=10, target_prevalence=target)


# ── the census statement is a fact, never a percentage ──────────────────────────────────────────

def test_a_census_says_everything_was_read_and_estimates_nothing() -> None:
    assert is_census(population=40, sample_size=40)
    assert is_census(population=40, sample_size=41)
    assert not is_census(population=40, sample_size=39)
    assert not is_census(population=0, sample_size=0)
    sentence = census_statement_fr(relevant_found=0, piece_count=1400)
    assert "recensement" in sentence and "aucune n'était pertinente" in sentence
    assert "%" not in sentence


def test_a_census_that_found_something_does_not_claim_none_was_relevant() -> None:
    sentence = census_statement_fr(relevant_found=3, piece_count=1400)
    assert "aucune" not in sentence
    assert "3" in sentence


# ── the run's state is derived, never stored ────────────────────────────────────────────────────

def test_an_open_run_whose_inputs_moved_is_invalidated() -> None:
    assert derive_run_state(
        status=STATUS_OPEN, stamped=True, changed=("corpus_count",)) == STATE_INVALIDATED


def test_an_open_run_whose_inputs_are_unchanged_stays_open() -> None:
    assert derive_run_state(status=STATUS_OPEN, stamped=True, changed=()) == STATUS_OPEN


def test_an_open_run_with_no_stamp_is_invalidated_not_assumed_valid() -> None:
    """An absence of evidence is not evidence of validity — the same rule 4.13 applies to an
    unstamped bound."""
    assert derive_run_state(
        status=STATUS_OPEN, stamped=False, changed=()) == STATE_INVALIDATED


def test_a_completed_or_abandoned_run_keeps_its_status_even_when_stale() -> None:
    """A completed run's bound can go stale — that is 4.13's job, and the export refuses it. It is
    not 'invalidated in flight', because it is not in flight."""
    assert derive_run_state(
        status=STATUS_COMPLETED, stamped=True, changed=("line_seq",)) == STATUS_COMPLETED
    assert derive_run_state(
        status=STATUS_ABANDONED, stamped=True, changed=("line_seq",)) == STATUS_ABANDONED


def test_an_unknown_status_fails_loudly() -> None:
    with pytest.raises(ValueError, match="unknown sampling run status"):
        derive_run_state(status="in-flight", stamped=True, changed=())
