"""Per-*pièce* confidence — DERIVED from observable quantities, never self-reported (Story 4.4,
FR-42 / AD-19 / AD-23).

Distinct from ``confidence.py`` (the Epic-5 hypergeometric *confidence bound* over a discarded
pile):
this is the certainty of a single *pièce*'s relevance **assessment**, computed by **one** pure
function from the cascade's own **observable** outputs — the **score margin** (how far the stage-2
semantic score sits beyond its band's decision boundary) and **cross-stage agreement** (does the
stage-3 LLM label agree with the cheap band's direction). It is **never** read from a figure the
language model states about itself: the judge's ``Verdict`` carries only ``label`` + ``rationale``
(no confidence field), and this module reads only ``judgement.score/band/label/outcome`` and the
configured band boundaries — enforced live by
``checks.forward_looking.no_model_reported_confidence``
and ``checks.confidence_derivation.confidence_has_one_derivation``.

**AD-19 — not-derived is a first-class state, never a zero.** Where no observable quantity exists —
an UNSCORED *pièce* (its judgement failed), a REJECTED near-duplicate member (no independent
judgement of its own), or an intrinsic *pièce* with neither a numeric score nor a stage-3 label —
:func:`derive_confidence` returns ``None`` (not derived). A reader must distinguish a derived
``0.0``
(low confidence) from ``None`` (nothing to derive from).

The derivation is a **versioned method** (:data:`CONFIDENCE_METHOD`) recorded in the *ranking
version*
identity (AD-23): a change to the formula or its weights is a NEW method = a new ranking version.
The
v1 weights are deliberately **conservative** (a boundary *pièce* → ~0 confidence; a cross-stage
conflict strongly deflates), so the derivation is not systematically overconfident by construction;
the gold-set calibration (SM-17, ``eval.harness.confidence_calibration``) measures it against
reality.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from apx.core.domain.cascade import Band, Outcome, PieceJudgement
from apx.core.domain.config import CascadeConfig

# The versioned derivation identity (AD-23). Bump on any change to the formula or its weights.
CONFIDENCE_METHOD = "margin-agreement-v1"

# v1 weights — conservative by design (never claim more than the observable supports). To be
# CALIBRATED against the gold set (SM-17); the tested contract is the PROPERTIES (monotone in the
# margin, conflict < agreement, boundary → low), not these absolute numbers.
_CONFLICT_FACTOR = 0.3        # a stage-2/stage-3 conflict deflates a confident-band margin to this
_UNCERTAIN_DECISIVE = 0.4     # an uncertain-band pièce the LLM gave a decisive relevant/discard
_UNCERTAIN_INDECISIVE = 0.15  # an uncertain-band pièce the LLM also could not decide ("uncertain")
_EPS = 1e-9                   # guards a degenerate band boundary at the score extreme


class ConfidenceSignal(StrEnum):
    """The observable quantities a confidence was derived from — recorded for transparency (FR-42).
    **Append-only** (a persisted signal string must always decode, like
    ``cascade.RejectionClass``)."""

    SCORE_MARGIN = "score-margin"                    # distance of the score beyond the band edge
    CROSS_STAGE_AGREEMENT = "cross-stage-agreement"  # stage-2 band vs the stage-3 LLM label
    # ── reserved: the cascade judges each pièce ONCE today, so no repeats are produced yet ──
    REPEATED_JUDGEMENT = "repeated-judgement"        # agreement across repeated LLM judgements


CONFIDENCE_SIGNALS: tuple[ConfidenceSignal, ...] = tuple(ConfidenceSignal)


@dataclass(frozen=True)
class Confidence:
    """A derived per-*pièce* confidence — a DOMAIN value (never a model subject). ``value`` is the
    certainty of the relevance assessment in ``[0, 1]``; ``signals`` names the observable quantities
    it was derived from (non-empty — a confidence with no signal is not derived, and is
    ``None``)."""

    value: float
    signals: tuple[ConfidenceSignal, ...]

    def __post_init__(self) -> None:
        if not 0.0 <= self.value <= 1.0:
            raise ValueError(f"confidence value must be in [0, 1], got {self.value!r}")
        if not self.signals:
            raise ValueError("a derived confidence carries at least one observable signal (FR-42)")


def _clamp(x: float) -> float:
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else x


def _band_direction(band: Band) -> str | None:
    """The relevance direction a CONFIDENT band implies, or None for the uncertain band."""
    if band is Band.CONFIDENT_RELEVANT:
        return "relevant"
    if band is Band.CONFIDENT_DISCARD:
        return "discard"
    return None


def derive_confidence(judgement: PieceJudgement, config: CascadeConfig) -> Confidence | None:
    """Derive a *pièce*'s confidence from the cascade's OBSERVABLE outputs (FR-42), or ``None`` when
    nothing observable exists (AD-19 — never imputed). Reads only ``judgement`` fields + the config
    band boundaries; NEVER a model-reported figure (the ``Verdict`` has none).

    - UNSCORED / REJECTED → ``None`` (no judgement / no independent judgement of its own).
    - a CONFIDENT band with a score → the normalised **margin** beyond the boundary, deflated by a
      cross-stage **conflict** with the stage-3 label (a confident-relevant the LLM calls discard is
      not confident).
    - the UNCERTAIN band (or an intrinsic *pièce*) → the LLM label is the only signal: a decisive
      ``relevant``/``discard`` gives a moderate confidence, an ``uncertain`` label a low one.
    - a JUDGED *pièce* with neither a score nor a stage-3 label → ``None`` (no observable)."""
    if judgement.outcome is not Outcome.JUDGED:
        # UNSCORED (judgement failed) or REJECTED (a duplicate, no own judgement) — never imputed
        return None
    band, score, label = judgement.band, judgement.score, judgement.label
    signals: list[ConfidenceSignal] = []

    if band in (Band.CONFIDENT_RELEVANT, Band.CONFIDENT_DISCARD) and score is not None:
        # confident-band regime: the margin drives it (0 at the boundary → 1 at the score extreme).
        hi, lo = config.uncertain_high, config.uncertain_low
        if band is Band.CONFIDENT_RELEVANT:
            margin = _clamp((score - hi) / max(1.0 - hi, _EPS))
        else:
            margin = _clamp((lo - score) / max(lo + 1.0, _EPS))
        signals.append(ConfidenceSignal.SCORE_MARGIN)
        value = margin
        if label is not None:  # a calibration-sampled confident pièce carries a stage-3 label
            signals.append(ConfidenceSignal.CROSS_STAGE_AGREEMENT)
            if label != _band_direction(band):  # a stage-2/stage-3 conflict deflates the confidence
                value = margin * _CONFLICT_FACTOR
    elif label is not None:
        # the uncertain band (or an intrinsic pièce): the LLM label is the sole signal.
        signals.append(ConfidenceSignal.CROSS_STAGE_AGREEMENT)
        value = _UNCERTAIN_DECISIVE if label in ("relevant", "discard") else _UNCERTAIN_INDECISIVE
    else:
        return None  # a JUDGED pièce with no numeric score AND no label — nothing to derive from

    return Confidence(value=_clamp(value), signals=tuple(signals))
