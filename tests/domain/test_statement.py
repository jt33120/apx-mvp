"""The sentence (Story 5.4, FR-23 / FR-55 / FR-58).

The one text this product says out loud, and the only artefact that routinely leaves it. A bound on
screen is qualified by the panel around it; a bound pasted into an email is qualified by nothing
except the characters inside it. Every test here is about what survives the paste.
"""

from __future__ import annotations

from datetime import date

import pytest

from apx.core.domain.sampling import (
    KIND_BOUND,
    KIND_CENSUS,
    KIND_COUNTS_ONLY,
    KIND_NO_POPULATION,
    NO_CUT_FR,
)
from apx.core.domain.statement import (
    REGISTERS,
    StatementInputs,
    qualifications_fr,
    singular_fr,
    statement_fr,
    unfitness,
    unfitness_statement_fr,
)

FAMILIES = "familles de quasi-doublons écartées"


def _bound(**over: object) -> StatementInputs:
    base: dict[str, object] = dict(
        kind=KIND_BOUND, unit_fr=FAMILIES, population_units=1400, sample_units=200,
        relevant_units=0, confidence=0.95, piece_count=1400, count_upper_units=21,
        prevalence_upper=0.015, count_upper_pieces=34, scope="contentieux-a",
        reviewed_on=date(2026, 8, 11), freshness_fr="à jour")
    base.update(over)
    return StatementInputs(**base)  # type: ignore[arg-type]


# ── the §0.2 form: the draw, then the inference ─────────────────────────────────────────────────

def test_the_bound_sentence_states_the_draw_before_the_inference() -> None:
    """§0.2's corrected form opens with what was drawn. The draw is the EVIDENCE and the bound is
    the inference; a sentence stating an inference without its evidence asks to be believed rather
    than checked. The shipped sentence opened at "Avec une confiance de…" and did not say so."""
    sentence = statement_fr(_bound())
    draw = sentence.index("tirées au hasard")
    inference = sentence.index("Avec une confiance")
    assert draw < inference
    assert "200 familles de quasi-doublons écartées sur 1400" in sentence
    assert "(1400 pièces)" in sentence
    assert "aucune n'était pertinente" in sentence


def test_the_piece_figure_is_a_worst_case_and_says_so_never_environ() -> None:
    """Declared deviation from §0.2's "about Y pièces". The figure is the sum of the D LARGEST
    frozen families; "environ" on a worst case understates it in the flattering direction — the one
    direction §0.2 exists to forbid."""
    sentence = statement_fr(_bound())
    assert "soit au plus 34 pièces au pire" in sentence
    assert "environ" not in sentence


def test_a_run_that_could_not_compute_the_worst_case_states_no_piece_figure() -> None:
    """AD-19 — an absent input is absent, never guessed. A Story-5.1 run froze no family sizes."""
    sentence = statement_fr(_bound(count_upper_pieces=None))
    assert "pièces au pire" not in sentence
    assert "au plus 21 des 1400" in sentence          # the bound itself is untouched


def test_the_bound_register_refuses_to_speak_without_a_bound() -> None:
    with pytest.raises(ValueError, match="no bound to state"):
        statement_fr(_bound(count_upper_units=None))
    with pytest.raises(ValueError, match="no bound to state"):
        statement_fr(_bound(prevalence_upper=None))


def test_an_unfavourable_result_is_stated_never_softened() -> None:
    """FR-23: where the sample found K > 0 the sentence says so and the bound widens; the product
    never suppresses or reframes an unfavourable result."""
    sentence = statement_fr(_bound(relevant_units=14, count_upper_units=104,
                                   prevalence_upper=0.867, sample_units=20))
    assert "14 familles de quasi-doublons écartées se sont révélées pertinentes" in sentence
    assert "86.7%" in sentence or "86,7" in sentence.replace(" ", "")


