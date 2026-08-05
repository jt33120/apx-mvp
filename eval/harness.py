"""The evaluation harness (Story 2.12, FR-54 / AD-34): ingest the gold corpus through the REAL
ingestion path and verify the denominator at the design target (SM-3).

A fake embedder is substituted at the port boundary (AD-11): the eval run indexes through the same
``admit`` seam as production, but never loads the real BGE-M3 model in CI. The recall figure at *the
line* (SM-2) needs a ranker (Epic 3/4, which does not exist yet), so that harness lands with the
ranker; the merge gate (``apx/checks/gold_gate.py``) makes Epic 4 unable to merge without it.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from apx.adapters.extraction.composite import CompositeExtractor
from apx.adapters.extraction.files import FileExtractor
from apx.adapters.extraction.msg import MsgExtractor
from apx.adapters.store_postgres.admission import admit
from apx.adapters.store_postgres.store import SqlStore
from apx.core.app.ingest import ingest_one_file
from apx.core.domain.inventory import Inventory
from apx.core.ports.embedding import Embedder
from eval.corpus_source import load_manifest, resolve


def real_extractor() -> CompositeExtractor:
    """The worker's extractor composition — ``.msg`` routes to the out-of-process, GPL-isolated
    MsgExtractor, everything else to FileExtractor — built here without importing the queue
    submodule (which pulls in Procrastinate). This is the real extraction path, not a fixture."""
    return CompositeExtractor([MsgExtractor(), FileExtractor()])


def ingest_gold_corpus(
    store: SqlStore, embedder: Embedder, *, tenant: str, matter: str, scope: str, actor: str,
) -> Inventory:
    """Ingest every gold-manifest item through the real ingestion path (``ingest_one_file`` →
    ``admit``), one unit at a time, as the worker does per unit — at the FULL corpus size (the
    design target for the eval, not a sample). No expander is wired: this corpus contains no
    expandable containers (a test guards that), so each file is one unit matching the manifest's
    one-item-per-file ground truth. Production wires a ``CompositeExpander``, so a corpus augmented
    with containers would need it too. Returns the matter's inventory; SM-3
    (``submitted == in_corpus + open``) must hold against it."""
    extractor = real_extractor()
    for item in load_manifest()["items"]:
        result = ingest_one_file(
            resolve(item["rel"]), item["id"], matter, tenant, extractor, custodian="eval-corpus")
        admit(store, embedder, result, scope=scope, actor=actor, matter=matter, tenant=tenant,
              audit=False)
    return store.inventory(matter, tenant, {scope})


def recall_at_the_line(ranker: object) -> float:
    """Recall at *the line* against the gold set (SM-2) — the metric the merge gate (AD-34) guards.

    It needs a ranker and a notion of *the line*, which are Epic 3/4 and do not exist yet, so this
    raises until they do. When they land it will ingest the corpus, run ``ranker`` to place *the
    line*, and return the fraction of the gold RETAINED pièces (``eval.gold_mapping.mapped_gold``)
    that fall above it — recorded on every CI run and ratcheted against the first measured baseline.
    Per PRD §7 SM-2 there is NO absolute target: the metric that matters is that it runs at all."""
    raise NotImplementedError(
        "recall_at_the_line needs a ranker and *the line* (Epic 3/4); the merge gate (AD-34) blocks"
        " ranking code from merging until this is wired and executed in CI")


@dataclass(frozen=True)
class BandCalibration:
    """One confidence band's calibration against the gold set (SM-17): the mean claimed
    **probability of relevance** the derivation asserted for the band vs the relevant share actually
    OBSERVED, and the overconfidence gap (positive when the claim exceeds reality)."""

    band: str
    claimed_p_relevant: float
    observed_share: float
    relevant: int
    total: int

    @property
    def overconfidence_gap(self) -> float:
        return self.claimed_p_relevant - self.observed_share


@dataclass(frozen=True)
class CalibrationResult:
    bands: tuple[BandCalibration, ...]
    systematically_overconfident: bool


def confidence_calibration(
    observations: Mapping[str, tuple[float, int, int]], *, tolerance: float = 0.1
) -> CalibrationResult:
    """Calibrate the per-pièce confidence derivation against the gold set (SM-17, FR-42): among the
    *pièces* in each confidence band, compare the derivation's claimed mean **probability of
    relevance** to the OBSERVED relevant share, and flag the derivation **systematically
    overconfident** when any band's claim exceeds its observed share beyond ``tolerance``.

    ``observations`` maps a band label to ``(claimed_p_relevant, relevant_count, total_count)`` —
    the
    derivation's claim as a **P(relevant)** and the gold ground truth for that band. **Direction
    matters:** the derivation's confidence is the certainty of the *assessment* (symmetric — a deep
    confident-DISCARD pièce is HIGH confidence that it is *irrelevant*), so a caller MUST convert a
    directional confidence to a probability of relevance before bucketing — ``p_relevant = c`` for a
    relevant-direction band, ``p_relevant = 1 - c`` for a discard-direction band. Comparing a raw
    discard confidence against the relevant share would spuriously read as overconfident; this
    contract makes the conversion the caller's explicit responsibility.

    This computes the calibration MATH (exercised in CI now); the FULL gold-corpus run — ingest the
    gold corpus, run the cascade, derive each confidence, convert to P(relevant), bucket by band
    against ``eval.gold_mapping.mapped_gold`` — **defers exactly like** :func:`recall_at_the_line`
    (it
    needs the ranking pipeline over the gold corpus). A build-gate property test asserts the
    derivation is not overconfident by construction; when the gold pipeline lands, this same
    function
    measures it for real and ratchets SM-17."""
    bands: list[BandCalibration] = []
    overconfident = False
    for band, (claimed_p_relevant, relevant, total) in sorted(observations.items()):
        if total <= 0:
            raise ValueError(f"band {band!r}: total must be positive, got {total}")
        if not 0 <= relevant <= total:
            raise ValueError(f"band {band!r}: relevant {relevant} out of [0, {total}]")
        if not 0.0 <= claimed_p_relevant <= 1.0:
            raise ValueError(
                f"band {band!r}: claimed_p_relevant {claimed_p_relevant} out of [0, 1] — convert a "
                "directional confidence to a probability of relevance before calibrating")
        share = relevant / total
        bands.append(BandCalibration(band, claimed_p_relevant, share, relevant, total))
        if claimed_p_relevant - share > tolerance:  # claimed more relevance than reality supports
            overconfident = True
    return CalibrationResult(bands=tuple(bands), systematically_overconfident=overconfident)


@dataclass(frozen=True)
class BandProjection:
    """One band's PROJECTION calibration against the gold set (SM-17, FR-19): the mean projected
    **probability of relevance** the ranking projection asserted for the band vs the relevant share
    actually OBSERVED, and the optimism gap (positive when reality has MORE relevant material than
    the projection claimed — the dangerous direction for a priced move)."""

    band: str
    projected_p_relevant: float
    observed_share: float
    relevant: int
    total: int

    @property
    def optimism_gap(self) -> float:
        return self.observed_share - self.projected_p_relevant


@dataclass(frozen=True)
class ProjectionCalibrationResult:
    bands: tuple[BandProjection, ...]
    systematically_optimistic: bool


def projection_calibration(
    observations: Mapping[str, tuple[float, int, int]], *, tolerance: float = 0.1
) -> ProjectionCalibrationResult:
    """Calibrate the ranking PREVALENCE PROJECTION against the gold set (SM-17, FR-19): among the
    *pièces* in each band, compare the projection's claimed mean **probability of relevance** to the
    OBSERVED relevant share, and flag the projection **systematically optimistic** when any band's
    observed share exceeds its claim beyond ``tolerance`` — i.e. the projection said the set was
    CLEANER (fewer relevant) than it is. That is the dangerous direction: a priced move that
    under-states the relevant material left in the discarded set is the single most dangerous
    artefact the product can emit (FR-19), so the build gate fires on it.

    ``observations`` maps a band label to ``(projected_p_relevant, relevant_count, total_count)`` —
    the projection's claim as a **P(relevant)** (already converted from any directional confidence,
    ``p_relevant = c`` for a relevant band, ``1 - c`` for a discard band) and the gold ground truth.
    This computes the calibration MATH now; the full gold-corpus run defers like
    :func:`confidence_calibration` and :func:`recall_at_the_line`."""
    bands: list[BandProjection] = []
    optimistic = False
    for band, (projected_p_relevant, relevant, total) in sorted(observations.items()):
        if total <= 0:
            raise ValueError(f"band {band!r}: total must be positive, got {total}")
        if not 0 <= relevant <= total:
            raise ValueError(f"band {band!r}: relevant {relevant} out of [0, {total}]")
        if not 0.0 <= projected_p_relevant <= 1.0:
            raise ValueError(
                f"band {band!r}: projected_p_relevant {projected_p_relevant} out of [0, 1] — "
                "convert a directional confidence to a probability of relevance before calibrating")
        share = relevant / total
        bands.append(BandProjection(band, projected_p_relevant, share, relevant, total))
        if share - projected_p_relevant > tolerance:  # reality has more relevant than projected
            optimistic = True
    return ProjectionCalibrationResult(bands=tuple(bands), systematically_optimistic=optimistic)
