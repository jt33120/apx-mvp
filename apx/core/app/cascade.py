"""The relevance-judgement cascade orchestrator (Story 4.2, FR-38 / AD-18 / AD-19 / AD-36).

A pure Application-layer use case: given a matter's pièces (+ the optional case theory), the
semantic scorer and the judge ports, and the cascade's configuration-as-data boundaries, it runs the
three stages and returns a :class:`CascadeResult`. It **persists nothing** and calls no store —
Story 4.3 wraps it to record the judgements against a *ranking version* (AD-23). It imports Domain +
Ports only (AD-4).

Stage 1 groups near-duplicate families (exact-modulo-formatting, reusing ``dedup.text_key``); a
non-representative member is REJECTED (``exact-duplicate-member``, AD-36) and kept IN the order,
never re-judged. Stage 2 scores each representative against the case-theory vector and bands it.
Stage 3 spends the LLM on **only** the uncertain band plus a mandatory calibration sample of the
confident bands. A judge failure makes the pièce **UNSCORED** — out of the order, never imputed
(AD-19). The
share reaching stage 3 is the measured SM-18 output.
"""

from __future__ import annotations

from apx.core.domain.cascade import (
    INTRINSIC_SIGNALS,
    Band,
    CascadeResult,
    CascadeUnit,
    PieceJudgement,
    RejectionClass,
    Stage,
)
from apx.core.domain.config import CascadeConfig
from apx.core.domain.dedup import text_key
from apx.core.domain.failures import redacted_diagnostic
from apx.core.ports.judge import Judge
from apx.core.ports.scorer import SemanticScorer

# Where no case theory exists, the judgement is relative to the enumerated intrinsic signals
# (FR-38). The judge is still asked a question; this is the intrinsic stand-in, and the result is
# marked ``intrinsic`` + names the signals so no artefact reads it as a matter-specific judgement.
_INTRINSIC_QUESTION = (
    "Aucune théorie de la cause n'a été fournie. Évaluez la pertinence de cette pièce d'après ses "
    "signaux intrinsèques (type de document, rôles des participants, distribution des dates, "
    "duplication, bruit manifeste)."
)


def _families(units: list[CascadeUnit]) -> tuple[dict[str, str], dict[str, str]]:
    """Group pièces into near-duplicate families by ``text_key`` (exact modulo formatting). Returns
    (family_id per piece_id, representative piece_id per family_id). The representative is the
    lexicographically smallest piece_id — the same stable rule as ``dedup.cluster`` — so a re-run
    picks the same representative regardless of input order."""
    fid_of: dict[str, str] = {}
    members: dict[str, list[str]] = {}
    for u in units:
        fid = text_key(u.text)
        fid_of[u.piece_id] = fid
        members.setdefault(fid, []).append(u.piece_id)
    rep_of = {fid: min(pids) for fid, pids in members.items()}
    return fid_of, rep_of