def test_one_relevant_unit_agrees_in_number_and_carries_its_unit() -> None:
    """The Story 5.3 review found "1 se sont révélées pertinentes" — a plural verb on a singular
    count, with no unit noun at all, in the one string a firm reads out loud."""
    sentence = statement_fr(_bound(relevant_units=1, count_upper_units=30, prevalence_upper=0.02))
    assert "1 famille de quasi-doublon écartée s'est révélée pertinente" in sentence


# ── what travels INSIDE the string (FR-23 / FR-58) ──────────────────────────────────────────────

def test_the_wall_is_inside_the_sentence_not_beside_it() -> None:
    """FR-23. A payload does not travel with a paste; only the characters do."""
    assert "périmètre « contentieux-a »" in statement_fr(_bound())


def test_the_staleness_is_inside_the_sentence() -> None:
    """FR-58: a stale bound cannot be copied as text without its staleness in the copied string."""
    stale = statement_fr(_bound(freshness_fr="périmée : le corpus du dossier a changé"))
    assert "périmée : le corpus du dossier a changé" in stale


def test_a_repeated_draw_says_so_inside_the_sentence() -> None:
    """FR-22 — abandon-and-redraw is the cheapest route to a favourable number, and the sentence
    travels alone, so the multiplicity fact travels inside it or not at all."""
    assert "tirage n° 3 sur cette population" in statement_fr(_bound(run_ordinal=3))
    assert "tirage n°" not in statement_fr(_bound())


def test_every_register_that_states_a_count_carries_the_wall_and_the_freshness() -> None:
    for kind, extra in (
        (KIND_BOUND, {}),
        (KIND_CENSUS, {"sample_units": 1400, "relevant_units": 0}),
        (KIND_COUNTS_ONLY, {"count_upper_units": None, "prevalence_upper": None,
                            "count_upper_pieces": None}),
    ):
        sentence = statement_fr(_bound(kind=kind, **extra))  # type: ignore[arg-type]
        assert "périmètre « contentieux-a »" in sentence, kind
        assert "à jour" in sentence, kind
        assert sentence.endswith("."), kind


def test_the_qualifications_appear_in_reading_order() -> None:
    quals = qualifications_fr(_bound(run_ordinal=2))
    assert quals == (
        "tirage n° 2 sur cette population — périmètre « contentieux-a » — revue du 2026-08-11 "
        "— à jour")


# ── the census register: an exact count, never a percentage ─────────────────────────────────────

def test_a_census_states_a_fact_and_carries_no_percentage_anywhere() -> None:
    sentence = statement_fr(_bound(
        kind=KIND_CENSUS, sample_units=1400, relevant_units=0, relevant_pieces=0,
        count_upper_units=None, prevalence_upper=None, count_upper_pieces=None))
    assert sentence.startswith("Recensement : les 1400 pièces écartées ont toutes été examinées")
    assert "aucune n'était pertinente" in sentence
    assert "%" not in sentence


def test_a_census_that_found_something_states_both_exact_counts() -> None:
    sentence = statement_fr(_bound(
        kind=KIND_CENSUS, sample_units=1400, relevant_units=3, relevant_pieces=47,
        count_upper_units=None, prevalence_upper=None, count_upper_pieces=None))
    assert "3 familles de quasi-doublons écartées — 47 pièces — se sont révélées pertinentes" \
        in sentence
    assert "aucune" not in sentence and "%" not in sentence


def test_a_census_singularises_one_family_and_one_piece() -> None:
    sentence = statement_fr(_bound(
        kind=KIND_CENSUS, population_units=9, sample_units=9, piece_count=9, relevant_units=1,
        relevant_pieces=1, count_upper_units=None, prevalence_upper=None, count_upper_pieces=None))
    assert "1 famille de quasi-doublon écartée — 1 pièce —" in sentence
    assert "familles" not in sentence


