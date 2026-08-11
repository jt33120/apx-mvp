"""The five Story-5.2 gates, proven LIVE (OQ-4 / FR-22 / FR-23 / FR-38 / FR-42 / FR-56).

One check per hard input. Each is exercised three ways: it passes the real tree, it FIRES on a
scratch copy carrying a deliberate reversal of the answer, and it FAILS CLOSED on something it
cannot read or cannot find. A check nobody has watched fail is a check nobody knows is connected.
The real tree is never modified — every violation is injected into a copy under ``tmp_path``.
"""

from __future__ import annotations

from pathlib import Path

from apx.checks.estimator import (
    a_census_states_no_bound,
    one_run_one_bound_chosen_by_recency,
    piece_figure_is_a_worst_case,
    the_bound_consumes_no_model_number,
    the_bound_is_computed_from_the_freeze,
    the_simulation_gate_is_wired,
)

_APX = Path(__file__).resolve().parents[2] / "apx"
_STORE = _APX / "adapters" / "store_postgres" / "store.py"
_SAMPLING = _APX / "core" / "domain" / "sampling.py"
# the census sentence's first statement, split so this file stays inside ruff's 100
_CENSUS_HEAD = (
    '    head = f"recensement : les {piece_count} pièces écartées '
    'ont toutes été examinées ; "')


def _mutated(tmp_path: Path, source: Path, old: str, new: str, name: str = "copy.py") -> Path:
    text = source.read_text(encoding="utf-8")
    assert old in text, f"the anchor is no longer in {source.name}: {old!r}"
    target = tmp_path / name
    target.write_text(text.replace(old, new, 1), encoding="utf-8")
    return target


def _module(tmp_path: Path, name: str, src: str) -> Path:
    path = tmp_path / f"{name}.py"
    path.write_text(src, encoding="utf-8")
    return path


# ── input 1: the pièce figure is a worst case, never a rescale ───────────────────────────────────

def test_the_worst_case_check_passes_the_real_tree() -> None:
    assert piece_figure_is_a_worst_case().ok


def test_it_fires_on_the_forbidden_rescale(tmp_path: Path) -> None:
    """The exact arithmetic OQ-4 input 1 forbids: a family prevalence spread over a pièce
    denominator, which understates whenever the largest families are the relevant ones."""
    src = (
        "def sentence(estimate, run):\n"
        "    return estimate.prevalence_upper * run.population_pieces\n")
    r = piece_figure_is_a_worst_case([_module(tmp_path, "rescale", src)])
    assert not r.ok and "uses a prevalence as a factor" in r.detail


def test_it_fires_when_the_operands_are_the_other_way_round(tmp_path: Path) -> None:
    src = "def sentence(e, r):\n    return r.population_pieces * e.prevalence_upper\n"
    r = piece_figure_is_a_worst_case([_module(tmp_path, "flipped", src)])
    assert not r.ok and "flattering direction" in r.detail


def test_it_still_fires_when_the_piece_operand_is_renamed_out_of_sight(tmp_path: Path) -> None:
    """CONFIRMED by the review. The first draft required BOTH operands to be recognisable — one
    named for a prevalence, one named for a *pièce* — so hoisting the denominator into a local
    called ``total`` walked the forbidden rescale straight past a green gate.

    A denylist keyed on two names is defeated by renaming either. The rule is now one-sided: a
    prevalence is a ratio you STATE, never a factor you multiply, and there is no legitimate
    multiplication of one anywhere in this product."""
    src = (
        "def sentence(estimate, run):\n"
        "    total = run.population_pieces\n"
        "    return estimate.prevalence_upper * total\n")
    r = piece_figure_is_a_worst_case([_module(tmp_path, "renamed", src)])
    assert not r.ok and "uses a prevalence as a factor" in r.detail


def test_it_fires_when_the_count_upper_is_the_factor_instead(tmp_path: Path) -> None:
    src = "def sentence(e, ratio):\n    return e.count_upper * ratio\n"
    r = piece_figure_is_a_worst_case([_module(tmp_path, "count_factor", src)])
    assert not r.ok and "uses a prevalence as a factor" in r.detail


