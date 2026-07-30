"""The truth-status data contract (Story 3.1, AD-20): a semantic result set is SUGGESTIVE by type,
carries no total/denominator, and can never be relabelled exhaustive by a caller or a config."""

from __future__ import annotations

import dataclasses

import pytest

from apx.core.domain.inventory import Inventory
from apx.core.domain.retrieval import (
    DeterministicResult,
    ExhaustiveResultSet,
    RegisterHit,
    SemanticResult,
    SuggestiveResultSet,
    TruthStatus,
)


def _inventory() -> Inventory:
    return Inventory(submitted_pieces=10, in_corpus=8, open_register_entries=2,
                     unknown_cardinality_entries=1)


def _exhaustive(**over) -> ExhaustiveResultSet:
    base = dict(
        results=(), denominator=_inventory(), ocr_share=0.2, below_quality_share=0.05,
        register_hits=(), normalization="fr-fold-v1",
    )
    base.update(over)
    return ExhaustiveResultSet(**base)


def test_an_exhaustive_set_is_constant_exhaustive_and_carries_its_denominator() -> None:
    rs = _exhaustive()
    assert rs.truth_status is TruthStatus.EXHAUSTIVE
    assert rs.denominator.open_register_entries == 2          # the register count (AD-38 record)
    assert rs.denominator.unknown_cardinality_entries == 1    # unknown-cardinality containers
    assert rs.ocr_share == 0.2 and rs.normalization == "fr-fold-v1"
    with pytest.raises(TypeError):                             # truth_status is not an init arg
        ExhaustiveResultSet(
            results=(), denominator=_inventory(), ocr_share=0.0, below_quality_share=0.0,
            register_hits=(), normalization="x", truth_status=TruthStatus.SUGGESTIVE,
        )


def test_an_exhaustive_set_has_no_limit_or_top_k_field() -> None:
    fields = {f.name for f in dataclasses.fields(_exhaustive())}
    for forbidden in ("limit", "top_k", "page_size", "cap", "max_results"):
        assert forbidden not in fields                        # never truncated (AD-20)


def test_a_register_hit_is_a_distinct_type_never_inside_the_exhaustive_results() -> None:
    hit = RegisterHit(matter="m", filename="scan.pdf", error_class="unreadable")
    rs = _exhaustive(register_hits=(hit,))
    assert hit not in rs.results                              # separate from the set (AD-21)
    assert isinstance(rs.register_hits[0], RegisterHit)
    assert not isinstance(hit, DeterministicResult)


def test_truth_status_has_exactly_two_values() -> None:
    assert {s.name for s in TruthStatus} == {"SUGGESTIVE", "EXHAUSTIVE"}


def test_a_suggestive_set_is_constant_suggestive_and_cannot_be_constructed_otherwise() -> None:
    rs = SuggestiveResultSet(results=(), k=10, similarity_threshold=0.35)
    assert rs.truth_status is TruthStatus.SUGGESTIVE
    # truth_status is not an init argument — a caller cannot supply EXHAUSTIVE
    with pytest.raises(TypeError):
        SuggestiveResultSet(
            results=(), k=10, similarity_threshold=0.35, truth_status=TruthStatus.EXHAUSTIVE
        )
    # frozen — cannot be reassigned after construction
    with pytest.raises(dataclasses.FrozenInstanceError):
        rs.truth_status = TruthStatus.EXHAUSTIVE  # type: ignore[misc]


def test_a_suggestive_set_carries_exactly_its_fields_no_denominator() -> None:
    # an allowlist, not a denylist — a denominator under ANY name (e.g. total_in_corpus) is excluded
    # by construction, so a suggestive set can never express completeness (AD-20).
    rs = SuggestiveResultSet(results=(), k=10, similarity_threshold=0.35)
    fields = {f.name for f in dataclasses.fields(rs)}
    assert fields == {"results", "k", "similarity_threshold", "truth_status"}
    assert "similarity" in rs.wording.lower()      # a suggestion, never a phrased total


def test_results_carry_piece_identity_openable_handle_and_score() -> None:
    r = SemanticResult(piece_id="p1", chunk_id="c1", similarity=0.9)
    assert r.piece_id and r.chunk_id               # chunk_id is the resolve_chunk handle (FR-11)
    assert 0.0 <= r.similarity <= 1.0


def test_the_set_is_ranked_best_first_and_k_bounded() -> None:
    results = tuple(SemanticResult(f"p{i}", f"c{i}", 1.0 - i * 0.1) for i in range(3))
    rs = SuggestiveResultSet(results=results, k=3, similarity_threshold=0.0)
    scores = [r.similarity for r in rs.results]
    assert scores == sorted(scores, reverse=True)   # ranked, best first
    assert len(rs.results) <= rs.k
