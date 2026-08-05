"""A taxonomy label never moves a pièce, the version, or a human-set label across re-ranking
(Story 4.5, FR-40/FR-43/AD-39/AD-23) — plus the SM-19 coverage figures over a ranking.

The label axis is orthogonal to the ranked order: assigning or changing a label leaves the ranked
order and the ranking-version fingerprint byte-identical, and — because the ledger is
version-independent — a human-set label survives re-ranking untouched. Deterministic SQLite."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apx.adapters.store_postgres.models import Base
from apx.adapters.store_postgres.store import SqlStore
from apx.core.app.ingest import IngestionResult
from apx.core.domain.cascade import Band, CascadeResult, PieceJudgement, Stage
from apx.core.domain.config import CascadeConfig
from apx.core.domain.ranking import RankingIdentityInputs, assemble_identity, rank_cascade

_CFG = CascadeConfig(uncertain_low=0.35, uncertain_high=0.65, calibration_sample=20,
                     stage3_max_share=0.5)


@pytest.fixture
def store() -> SqlStore:
    e = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(e)
    s = SqlStore(sessionmaker(bind=e, future=True))
    s.save(IngestionResult(), scope="w", actor="setup", matter="m", tenant="t", audit=False)
    s.set_config("t", "admin", "taxonomy", ["Contrats", "Jurisprudence"])
    return s


def _identity():  # noqa: ANN202
    inputs = RankingIdentityInputs(
        case_theory_version_id=None, model_provider="mistral",
        model_endpoint="https://api.mistral.ai/v1", model_name="mistral-small-latest",
        prompt_version="cascade-question-v1", temperature=0.0, sampling={"top_p": 1.0},
        embedder_model_id="bge-m3", embedder_model_version="1.5",
        chunking_config_version="chunk-v1", schema_version="slice-a")
    return assemble_identity(
        inputs=inputs, basis="intrinsic", uncertain_low=0.35, uncertain_high=0.65,
        calibration_sample=20, stage3_max_share=0.5)


def _judged(pid: str, band: Band, score: float) -> PieceJudgement:
    return PieceJudgement.judged(piece_id=pid, family_id=f"fam-{pid}", is_representative=True,
                                 stage_reached=Stage.STAGE_2, band=band, score=score)


def _order():  # noqa: ANN202
    judgements = [_judged("rel", Band.CONFIDENT_RELEVANT, 0.9),
                  _judged("dis", Band.CONFIDENT_DISCARD, 0.1)]
    families = {j.family_id: (j.piece_id,) for j in judgements}
    result = CascadeResult(
        judgements=tuple(judgements), families=families, unscored=(), stage3_share=0.5,
        over_stage3_floor=False, basis="intrinsic")
    return rank_cascade(result, _CFG)


def _record(store: SqlStore):  # noqa: ANN202
    return store.record_ranking(
        tenant="t", matter="m", actor="a", identity=_identity(), order=_order())


def test_labelling_leaves_the_ranked_order_and_the_fingerprint_unchanged(store: SqlStore) -> None:
    _record(store)
    before_order = [(r.piece_id, r.rank) for r in
                    store.read_ranked_order(tenant="t", matter="m", scopes={"w"})]
    before_fp = store.read_ranking(tenant="t", matter="m", scopes={"w"}).fingerprint

    store.assign_label(tenant="t", matter="m", actor="a", piece_id="rel", label="Contrats",
                       scopes={"w"})

    after_order = [(r.piece_id, r.rank) for r in
                   store.read_ranked_order(tenant="t", matter="m", scopes={"w"})]
    after_fp = store.read_ranking(tenant="t", matter="m", scopes={"w"}).fingerprint
    assert after_order == before_order == [("rel", 1), ("dis", 2)]  # a label is not a rank (FR-43)
    assert after_fp == before_fp                                    # no new version, same identity


def test_a_human_set_label_survives_re_ranking(store: SqlStore) -> None:
    _record(store)  # version 1
    store.assign_label(tenant="t", matter="m", actor="lawyer", piece_id="rel", label="Contrats",
                       scopes={"w"})
    v2 = _record(store)  # re-rank → a new ranking version
    assert v2.version_no == 2
    cur = store.read_current_label(tenant="t", matter="m", piece_id="rel", scopes={"w"})
    assert cur.label == "Contrats" and cur.source == "human"  # untouched by the re-rank (AD-23)


def test_coverage_reports_the_sm19_figures_over_the_ranking(store: SqlStore) -> None:
    _record(store)  # pièces rel + dis
    store.assign_label(tenant="t", matter="m", actor="a", piece_id="rel", label="Contrats",
                       scopes={"w"})  # dis stays unlabelled
    cov = store.read_label_coverage(tenant="t", matter="m", scopes={"w"})
    assert cov.total == 2 and cov.labelled == 1 and cov.unlabelled == 1
    assert cov.unlabelled_share == pytest.approx(0.5)
    assert cov.out_of_taxonomy == 0 and cov.without_label == 0  # exactly one label each (FR-40)


def test_coverage_counts_a_label_dropped_from_the_taxonomy_as_out_of_taxonomy(
    store: SqlStore,
) -> None:
    _record(store)
    store.assign_label(tenant="t", matter="m", actor="a", piece_id="rel", label="Contrats",
                       scopes={"w"})
    store.set_config("t", "admin", "taxonomy", ["Jurisprudence"])  # drop Contrats
    cov = store.read_label_coverage(tenant="t", matter="m", scopes={"w"})
    assert cov.labelled == 1 and cov.out_of_taxonomy == 1  # counted honestly, never remapped