def test_the_worst_case_check_reads_the_typescript_client_too(tmp_path: Path) -> None:
    """CONFIRMED by the review. The check globbed ``*.py`` and reported *"no prevalence is
    multiplied ANYWHERE"* while ``apx/web`` — which holds both operands one line under the sentence
    a lawyer reads — was invisible to it. A success message claiming a coverage it never had is
    worse than no check, because it is believed."""
    from apx.checks.estimator import _web_rescales
    web = tmp_path / "src"
    web.mkdir()
    (web / "clean.tsx").write_text(
        "/* a * b in a comment must not fire, nor /** jsdoc * stars */\n"
        "const label = `${bound.prevalence_upper}`;\n"
        "const pct = ((bound.prevalence_upper ?? 0) * 100).toFixed(1);\n", encoding="utf-8")
    assert _web_rescales(web) == [], "a comment and a percent rendering are not rescales"
    (web / "bad.tsx").write_text(
        "const y = bound.prevalence_upper * bound.piece_count;\n", encoding="utf-8")
    hits = _web_rescales(web)
    assert len(hits) == 1 and "bad.tsx:1" in hits[0]


def test_the_web_leg_sees_through_the_parenthesised_null_coalesce(tmp_path: Path) -> None:
    """The shape the client actually writes. ``(x ?? 0) * y`` puts a literal ``0`` immediately left
    of the ``*``, so a leg that only inspected the adjacent tokens would read it as arithmetic on
    two numbers and miss the rescale entirely."""
    from apx.checks.estimator import _web_rescales
    web = tmp_path / "src"
    web.mkdir()
    (web / "sneaky.tsx").write_text(
        "const y = (bound.prevalence_upper ?? 0) * bound.piece_count;\n", encoding="utf-8")
    assert len(_web_rescales(web)) == 1


def test_it_fires_when_the_piece_figure_comes_from_somewhere_else(tmp_path: Path) -> None:
    src = (
        "def build(bound):\n"
        "    return Estimate(kind='bound', count_upper_pieces=round(bound.prevalence * 1400))\n")
    r = piece_figure_is_a_worst_case([_module(tmp_path, "invented", src)])
    assert not r.ok and "pieces_upper_bound" in r.detail


def test_passing_the_worst_case_through_a_variable_is_allowed(tmp_path: Path) -> None:
    """The two legs are a pair: this one permits a pass-through, and the rescale leg is what stops
    the pass-through carrying a rescale."""
    src = (
        "def build(sizes, d):\n"
        "    worst = pieces_upper_bound(count_upper_families=d, family_sizes=sizes)\n"
        "    return Estimate(kind='bound', count_upper_pieces=worst)\n")
    assert piece_figure_is_a_worst_case([_module(tmp_path, "passthrough", src)]).ok


def test_the_worst_case_check_fails_closed_on_an_unparseable_module(tmp_path: Path) -> None:
    r = piece_figure_is_a_worst_case([_module(tmp_path, "broken", "def (:\n")])
    assert not r.ok and "cannot parse" in r.detail


# ── input 2: a census states an exact count and no bound ─────────────────────────────────────────

def test_the_census_check_passes_the_real_tree() -> None:
    assert a_census_states_no_bound().ok


def test_it_fires_when_the_census_branch_carries_a_bound(tmp_path: Path) -> None:
    copy = _mutated(
        tmp_path, _SAMPLING,
        "        return Estimate(kind=KIND_CENSUS, relevant_pieces=relevant_pieces_drawn, "
        "**common)",
        "        return Estimate(kind=KIND_CENSUS, relevant_pieces=relevant_pieces_drawn, "
        "prevalence_upper=0.0, **common)")
    r = a_census_states_no_bound(copy)
    assert not r.ok and "prevalence_upper" in r.detail and "disjoint" in r.detail


def test_it_fires_when_the_census_sentence_states_a_percentage(tmp_path: Path) -> None:
    """FR-22's named failure: a residual-risk figure over a population that was read in full."""
    copy = _mutated(
        tmp_path, _SAMPLING,
        'return head + "aucune n\'était pertinente"',
        'return head + "au plus 0,0 % est pertinent"')
    r = a_census_states_no_bound(copy)
    assert not r.ok and "can reach a percentage" in r.detail


def test_it_fires_when_the_bound_branch_claims_an_exact_count(tmp_path: Path) -> None:
    copy = _mutated(
        tmp_path, _SAMPLING, "        kind=KIND_BOUND,",
        "        kind=KIND_BOUND, relevant_pieces=0,")
    r = a_census_states_no_bound(copy)
    assert not r.ok and "never states an exact count" in r.detail


