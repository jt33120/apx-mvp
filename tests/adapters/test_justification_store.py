"""record_justification / read_justification / reject / restore (Story 4.6, FR-41/FR-18/FR-11): a
per-pièce justification derived from NAMED evidence, verified by exact containment at SHOW time (an
extract that no longer resolves is shown unverified, never ordinary), carrying the derived
confidence; a rejection is append-only, reversible, audited, and version-independent. On SQLite with
a fake embedder at the port boundary (the real model is never loaded)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apx.adapters.store_postgres.admission import admit
from apx.adapters.store_postgres.models import (
    AuditRecord,
    Base,
    Chunk,
    JustificationRejection,
    Piece,
    PieceJustification,
)
from apx.adapters.store_postgres.store import ScopeDenied, SqlStore, StaleJustification
from apx.core.app.ingest import SCHEMA_VERSION, IngestedPiece, IngestionResult
from apx.core.domain.cascade import Band, CascadeResult, IntrinsicSignal, PieceJudgement, Stage
from apx.core.domain.config import CascadeConfig
from apx.core.domain.identity import content_hash, piece_id
from apx.core.domain.justification import EvidenceExtract, JustificationBasis
from apx.core.domain.ranking import RankingIdentityInputs, assemble_identity, rank_cascade
from tests.embedding_fakes import FakeEmbedder

TENANT, WALL, MATTER = "t", "w", "m"
_LONG = "Le contrat de bail commercial est nul et de nul effet. La cour le confirme enfin. " * 30
_PID = piece_id(TENANT, content_hash(_LONG.encode()), MATTER)
_QUOTE = "Le contrat de bail commercial est nul"  # a real substring of the first passage
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


def _piece() -> IngestedPiece:
    ch = content_hash(_LONG.encode())
    return IngestedPiece(
        id=_PID, matter=MATTER, tenant=TENANT, content_hash=ch, text_key=ch,
        provenance_path="c.txt", custodian="Dupont", extraction_method="text",
        extractor_version="v", schema_version=SCHEMA_VERSION,
        ingestion_timestamp=datetime.now(UTC), full_text=_LONG, text_version="tv")


def _order(chunk_id: str):  # noqa: ANN202
    # a stage-3 judged pièce whose retained extract is the real chunk (so a justification's evidence
    # is exactly what the judgement used, and a confidence is derived — Story 4.4).
    j = PieceJudgement.judged(
        piece_id=_PID, family_id="fam", is_representative=True, stage_reached=Stage.STAGE_3,
        band=Band.CONFIDENT_RELEVANT, score=0.9, label="relevant",
        retained_extract_chunk_ids=(chunk_id,))
    result = CascadeResult(
        judgements=(j,), families={"fam": (_PID,)}, unscored=(), stage3_share=1.0,
        over_stage3_floor=False, basis="intrinsic")
    return rank_cascade(result, _CFG)


def _setup(store: SqlStore) -> str:
    """Admit the real pièce (→ chunks), record a ranking over it, return its first chunk id."""
    admit(store, FakeEmbedder(), IngestionResult(pieces=[_piece()]),
          scope=WALL, actor="a", matter=MATTER, tenant=TENANT, audit=False)
    with store._sf() as s:
        chunk_id = s.scalars(select(Chunk.chunk_id).order_by(Chunk.position)).first()
    store.record_ranking(
        tenant=TENANT, matter=MATTER, actor="a", identity=_identity(), order=_order(chunk_id))
    return chunk_id


def _record(store: SqlStore, chunk_id: str, quote: str = _QUOTE) -> None:
    store.record_justification(
        tenant=TENANT, matter=MATTER, actor="claire", piece_id=_PID,
        sentence="La cour confirme la nullité du bail.",
        basis=JustificationBasis.intrinsic((IntrinsicSignal.DOCUMENT_TYPE,)),
        evidence=(EvidenceExtract(chunk_id, quote),), source_language="fr", scopes={WALL})


# ── AC-1 / AC-2 — the justification carries confidence + named evidence, verified at show time ────
def test_a_recorded_justification_reads_back_verified_with_its_confidence() -> None:
    store = SqlStore(_sf())
    chunk_id = _setup(store)
    _record(store, chunk_id)
    vj = store.read_justification(tenant=TENANT, matter=MATTER, scopes={WALL}, piece_id=_PID)
    assert vj is not None
    assert vj.justification.confidence is not None            # AC-1 — the DERIVED confidence (4.4)
    assert vj.justification.sentence == "La cour confirme la nullité du bail."
    assert vj.justification.source_language == "fr"
    assert [e.chunk_id for e in vj.justification.evidence] == [chunk_id]  # named evidence
    assert vj.extracts[0].verified and not vj.is_unverified  # AC-2 — containment-verified at show
    assert not vj.rejected


def test_an_extract_that_no_longer_contains_is_shown_unverified_never_ordinary() -> None:
    store = SqlStore(_sf())
    chunk_id = _setup(store)
    _record(store, chunk_id, quote="clause jamais écrite dans cette source")
    vj = store.read_justification(tenant=TENANT, matter=MATTER, scopes={WALL}, piece_id=_PID)
    assert vj is not None
    assert not vj.extracts[0].verified          # the stored quote is not in the resolved passage
    assert vj.is_unverified                      # so the whole justification is unverified (FR-41)


def test_an_extract_whose_source_changed_under_it_is_unverified() -> None:
    store = SqlStore(_sf())
    chunk_id = _setup(store)
    _record(store, chunk_id)
    with store._sf() as s, s.begin():  # a re-extraction bumps the pièce's text_version (AD-40)
        s.get(Piece, _PID).text_version = "tv2"
    vj = store.read_justification(tenant=TENANT, matter=MATTER, scopes={WALL}, piece_id=_PID)
    assert vj is not None and vj.is_unverified and not vj.extracts[0].verified


# ── AC-1 — write-once per (version, pièce); recorded as an audit act ──────────────────────────────
def test_recording_is_write_once_and_audited() -> None:
    store = SqlStore(_sf())
    chunk_id = _setup(store)
    _record(store, chunk_id)
    with pytest.raises(ValueError, match="already recorded"):
        _record(store, chunk_id)
    with store._sf() as s:
        assert s.scalar(select(func.count()).select_from(PieceJustification)) == 1
        assert s.scalar(select(func.count()).select_from(AuditRecord).where(
            AuditRecord.action == "justification_recorded")) == 1


def _assert_nothing_written(store: SqlStore) -> None:
    with store._sf() as s:  # no row AND no audit entry — the refusal is total (AD-22)
        assert s.scalar(select(func.count()).select_from(PieceJustification)) == 0
        assert s.scalar(select(func.count()).select_from(AuditRecord).where(
            AuditRecord.action == "justification_recorded")) == 0


def test_a_justification_with_no_named_evidence_is_refused_at_the_write() -> None:
    # the review's CONFIRMED finding: the invariant ran only on READ, so a sentence-alone
    # justification could be persisted and then raise on every read — unreadable forever, since
    # recording is write-once and AD-7 forbids a delete. It is now refused at the write (FR-41).
    store = SqlStore(_sf())
    chunk_id = _setup(store)
    assert chunk_id  # the fixture really produced a chunk
    with pytest.raises(ValueError, match="name checkable evidence"):
        store.record_justification(
            tenant=TENANT, matter=MATTER, actor="c", piece_id=_PID, sentence="fluent but unbacked",
            basis=JustificationBasis.case_theory("ct-v1"), evidence=(), scopes={WALL})
    _assert_nothing_written(store)


def test_a_blank_sentence_is_refused_at_the_write() -> None:
    store = SqlStore(_sf())
    chunk_id = _setup(store)
    with pytest.raises(ValueError, match="one-line sentence"):
        store.record_justification(
            tenant=TENANT, matter=MATTER, actor="c", piece_id=_PID, sentence="   ",
            basis=JustificationBasis.intrinsic((IntrinsicSignal.DOCUMENT_TYPE,)),
            evidence=(EvidenceExtract(chunk_id, _QUOTE),), scopes={WALL})
    _assert_nothing_written(store)


def test_an_extract_with_an_empty_quote_is_refused_at_the_write() -> None:
    # an empty quote satisfies containment VACUOUSLY ("" in text is always True), so it is not
    # evidence — refused before it can be persisted as a permanently-"verified" extract.
    store = SqlStore(_sf())
    chunk_id = _setup(store)
    with pytest.raises(ValueError, match="empty quote"):
        store.record_justification(
            tenant=TENANT, matter=MATTER, actor="c", piece_id=_PID, sentence="s",
            basis=JustificationBasis.case_theory("ct-v1"),
            evidence=(EvidenceExtract(chunk_id, ""),), scopes={WALL})
    _assert_nothing_written(store)


def test_recording_without_a_ranking_version_fails_loudly() -> None:
    store = SqlStore(_sf())
    store.save(IngestionResult(), scope=WALL, actor="s", matter=MATTER, tenant=TENANT, audit=False)
    with pytest.raises(ValueError, match="no ranking version"):
        store.record_justification(
            tenant=TENANT, matter=MATTER, actor="c", piece_id=_PID, sentence="s",
            basis=JustificationBasis.intrinsic((IntrinsicSignal.DOCUMENT_TYPE,)),
            evidence=(EvidenceExtract("c", "x"),), scopes={WALL})


# ── AC-3 — reject / restore is append-only, reversible, audited ───────────────────────────────────
def test_reject_then_restore_is_append_only_and_audited() -> None:
    store = SqlStore(_sf())
    chunk_id = _setup(store)
    _record(store, chunk_id)
    store.reject_justification(
        tenant=TENANT, matter=MATTER, actor="claire", piece_id=_PID, scopes={WALL},
        reason="the sentence overstates the extract")
    assert store.read_justification(
        tenant=TENANT, matter=MATTER, scopes={WALL}, piece_id=_PID).rejected
    store.restore_justification(
        tenant=TENANT, matter=MATTER, actor="claire", piece_id=_PID, scopes={WALL})
    assert not store.read_justification(
        tenant=TENANT, matter=MATTER, scopes={WALL}, piece_id=_PID).rejected
    with store._sf() as s:  # BOTH rows remain — append-only (the restore did not delete the reject)
        assert s.scalar(select(func.count()).select_from(JustificationRejection).where(
            JustificationRejection.piece_id == _PID)) == 2
        assert s.scalar(select(func.count()).select_from(AuditRecord).where(
            AuditRecord.action == "justification_rejected")) == 1
        assert s.scalar(select(func.count()).select_from(AuditRecord).where(
            AuditRecord.action == "justification_restored")) == 1


def test_rejecting_an_already_rejected_assessment_fails_loudly() -> None:
    store = SqlStore(_sf())
    chunk_id = _setup(store)
    _record(store, chunk_id)
    store.reject_justification(
        tenant=TENANT, matter=MATTER, actor="c", piece_id=_PID, scopes={WALL})
    with pytest.raises(ValueError, match="already rejected"):
        store.reject_justification(
            tenant=TENANT, matter=MATTER, actor="c", piece_id=_PID, scopes={WALL})


def test_restoring_a_non_rejected_assessment_fails_loudly() -> None:
    store = SqlStore(_sf())
    chunk_id = _setup(store)
    _record(store, chunk_id)
    with pytest.raises(ValueError, match="no rejected assessment"):
        store.restore_justification(
            tenant=TENANT, matter=MATTER, actor="c", piece_id=_PID, scopes={WALL})


def test_a_stale_expected_seq_is_refused() -> None:
    store = SqlStore(_sf())
    chunk_id = _setup(store)
    _record(store, chunk_id)
    store.reject_justification(
        tenant=TENANT, matter=MATTER, actor="c", piece_id=_PID, scopes={WALL})  # seq 1
    with pytest.raises(StaleJustification):  # a caller who still thinks seq is 0 is refused
        store.restore_justification(
            tenant=TENANT, matter=MATTER, actor="c", piece_id=_PID, scopes={WALL}, expected_seq=0)


# ── AC-3 — the rejection is version-INDEPENDENT (survives re-ranking) ─────────────────────────────
def test_a_rejection_carries_to_a_new_ranking_version() -> None:
    store = SqlStore(_sf())
    chunk_id = _setup(store)
    _record(store, chunk_id)
    store.reject_justification(
        tenant=TENANT, matter=MATTER, actor="claire", piece_id=_PID, scopes={WALL})
    store.record_ranking(  # a re-rank → version 2
        tenant=TENANT, matter=MATTER, actor="a", identity=_identity(), order=_order(chunk_id))
    _record(store, chunk_id)  # a justification for the NEW latest version (v2)
    vj2 = store.read_justification(
        tenant=TENANT, matter=MATTER, scopes={WALL}, piece_id=_PID, version_no=2)
    assert vj2 is not None and vj2.rejected  # the rejection applies to v2 too (version-independent)


# ── scope-gating — non-disclosing reads, refused writes ──────────────────────────────────────────
def test_reads_and_writes_are_scope_gated() -> None:
    store = SqlStore(_sf())
    chunk_id = _setup(store)
    _record(store, chunk_id)
    assert store.read_justification(
        tenant=TENANT, matter=MATTER, scopes={"other"}, piece_id=_PID) is None
    with pytest.raises(ScopeDenied):
        store.reject_justification(
            tenant=TENANT, matter=MATTER, actor="c", piece_id=_PID, scopes={"other"})
    with pytest.raises(ScopeDenied):
        store.record_justification(
            tenant=TENANT, matter=MATTER, actor="c", piece_id=_PID, sentence="s",
            basis=JustificationBasis.intrinsic((IntrinsicSignal.DOCUMENT_TYPE,)),
            evidence=(EvidenceExtract(chunk_id, _QUOTE),), scopes={"other"})
