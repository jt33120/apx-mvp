"""The named-evidence justification domain (Story 4.6, FR-41/FR-18/FR-11): a justification names
checkable evidence (never the sentence alone), is assembled only from a stage-3 judged pièce, and is
verified by exact containment at show time (an unresolved extract ⇒ unverified). Pure — the resolver
is injected."""

from __future__ import annotations

import pytest

from apx.core.domain.cascade import Band, IntrinsicSignal, PieceJudgement, RejectionClass, Stage
from apx.core.domain.chunking import CONTAINMENT_FAILED, FailedResolution, ResolvedPassage
from apx.core.domain.justification import (
    EvidenceExtract,
    Justification,
    JustificationBasis,
    VerifiedJustification,
    build_justification,
    source_language_note,
    validate_named_evidence,
    verify_justification,
)


def _stage3(chunk_ids: tuple[str, ...]) -> PieceJudgement:
    return PieceJudgement.judged(
        piece_id="p", family_id="f", is_representative=True, stage_reached=Stage.STAGE_3,
        band=Band.CONFIDENT_RELEVANT, score=0.9, label="relevant",
        retained_extract_chunk_ids=chunk_ids)


# ── the basis is named, tagged ───────────────────────────────────────────────────────────────────
def test_a_case_theory_basis_names_its_version_and_an_intrinsic_basis_names_signals() -> None:
    assert JustificationBasis.case_theory("v1").named == "case-theory:v1"
    b = JustificationBasis.intrinsic((IntrinsicSignal.DOCUMENT_TYPE, IntrinsicSignal.DUPLICATION))
    assert b.named == "intrinsic:document-type,duplication"
    with pytest.raises(ValueError, match="names its case-theory version"):
        JustificationBasis(kind="case-theory")
    with pytest.raises(ValueError, match="at least one intrinsic signal"):
        JustificationBasis(kind="intrinsic")


# ── AC-1 — the checkable part is NAMED evidence, never the sentence alone ─────────────────────────
def test_a_justification_cannot_exist_without_named_evidence() -> None:
    # a case-theory justification with no extracts has no checkable part — refused
    with pytest.raises(ValueError, match="must name checkable evidence"):
        Justification(piece_id="p", sentence="fluent but unbacked",
                      basis=JustificationBasis.case_theory("v"), evidence=())
    # an intrinsic justification names its evidence through its signals — allowed with no extracts
    ok = Justification(piece_id="p", sentence="ranked on document type",
                       basis=JustificationBasis.intrinsic((IntrinsicSignal.DOCUMENT_TYPE,)),
                       evidence=())
    assert ok.evidence == ()
    # a case-theory justification WITH named extracts is fine
    Justification(piece_id="p", sentence="s", basis=JustificationBasis.case_theory("v"),
                  evidence=(EvidenceExtract("c1", "an extract"),))


def test_the_invariant_is_callable_at_a_write_seam() -> None:
    # the review's CONFIRMED finding: the rule must be runnable BEFORE anything is persisted, so a
    # write seam refuses what the read path could not rebuild (mirrors pin.validate_pin_reason).
    ct = JustificationBasis.case_theory("v")
    with pytest.raises(ValueError, match="name checkable evidence"):
        validate_named_evidence("a sentence alone", ct, ())
    with pytest.raises(ValueError, match="one-line sentence"):
        validate_named_evidence("  ", ct, (EvidenceExtract("c", "x"),))
    validate_named_evidence("ok", ct, (EvidenceExtract("c", "x"),))  # the good shape passes


def test_an_extract_with_an_empty_quote_is_refused() -> None:
    # "" in text is vacuously True — an empty quote would pass containment forever, so it is refused
    with pytest.raises(ValueError, match="empty quote"):
        validate_named_evidence(
            "s", JustificationBasis.case_theory("v"), (EvidenceExtract("c", ""),))
    with pytest.raises(ValueError, match="empty quote"):
        Justification(piece_id="p", sentence="s", basis=JustificationBasis.case_theory("v"),
                      evidence=(EvidenceExtract("c", ""),))


def test_a_blank_sentence_is_refused() -> None:
    with pytest.raises(ValueError, match="one-line sentence"):
        Justification(piece_id="p", sentence="   ",
                      basis=JustificationBasis.intrinsic((IntrinsicSignal.DUPLICATION,)),
                      evidence=())