def test_it_fires_when_the_percentage_hides_in_a_helper(tmp_path: Path) -> None:
    """CONFIRMED by the review. The percent leg read ``census_statement_fr``'s own body only, so
    moving the percentage one function over left the census sentence carrying a prevalence with the
    gate green — the exact failure the check exists for, not a variation on it."""
    copy = _mutated(
        tmp_path, _SAMPLING,
        _CENSUS_HEAD,
        "    head = _residual(piece_count)")
    copy.write_text(
        copy.read_text(encoding="utf-8").replace(
            "def census_statement_fr(",
            "def _residual(n: int) -> str:\n"
            "    return f\"résiduel {0.0:.1%} sur {n} — \"\n\n\n"
            "def census_statement_fr(", 1), encoding="utf-8")
    r = a_census_states_no_bound(copy)
    assert not r.ok and "can reach a percentage" in r.detail and "_residual()" in r.detail


def test_it_fires_when_the_percentage_hides_in_a_module_constant(tmp_path: Path) -> None:
    """The other half of the same evasion: hoist the string out of the function entirely."""
    copy = _mutated(
        tmp_path, _SAMPLING,
        _CENSUS_HEAD,
        "    head = _RESIDUAL")
    copy.write_text(
        copy.read_text(encoding="utf-8").replace(
            "def census_statement_fr(",
            "_RESIDUAL = \"au plus 0,0 % du jeu écarté — \"\n\n\n"
            "def census_statement_fr(", 1), encoding="utf-8")
    r = a_census_states_no_bound(copy)
    assert not r.ok and "the module constant _RESIDUAL" in r.detail


def test_the_census_check_fails_closed_when_a_register_disappears(tmp_path: Path) -> None:
    copy = _mutated(tmp_path, _SAMPLING, "        kind=KIND_BOUND,", '        kind="bound",')
    r = a_census_states_no_bound(copy)
    assert not r.ok and "no longer builds every register" in r.detail


def test_the_census_check_fails_closed_when_the_sentence_is_renamed(tmp_path: Path) -> None:
    copy = _mutated(
        tmp_path, _SAMPLING, "def census_statement_fr(", "def census_sentence_renamed(")
    r = a_census_states_no_bound(copy)
    assert not r.ok and "renamed?" in r.detail


def test_the_census_check_fails_closed_on_an_unparseable_module(tmp_path: Path) -> None:
    r = a_census_states_no_bound(_module(tmp_path, "broken", "def (:\n"))
    assert not r.ok and "cannot parse" in r.detail


# ── input 3: one run per bound, and the current one chosen by recency ────────────────────────────

def test_the_one_run_check_passes_the_real_tree() -> None:
    assert one_run_one_bound_chosen_by_recency().ok


def test_it_fires_on_a_second_birthplace_for_a_bound(tmp_path: Path) -> None:
    """A second call site is a second chance to pool two draws over one population."""
    src = (
        "from apx.core.domain.confidence import prevalence_upper_bound\n"
        "def pooled(runs):\n"
        "    n = sum(r.sample_size for r in runs)\n"
        "    return prevalence_upper_bound(runs[0].population, n, 0)\n")
    r = one_run_one_bound_chosen_by_recency([_module(tmp_path, "pooling", src)])
    assert not r.ok and "second birthplace" in r.detail


def test_it_fires_when_the_current_bound_is_chosen_by_favourability(tmp_path: Path) -> None:
    """The leg that actually bites: 'show the best one' is a request someone makes in good faith."""
    copy = _mutated(
        tmp_path, _STORE,
        ".order_by(SamplingRun.completed_at.desc(), SamplingRun.id.desc()).limit(1)).first()",
        ".order_by(SamplingRun.prevalence_upper.asc()).limit(1)).first()")
    r = one_run_one_bound_chosen_by_recency(store_path=copy)
    assert not r.ok and "most flattering" in r.detail


def test_it_fires_on_a_second_birthplace_reached_under_an_alias(tmp_path: Path) -> None:
    """CONFIRMED by the review. The first draft matched ``ast.Name`` alone, so an ``import … as``
    (an ``ast.alias``, whose name is a plain string) reintroduced pooling with the gate green.
    A guard one import style from silence is a habit, not a property."""
    src = (
        "from apx.core.domain.confidence import prevalence_upper_bound as pub\n"
        "def pooled(runs):\n"
        "    return pub(runs[0].population, sum(r.sample_size for r in runs), 0)\n")
    r = one_run_one_bound_chosen_by_recency([_module(tmp_path, "aliased_pool", src)])
    assert not r.ok and "second birthplace" in r.detail


