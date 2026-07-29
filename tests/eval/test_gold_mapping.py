"""The gold-set relevance mapping is complete, versioned, and reviewable (Story 2.12, FR-54): the v1
two-axis ground truth maps onto *the line* with no silent gap, an unmapped value fails the build,
and the mapping is pure data (no ranking logic — that is Epic 4).
"""

from __future__ import annotations

from collections import Counter

import pytest

from eval.corpus_source import load_manifest
from eval.gold_mapping import (
    LINE_POSITIONS,
    MAPPING_VERSION,
    PERTINENCE_TO_LINE,
    RETAINED,
    map_item,
    mapped_gold,
)


def test_the_mapping_is_versioned() -> None:
    assert isinstance(MAPPING_VERSION, str) and MAPPING_VERSION


def test_every_gold_pertinence_value_in_the_corpus_is_mapped() -> None:
    # completeness: the mapping covers every value the corpus actually uses — no silent gap
    used = {item["gold_pertinence"] for item in load_manifest()["items"]}
    assert used <= set(PERTINENCE_TO_LINE)


def test_the_whole_gold_set_maps_onto_the_line_without_a_gap() -> None:
    labels = mapped_gold()
    assert len(labels) == len(load_manifest()["items"])          # every item mapped, none dropped
    assert all(label.line_position in LINE_POSITIONS for label in labels)


def test_an_unmapped_pertinence_value_fails_the_build() -> None:
    with pytest.raises(KeyError):
        map_item({"id": "x", "gold_pertinence": "not-a-real-grade", "gold_dossier": None})


def test_the_retained_set_the_recall_target_is_non_empty_and_pinned() -> None:
    # recall (SM-2) is measured against the RETAINED gold pièces, so there must be some to measure.
    # The distribution is pinned so a corpus drift or a re-mapping is a detectable, reviewable
    # event: retained 46 (pertinent 33 + référence 13), discarded 85 (rebut), uncertain 8.
    dist = Counter(label.line_position for label in mapped_gold())
    assert dist[RETAINED] > 0
    assert dict(dist) == {"retained": 46, "discarded": 85, "uncertain": 8}
