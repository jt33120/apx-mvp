"""The relevance-cascade orchestrator (Story 4.2, FR-38): stage gating, SM-18, near-duplicate
families, the AD-19 unscored failure path, and case-theory vs intrinsic — all deterministic (fake
scorer + fake judge, no network, no DB)."""

from __future__ import annotations

from apx.core.app.cascade import run_cascade
from apx.core.domain.cascade import Band, CascadeUnit, Outcome, RejectionClass, Stage
from apx.core.domain.config import CascadeConfig
from tests.scoring_fakes import FailingJudge, FakeScorer, FixedJudge


def _cfg(*, low: float = 0.35, high: float = 0.65, sample: int = 0,
         max_share: float = 0.5) -> CascadeConfig:
    return CascadeConfig(uncertain_low=low, uncertain_high=high,
                         calibration_sample=sample, stage3_max_share=max_share)


def _unit(pid: str, text: str, chunks: tuple[str, ...] = ("c",)) -> CascadeUnit:
    return CascadeUnit(piece_id=pid, text=text, chunk_ids=chunks)


def _run(units, scores, judge, cfg, case_theory="ma théorie"):  # noqa: ANN001
    return run_cascade(units, case_theory=case_theory, scorer=FakeScorer(scores), judge=judge,
                       config=cfg, tenant="t", matter="m", scopes={"w"})


def test_stage3_runs_only_on_the_uncertain_band_with_no_calibration_sample() -> None:
    units = [_unit("rel", "a"), _unit("dis", "b"), _unit("unc", "c", ("chk-unc",))]
    scores = {"rel": 0.9, "dis": 0.1, "unc": 0.5}
    judge = FixedJudge()
    res = _run(units, scores, judge, _cfg(sample=0))
    assert [t for (_q, t) in judge.calls] == ["c"]  # the LLM saw ONLY the uncertain pièce
    by = {j.piece_id: j for j in res.judgements}
    assert by["rel"].stage_reached is Stage.STAGE_2 and by["rel"].band is Band.CONFIDENT_RELEVANT
    assert by["rel"].label is None                                   # settled cheaply, no LLM
    assert by["dis"].stage_reached is Stage.STAGE_2 and by["dis"].band is Band.CONFIDENT_DISCARD
    assert by["unc"].stage_reached is Stage.STAGE_3 and by["unc"].label == "relevant"
    assert by["unc"].retained_extract_chunk_ids == ("chk-unc",)      # its extracts recorded


def test_sm18_stage3_share_is_measured_and_flagged_over_the_ceiling() -> None:
    units = [_unit("rel", "a"), _unit("dis", "b"), _unit("unc", "c")]
    res = _run(units, {"rel": 0.9, "dis": 0.1, "unc": 0.5}, FixedJudge(), _cfg(sample=0))
    assert res.stage3_share == 1 / 3 and not res.over_stage3_floor
    # a matter the cheap tier cannot separate → everyone uncertain → the whole matter hits the LLM
    res2 = _run(units, {"rel": 0.5, "dis": 0.5, "unc": 0.5}, FixedJudge(), _cfg(sample=0))
    assert res2.stage3_share == 1.0 and res2.over_stage3_floor


def test_a_calibration_sample_of_the_confident_bands_reaches_stage3() -> None:
    units = [_unit("r1", "a"), _unit("r2", "b")]  # both confident-relevant
    judge = FixedJudge()
    res = _run(units, {"r1": 0.9, "r2": 0.95}, judge, _cfg(sample=1))  # sample 1 of the 2
    stage3 = [j.piece_id for j in res.judgements if j.stage_reached is Stage.STAGE_3]
    assert len(stage3) == 1 and len(judge.calls) == 1 and res.stage3_share == 0.5


def test_near_duplicate_family_is_judged_once_members_kept_in_order() -> None:
    units = [_unit("p1", "meme texte"), _unit("p2", "meme texte"), _unit("p3", "meme texte"),
             _unit("p4", "autre")]
    judge = FixedJudge()
    res = _run(units, {"p1": 0.5, "p4": 0.5}, judge, _cfg(sample=0))
    by = {j.piece_id: j for j in res.judgements}
    assert by["p1"].is_representative and by["p1"].stage_reached is Stage.STAGE_3
    assert by["p2"].outcome is Outcome.REJECTED and not by["p2"].is_representative
    assert by["p2"].rejection_class is RejectionClass.EXACT_DUPLICATE_MEMBER
    assert by["p3"].outcome is Outcome.REJECTED
    fid = by["p1"].family_id
    assert by["p2"].family_id == fid and by["p3"].family_id == fid
    assert set(res.families[fid]) == {"p1", "p2", "p3"}
    assert {t for (_q, t) in judge.calls} == {"meme texte", "autre"}  # 2 reps judged, not 4 pièces
    # a rejected member is IN the order (AD-36), never in the unscored set
    assert "p2" in [j.piece_id for j in res.in_order] and res.unscored == ()