def test_it_fires_on_a_second_birthplace_reached_by_a_qualified_call(tmp_path: Path) -> None:
    """The other half of the same evasion: ``confidence.prevalence_upper_bound(...)`` is an
    ``ast.Attribute``, also invisible to a bare-name match."""
    src = (
        "from apx.core.domain import confidence\n"
        "def pooled(runs):\n"
        "    return confidence.prevalence_upper_bound(runs[0].population, 10, 0)\n")
    r = one_run_one_bound_chosen_by_recency([_module(tmp_path, "qualified_pool", src)])
    assert not r.ok and "second birthplace" in r.detail


def test_it_fires_when_the_favourability_column_is_held_in_a_variable(tmp_path: Path) -> None:
    """Unadjudicated by the review — its skeptic died on the weekly limit — and fixed anyway, on the
    ground that an unadjudicated finding is not a refuted one. Hoisting the ordering column into a
    local mentions nothing flattering at the ``order_by`` site."""
    copy = _mutated(
        tmp_path, _STORE,
        "            run = session.scalars(\n                select(SamplingRun)",
        "            nicest = SamplingRun.prevalence_upper.asc()\n"
        "            run = session.scalars(\n                select(SamplingRun)")
    copy.write_text(
        copy.read_text(encoding="utf-8").replace(
            ".order_by(SamplingRun.completed_at.desc(), SamplingRun.id.desc()).limit(1)).first()",
            ".order_by(nicest).limit(1)).first()", 1), encoding="utf-8")
    r = one_run_one_bound_chosen_by_recency(store_path=copy)
    assert not r.ok and "most flattering" in r.detail


def test_reading_a_run_without_calling_the_estimator_is_allowed(tmp_path: Path) -> None:
    src = "def show(run):\n    return run.prevalence_upper, run.count_upper\n"
    assert one_run_one_bound_chosen_by_recency([_module(tmp_path, "reader", src)]).ok


def test_the_one_run_check_fails_closed_when_the_reader_is_renamed(tmp_path: Path) -> None:
    copy = _mutated(
        tmp_path, _STORE, "    def read_current_bound(", "    def read_bound_renamed(")
    r = one_run_one_bound_chosen_by_recency(store_path=copy)
    assert not r.ok and "renamed?" in r.detail


def test_the_one_run_check_fails_closed_on_an_unparseable_module(tmp_path: Path) -> None:
    r = one_run_one_bound_chosen_by_recency([_module(tmp_path, "broken", "def (:\n")])
    assert not r.ok and "cannot parse" in r.detail


# ── input 4: the bound is computed from the freeze ───────────────────────────────────────────────

def test_the_freeze_check_passes_the_real_tree() -> None:
    assert the_bound_is_computed_from_the_freeze().ok


def test_it_fires_when_completion_re_derives_the_discarded_set(tmp_path: Path) -> None:
    """A bound over the matter as it is NOW, quoted with the authority of a draw made over what it
    was THEN — the wrong referent, one layer deeper."""
    copy = _mutated(
        tmp_path, _STORE,
        "            bound = bound_for_run(",
        "            _ = derive_triage_sets(1, 2, 3)\n"
        "            bound = bound_for_run(")
    r = the_bound_is_computed_from_the_freeze(copy)
    assert not r.ok and "derive_triage_sets" in r.detail


def test_it_fires_when_the_population_is_computed_rather_than_frozen(tmp_path: Path) -> None:
    copy = _mutated(
        tmp_path, _STORE,
        "            bound = bound_for_run(\n"
        "                population=run.population_families,",
        "            bound = bound_for_run(\n"
        "                population=len(families),")
    r = the_bound_is_computed_from_the_freeze(copy)
    assert not r.ok and "'population=' is not read off the frozen run row" in r.detail


def test_the_freeze_check_fails_closed_when_completion_is_renamed(tmp_path: Path) -> None:
    copy = _mutated(
        tmp_path, _STORE, "    def complete_sampling_run(", "    def complete_renamed(")
    r = the_bound_is_computed_from_the_freeze(copy)
    assert not r.ok and "renamed?" in r.detail