def run_cascade(
    units: list[CascadeUnit], *, case_theory: str | None, scorer: SemanticScorer, judge: Judge,
    config: CascadeConfig, tenant: str, matter: str, scopes: set[str],
) -> CascadeResult:
    """Run the three-stage cascade over ``units`` and return the structured result (FR-38)."""
    fid_of, rep_of = _families(units)
    members_by_fid: dict[str, list[str]] = {}
    for u in units:
        members_by_fid.setdefault(fid_of[u.piece_id], []).append(u.piece_id)

    judgements: list[PieceJudgement] = []

    # ── Stage 1: family grouping. A non-representative member is rejected (in the order), AD-36. ──
    reps: list[CascadeUnit] = []
    for u in units:
        fid = fid_of[u.piece_id]
        if u.piece_id == rep_of[fid]:
            reps.append(u)
        else:
            judgements.append(PieceJudgement.rejected(
                piece_id=u.piece_id, family_id=fid, is_representative=False,
                stage_reached=Stage.STAGE_1,
                rejection_class=RejectionClass.EXACT_DUPLICATE_MEMBER))

    # ── Stage 2: cheap semantic scoring of representatives → a band. ──
    basis = "case-theory" if (case_theory and case_theory.strip()) else "intrinsic"
    scores: dict[str, float] = {}
    if basis == "case-theory" and reps:
        scores = dict(scorer.score(
            tenant=tenant, matter=matter, scopes=scopes, query_text=case_theory or "",
            piece_ids=[r.piece_id for r in reps]))

    rep_band: dict[str, Band] = {}
    rep_score: dict[str, float | None] = {}
    for r in reps:
        # a scored representative bands by its score; an absent score (no signal) or the intrinsic
        # path is UNCERTAIN — never imputed to a number, so it is judged, not silently discarded.
        if basis == "case-theory" and r.piece_id in scores:
            s = scores[r.piece_id]
            rep_score[r.piece_id] = s
            rep_band[r.piece_id] = Band(config.band_of(s))
        else:
            rep_score[r.piece_id] = None
            rep_band[r.piece_id] = Band.UNCERTAIN

    # ── Stage 3: the LLM on ONLY the uncertain band + a mandatory calibration sample of the
    # confident bands (so the cascade's own calibration is measurable). ──
    uncertain = [r for r in reps if rep_band[r.piece_id] is Band.UNCERTAIN]
    confident = [r for r in reps if rep_band[r.piece_id] is not Band.UNCERTAIN]
    sample = sorted(confident, key=lambda r: r.piece_id)[: config.calibration_sample]
    to_stage3 = {r.piece_id for r in uncertain} | {r.piece_id for r in sample}

    question = case_theory if basis == "case-theory" else _INTRINSIC_QUESTION
    unscored_ids: list[str] = []
    for r in reps:
        fid = fid_of[r.piece_id]
        band = rep_band[r.piece_id]
        score = rep_score[r.piece_id]
        if r.piece_id not in to_stage3:
            # settled at stage 2 (a confident band, not sampled) — no LLM, no label.
            judgements.append(PieceJudgement.judged(
                piece_id=r.piece_id, family_id=fid, is_representative=True,
                stage_reached=Stage.STAGE_2, band=band, score=score, label=None))
            continue
        # stage 3 — read only label/rationale from the verdict, never a self-reported confidence
        # (FR-42; derivation is Story 4.4).
        try:
            verdict = judge.judge(question=question or "", text=r.text)
        except Exception as exc:  # noqa: BLE001 — a judge failure is loud, never imputed (AD-19)
            if band is Band.UNCERTAIN:
                # an uncertain pièce's ONLY judgement is the LLM — a failure makes it UNSCORED
                # (AD-19): out of the order, never scored zero, never ranked last, never imputed.
                judgements.append(PieceJudgement.unscored(
                    piece_id=r.piece_id, family_id=fid, is_representative=True,
                    failure_reason=redacted_diagnostic(exc)))
                unscored_ids.append(r.piece_id)
            else:
                # a CONFIDENT pièce was already judged by the cheap tier (stage 2); this LLM call
                # was only a CALIBRATION sample. A failed calibration does NOT un-judge it —
                # recall-first (a non-negotiable) never drops a confidently-relevant pièce from the
                # order on a transient outage. It keeps its stage-2 band/score, without an LLM
                # label. The outage still surfaces (every uncertain pièce goes unscored; SM-18
                # counts the call).
                judgements.append(PieceJudgement.judged(
                    piece_id=r.piece_id, family_id=fid, is_representative=True,
                    stage_reached=Stage.STAGE_2, band=band, score=score, label=None))
            continue
        judgements.append(PieceJudgement.judged(
            piece_id=r.piece_id, family_id=fid, is_representative=True,
            stage_reached=Stage.STAGE_3, band=band, score=score, label=str(verdict.label),
            retained_extract_chunk_ids=r.chunk_ids))

    # ── SM-18: the share of the MATTER (all pièces, so near-duplicate collapsing counts as the
    # cost saving it is) that reached the LLM. Over the ceiling sets the AD-18 flag. ──
    total = len(units)
    stage3_share = (len(to_stage3) / total) if total else 0.0
    over_floor = stage3_share > config.stage3_max_share

    families = {fid: tuple(sorted(pids)) for fid, pids in members_by_fid.items()}
    signals = INTRINSIC_SIGNALS if basis == "intrinsic" else ()
    return CascadeResult(
        judgements=tuple(judgements), families=families, unscored=tuple(unscored_ids),
        stage3_share=stage3_share, over_stage3_floor=over_floor, basis=basis,
        intrinsic_signals=signals)
