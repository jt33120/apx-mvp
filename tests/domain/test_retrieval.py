"""The truth-status data contract (Story 3.1, AD-20): a semantic result set is SUGGESTIVE by type,
carries no total/denominator, and can never be relabelled exhaustive by a caller or a config."""

from __future__ import annotations

import dataclasses

import pytest

from apx.core.domain.retrieval import SemanticResult, SuggestiveResultSet, TruthStatus


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