def test_the_freeze_check_fails_closed_on_an_unparseable_module(tmp_path: Path) -> None:
    r = the_bound_is_computed_from_the_freeze(_module(tmp_path, "broken", "def (:\n"))
    assert not r.ok and "cannot parse" in r.detail


# ── input 5: the bound consumes no model-reported number ─────────────────────────────────────────

def test_the_no_model_number_check_passes_the_real_tree() -> None:
    assert the_bound_consumes_no_model_number().ok


def test_it_fires_when_the_estimator_reaches_the_priced_projection(tmp_path: Path) -> None:
    src = (
        "from apx.core.domain.line_projection import project\n"
        "def bound(x):\n    return project(x)\n")
    r = the_bound_consumes_no_model_number([_module(tmp_path, "crossed", src)])
    assert not r.ok and "different kinds of statement" in r.detail


def test_it_fires_when_the_projection_is_reached_under_an_alias(tmp_path: Path) -> None:
    """CONFIRMED by the review, which walked past the first draft with two spellings it never
    looked at: ``import a.b.line_projection as lp`` and ``from a.b import line_projection as lp``
    are both an ``ast.alias``, invisible to a leg matching ``ImportFrom.module`` and a bare name."""
    plain = ("import apx.core.domain.line_projection as lp\n"
             "def x(a, b):\n    return lp.project(a, b)\n")
    r = the_bound_consumes_no_model_number([_module(tmp_path, "plain_alias", plain)])
    assert not r.ok and "imported as lp" in r.detail

    frm = "from apx.core.domain import line_projection as lp\ndef x(a):\n    return lp.project(a)\n"
    r = the_bound_consumes_no_model_number([_module(tmp_path, "from_alias", frm)])
    assert not r.ok and "reaches line_projection" in r.detail


def test_it_fires_when_the_estimator_reads_a_model_s_own_confidence(tmp_path: Path) -> None:
    """§0.2, one layer down: a made-up number laundered through a statistical sentence."""
    src = "def bound(response):\n    return response.confidence\n"
    r = the_bound_consumes_no_model_number([_module(tmp_path, "laundered", src)])
    assert not r.ok and "model response" in r.detail


def test_the_statistical_confidence_level_is_not_a_model_number(tmp_path: Path) -> None:
    src = "def bound(run):\n    return run.confidence\n"
    assert the_bound_consumes_no_model_number([_module(tmp_path, "level", src)]).ok


def test_the_no_model_number_check_fails_closed_on_an_unparseable_module(tmp_path: Path) -> None:
    r = the_bound_consumes_no_model_number([_module(tmp_path, "broken", "def (:\n")])
    assert not r.ok and "cannot parse" in r.detail


# ── Story 5.3: the word "proven" is un-writable without the proof running ────────────────────────

_CONFIDENCE = _APX / "core" / "domain" / "confidence.py"
_HARNESS = _APX / "eval" / "estimator_simulation.py"
_GATE_TEST = _APX.parent / "tests" / "eval" / "test_estimator_simulation.py"


def test_the_gate_check_passes_the_real_tree() -> None:
    assert the_simulation_gate_is_wired().ok


def test_it_fires_when_proven_is_claimed_and_the_harness_does_not_exist(tmp_path: Path) -> None:
    """The §0.2 failure in one line of Python: a claim of soundness nobody checked, written into
    the product and defended by a green build."""
    r = the_simulation_gate_is_wired(
        domain_path=_CONFIDENCE, harness_path=tmp_path / "gone.py", test_path=_GATE_TEST)
    assert not r.ok and "does not exist" in r.detail


def test_it_fires_when_the_gate_s_test_module_is_missing(tmp_path: Path) -> None:
    r = the_simulation_gate_is_wired(
        domain_path=_CONFIDENCE, harness_path=_HARNESS, test_path=tmp_path / "gone.py")
    assert not r.ok and "does not exist" in r.detail


def test_it_fires_when_the_harness_stops_naming_its_target(tmp_path: Path) -> None:
    copy = _mutated(tmp_path, _HARNESS, "COVERAGE_TARGET = 0.95", "_target = 0.95")
    r = the_simulation_gate_is_wired(
        domain_path=_CONFIDENCE, harness_path=copy, test_path=_GATE_TEST)
    assert not r.ok and "COVERAGE_TARGET" in r.detail