def test_a_legacy_census_is_stated_in_ITS_unit_never_in_families() -> None:
    """A legacy ``recall_review`` counted *pièces*; rendering its census as "3 familles" is the
    Story-5.1 denominator defect with the units swapped."""
    sentence = statement_fr(_bound(
        kind=KIND_CENSUS, unit_fr="pièces écartées", population_units=40, sample_units=40,
        piece_count=None, relevant_units=3, relevant_pieces=None,
        count_upper_units=None, prevalence_upper=None, count_upper_pieces=None))
    assert "3 pièces écartées se sont révélées pertinentes" in sentence
    assert "famille" not in sentence and "%" not in sentence


# ── the counts-only register: counts, and the refusal said out loud ─────────────────────────────

def test_counts_only_states_the_counts_the_refusal_and_the_reason() -> None:
    sentence = statement_fr(_bound(
        kind=KIND_COUNTS_ONLY, relevant_units=3, count_upper_units=None, prevalence_upper=None,
        count_upper_pieces=None))
    assert "%" not in sentence
    assert "Aucune borne n'est énoncée" in sentence and "prouvé par simulation" in sentence
    assert "200" in sentence and "1400" in sentence and "1400 pièces" in sentence


def test_counts_only_and_the_bound_describe_the_SAME_draw_word_for_word() -> None:
    """One draw, one account of it. Two copies of the evidence clause would let a reader comparing
    a bound sentence with a counts-only one be comparing two descriptions of one draw."""
    bound = statement_fr(_bound())
    counts = statement_fr(_bound(kind=KIND_COUNTS_ONLY, count_upper_units=None,
                                 prevalence_upper=None, count_upper_pieces=None))
    clause = "200 familles de quasi-doublons écartées sur 1400 (1400 pièces) ont été tirées au "
    assert clause in bound and clause in counts


# ── no_population: no claim applies, and never a flattering zero ────────────────────────────────

def test_no_population_states_that_no_bound_applies_never_zero_percent() -> None:
    sentence = statement_fr(StatementInputs(
        kind=KIND_NO_POPULATION, unit_fr=FAMILIES, population_units=0, sample_units=0,
        relevant_units=0, confidence=0.95))
    assert sentence == "Le jeu écarté est vide : aucune borne ne s'applique."
    assert "0" not in sentence.replace("écarté", "") or "%" not in sentence


def test_the_two_empty_facts_get_two_different_sentences() -> None:
    """"le jeu écarté est vide" told to a lawyer whose dossier was never ranked is a false statement
    about her file — it says the tool looked and found nothing, when the tool never looked."""
    never_cut = statement_fr(StatementInputs(
        kind=KIND_NO_POPULATION, unit_fr=FAMILIES, population_units=0, sample_units=0,
        relevant_units=0, confidence=0.95, empty_reason_fr=NO_CUT_FR))
    assert "n'existe pas encore" in never_cut
    assert never_cut != statement_fr(StatementInputs(
        kind=KIND_NO_POPULATION, unit_fr=FAMILIES, population_units=0, sample_units=0,
        relevant_units=0, confidence=0.95))


def test_no_population_carries_no_qualifications_there_is_nothing_to_qualify() -> None:
    inputs = StatementInputs(
        kind=KIND_NO_POPULATION, unit_fr=FAMILIES, population_units=0, sample_units=0,
        relevant_units=0, confidence=0.95, scope="contentieux-a", run_ordinal=4,
        reviewed_on=date(2026, 8, 11), freshness_fr="à jour")
    assert qualifications_fr(inputs) == ""
    assert "périmètre" not in statement_fr(inputs)


# ── no default arm ──────────────────────────────────────────────────────────────────────────────

def test_an_unknown_register_raises_rather_than_degrading_to_the_nearest_one() -> None:
    with pytest.raises(ValueError, match="unknown register"):
        StatementInputs(kind="probably_a_bound", unit_fr=FAMILIES, population_units=1,
                        sample_units=1, relevant_units=0, confidence=0.95)


def test_the_register_list_is_the_estimate_s_own_four() -> None:
    assert set(REGISTERS) == {KIND_BOUND, KIND_CENSUS, KIND_COUNTS_ONLY, KIND_NO_POPULATION}


