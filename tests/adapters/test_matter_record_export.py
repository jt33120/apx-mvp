"""The *matter* record as an exported document (Story 5.7, FR-26 / FR-11 / FR-53 / AD-35 / AD-43).

Against the real SQLite store. The document carries the eight sections FR-26 enumerates; the tier
is chosen before production and the numbers-only document is *built without* the content rather
than stripped of it; the cover states the wall, the per-chain continuity verdict, an unacknowledged
truncation and the degraded count; producing it is a recorded egress act and a refusal writes
nothing; and the two sections Story 5.8 owns say so instead of printing a zero.

The self-containment assertion — a reader with the document and no access to the stores recomputes
every number in it — lives in ``tests/probe/test_export_self_contained.py``, in its own process.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apx.adapters.store_postgres.models import AuditRecord, Base, TruncationMarker
from apx.adapters.store_postgres.store import ScopeDenied, SqlStore
from apx.core.app.ingest import IngestedFailure, IngestionResult
from apx.core.domain import audit as AUDIT
from apx.core.domain.cascade import Band, CascadeResult, PieceJudgement, Stage
from apx.core.domain.config import CascadeConfig
from apx.core.domain.failures import ErrorClass
from apx.core.domain.matter_record import Tier
from apx.core.domain.ranking import RankingIdentityInputs, assemble_identity, rank_cascade
from apx.core.domain.triage_sets import PinSide

TENANT, MATTER, WALL = "t", "Vinci / Sogea", "contentieux"
THEORY = "Le retard est imputable au maître d'ouvrage."
PIN_REASON = "aveu implicite au §4 — décisif malgré le rang"
PRICE = "400 pièces de plus à lire ; part estimée ≈3 % → ≈0,4 %"
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


@pytest.fixture
def store() -> SqlStore:
    """A matter with a theory, a ranking, a placed and moved line, a pin, and an override."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    s = SqlStore(sessionmaker(bind=engine, future=True))
    s.save(
        IngestionResult(failures=[IngestedFailure(
            filename="scelle.pdf", submitted_path="/d/scelle.pdf", matter=MATTER, tenant=TENANT,
            error_class=ErrorClass.PASSWORD_PROTECTED, detail="x", custodian="Me Martin")]),
        actor="Me Dupont", scope=WALL, matter=MATTER, tenant=TENANT)
    s.record_ranking(
        tenant=TENANT, matter=MATTER, actor="Claire Fontaine", identity=_identity(),
        order=_order())
    # after the ranking: the identity above records `case_theory_version_id=None`, and recording a
    # ranking against a theory that moved under it is refused (AD-23) — correctly
    s.append_case_theory_version(
        tenant=TENANT, matter=MATTER, actor="Claire Fontaine", text=THEORY)
    placed = s.place_line(
        tenant=TENANT, matter=MATTER, actor="Claire Fontaine", scopes={WALL})
    s.move_line(
        tenant=TENANT, matter=MATTER, actor="Claire Fontaine", scopes={WALL},
        last_retained_piece_id="c", expected_seq=placed.seq, priced_statement=PRICE)
    s.pin_piece(tenant=TENANT, matter=MATTER, actor="Claire Fontaine", scopes={WALL},
                piece_id="d", side=PinSide.RETAIN, reason=PIN_REASON)
    entry = s.register(MATTER, TENANT, {WALL})[0].id
    s.override_register_entry(
        entry_id=entry, tenant=TENANT, actor="Claire Fontaine", scopes={WALL},
        reason="scellé jamais ouvert, mot de passe perdu chez le client")
    return s


def _export(store: SqlStore, tier: Tier = Tier.NUMBERS_ONLY):  # noqa: ANN202
    return store.export_matter_record(
        tenant=TENANT, matter=MATTER, actor="Claire Fontaine", scopes={WALL}, tier=tier)


# ── AC-5: the eight sections ──────────────────────────────────────────────────────────────────
def test_the_document_carries_every_section_fr26_enumerates(store: SqlStore) -> None:
    r = _export(store)
    assert len(r.denominator) == 7                        # the seven named counts (AD-38)
    assert [c.version_no for c in r.case_theory] == [1]
    assert [h.seq for h in r.line_history] == [1, 2]      # the HISTORY, not the current position
    assert [(p.piece_id, p.action) for p in r.pins] == [("d", "retain")]
    assert r.overrides_total == 2                         # the pin + the register override
    # §7 and §8 are real sections as of Story 5.8, so nothing is declared pending and both print
    # counts. Their emptiness here is the FIRM's — nobody validated anything on this matter.
    assert r.pending == ()
    assert r.validation_summary is not None and r.validation_summary.in_force == 0


def test_the_line_history_carries_its_author_and_the_price_it_was_shown(store: SqlStore) -> None:
    r = _export(store)
    assert r.line_history[0].priced_statement is None      # a first placement was not a move
    assert r.line_history[1].priced_statement == PRICE
    assert all(h.placed_by == "Claire Fontaine" for h in r.line_history)


def test_the_override_count_is_over_the_record_not_the_printed_list(store: SqlStore) -> None:
    # FR-25: a tier or a filter can shorten the list; neither changes how many the matter holds
    r = _export(store)
    assert r.overrides_total == 2
    assert all(o.ground and o.ground_fr for o in r.overrides)
    assert all(o.action_fr != o.action for o in r.overrides)   # said in the lawyer's language


