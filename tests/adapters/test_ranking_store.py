"""record_ranking — the owning use case for a ranking version (Story 4.3, FR-39/AD-23/AD-37/AD-22).

Atomic version + entries + one audit entry; a per-matter monotonic version_no; the conditional
commit
that refuses a ranking whose recorded case-theory version moved under it; scope-gated non-disclosing
reads; and the AC-2 reproduction (the same identity + corpus records the same order pièce for
pièce).
Deterministic SQLite, no network."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apx.adapters.store_postgres.models import AuditRecord, Base, RankedEntry
from apx.adapters.store_postgres.models import RankingVersion as RankingVersionRow
from apx.adapters.store_postgres.store import SqlStore, StaleRankingInput
from apx.core.app.ingest import IngestionResult
from apx.core.domain.cascade import Band, CascadeResult, PieceJudgement, Stage
from apx.core.domain.config import CascadeConfig
from apx.core.domain.ranking import RankingIdentityInputs, assemble_identity, rank_cascade


@pytest.fixture
def engine():  # noqa: ANN201
    e = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(e)
    return e


@pytest.fixture
def store(engine) -> SqlStore:  # noqa: ANN001
    s = SqlStore(sessionmaker(bind=engine, future=True))
    s.save(IngestionResult(), scope="w", actor="setup", matter="m", tenant="t", audit=False)
    return s


def _inputs(ct_id: str | None = None, **over: object) -> RankingIdentityInputs:
    base = dict(
        case_theory_version_id=ct_id, model_provider="mistral",
        model_endpoint="https://api.mistral.ai/v1", model_name="mistral-small-latest",
        prompt_version="cascade-question-v1", temperature=0.0, sampling={"top_p": 1.0},
        embedder_model_id="bge-m3", embedder_model_version="1.5",
        chunking_config_version="chunk-v1", schema_version="slice-a")
    base.update(over)
    return RankingIdentityInputs(**base)  # type: ignore[arg-type]


def _identity(basis: str, ct_id: str | None = None):  # noqa: ANN202
    return assemble_identity(
        inputs=_inputs(ct_id), basis=basis, uncertain_low=0.35, uncertain_high=0.65,
        calibration_sample=20, stage3_max_share=0.5)


_CFG = CascadeConfig(uncertain_low=0.35, uncertain_high=0.65, calibration_sample=20,
                     stage3_max_share=0.5)


def _order(judgements: list[PieceJudgement], *, unscored: tuple[str, ...] = ()):  # noqa: ANN202
    families: dict[str, list[str]] = {}
    for j in judgements:
        families.setdefault(j.family_id, []).append(j.piece_id)
    result = CascadeResult(
        judgements=tuple(judgements), families={k: tuple(v) for k, v in families.items()},
        unscored=unscored, stage3_share=0.5, over_stage3_floor=False, basis="case-theory")
    return rank_cascade(result, _CFG)


def _judged(pid: str, band: Band, score: float) -> PieceJudgement:
    return PieceJudgement.judged(piece_id=pid, family_id=f"fam-{pid}", is_representative=True,
                                 stage_reached=Stage.STAGE_2, band=band, score=score)


def _simple_order():  # noqa: ANN202
    return _order([_judged("rel", Band.CONFIDENT_RELEVANT, 0.9),
                   _judged("dis", Band.CONFIDENT_DISCARD, 0.1)])


def _actions(store: SqlStore) -> list[str]:
    with store._sf() as s:
        return list(s.scalars(
            select(AuditRecord.action).where(AuditRecord.tenant == "t").order_by(AuditRecord.seq)))


def test_record_ranking_persists_version_entries_and_one_audit_atomically(store: SqlStore) -> None:
    version = store.record_ranking(
        tenant="t", matter="m", actor="me.durand", identity=_identity("intrinsic"),
        order=_simple_order())
    assert version.version_no == 1 and len(version.version_id) == 64
    with store._sf() as s:
        assert s.scalar(select(func.count()).select_from(RankingVersionRow)) == 1
        assert s.scalar(select(func.count()).select_from(RankedEntry)) == 2
    assert _actions(store) == ["ranking_recorded"]  # one audit entry, atomic with the write
    view = store.read_ranking(tenant="t", matter="m", scopes={"w"})
    assert view.version_no == 1 and view.ranked_count == 2 and view.unscored_count == 0


def test_version_no_is_monotonic_per_matter(store: SqlStore) -> None:
    v1 = store.record_ranking(tenant="t", matter="m", actor="a", identity=_identity("intrinsic"),
                              order=_simple_order())
    v2 = store.record_ranking(tenant="t", matter="m", actor="a", identity=_identity("intrinsic"),
                              order=_simple_order())
    assert (v1.version_no, v2.version_no) == (1, 2)
    hist = store.list_ranking_versions(tenant="t", matter="m", scopes={"w"})
    assert [h.version_no for h in hist] == [1, 2]


def test_the_reproduction_records_the_same_order_piece_for_piece(store: SqlStore) -> None:
    order = _simple_order()  # a fixed identity over a fixed corpus → the SAME order (AC-2)
    store.record_ranking(tenant="t", matter="m", actor="a", identity=_identity("intrinsic"),
                         order=order)
    store.record_ranking(tenant="t", matter="m", actor="a", identity=_identity("intrinsic"),
                         order=order)
    first = store.read_ranked_order(tenant="t", matter="m", scopes={"w"}, version_no=1)
    second = store.read_ranked_order(tenant="t", matter="m", scopes={"w"}, version_no=2)
    assert [(r.piece_id, r.rank) for r in first] == [(r.piece_id, r.rank) for r in second]
    assert [(r.piece_id, r.rank) for r in first] == [("rel", 1), ("dis", 2)]


def test_the_conditional_commit_rejects_a_stale_case_theory_version(store: SqlStore) -> None:
    ct1 = store.append_case_theory_version(tenant="t", matter="m", actor="a", text="v1")
    identity = _identity("case-theory", ct_id=ct1.current.version_id)
    # a rewrite moves the latest case theory version under the ranking → the commit must refuse
    store.append_case_theory_version(tenant="t", matter="m", actor="a", text="v2")
    with pytest.raises(StaleRankingInput):
        store.record_ranking(tenant="t", matter="m", actor="a", identity=identity,
                             order=_simple_order())
    with store._sf() as s:  # nothing written
        assert s.scalar(select(func.count()).select_from(RankingVersionRow)) == 0


def test_the_conditional_commit_admits_the_current_case_theory_version(store: SqlStore) -> None:
    ct = store.append_case_theory_version(tenant="t", matter="m", actor="a", text="v1")
    version = store.record_ranking(
        tenant="t", matter="m", actor="a",
        identity=_identity("case-theory", ct_id=ct.current.version_id), order=_simple_order())
    assert version.version_no == 1  # recorded id == the matter's latest → commits


def test_an_intrinsic_ranking_is_stale_once_a_case_theory_appears(store: SqlStore) -> None:
    # the recorded input is "no case theory"; a case theory added under it changes the input (AD-23)
    identity = _identity("intrinsic", ct_id=None)
    store.append_case_theory_version(tenant="t", matter="m", actor="a", text="now there is one")
    with pytest.raises(StaleRankingInput):
        store.record_ranking(tenant="t", matter="m", actor="a", identity=identity,
                             order=_simple_order())


def test_an_intrinsic_ranking_commits_over_a_WITHDRAWN_case_theory(store: SqlStore) -> None:
    # a WITHDRAWN case theory is operatively absent (present=False), so the operative id is None ==
    # the intrinsic identity's recorded None → the ranking must COMMIT. (Regression: comparing the
    # raw latest-row id, which is the withdrawal row's non-None id, would refuse EVERY ranking on a
    # withdrawn matter forever.)
    store.append_case_theory_version(tenant="t", matter="m", actor="a", text="v1")
    store.append_case_theory_version(tenant="t", matter="m", actor="a", text=None)  # withdrawal
    version = store.record_ranking(
        tenant="t", matter="m", actor="a", identity=_identity("intrinsic", ct_id=None),
        order=_simple_order())
    assert version.version_no == 1  # committed, not falsely stale
    assert store.read_ranking(tenant="t", matter="m", scopes={"w"}).version_no == 1


def test_an_unknown_matter_raises(store: SqlStore) -> None:
    with pytest.raises(ValueError, match="unknown matter"):
        store.record_ranking(tenant="t", matter="ghost", actor="a", identity=_identity("intrinsic"),
                             order=_simple_order())


def test_the_unscored_tail_carries_no_rank_and_is_returned_separately(store: SqlStore) -> None:
    order = _order(
        [_judged("ok", Band.UNCERTAIN, 0.5),
         PieceJudgement.unscored(piece_id="bad", family_id="fam-bad", is_representative=True,
                                 failure_reason="RuntimeError")],
        unscored=("bad",))
    store.record_ranking(tenant="t", matter="m", actor="a", identity=_identity("intrinsic"),
                         order=order)
    rows = store.read_ranked_order(tenant="t", matter="m", scopes={"w"})
    assert [(r.piece_id, r.rank) for r in rows] == [("ok", 1), ("bad", None)]  # unscored tail
    view = store.read_ranking(tenant="t", matter="m", scopes={"w"})
    assert view.ranked_count == 1 and view.unscored_count == 1


def test_reads_are_scope_gated_and_non_disclosing(store: SqlStore) -> None:
    store.record_ranking(tenant="t", matter="m", actor="a", identity=_identity("intrinsic"),
                         order=_simple_order())
    # a scope not holding the matter's wall is indistinguishable from an absent matter (FR-14)
    assert store.read_ranking(tenant="t", matter="m", scopes={"other"}) is None
    assert store.list_ranking_versions(tenant="t", matter="m", scopes={"other"}) is None
    assert store.read_ranked_order(tenant="t", matter="m", scopes={"other"}) is None
    assert store.read_ranking(tenant="t", matter="absent", scopes={"w"}) is None
    # held but no such version → [] (distinguishable from out-of-scope None)
    assert store.read_ranked_order(tenant="t", matter="m", scopes={"w"}, version_no=99) == []


def test_the_version_no_unique_constraint_forbids_a_silent_overwrite(store: SqlStore) -> None:
    store.record_ranking(tenant="t", matter="m", actor="a", identity=_identity("intrinsic"),
                         order=_simple_order())
    # a second row at the same (tenant, matter, version_no) is refused by the DB — never an
    # overwrite
    with pytest.raises(IntegrityError), store._sf() as s, s.begin():
        s.add(RankingVersionRow(
            id="dup", tenant="t", matter="m", version_no=1, fingerprint="x", basis="intrinsic",
            identity_json="{}", case_theory_version_id=None, stage3_share=0.0,
            created_at=store_now()))


def store_now():  # noqa: ANN201
    from datetime import UTC, datetime
    return datetime.now(UTC)


def test_the_derived_confidence_is_persisted_and_read_back(store: SqlStore) -> None:
    # Story 4.4: a confident-relevant pièce carries a derived confidence; an unscored one is NULL
    # (not derived, AD-19). The round-trip preserves the NULL-vs-value distinction.
    order = _order(
        [_judged("rel", Band.CONFIDENT_RELEVANT, 0.9),
         PieceJudgement.unscored(piece_id="bad", family_id="fam-bad", is_representative=True,
                                 failure_reason="RuntimeError")],
        unscored=("bad",))
    store.record_ranking(tenant="t", matter="m", actor="a", identity=_identity("intrinsic"),
                         order=order)
    rows = {r.piece_id: r for r in store.read_ranked_order(tenant="t", matter="m", scopes={"w"})}
    assert rows["rel"].confidence is not None and 0.0 <= rows["rel"].confidence <= 1.0
    assert "score-margin" in rows["rel"].confidence_signals
    assert rows["bad"].confidence is None and rows["bad"].confidence_signals is None  # not derived