def test_an_ordinal_below_one_raises() -> None:
    with pytest.raises(ValueError, match="ordinal 1"):
        _bound(run_ordinal=0)


def test_the_singulariser_is_not_a_general_pluraliser_and_leaves_short_words_alone() -> None:
    assert singular_fr("familles de quasi-doublons écartées") == (
        "famille de quasi-doublon écartée")
    assert singular_fr("pièces écartées") == "pièce écartée"
    assert singular_fr("des pièces") == "des pièce"      # "des" is short: deliberately untouched


# ── FR-23's unfitness declaration ───────────────────────────────────────────────────────────────

def test_a_sample_that_comes_back_mostly_relevant_declares_the_ranking_unfit() -> None:
    finding = unfitness(relevant_units=14, sample_units=20, threshold=0.5)
    assert finding is not None and finding.share == pytest.approx(0.7)


def test_the_threshold_is_inclusive_at_its_own_boundary() -> None:
    assert unfitness(relevant_units=10, sample_units=20, threshold=0.5) is not None
    assert unfitness(relevant_units=9, sample_units=20, threshold=0.5) is None


def test_an_unjudged_sample_yields_no_finding_never_a_share_of_zero() -> None:
    """AD-19. A share of zero over a draw nobody judged would read as "the ranking is fine"."""
    assert unfitness(relevant_units=0, sample_units=0, threshold=0.5) is None


def test_impossible_counts_and_thresholds_raise() -> None:
    with pytest.raises(ValueError, match="share in"):
        unfitness(relevant_units=1, sample_units=2, threshold=0.0)
    with pytest.raises(ValueError, match="share in"):
        unfitness(relevant_units=1, sample_units=2, threshold=1.5)
    with pytest.raises(ValueError, match="impossible counts"):
        unfitness(relevant_units=3, sample_units=2, threshold=0.5)


def test_the_declaration_names_the_share_the_rule_and_refuses_the_line_move() -> None:
    finding = unfitness(relevant_units=14, sample_units=20, threshold=0.5)
    assert finding is not None
    said = unfitness_statement_fr(finding, version_no=3, unit_fr=FAMILIES)
    # the finding AND the rule that fired — a verdict without its rule is an accusation
    assert "14" in said and "70" in said and "50" in said
    assert "classement v3" in said.lower()
    assert "déplacer la ligne ne corrigerait rien" in said
    assert said.startswith("Sur les 20")                        # capitalised, not lower-cased after


def test_the_remedy_named_by_a_finding_is_never_the_line_move() -> None:
    finding = unfitness(relevant_units=20, sample_units=20, threshold=0.5)
    assert finding is not None and finding.remedy == "re-rank"


# ══ the adversarial review's confirmed defects, each proven fixed ════════════════════════════════

def test_a_positive_bound_never_renders_as_a_zero_percentage() -> None:
    """CONFIRMED [HIGH] by two skeptics, reproduced by execution. `{p:.1%}` printed « 0.0% » for
    every share below 0.05 %, and the product's own planner recommends exactly such draws: at most
    3 of 8 000 is a prevalence of 0.0375 %. The sentence then held two numbers in one parenthesis,
    one of them false and false in the flattering direction — a residual-prevalence bound of zero
    reads as *nothing relevant remains*, which is §0.2 re-created by a format specifier."""
    sentence = statement_fr(_bound(
        population_units=8000, sample_units=4217, piece_count=8000, count_upper_units=3,
        prevalence_upper=3 / 8000, count_upper_pieces=None))
    assert "au plus 3 des 8000" in sentence
    assert "0.0%" not in sentence and "0,0 %" not in sentence
    assert "prévalence ≤ 0.04%" in sentence


def test_a_bound_of_exactly_zero_is_stated_without_a_misleading_decimal() -> None:
    """A sample above n > N(1-c) — §0.2's own 1 330 of 1 400 — genuinely bounds at zero. That is a
    true and very strong statement, and it is spelled « 0 % », not « 0.0 % »: the two are different
    claims and only the second one is being made here."""
    sentence = statement_fr(_bound(count_upper_units=0, prevalence_upper=0.0,
                                   count_upper_pieces=0))
    assert "prévalence ≤ 0 %" in sentence