def test_nothing_is_pending_and_the_validation_section_prints_real_counts(
    store: SqlStore,
) -> None:
    """Story 5.8 built both sections that named it, so nothing is declared pending.

    The rule they enforced still holds and is now enforced from the other side: while an act did
    not exist, §7 said so in words; now that it does, §7 prints a **0** — and that 0 finally means
    what a *bâtonnier* would take it to mean, a finding about the **firm**. The invariant is
    checked structurally in both directions by ``a_pending_section_is_not_a_zero``."""
    r = _export(store)
    assert r.pending == ()
    assert r.validation_summary is not None
    assert r.validation_summary.in_force == 0
    assert r.validation_summary.never_validated == len(_PAIRS)
    assert r.accepted_values == 0


# ── AC-6: the tier, applied by omission ───────────────────────────────────────────────────────
def test_numbers_only_carries_no_client_content(store: SqlStore) -> None:
    r = _export(store, Tier.NUMBERS_ONLY)
    assert all(c.text is None for c in r.case_theory)      # the firm's legal strategy
    assert all(p.reason is None for p in r.pins)           # an override reason, written by a lawyer
    assert all(o.reason is None for o in r.overrides)


def test_the_full_tier_carries_it_and_the_numbers_only_document_never_contains_it(
    store: SqlStore,
) -> None:
    numbers = repr(_export(store, Tier.NUMBERS_ONLY))
    full = repr(_export(store, Tier.FULL))
    for secret in (THEORY, PIN_REASON):
        assert secret in full                               # the full tier is the one that carries
        assert secret not in numbers                        # and numbers-only never does


def test_both_tiers_carry_the_counts_and_the_positions(store: SqlStore) -> None:
    numbers, full = _export(store, Tier.NUMBERS_ONLY), _export(store, Tier.FULL)
    assert numbers.denominator == full.denominator
    assert numbers.line_history == full.line_history       # a projection over counts, not content
    assert numbers.overrides_total == full.overrides_total


def test_the_tier_has_no_default_at_the_boundary(store: SqlStore) -> None:
    # a default on the boundary that produces client content is the wrong place to be forgiving
    with pytest.raises(TypeError):
        store.export_matter_record(                        # type: ignore[call-arg]
            tenant=TENANT, matter=MATTER, actor="Claire Fontaine", scopes={WALL})


# ── AC-9: the cover declares the document's limits ────────────────────────────────────────────
def test_the_cover_states_the_wall_it_was_produced_under(store: SqlStore) -> None:
    cover = _export(store).cover
    assert cover.scope == WALL and cover.matter == MATTER
    assert cover.produced_by == "Claire Fontaine" and cover.produced_at


def test_the_continuity_verdict_is_per_chain_and_says_which_one_the_reader_can_recompute(
    store: SqlStore,
) -> None:
    # AD-43: one boolean over both would claim a property of bytes the reader does not hold
    chains = _export(store).cover.chains
    own = next(c for c in chains if c.chain_scope == MATTER)
    assert own.verified and own.recomputable_from_this_document
    assert own.label_fr == f"affaire « {MATTER} »"
    for other in (c for c in chains if c.chain_scope != MATTER):
        assert not other.recomputable_from_this_document


def test_an_unacknowledged_truncation_is_named_on_the_face(store: SqlStore) -> None:
    with store._sf() as s, s.begin():
        s.add(TruncationMarker(
            tenant=TENANT, detected_at=datetime.now(UTC), journal_seq=9, live_seq=4,
            chains=f"{MATTER}:9->4", entries_lost=5))
    cover = _export(store).cover
    assert cover.truncation_unacknowledged and "5" in (cover.truncation_note or "")


def test_a_clean_matter_is_not_degraded_and_says_nothing_about_it(store: SqlStore) -> None:
    cover = _export(store).cover
    assert cover.degraded_extracts == 0 and not cover.degraded
    assert cover.degraded_sentence_fr is None


# ── AC-7: the recorded egress act ─────────────────────────────────────────────────────────────
def test_producing_the_document_is_a_recorded_act_on_the_matters_own_chain(
    store: SqlStore,
) -> None:
    _export(store, Tier.FULL)
    with store._sf() as s:
        entry = s.scalars(select(AuditRecord).where(
            AuditRecord.action == AUDIT.ACT_EXPORT_MATTER_RECORD)).one()
    assert entry.chain_scope == MATTER                     # where a bâtonnier can recompute it
    assert entry.matter == MATTER and entry.actor == "Claire Fontaine"
    assert "tier=full" in entry.detail and "scopes=1" in entry.detail


def test_a_refused_export_is_not_an_export(store: SqlStore) -> None:
    with store._sf() as s:
        before = s.scalar(select(func.count()).select_from(AuditRecord))
    with pytest.raises(ScopeDenied):
        store.export_matter_record(
            tenant=TENANT, matter=MATTER, actor="Me Martin", scopes={"other-wall"},
            tier=Tier.FULL)
    with store._sf() as s:
        assert s.scalar(select(func.count()).select_from(AuditRecord)) == before


def test_the_export_itself_appears_in_the_next_document(store: SqlStore) -> None:
    # the act that moves material out of the firm is part of the record it moved: a second document
    # produced later carries the first export's entry, so a reader can see that material left
    first = _export(store, Tier.FULL)
    trail = store.read_audit(MATTER, TENANT, {WALL})
    exports = [e for e in trail.entries if e.action == AUDIT.ACT_EXPORT_MATTER_RECORD]
    assert len(exports) == 1 and "tier=full" in exports[0].detail

    second = _export(store, Tier.NUMBERS_ONLY)
    own_first = next(c for c in first.cover.chains if c.chain_scope == MATTER)
    own_second = next(c for c in second.cover.chains if c.chain_scope == MATTER)
    assert own_second.entries > own_first.entries      # the first export is now in the record
