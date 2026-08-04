"""The ranking act orchestrator (Story 4.3, FR-39) — cascade → identity → order → recorder.

Deterministic (fake scorer/judge/recorder, no DB, no network): the act records ONE order + the AD-23
identity; a matter with nothing to rank fails loudly (never an arbitrary order); the intrinsic basis
carries no case-theory version id; a judge outage still produces an order with an unscored tail."""

from __future__ import annotations

import pytest

from apx.core.app.rank import produce_ranking
from apx.core.domain.cascade import CascadeUnit
from apx.core.domain.config import CascadeConfig
from apx.core.domain.ranking import (
    RankedOrder,
    RankingIdentity,
    RankingIdentityInputs,
    RankingVersion,
)
from tests.scoring_fakes import FailingJudge, FakeScorer, FixedJudge


class FakeRecorder:
    """Captures the identity + order it was handed and returns a minted version (as the store
    would),
    without touching a database."""

    def __init__(self) -> None:
        self.calls: list[tuple[RankingIdentity, RankedOrder]] = []

    def record_ranking(
        self, *, tenant: str, matter: str, actor: str, identity: RankingIdentity, order: RankedOrder
    ) -> RankingVersion:
        self.calls.append((identity, order))
        return RankingVersion.build(
            tenant=tenant, matter=matter, version_no=1, identity=identity)


def _cfg() -> CascadeConfig:
    return CascadeConfig(uncertain_low=0.35, uncertain_high=0.65, calibration_sample=0,
                         stage3_max_share=0.5)


def _inputs(**over: object) -> RankingIdentityInputs:
    base = dict(
        case_theory_version_id="ct-v1", model_provider="mistral",
        model_endpoint="https://api.mistral.ai/v1", model_name="mistral-small-latest",
        prompt_version="cascade-question-v1", temperature=0.0, sampling={"top_p": 1.0},
        embedder_model_id="bge-m3", embedder_model_version="1.5",
        chunking_config_version="chunk-v1", schema_version="slice-a")
    base.update(over)
    return RankingIdentityInputs(**base)  # type: ignore[arg-type]


def _units(*ids: str) -> list[CascadeUnit]:
    return [CascadeUnit(piece_id=pid, text=pid, chunk_ids=("c",)) for pid in ids]


def _run(units, scores, judge, *, case_theory="ma théorie", inputs=None, recorder=None):  # noqa: ANN001
    rec = recorder or FakeRecorder()
    version = produce_ranking(
        units, case_theory=case_theory, scorer=FakeScorer(scores), judge=judge, config=_cfg(),
        inputs=inputs or _inputs(), tenant="t", matter="m", actor="me.durand", scopes={"w"},
        recorder=rec)
    return version, rec


def test_produce_ranking_records_one_order_and_the_full_identity() -> None:
    version, rec = _run(_units("rel", "dis"), {"rel": 0.9, "dis": 0.1}, FixedJudge())
    (identity, order) = rec.calls[-1]
    assert identity.basis == "case-theory" and identity.case_theory_version_id == "ct-v1"
    assert identity.model_name == "mistral-small-latest" and identity.tie_break == "piece-id-hash"
    assert [r.piece_id for r in order.rows] == ["rel", "dis"]  # confident-relevant ranks first
    assert version.version_no == 1 and version.identity.fingerprint == identity.fingerprint


def test_a_matter_with_nothing_to_rank_fails_loudly() -> None:
    with pytest.raises(ValueError, match="no pièce to rank"):
        _run([], {}, FixedJudge())


def test_the_intrinsic_basis_drops_a_stale_case_theory_version_id() -> None:
    # no case theory → intrinsic basis; even if the caller left an id in the inputs, the identity
    # must not carry it (the intrinsic ranking references no case theory version).
    _version, rec = _run(_units("p"), {}, FixedJudge(), case_theory=None,
                         inputs=_inputs(case_theory_version_id="stale"))
    (identity, _order) = rec.calls[-1]
    assert identity.basis == "intrinsic" and identity.case_theory_version_id is None


def test_a_judge_outage_still_produces_an_order_with_an_unscored_tail() -> None:
    # recall-first: a confident-relevant pièce stays in the order; the uncertain pièce whose only
    # judge failed goes to the unscored tail (AD-19), and the act still produces an order.
    _version, rec = _run(_units("rel", "unc"), {"rel": 0.9, "unc": 0.5}, FailingJudge())
    (_identity, order) = rec.calls[-1]
    assert [r.piece_id for r in order.rows] == ["rel"] and order.unscored == ("unc",)
    assert order.is_consistent()


def test_a_blank_identity_input_fails_loudly() -> None:
    with pytest.raises(ValueError, match="model_provider"):
        _run(_units("p"), {"p": 0.9}, FixedJudge(), inputs=_inputs(model_provider=""))
