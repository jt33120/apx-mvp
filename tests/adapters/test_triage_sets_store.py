"""read_triage_sets + the FR-13 proof + read_version_retention (Story 4.7, FR-16/FR-43/FR-13).

The retained/discarded sets are DERIVED at read time from the persisted order + a line + pins — not
stored. A discarded pièce is STILL found by exhaustive search (discard is not deletion, AD-7). The
view names its ranking version. The retained-versions bound is configuration. On SQLite."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apx.adapters.store_postgres.models import Base, MatterScope, Piece
from apx.adapters.store_postgres.store import SqlStore
from apx.core.app.ingest import IngestionResult
from apx.core.domain.cascade import Band, CascadeResult, PieceJudgement, Stage
from apx.core.domain.config import CascadeConfig
from apx.core.domain.normalization import normalize
from apx.core.domain.ranking import RankingIdentityInputs, assemble_identity, rank_cascade
from apx.core.domain.triage_sets import Line, Pin, PinSide

_CFG = CascadeConfig(uncertain_low=0.35, uncertain_high=0.65, calibration_sample=20,
                     stage3_max_share=0.5)


def _sf():  # noqa: ANN202
    e = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(e)
    return sessionmaker(bind=e, future=True)


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


def _order(pairs, unscored=()):  # noqa: ANN001,ANN202
    judgements = [_judged(pid, band, score) for pid, band, score in pairs]
    families = {j.family_id: (j.piece_id,) for j in judgements}
    result = CascadeResult(
        judgements=tuple(judgements), families=families, unscored=unscored, stage3_share=0.5,
        over_stage3_floor=False, basis="intrinsic")
    return rank_cascade(result, _CFG)


def _store_with_ranking():  # noqa: ANN202
    """A store with matter 'm' (scope 'w') and a recorded ranking: rel(rank1), dis(rank2)."""
    store = SqlStore(_sf())
    store.save(IngestionResult(), scope="w", actor="setup", matter="m", tenant="t", audit=False)
    store.record_ranking(
        tenant="t", matter="m", actor="a", identity=_identity(),
        order=_order([("rel", Band.CONFIDENT_RELEVANT, 0.9), ("dis", Band.CONFIDENT_DISCARD, 0.1)]))
    return store


def test_the_sets_are_derived_over_the_order_and_name_their_version() -> None:
    store = _store_with_ranking()
    sets = store.read_triage_sets(tenant="t", matter="m", scopes={"w"}, line=Line("rel"))
    assert sets.retained == ("rel",) and sets.discarded == ("dis",)
    assert sets.line_placed is True and len(sets.version_id) == 64  # names its ranking version


def test_no_line_means_no_split() -> None:
    store = _store_with_ranking()
    sets = store.read_triage_sets(tenant="t", matter="m", scopes={"w"})  # line defaults to None
    assert sets.retained == () and sets.discarded == () and sets.line_placed is False


def test_a_pin_moves_exactly_one_piece_the_count_is_reported() -> None:
    store = _store_with_ranking()
    sets = store.read_triage_sets(
        tenant="t", matter="m", scopes={"w"}, line=Line("rel"),
        pins=(Pin("dis", PinSide.RETAIN),))  # pin the discarded pièce back in
    assert sets.retained == ("rel", "dis") and sets.discarded == ()
    assert sets.pins_in_force == 1


def test_the_read_is_scope_gated_and_non_disclosing() -> None:
    store = _store_with_ranking()
    denied = store.read_triage_sets(tenant="t", matter="m", scopes={"other"}, line=Line("rel"))
    assert denied is None
    # a matter with no ranking is indistinguishable from absent (None)
    store.save(IngestionResult(), scope="w", actor="s", matter="empty", tenant="t", audit=False)
    assert store.read_triage_sets(tenant="t", matter="empty", scopes={"w"}) is None


def test_each_version_derives_sets_that_name_that_version() -> None:
    store = _store_with_ranking()
    store.record_ranking(  # a second version (re-rank) — same order
        tenant="t", matter="m", actor="a", identity=_identity(),
        order=_order([("rel", Band.CONFIDENT_RELEVANT, 0.9), ("dis", Band.CONFIDENT_DISCARD, 0.1)]))
    v1 = store.read_triage_sets(
        tenant="t", matter="m", scopes={"w"}, line=Line("rel"), version_no=1)
    v2 = store.read_triage_sets(
        tenant="t", matter="m", scopes={"w"}, line=Line("rel"), version_no=2)
    assert v1.version_id != v2.version_id  # each set names the version it was computed against


# ── FR-13: discard is not deletion — a discarded pièce is still found by exhaustive search ──────
def _seed_piece(session, matter, pid, full_text):  # noqa: ANN001,ANN202
    session.add(Piece(
        id=pid, tenant="t", matter=matter, content_hash=pid, text_key=pid,
        provenance_path=f"{pid}.txt", extraction_method="text", extractor_version="v1",
        schema_version="v1", ingestion_timestamp=datetime.now(UTC), piece_date=None,
        piece_date_status="undetermined", full_text=full_text, text_identity=pid,
        text_version="v1"))
    session.merge(MatterScope(tenant="t", matter=matter, scope="w", submitted_pieces=1))


def test_a_discarded_piece_is_still_returned_by_exhaustive_search() -> None:
    sf = _sf()
    store = SqlStore(sf)
    with sf() as s:
        _seed_piece(s, "m", "keep", "un contrat de bail commercial")
        _seed_piece(s, "m", "drop", "une facture émise par l'État")  # searchable via "État"
        s.commit()
    store.record_ranking(
        tenant="t", matter="m", actor="a", identity=_identity(),
        order=_order([("keep", Band.CONFIDENT_RELEVANT, 0.9),
                      ("drop", Band.CONFIDENT_DISCARD, 0.1)]))
    sets = store.read_triage_sets(tenant="t", matter="m", scopes={"w"}, line=Line("keep"))
    assert sets.discarded == ("drop",)  # 'drop' is in the discarded set
    # FR-13: discarding is a derived view, not a deletion — the pièce is STILL in the corpus/search
    found = store.exact_search(tenant="t", scopes={"w"}, normalized_query=normalize("etat"))
    assert "drop" in {r.piece_id for r in found.results}


# ── the retained-versions bound is configuration; the read retires nothing ─────────────────────
def test_version_retention_reports_the_count_against_the_configured_bound() -> None:
    store = _store_with_ranking()  # version 1 recorded
    store.set_config("t", "admin", "retained_ranking_versions_max", 1)
    store.record_ranking(  # a 2nd version → over the bound of 1
        tenant="t", matter="m", actor="a", identity=_identity(),
        order=_order([("rel", Band.CONFIDENT_RELEVANT, 0.9)]))
    ret = store.read_version_retention(tenant="t", matter="m", scopes={"w"})
    assert ret.total == 2 and ret.bound == 1 and ret.over_bound == 1
    # nothing is deleted — both versions remain readable (AD-7)
    assert len(store.list_ranking_versions(tenant="t", matter="m", scopes={"w"})) == 2


def test_version_retention_is_scope_gated() -> None:
    store = _store_with_ranking()
    assert store.read_version_retention(tenant="t", matter="m", scopes={"other"}) is None