def test_it_fires_when_the_gate_asserts_no_tightness_ceiling(tmp_path: Path) -> None:
    """AC-2. Soundness alone is satisfiable by an estimator answering "at most all of them", which
    covers the truth every time and says nothing."""
    text = _GATE_TEST.read_text(encoding="utf-8")
    stripped = tmp_path / "no_ceiling.py"
    stripped.write_text(
        text.replace("tightness_ceiling", "ceiling_removed")
            .replace("worst_prevalence_upper", "loosest_removed"), encoding="utf-8")
    r = the_simulation_gate_is_wired(
        domain_path=_CONFIDENCE, harness_path=_HARNESS, test_path=stripped)
    assert not r.ok and "tightness CEILING" in r.detail


def test_it_fires_when_the_gate_s_test_is_skipped(tmp_path: Path) -> None:
    """A gate that is registered and skipped looks exactly like a gate that runs — the Epic 4
    lesson about silent reviewers, applied to the harness itself."""
    copy = _mutated(
        tmp_path, _GATE_TEST,
        "def test_every_scenario_covers_the_truth_at_the_stated_confidence() -> None:",
        "@pytest.mark.skip(reason='flaky')\n"
        "def test_every_scenario_covers_the_truth_at_the_stated_confidence() -> None:")
    r = the_simulation_gate_is_wired(
        domain_path=_CONFIDENCE, harness_path=_HARNESS, test_path=copy)
    assert not r.ok and "is skipped or de-collected" in r.detail


def test_an_UNPROVEN_estimator_that_says_so_is_not_a_violation(tmp_path: Path) -> None:
    """Shipping counts-only is FR-23 working, not FR-23 broken. The check must not push anyone
    toward flipping the flag back to keep a build green."""
    copy = _mutated(tmp_path, _CONFIDENCE, "ESTIMATOR_PROVEN = True", "ESTIMATOR_PROVEN = False")
    r = the_simulation_gate_is_wired(
        domain_path=copy, harness_path=tmp_path / "nothing.py", test_path=tmp_path / "nothing.py")
    assert r.ok and "counts only" in r.detail


def test_the_gate_check_fails_closed_when_the_flag_is_not_a_literal(tmp_path: Path) -> None:
    copy = _mutated(
        tmp_path, _CONFIDENCE, "ESTIMATOR_PROVEN = True", "ESTIMATOR_PROVEN = _read_somewhere()")
    r = the_simulation_gate_is_wired(domain_path=copy)
    assert not r.ok and "module-level boolean" in r.detail


def test_the_gate_check_fails_closed_when_the_predicate_is_renamed(tmp_path: Path) -> None:
    copy = _mutated(
        tmp_path, _CONFIDENCE, "def estimator_is_proven()", "def proven_renamed()")
    r = the_simulation_gate_is_wired(domain_path=copy)
    assert not r.ok and "renamed?" in r.detail


def test_the_counts_only_register_may_carry_no_bound(tmp_path: Path) -> None:
    """The fourth register is disjoint like the other three: an unproven estimator states the
    counts it observed and nothing derived from them."""
    copy = _mutated(
        tmp_path, _SAMPLING,
        "        return Estimate(kind=KIND_COUNTS_ONLY, **common)",
        "        return Estimate(kind=KIND_COUNTS_ONLY, prevalence_upper=0.0, **common)")
    r = a_census_states_no_bound(copy)
    assert not r.ok and "counts-only branch" in r.detail


def test_the_census_check_fails_closed_when_the_counts_only_register_disappears(
    tmp_path: Path
) -> None:
    copy = _mutated(
        tmp_path, _SAMPLING, "kind=KIND_COUNTS_ONLY, **common", 'kind="counts_only", **common')
    r = a_census_states_no_bound(copy)
    assert not r.ok and "every register" in r.detail


# ── the review's evasions of the Story-5.3 gate, each proven to fire now ─────────────────────────

def test_it_fires_when_the_predicate_ignores_the_flag(tmp_path: Path) -> None:
    """CONFIRMED [HIGH]. The gate asserted the predicate EXISTS and never that it consults the
    flag, so `def estimator_is_proven(): return True` passed every leg — the one seam the whole
    mechanism hangs from, unchecked."""
    copy = _mutated(
        tmp_path, _CONFIDENCE, "    return ESTIMATOR_PROVEN", "    return True")
    r = the_simulation_gate_is_wired(domain_path=copy)
    assert not r.ok and "does not read ESTIMATOR_PROVEN" in r.detail


