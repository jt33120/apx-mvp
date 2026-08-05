"""The ranked order and the reproducible ranking version — the domain vocabulary (Story 4.3,
FR-39 / AD-23 / AD-37 / AD-36 / AD-19).

A *ranking act* turns one :class:`~apx.core.domain.cascade.CascadeResult` (Story 4.2) into **exactly
one deterministic ranked order** and records the complete **immutable identity** (AD-23) of what
produced it. This module is the pure vocabulary the orchestrator (`core/app/rank.py`) and the store
speak; it stores nothing and imports Domain only (AD-4).

Two load-bearing guarantees live here, both pure and testable without a DB:

- **The version identity (AD-23).** :class:`RankingIdentity` names every input a re-run would need —
  case-theory version, model identity, prompt version, temperature and every sampling parameter,
  cascade configuration, embedder identity, chunking configuration, schema version **and the
  near-duplicate grouping**. Its ``fingerprint`` is a stable hash over those inputs, so "the same
  ranking version" is decidable; :meth:`RankingVersion.build` mints the referenceable
  ``version_id``.

- **The deterministic order (AD-23).** :func:`rank_cascade` is a **pure function** of the cascade
  outputs + the *pièce* identity hashes. Ties are broken by the *pièce* identity hash compared in
  **byte order** (the ids are ASCII hex, so Python's codepoint comparison IS byte order — locale
  independent), never by collated text and never by the order a store returned. Near-duplicate
  families stay contiguous (representative first); a REJECTED member stays IN the order carrying its
  class (AD-36); an UNSCORED pièce is OUT of the order, never imputed a rank (AD-19).
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass

from apx.core.domain.cascade import Band, CascadeResult, Outcome, PieceJudgement, RejectionClass
from apx.core.domain.config import CascadeConfig
from apx.core.domain.piece_confidence import (
    CONFIDENCE_METHOD,
    ConfidenceSignal,
    derive_confidence,
)

# The near-duplicate grouping identity (AD-23: "a change to the grouping threshold produces a new
# version"). Story 4.2 groups by exact ``dedup.text_key`` (sha256 of normalised text); when a fuzzy
# tier lands it takes a new identity string, so a re-group cannot masquerade as the same version.
GROUPING_IDENTITY = "exact-text-key-v1"

# The prompt version the cascade judged under (AD-23 "prompt version"). Bump when the case-theory or
# intrinsic question in ``core/app/cascade.py`` changes, so a re-worded prompt is a new version.
PROMPT_VERSION = "cascade-question-v1"

# The tie-break recorded in the version (AD-23): the pièce identity hash, byte-ordered.
TIE_BREAK = "piece-id-hash"

# ── the relevance ladder (AD-23's "score OR rejection class" order) ─────────────────────────────
# The order is the honest, minimal ladder over the cascade's OWN signal (band → stage-3 label); it
# is
# NOT the confidence derivation (4.4), the taxonomy label (4.5) or the line (4.7/4.8). Lower tier =
# more relevant = ranked earlier. band-first, then the stage-3 label refines the uncertain band.
_TIER_CONFIDENT_RELEVANT = 0
_TIER_UNCERTAIN_RELEVANT = 10
_TIER_UNCERTAIN_NEUTRAL = 11   # uncertain band, LLM said "uncertain" or no stage-3 label
_TIER_UNCERTAIN_DISCARD = 12
_TIER_CONFIDENT_DISCARD = 21
# A family whose representative is UNSCORED (its only judge failed, AD-19): the rep is OUT of the
# order but its exact-duplicate members are REJECTED and stay IN it (AD-36). Recall-first — never
# bury the duplicates of an un-judgeable document — anchors them in the uncertain review region
# without imputing a score. It never imputes a SCORE or a label; only an order position.
_TIER_UNKNOWN = 11


def _label_tier(label: str | None) -> int:
    if label == "relevant":
        return _TIER_UNCERTAIN_RELEVANT
    if label == "discard":
        return _TIER_UNCERTAIN_DISCARD
    return _TIER_UNCERTAIN_NEUTRAL  # "uncertain" or an intrinsic/None label


def _relevance_tier(rep: PieceJudgement) -> int:
    """The relevance tier of a family, from its representative's judgement. UNSCORED reps anchor at
    the uncertain region (recall-first); JUDGED reps band-first, uncertain refined by the label."""
    if rep.outcome is Outcome.UNSCORED:
        return _TIER_UNKNOWN
    if rep.band is Band.CONFIDENT_RELEVANT:
        return _TIER_CONFIDENT_RELEVANT
    if rep.band is Band.CONFIDENT_DISCARD:
        return _TIER_CONFIDENT_DISCARD
    return _label_tier(rep.label)  # the uncertain band — the LLM label decides


@dataclass(frozen=True)
class RankingIdentity:
    """The complete immutable identity of what produced one ranked order (AD-23). Every field a
    re-run would need; a change to any of them is a new ranking version. ``fingerprint`` is the
    stable hash over these inputs (so "the same ranking version" is decidable), computed over a
    canonical JSON with sorted keys — collation- and insertion-order-independent."""

    basis: str                          # "case-theory" | "intrinsic"
    case_theory_version_id: str | None  # the referenced 4.1 version id (None on the intrinsic path)
    model_provider: str
    model_endpoint: str
    model_name: str
    prompt_version: str
    temperature: float
    sampling: Mapping[str, float | int | str]  # every sampling parameter (top_p, max_tokens, …)
    cascade_uncertain_low: float
    cascade_uncertain_high: float
    cascade_calibration_sample: int
    cascade_stage3_max_share: float
    embedder_model_id: str
    embedder_model_version: str
    chunking_config_version: str
    schema_version: str
    grouping_identity: str
    tie_break: str
    confidence_method: str  # the per-pièce confidence derivation method (Story 4.4, AD-23)

    def __post_init__(self) -> None:
        # A blank required identity input would make the version dishonest (AD-23: the identity is
        # complete). The intrinsic path legitimately has no case theory version, so that field alone
        # may be None; everything else is required and non-blank (AC-7 — fail loudly, never a silent
        # default).
        for field_name in (
            "basis", "model_provider", "model_endpoint", "model_name", "prompt_version",
            "embedder_model_id", "embedder_model_version", "chunking_config_version",
            "schema_version", "grouping_identity", "tie_break", "confidence_method",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"ranking identity: {field_name} is required and non-blank (AD-23)")
        if self.basis == "case-theory" and not (self.case_theory_version_id or "").strip():
            raise ValueError(
                "ranking identity: the case-theory basis requires a case_theory_version_id (AD-23)")

    def _canonical(self) -> dict[str, object]:
        return {
            "basis": self.basis,
            "case_theory_version_id": self.case_theory_version_id,
            "model_provider": self.model_provider,
            "model_endpoint": self.model_endpoint,
            "model_name": self.model_name,
            "prompt_version": self.prompt_version,
            "temperature": self.temperature,
            "sampling": dict(self.sampling),
            "cascade_uncertain_low": self.cascade_uncertain_low,
            "cascade_uncertain_high": self.cascade_uncertain_high,
            "cascade_calibration_sample": self.cascade_calibration_sample,
            "cascade_stage3_max_share": self.cascade_stage3_max_share,
            "embedder_model_id": self.embedder_model_id,
            "embedder_model_version": self.embedder_model_version,
            "chunking_config_version": self.chunking_config_version,
            "schema_version": self.schema_version,
            "grouping_identity": self.grouping_identity,
            "tie_break": self.tie_break,
            "confidence_method": self.confidence_method,
        }

    def canonical_json(self) -> str:
        """The canonical serialisation the fingerprint hashes — sorted keys, stable separators, so
        two identities with the same inputs serialise byte-for-byte identically (AD-23)."""
        return json.dumps(
            self._canonical(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    @property
    def fingerprint(self) -> str:
        """sha256 over the canonical identity — "the same ranking version" is fingerprint
        equality."""
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class RankingIdentityInputs:
    """The identity inputs a ranking act is GIVEN (never guesses): the model, embedder, chunking,
    schema, prompt and sampling identities, plus the referenced *case-theory* version. The cascade
    numbers and the basis are supplied separately (from the ``CascadeConfig`` and the cascade run)
    so
    each input is sourced exactly once. A later surface story reads these from the live
    tenant/config
    and the embedder; ``core/app`` never reaches into an adapter for them (AD-4)."""

    case_theory_version_id: str | None
    model_provider: str
    model_endpoint: str
    model_name: str
    prompt_version: str
    temperature: float
    sampling: Mapping[str, float | int | str]
    embedder_model_id: str
    embedder_model_version: str
    chunking_config_version: str
    schema_version: str


def assemble_identity(
    *, inputs: RankingIdentityInputs, basis: str,
    uncertain_low: float, uncertain_high: float, calibration_sample: int, stage3_max_share: float,
) -> RankingIdentity:
    """Assemble the complete AD-23 identity from the caller's inputs + the cascade configuration +
    the run's basis, stamping this build's ``GROUPING_IDENTITY`` and ``TIE_BREAK`` constants."""
    return RankingIdentity(
        basis=basis, case_theory_version_id=inputs.case_theory_version_id,
        model_provider=inputs.model_provider, model_endpoint=inputs.model_endpoint,
        model_name=inputs.model_name, prompt_version=inputs.prompt_version,
        temperature=inputs.temperature, sampling=inputs.sampling,
        cascade_uncertain_low=uncertain_low, cascade_uncertain_high=uncertain_high,
        cascade_calibration_sample=calibration_sample, cascade_stage3_max_share=stage3_max_share,
        embedder_model_id=inputs.embedder_model_id,
        embedder_model_version=inputs.embedder_model_version,
        chunking_config_version=inputs.chunking_config_version,
        schema_version=inputs.schema_version,
        grouping_identity=GROUPING_IDENTITY, tie_break=TIE_BREAK,
        confidence_method=CONFIDENCE_METHOD)


@dataclass(frozen=True)
class RankingVersion:
    """A minted ranking version: the identity plus its per-*matter* monotonic ``version_no``
    (AD-49's
    counter) and the referenceable ``version_id`` (AD-23 — referenceable + immutable).
    ``version_id``
    mirrors the 4.1 shape ``sha256(tenant \\x00 matter \\x00 version_no \\x00 fingerprint)`` — the
    fingerprint makes two identical-identity versions in different matters distinct rows."""

    tenant: str
    matter: str
    version_no: int
    version_id: str
    identity: RankingIdentity

    @classmethod
    def build(
        cls, *, tenant: str, matter: str, version_no: int, identity: RankingIdentity
    ) -> RankingVersion:
        version_id = hashlib.sha256(
            f"{tenant}\x00{matter}\x00{version_no}\x00{identity.fingerprint}".encode()
        ).hexdigest()
        return cls(tenant=tenant, matter=matter, version_no=version_no,
                   version_id=version_id, identity=identity)


@dataclass(frozen=True)
class RankedRow:
    """One *pièce*'s recorded row in a ranking (AD-23's per-*pièce* output). ``rank`` is 1-based
    for a
    pièce IN the order (judged or rejected) and ``None`` for an UNSCORED pièce (out of the order,
    never ranked last — AD-19). It carries its ``score`` OR its ``rejection_class`` (AD-36), its
    near-duplicate ``family_id`` and ``is_representative``, and its ``supersedes`` state (always
    ``False`` until the AD-8 superseding transition exists — a documented deferral)."""

    piece_id: str
    rank: int | None
    family_id: str
    is_representative: bool
    outcome: Outcome
    score: float | None = None
    band: Band | None = None
    label: str | None = None
    rejection_class: RejectionClass | None = None
    failure_reason: str | None = None
    supersedes: bool = False
    # Story 4.4: the DERIVED confidence — None == not derived (AD-19, never imputed); the observable
    # signals it came from (empty when not derived). Does NOT affect the rank (the order is 4.3's).
    confidence: float | None = None
    confidence_signals: tuple[ConfidenceSignal, ...] = ()


@dataclass(frozen=True)
class RankedOrder:
    """One deterministic ranked order produced from a cascade result. ``rows`` are the pièces IN the
    order (judged + rejected), rank 1..N; ``unscored_rows`` are the UNSCORED pièces (rank ``None``),
    recorded as their own set (AD-36/AD-19) — never ranked, never dropped from the population.
    ``stage3_share`` (SM-18) and ``over_stage3_floor`` are the cascade run's measured cost outputs,
    carried through so the ranking records them (AD-18)."""

    rows: tuple[RankedRow, ...]
    unscored_rows: tuple[RankedRow, ...]
    stage3_share: float = 0.0
    over_stage3_floor: bool = False

    @property
    def unscored(self) -> tuple[str, ...]:
        return tuple(r.piece_id for r in self.unscored_rows)

    @property
    def all_rows(self) -> tuple[RankedRow, ...]:
        """Every recorded row — the ranked order plus the unscored tail — the whole population the
        store persists (AD-36: nothing dropped)."""
        return self.rows + self.unscored_rows

    def is_consistent(self) -> bool:
        """Ranks are exactly ``1..len(rows)`` contiguous; the unscored set is disjoint from the
        ranked pièces; every near-duplicate family occupies a contiguous rank range (AD-23 —
        families
        are grouped, which the estimator relies on)."""
        ranks = [r.rank for r in self.rows]
        if ranks != list(range(1, len(self.rows) + 1)):
            return False
        ranked_ids = {r.piece_id for r in self.rows}
        if ranked_ids & set(self.unscored):
            return False
        seen_families: set[str] = set()
        last_family: str | None = None
        for r in self.rows:  # a family is contiguous iff we never RE-enter one we already left
            if r.family_id != last_family:
                if r.family_id in seen_families:
                    return False
                seen_families.add(r.family_id)
                last_family = r.family_id
        return True


def _to_row(j: PieceJudgement, rank: int | None, config: CascadeConfig) -> RankedRow:
    conf = derive_confidence(j, config)  # Story 4.4 — None when not derivable (AD-19)
    return RankedRow(
        piece_id=j.piece_id, rank=rank, family_id=j.family_id,
        is_representative=j.is_representative, outcome=j.outcome, score=j.score, band=j.band,
        label=j.label, rejection_class=j.rejection_class, failure_reason=j.failure_reason,
        confidence=conf.value if conf is not None else None,
        confidence_signals=conf.signals if conf is not None else ())


def rank_cascade(result: CascadeResult, config: CascadeConfig) -> RankedOrder:
    """Turn a cascade result into ONE deterministic ranked order (AD-23), attaching each *pièce*'s
    DERIVED confidence (Story 4.4 — from observables, None when not derivable; it never affects the
    rank). Pure and reproducible: the same result yields the same order, and every tie is broken by
    the *pièce* identity hash in byte order (never collated text). Near-duplicate families are
    contiguous (representative first); a REJECTED member stays in the order (AD-36); an UNSCORED
    pièce is excluded and collected into the unscored set (AD-19)."""
    by_id = {j.piece_id: j for j in result.judgements}
    # the representative judgement of each family (exactly one per family carries
    # is_representative);
    # a member inherits its family's anchor so duplicates rank beside their representative.
    rep_of: dict[str, PieceJudgement] = {}
    for j in result.judgements:
        if j.is_representative:
            rep_of[j.family_id] = j

    def _sort_key(j: PieceJudgement) -> tuple[int, int, float, str, int, str]:
        rep = rep_of.get(j.family_id, j)
        tier = _relevance_tier(rep)
        # scored reps sort before score-less ones within a tier (the intrinsic path has no scores,
        # so everything falls to the identity-hash tie-break). A tuple (has_no_score, -score)
        # keeps it total and avoids comparing None/inf. A NON-FINITE score (NaN/inf) is treated as
        # no-score: a raw NaN in a sort key would short-circuit tuple comparison (NaN != NaN) BEFORE
        # the piece-id tie-break and make the order input-dependent — fatal to reproducibility (the
        # story's spine). The production scorer cannot emit one, but a pure domain function must be
        # robust to its inputs, so we neutralise it deterministically here (the stored score is
        # untouched — never imputed, AD-19).
        scored = rep.score is not None and math.isfinite(rep.score)
        has_no_score = 0 if scored else 1
        neg_score = -rep.score if scored else 0.0
        # family anchor first (tier, score, rep id → keeps whole families contiguous & ordered),
        # then
        # WITHIN a family the representative precedes its members, then the identity-hash tie-break.
        return (tier, has_no_score, neg_score, rep.piece_id, 0 if j.is_representative else 1,
                j.piece_id)

    ordered = sorted(result.in_order, key=_sort_key)
    rows = tuple(_to_row(j, rank, config) for rank, j in enumerate(ordered, start=1))
    unscored_rows = tuple(
        _to_row(by_id[pid], None, config) for pid in sorted(result.unscored))
    return RankedOrder(
        rows=rows, unscored_rows=unscored_rows,
        stage3_share=result.stage3_share, over_stage3_floor=result.over_stage3_floor)
