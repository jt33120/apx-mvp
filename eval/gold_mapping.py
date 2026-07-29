"""The gold-set relevance mapping (Story 2.12, FR-54): the v1 manifest's two-axis ground truth
mapped onto THIS product's notion of relevance — *the line* (retained / discarded) and the uncertain
band. It is written, versioned, reviewable, and **pure data** (no ranking logic — that is Epic 4).
This is the contract the future ranker's recall (SM-2) is measured against.

"The mapping is the hard part and is not trivial" (WORK-BREAKDOWN U3): a gold-set's notion of
relevance is not *ordonnance 145 CPC* relevance, so the translation is declared explicitly and
reviewably here rather than assumed. Bump ``MAPPING_VERSION`` on any change — a re-mapping is a new,
recorded generation, exactly like a ranking version (AD-23).
"""

from __future__ import annotations

from dataclasses import dataclass

MAPPING_VERSION = "line-map-1"

# The three positions relative to *the line* (Epic 4): the retained set (above the line), the
# discarded set (below it), and the uncertain band the cascade routes to the LLM / a human.
RETAINED = "retained"
DISCARDED = "discarded"
UNCERTAIN = "uncertain"
LINE_POSITIONS = frozenset({RETAINED, DISCARDED, UNCERTAIN})

# The reviewable contract — v1 ``gold_pertinence`` (5-value) → position relative to *the line*:
#   pertinent / référence  → RETAINED  (relevant to the matter; a lawyer keeps it)
#   rebut                  → DISCARDED (noise / irrelevant)
#   edge / borderline      → UNCERTAIN (the band a human or the LLM must judge)
PERTINENCE_TO_LINE: dict[str, str] = {
    "pertinent": RETAINED,
    "référence": RETAINED,
    "rebut": DISCARDED,
    "edge": UNCERTAIN,
    "borderline": UNCERTAIN,
}


@dataclass(frozen=True)
class GoldLabel:
    """One item's gold truth mapped onto this product's relevance: its position relative to *the
    line*, and the matter it routes to (``None`` = unrouted / in no matter)."""

    item_id: str
    line_position: str
    matter: str | None


def map_item(item: dict) -> GoldLabel:
    """Map one manifest item onto *the line* + the matter (routing) axis. Raises ``KeyError`` on an
    unmapped ``gold_pertinence`` value — the build fails rather than silently guessing, so the
    mapping stays complete and reviewable."""
    pertinence = item["gold_pertinence"]
    if pertinence not in PERTINENCE_TO_LINE:
        raise KeyError(f"gold_pertinence {pertinence!r} has no mapping onto the line")
    return GoldLabel(item["id"], PERTINENCE_TO_LINE[pertinence], item.get("gold_dossier"))


def mapped_gold() -> list[GoldLabel]:
    """The whole gold set mapped onto *the line* + matters — the recall harness's target (Epic 4).

    Pure data assembled from the manifest; the recall FIGURE lands with the ranker."""
    from eval.corpus_source import load_manifest

    return [map_item(item) for item in load_manifest()["items"]]