def test_a_judge_failure_makes_the_piece_unscored_and_leaves_the_rest_intact() -> None:
    units = [_unit("rel", "a"), _unit("unc1", "b"), _unit("unc2", "c")]
    scores = {"rel": 0.9, "unc1": 0.5, "unc2": 0.5}
    judge = FailingJudge(fails_on=lambda t: t == "b")  # fails only on unc1
    res = _run(units, scores, judge, _cfg(sample=0))
    by = {j.piece_id: j for j in res.judgements}
    assert by["unc1"].outcome is Outcome.UNSCORED and by["unc1"].score is None  # never imputed
    assert res.unscored == ("unc1",)
    assert "unc1" not in [j.piece_id for j in res.in_order]           # excluded from the order
    assert by["unc2"].outcome is Outcome.JUDGED and by["unc2"].label == "uncertain"  # rest intact
    assert by["rel"].stage_reached is Stage.STAGE_2                   # stage-2 result survives
    assert res.is_consistent()


def test_a_calibration_failure_keeps_a_confident_piece_in_the_order() -> None:
    # recall-first (a non-negotiable): a confident-relevant pièce was already judged by the cheap
    # tier; a FAILED calibration LLM call must not drop it to the unscored set / out of the order.
    units = [_unit("relA", "a"), _unit("unc", "b")]
    scores = {"relA": 0.9, "unc": 0.5}       # relA confident-relevant, unc uncertain
    judge = FailingJudge()                    # the LLM is down for everyone
    res = _run(units, scores, judge, _cfg(sample=1))   # relA is calibration-sampled
    by = {j.piece_id: j for j in res.judgements}
    assert by["relA"].outcome is Outcome.JUDGED and by["relA"].band is Band.CONFIDENT_RELEVANT
    assert by["relA"].stage_reached is Stage.STAGE_2 and by["relA"].label is None  # keeps stage-2
    assert "relA" in [j.piece_id for j in res.in_order]
    # the outage still surfaces: the uncertain pièce (its ONLY judge is the LLM) IS unscored
    assert by["unc"].outcome is Outcome.UNSCORED and res.unscored == ("unc",)
    assert res.stage3_share == 1.0            # both reached the LLM (calls made / egressed)


def test_intrinsic_basis_when_no_case_theory_names_the_signals() -> None:
    judge = FixedJudge()
    res = run_cascade([_unit("p", "x")], case_theory=None, scorer=FakeScorer({}), judge=judge,
                      config=_cfg(sample=0), tenant="t", matter="m", scopes={"w"})
    assert res.basis == "intrinsic" and res.intrinsic_signals
    by = {j.piece_id: j for j in res.judgements}
    assert by["p"].band is Band.UNCERTAIN and by["p"].stage_reached is Stage.STAGE_3
    assert judge.calls and "théorie de la cause" in judge.calls[0][0]  # the intrinsic question


def test_case_theory_basis_queries_the_scorer_with_its_text() -> None:
    class _Recording:
        def __init__(self) -> None:
            self.query: str | None = None

        def score(self, *, tenant, matter, scopes, query_text, piece_ids):  # noqa: ANN001
            self.query = query_text
            return {pid: 0.9 for pid in piece_ids}

    rec = _Recording()
    res = run_cascade([_unit("p", "x")], case_theory="contestation licenciement", scorer=rec,
                      judge=FixedJudge(), config=_cfg(sample=0), tenant="t", matter="m",
                      scopes={"w"})
    assert res.basis == "case-theory" and rec.query == "contestation licenciement"


def test_config_thresholds_move_band_membership() -> None:
    units = [_unit("p", "x")]
    res = _run(units, {"p": 0.5}, FixedJudge(), _cfg(low=0.35, high=0.65, sample=0))
    assert {j.piece_id: j for j in res.judgements}["p"].band is Band.UNCERTAIN
    judge = FixedJudge()
    res2 = _run(units, {"p": 0.5}, judge, _cfg(low=0.6, high=0.8, sample=0))
    j = {x.piece_id: x for x in res2.judgements}["p"]
    assert j.band is Band.CONFIDENT_DISCARD and j.stage_reached is Stage.STAGE_2 and not judge.calls
