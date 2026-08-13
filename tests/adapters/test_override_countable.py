"""Overrides are countable and filterable, SEPARATELY from ordinary modifications
(Story 5.6, FR-25).

FR-25's fourth testable consequence, against the real store: a matter that has been ranked, lined,
pinned twice, un-pinned once and had a register entry overridden reports exactly the overrides —
pins included, because a pin's FR-24 class is ``pin`` and counting by class would report
one. The count is taken over the whole trail and does not change when the filter is
applied, so a filtered read can never present a smaller record as the whole one.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apx.adapters.store_postgres.models import AuditRecord, Base, TruncationMarker
from apx.adapters.store_postgres.store import SqlStore
from apx.core.app.ingest import IngestedFailure, IngestionResult
from apx.core.domain import audit as AUDIT
from apx.core.domain.cascade import Band, CascadeResult, PieceJudgement, Stage
from apx.core.domain.config import CascadeConfig
from apx.core.domain.failures import ErrorClass
from apx.core.domain.override import (
    GROUND_CONTRADICTS_MACHINE,
    GROUND_REGISTER_EXIT,
    reason_from_detail,
)
from apx.core.domain.ranking import RankingIdentityInputs, assemble_identity, rank_cascade
from apx.core.domain.triage_sets import PinSide

TENANT, MATTER, WALL = "t", "m", "w"
_CFG = CascadeConfig(uncertain_low=0.35, uncertain_high=0.65, calibration_sample=20,
                     stage3_max_share=0.5)
_PAIRS = [("a", Band.CONFIDENT_RELEVANT, 0.9), ("b", Band.CONFIDENT_RELEVANT, 0.7),
          ("c", Band.CONFIDENT_DISCARD, 0.2), ("d", Band.CONFIDENT_DISCARD, 0.1)]


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


def _order():  # noqa: ANN202
    judgements = [
        PieceJudgement.judged(piece_id=pid, family_id=f"fam-{pid}", is_representative=True,
                              stage_reached=Stage.STAGE_2, band=band, score=score)
        for pid, band, score in _PAIRS
    ]
    result = CascadeResult(
        judgements=tuple(judgements), families={j.family_id: (j.piece_id,) for j in judgements},
        unscored=(), stage3_share=0.5, over_stage3_floor=False, basis="intrinsic")
    return rank_cascade(result, _CFG)


def _busy_matter() -> tuple[SqlStore, str]:
    """A matter with two pins (overrides), a register override, and several ordinary acts."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    store = SqlStore(sessionmaker(bind=engine, future=True))
    store.save(
        IngestionResult(failures=[IngestedFailure(
            filename="a.pdf", submitted_path="/a.pdf", matter=MATTER, tenant=TENANT,
            error_class=ErrorClass.CORRUPT_FILE, detail="x", custodian="Dupont")]),
        actor="Me Dupont", scope=WALL, matter=MATTER, tenant=TENANT)
    store.record_ranking(
        tenant=TENANT, matter=MATTER, actor="a", identity=_identity(), order=_order())
    store.place_line(tenant=TENANT, matter=MATTER, actor="a", scopes={WALL})  # ordinary act
    # two OVERRIDES on the matter chain, whose FR-24 class is `pin`
    store.pin_piece(tenant=TENANT, matter=MATTER, actor="claire", scopes={WALL}, piece_id="c",
                    side=PinSide.RETAIN, reason="aveu au §4 — décisif malgré le rang")
    store.pin_piece(tenant=TENANT, matter=MATTER, actor="claire", scopes={WALL}, piece_id="a",
                    side=PinSide.DISCARD, reason="hors périmètre, malgré le score")
    # an ordinary modification, NOT an override: lifting a pin puts the pièce back where the tool
    # had it (no reason owed)
    store.remove_pin(tenant=TENANT, matter=MATTER, actor="claire", scopes={WALL}, piece_id="a")
    entry_id = store.register(MATTER, TENANT, {WALL})[0].id
    store.override_register_entry(
        entry_id=entry_id, tenant=TENANT, actor="Me Dupont", scopes={WALL},
        reason="fichier corrompu à la source, jamais lisible")
    return store, entry_id