def test_a_census_of_one_relevant_family_agrees_in_number() -> None:
    """CONFIRMED. « 1 famille … SE SONT RÉVÉLÉES pertinentes » — the plural-verb-on-a-singular-count
    defect the Story 5.3 review fixed in `_found_fr`, reintroduced eight lines away."""
    sentence = statement_fr(_bound(
        kind=KIND_CENSUS, population_units=9, sample_units=9, piece_count=9, relevant_units=1,
        relevant_pieces=1, count_upper_units=None, prevalence_upper=None, count_upper_pieces=None))
    assert "s'est révélée pertinente" in sentence
    assert "se sont révélées" not in sentence


def test_the_wall_is_STATED_as_unrecorded_rather_than_silently_dropped() -> None:
    """CONFIRMED by two lenses. Decision 3 says the wall is named "unconditionally"; the code said
    `if inputs.scope`. A legacy recall_review recorded none, so its copied sentence dropped the
    clause and a lawyer pasted "1 400" with nothing saying under whose walls it was counted. An
    absence of evidence is stated here, exactly as an unstamped bound's freshness is."""
    sentence = statement_fr(_bound(scope=None))
    assert "périmètre non enregistré" in sentence


def test_the_declaration_does_not_claim_a_random_draw_on_a_census() -> None:
    """CONFIRMED. The declaration hard-coded « tirées au hasard » and was called for every
    register, so a census panel said "everything was examined" on one line and "5 were drawn at
    random" on the next — two incompatible accounts of one judgement."""
    finding = unfitness(relevant_units=5, sample_units=5, threshold=0.5)
    assert finding is not None
    said = unfitness_statement_fr(
        finding, version_no=3, unit_fr=FAMILIES, kind=KIND_CENSUS)
    assert "examinées" in said and "tirées au hasard" not in said


def test_the_declaration_does_not_say_ABOVE_when_the_share_equals_the_threshold() -> None:
    """CONFIRMED. The rule is `share >= threshold`, so it fires AT the boundary — where "au-dessus"
    is false and both figures round to the same displayed number, making the sentence read as a
    contradiction of itself."""
    finding = unfitness(relevant_units=10, sample_units=20, threshold=0.5)
    assert finding is not None
    said = unfitness_statement_fr(finding, version_no=3, unit_fr=FAMILIES)
    assert "au niveau ou au-dessus du seuil" in said


def test_the_declaration_agrees_in_number_on_a_single_unit() -> None:
    """CONFIRMED by two lenses: « les 1 familles … 1 étaient pertinentes »."""
    finding = unfitness(relevant_units=1, sample_units=1, threshold=0.5)
    assert finding is not None
    said = unfitness_statement_fr(finding, version_no=2, unit_fr=FAMILIES)
    assert "1 famille de quasi-doublon écartée" in said
    assert "était pertinente" in said and "étaient pertinentes" not in said


def test_the_declaration_names_the_remedy_FR_23_requires() -> None:
    finding = unfitness(relevant_units=14, sample_units=20, threshold=0.5)
    assert finding is not None
    said = unfitness_statement_fr(finding, version_no=3, unit_fr=FAMILIES)
    assert "théorie du cas révisée" in said
    assert "déplacer la ligne ne corrigerait rien" in said


def test_an_uncomputable_piece_worst_case_is_STATED_not_silently_omitted() -> None:
    """Raised by the review. The expression emitted nothing at all, and the client arm this
    replaced did carry the refusal — deleted with the arm, leaving zero occurrences repo-wide. It
    is the module's own rule, applied two functions over: a number withheld without a reason reads
    as one the product forgot rather than one it refused."""
    sentence = statement_fr(_bound(count_upper_pieces=None))
    assert "pas calculable pour ce tirage" in sentence
    assert "au plus 21 des 1400" in sentence          # the bound itself is untouched