# ── AC-1 — assembled only from a stage-3 judged pièce; never imputed otherwise ────────────────────
def test_build_only_for_a_stage3_judged_piece() -> None:
    j = build_justification(
        _stage3(("c1",)), sentence="s", basis=JustificationBasis.case_theory("v"),
        evidence=(EvidenceExtract("c1", "x"),))
    assert j is not None and j.piece_id == "p"
    # a stage-2-settled pièce (no LLM, no extracts) has no justification to derive → None
    stage2 = PieceJudgement.judged(
        piece_id="p", family_id="f", is_representative=True, stage_reached=Stage.STAGE_2,
        band=Band.CONFIDENT_RELEVANT, score=0.9)
    assert build_justification(
        stage2, sentence="s", basis=JustificationBasis.case_theory("v"), evidence=()) is None
    # a rejected pièce → None
    rej = PieceJudgement.rejected(
        piece_id="p", family_id="f", is_representative=True, stage_reached=Stage.STAGE_1,
        rejection_class=RejectionClass.EXACT_DUPLICATE_MEMBER)
    assert build_justification(
        rej, sentence="s", basis=JustificationBasis.case_theory("v"), evidence=()) is None


def test_build_case_theory_with_no_named_extracts_is_none_never_imputed() -> None:
    # a case-theory judged pièce with no retained extracts has no checkable evidence → None (AD-19)
    assert build_justification(
        _stage3(()), sentence="s", basis=JustificationBasis.case_theory("v"), evidence=()) is None


def test_build_refuses_evidence_the_judgement_did_not_use() -> None:
    with pytest.raises(ValueError, match="extracts the judgement used"):
        build_justification(
            _stage3(("c1",)), sentence="s", basis=JustificationBasis.case_theory("v"),
            evidence=(EvidenceExtract("c2", "not used"),))


# ── AC-2 — verified by exact containment at show time; unresolved ⇒ unverified ────────────────────
def test_all_extracts_contained_is_verified() -> None:
    j = Justification(piece_id="p", sentence="s", basis=JustificationBasis.case_theory("v"),
                      evidence=(EvidenceExtract("c1", "a"), EvidenceExtract("c2", "b")))
    vj = verify_justification(j, lambda cid, q: ResolvedPassage(text=q, start=0, end=1))
    assert isinstance(vj, VerifiedJustification)
    assert all(e.verified for e in vj.extracts) and not vj.is_unverified


def test_one_unresolved_extract_makes_the_justification_unverified() -> None:
    j = Justification(piece_id="p", sentence="s", basis=JustificationBasis.case_theory("v"),
                      evidence=(EvidenceExtract("c1", "here"), EvidenceExtract("c2", "gone")))

    def _resolve(cid: str, q: str) -> ResolvedPassage | FailedResolution:
        return FailedResolution(CONTAINMENT_FAILED) if cid == "c2" else ResolvedPassage(q, 0, 1)

    vj = verify_justification(j, _resolve)
    assert vj.is_unverified  # never shown as ordinary (FR-41)
    bad = next(e for e in vj.extracts if e.chunk_id == "c2")
    assert not bad.verified and bad.cause == CONTAINMENT_FAILED


def test_an_intrinsic_justification_with_no_extracts_is_not_unverified() -> None:
    # its checkable part is its named signals, not a containment claim — never "unverified"
    j = Justification(piece_id="p", sentence="s",
                      basis=JustificationBasis.intrinsic((IntrinsicSignal.DOCUMENT_TYPE,)),
                      evidence=())
    vj = verify_justification(j, lambda cid, q: ResolvedPassage(q, 0, 1))
    assert vj.extracts == () and not vj.is_unverified


# ── AC-4 — the source language is stated where it differs ─────────────────────────────────────────
def test_source_language_is_stated_only_where_it_differs() -> None:
    fr = Justification(piece_id="p", sentence="s", basis=JustificationBasis.case_theory("v"),
                       evidence=(EvidenceExtract("c", "x"),), source_language="fr")
    assert source_language_note(fr, interface_language="en") == "fr"
    assert source_language_note(fr, interface_language="fr") is None
    unknown = Justification(piece_id="p", sentence="s", basis=JustificationBasis.case_theory("v"),
                            evidence=(EvidenceExtract("c", "x"),), source_language=None)
    assert source_language_note(unknown, interface_language="en") is None