def test_the_count_includes_the_pins_although_their_class_is_pin() -> None:
    store, _ = _busy_matter()
    trail = store.read_audit(MATTER, TENANT, {WALL})
    assert trail.overrides == 3                                  # 2 pins + 1 register override
    by_class = [e for e in trail.entries
                if AUDIT.ACTS[e.action].act_class == AUDIT.CLASS_OVERRIDE]
    assert len(by_class) == 1                                    # what the wrong count would say
    assert trail.entries_total > trail.overrides                 # ordinary acts are there too


def test_every_counted_override_names_its_ground() -> None:
    store, _ = _busy_matter()
    trail = store.read_audit(MATTER, TENANT, {WALL})
    grounds = sorted(e.override_ground for e in trail.entries if e.override)
    assert grounds == sorted(
        [GROUND_CONTRADICTS_MACHINE, GROUND_CONTRADICTS_MACHINE, GROUND_REGISTER_EXIT])


def test_an_ordinary_modification_is_never_counted_as_an_override() -> None:
    store, _ = _busy_matter()
    trail = store.read_audit(MATTER, TENANT, {WALL})
    ordinary = [e for e in trail.entries if not e.override]
    assert any(e.action == AUDIT.ACT_PIN_REMOVED for e in ordinary)   # lifting a pin
    assert any(e.action == AUDIT.ACT_LINE_PLACED for e in ordinary)   # placing the line
    for e in ordinary:
        assert e.override_ground is None


def test_the_filter_narrows_the_entries_and_never_the_count() -> None:
    store, _ = _busy_matter()
    whole = store.read_audit(MATTER, TENANT, {WALL})
    filtered = store.read_audit(MATTER, TENANT, {WALL}, overrides_only=True)
    assert len(filtered.entries) == 3
    assert all(e.override for e in filtered.entries)
    # the counts describe the RECORD, not the page: a filtered read says how much it is not showing
    assert filtered.overrides == whole.overrides == 3
    assert filtered.entries_total == whole.entries_total == len(whole.entries)
    assert filtered.verified == whole.verified
    assert filtered.slices == whole.slices


def test_a_matter_with_no_override_reports_zero_rather_than_nothing() -> None:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    store = SqlStore(sessionmaker(bind=engine, future=True))
    store.save(IngestionResult(), actor="Me Dupont", scope=WALL, matter=MATTER, tenant=TENANT)
    trail = store.read_audit(MATTER, TENANT, {WALL})
    assert trail.overrides == 0 and trail.entries_total == len(trail.entries) > 0
    assert store.read_audit(MATTER, TENANT, {WALL}, overrides_only=True).entries == []


def test_every_counted_override_carries_its_reason_in_the_record() -> None:
    store, _ = _busy_matter()
    trail = store.read_audit(MATTER, TENANT, {WALL}, overrides_only=True)
    for e in trail.entries:
        reason = reason_from_detail(e.detail)
        assert reason is not None and reason.strip(), e.action


def test_the_truncation_override_carries_its_reason_into_the_record() -> None:
    # FR-25 requires the reason in the AUDIT RECORD. Before Story 5.6 this path put it on the
    # truncation marker row and nowhere else — a mutable row outside the chain.
    #
    # Read from the record directly, not through a matter's trail: clearing a truncation is a
    # TENANT-wide act with no matter, so it belongs to no matter's history and must not appear in
    # one. That is the AD-43 tenant chain doing its job, not an omission.
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    store = SqlStore(sessionmaker(bind=engine, future=True))
    with store._sf() as s, s.begin():
        s.add(TruncationMarker(
            tenant=TENANT, detected_at=datetime.now(UTC), journal_seq=9, live_seq=4,
            chains="m:9->4", entries_lost=5))
    reason = "restauration vérifiée pièce à pièce, perte acceptée par le bâtonnier"
    store.clear_truncation(TENANT, "patron", reason)
    with store._sf() as s:
        entry = s.scalars(select(AuditRecord).where(
            AuditRecord.action == AUDIT.ACT_TRUNCATION_OVERRIDE)).one()
    assert AUDIT.is_override(entry.action)
    assert reason_from_detail(entry.detail) == reason
    assert "journal_seq=9" in entry.detail and "live_seq=4" in entry.detail