def test_it_reads_the_LAST_module_level_flag_and_ignores_nested_ones(tmp_path: Path) -> None:
    """CONFIRMED [HIGH]. `ast.walk` returned the FIRST literal anywhere in the tree, so a
    `ESTIMATOR_PROVEN = False` nested in any function shadowed the real module-level value — and
    Python binds the LAST top-level assignment, which the walk order does not respect either."""
    nested = _mutated(
        tmp_path, _CONFIDENCE,
        "def estimator_is_proven() -> bool:",
        "def _decoy() -> bool:\n    ESTIMATOR_PROVEN = False\n    return ESTIMATOR_PROVEN\n\n\n"
        "def estimator_is_proven() -> bool:", name="nested.py")
    r = the_simulation_gate_is_wired(
        domain_path=nested, harness_path=_HARNESS, test_path=_GATE_TEST)
    assert r.ok, "a nested assignment is not the module-level flag"


def test_it_fires_when_the_floor_is_only_MENTIONED_and_never_asserted(tmp_path: Path) -> None:
    """CONFIRMED [MEDIUM], on two counts. The leg searched the whole unparsed module, and
    ``ast.unparse`` keeps DOCSTRINGS — so naming ``piece_coverage`` in prose satisfied the leg that
    exists to guarantee the pièce claim. And the floor markers were joined by ``any()``, so
    asserting only ``family_coverage`` — the textbook hypergeometric — was enough."""
    prose = _module(
        tmp_path, "prose",
        'def test_floor():\n'
        '    """piece_coverage matters a great deal."""\n'
        '    assert v.family_coverage >= t\n'
        '    assert v.tightness_ceiling is not None\n')
    r = the_simulation_gate_is_wired(
        domain_path=_CONFIDENCE, harness_path=_HARNESS, test_path=prose)
    assert not r.ok and "piece_coverage" in r.detail and "coverage FLOOR" in r.detail


def test_the_floor_leg_is_satisfied_only_by_asserting_BOTH_claims(tmp_path: Path) -> None:
    both = _module(
        tmp_path, "both",
        'def test_floor():\n'
        '    assert v.family_coverage_lower >= t\n'
        '    assert v.piece_coverage_lower >= t\n'
        '    assert v.worst_prevalence_upper <= c\n')
    assert the_simulation_gate_is_wired(
        domain_path=_CONFIDENCE, harness_path=_HARNESS, test_path=both).ok


def test_it_fires_on_a_module_level_pytestmark_skip(tmp_path: Path) -> None:
    """CONFIRMED [HIGH]. The first version read decorators on `def test*` only, so one module-level
    line disabled the whole gate while the check reported nothing skipped."""
    copy = _mutated(
        tmp_path, _GATE_TEST, "_VERDICTS = run_all()",
        "pytestmark = pytest.mark.skip(reason='slow')\n_VERDICTS = run_all()")
    r = the_simulation_gate_is_wired(
        domain_path=_CONFIDENCE, harness_path=_HARNESS, test_path=copy)
    assert not r.ok and "pytestmark" in r.detail


def test_it_fires_on_an_imperative_skip_at_import_time(tmp_path: Path) -> None:
    copy = _mutated(
        tmp_path, _GATE_TEST, "_VERDICTS = run_all()",
        "pytest.skip('later', allow_module_level=True)\n_VERDICTS = run_all()")
    r = the_simulation_gate_is_wired(
        domain_path=_CONFIDENCE, harness_path=_HARNESS, test_path=copy)
    assert not r.ok and "skip()" in r.detail


def test_it_fires_when_a_conftest_de_collects_the_gate(tmp_path: Path) -> None:
    """CONFIRMED [LOW]. The check's only evidence the module was COLLECTED was that the file
    exists, and pytest collection is governed by conftest.py."""
    home = tmp_path / "eval"
    home.mkdir()
    gate = home / "test_estimator_simulation.py"
    gate.write_text(_GATE_TEST.read_text(encoding="utf-8"), encoding="utf-8")
    (home / "conftest.py").write_text(
        "collect_ignore = ['test_estimator_simulation.py']\n", encoding="utf-8")
    r = the_simulation_gate_is_wired(
        domain_path=_CONFIDENCE, harness_path=_HARNESS, test_path=gate)
    assert not r.ok and "de-collects" in r.detail
