"""The recall guarantee loop: sample the discard pile, record a review, get the bound.

Uses the store end to end (real ingestion + labels), so the discards are real rows.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apx.adapters.extraction.files import FileExtractor
from apx.adapters.store_postgres.models import Base
from apx.adapters.store_postgres.store import ScopeDenied, SqlStore
from apx.core.app.ingest import ingest_folder
from apx.core.domain.triage import Label, PieceLabel, TriageOutcome


@pytest.fixture
def store() -> SqlStore:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return SqlStore(sessionmaker(bind=engine, future=True))


def _seed_discards(store: SqlStore, tmp_path: Path, n_discard: int, n_relevant: int = 0) -> None:
    for i in range(n_discard + n_relevant):
        (tmp_path / f"p{i}.txt").write_text(f"pièce unique numéro {i}", encoding="utf-8")
    store.save(ingest_folder(tmp_path, matter="m", tenant="t", extractor=FileExtractor()),
               scope="wall-1")
    reps = store.representatives("m", "t", {"wall-1"})
    labels = tuple(
        PieceLabel(pid, Label.DISCARD if i < n_discard else Label.RELEVANT, "test")
        for i, (pid, _text) in enumerate(reps)
    )
    store.save_labels("m", "t", {"wall-1"}, TriageOutcome(labels), "criteria", actor="me")


def test_sample_draws_only_from_the_discard_pile(tmp_path: Path, store: SqlStore) -> None:
    _seed_discards(store, tmp_path, n_discard=10, n_relevant=3)
    s = store.sample_discards("m", "t", {"wall-1"}, 5, seed=1)
    assert s.population == 10 and len(s.sample) == 5
    # every sampled piece is a discard, so recording the review is accepted
    result = store.record_recall_review(
        "m", "t", {"wall-1"}, {sd.piece_id: False for sd in s.sample}, "me")
    assert result.population == 10 and result.sample_size == 5 and result.relevant_found == 0
    assert 0 < result.prevalence_upper < 1


def test_more_false_discards_found_loosens_the_bound(tmp_path: Path, store: SqlStore) -> None:
    _seed_discards(store, tmp_path, n_discard=100)
    clean = store.sample_discards("m", "t", {"wall-1"}, 20, seed=2)
    zero = store.record_recall_review(
        "m", "t", {"wall-1"}, {sd.piece_id: False for sd in clean.sample}, "me")
    again = store.sample_discards("m", "t", {"wall-1"}, 20, seed=3)
    verdicts = {sd.piece_id: (i < 2) for i, sd in enumerate(again.sample)}  # 2 false discards
    found = store.record_recall_review("m", "t", {"wall-1"}, verdicts, "me")
    assert found.relevant_found == 2 and found.count_upper > zero.count_upper


def test_recall_review_is_recorded_on_the_audit_trail(tmp_path: Path, store: SqlStore) -> None:
    _seed_discards(store, tmp_path, n_discard=5)
    s = store.sample_discards("m", "t", {"wall-1"}, 3, seed=1)
    store.record_recall_review(
        "m", "t", {"wall-1"}, {sd.piece_id: False for sd in s.sample}, "me.durand")
    trail = store.read_audit("m", "t", {"wall-1"})
    entry = next(e for e in trail.entries if e.action == "recall-review")
    assert entry.actor == "me.durand" and "population=5" in entry.detail and trail.verified


def test_reviewing_a_non_discarded_piece_is_rejected(tmp_path: Path, store: SqlStore) -> None:
    _seed_discards(store, tmp_path, n_discard=3, n_relevant=2)
    with pytest.raises(ValueError):
        store.record_recall_review("m", "t", {"wall-1"}, {"not-a-real-discard": True}, "me")


def test_recall_is_scope_checked(tmp_path: Path, store: SqlStore) -> None:
    _seed_discards(store, tmp_path, n_discard=3)
    with pytest.raises(ScopeDenied):
        store.sample_discards("m", "t", {"wall-OTHER"}, 2)
    with pytest.raises(ScopeDenied):
        store.record_recall_review("m", "t", {"wall-OTHER"}, {}, "me")
