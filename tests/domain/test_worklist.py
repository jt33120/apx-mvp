"""The derived worklist (Story 4.13, FR-58): a line per stale artefact, offering — never acting."""

from __future__ import annotations

from apx.core.domain.freshness import KIND_BOUND, KIND_LINE, KIND_RANKING, Freshness
from apx.core.domain.worklist import (
    OFFER_REPLACE_LINE,
    OFFER_RERANK,
    OFFER_RESAMPLE,
    offers,
    worklist_line,
    worklist_lines,
)


def _stale(kind: str, *changed: str) -> Freshness:
    return Freshness(kind=kind, artefact_id=f"{kind}-1", changed=changed)


def _fresh(kind: str) -> Freshness:
    return Freshness(kind=kind, artefact_id=f"{kind}-1", changed=())


def test_a_fresh_artefact_is_not_work() -> None:
    assert worklist_line(_fresh(KIND_RANKING)) is None
    assert worklist_lines([_fresh(KIND_RANKING), _fresh(KIND_BOUND)]) == ()


def test_an_ingestion_into_a_ranked_matter_offers_a_re_rank() -> None:
    # FR-58 verbatim: ingestion "generates a worklist line offering a re-rank".
    (line,) = worklist_lines([_stale(KIND_RANKING, "corpus_count")])
    assert line.kind == KIND_RANKING and line.offer == OFFER_RERANK
    assert line.changed == ("corpus_count",)
    assert line.changed_fr == ("une importation dans le dossier",)
    assert "Re-classer" in line.offer_fr and "conservées" in line.offer_fr


def test_each_kind_offers_its_own_recomputation() -> None:
    lines = worklist_lines([
        _stale(KIND_RANKING, "corpus_count"),
        _stale(KIND_LINE, "ranking_version_no"),
        _stale(KIND_BOUND, "pin_ledger_seq"),
    ])
    assert [line.offer for line in lines] == [OFFER_RERANK, OFFER_REPLACE_LINE, OFFER_RESAMPLE]
    assert offers(lines) == (OFFER_RERANK, OFFER_REPLACE_LINE, OFFER_RESAMPLE)


def test_a_line_names_the_artefact_it_would_supersede_never_one_that_does_not_exist() -> None:
    (line,) = worklist_lines([_stale(KIND_BOUND, "corpus_count")])
    assert line.artefact_id == "bound-1"


def test_every_changed_input_is_named_on_the_line() -> None:
    (line,) = worklist_lines([_stale(KIND_RANKING, "corpus_count", "extraction_digest")])
    assert len(line.changed) == len(line.changed_fr) == 2


def test_an_empty_worklist_is_a_read_result_not_a_failure() -> None:
    # () means "read, and nothing is stale". A read that FAILED is None at the seam, never () here
    # — the Story 4.10 lesson: a failed read must not render as a verified absence.
    assert worklist_lines([]) == ()
    assert offers(()) == ()
