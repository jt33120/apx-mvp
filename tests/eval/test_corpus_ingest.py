"""The gold corpus ingests through the REAL path and the denominator holds at the design target
(Story 2.12, FR-54 / SM-3). SQLite, a fake embedder at the port boundary — the real model is never
loaded. The corpus is NOT sampled: all 139 manifest items are run (the design target for the eval).
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apx.adapters.store_postgres.models import Base
from apx.adapters.store_postgres.store import SqlStore
from eval.corpus_source import load_manifest
from eval.harness import ingest_gold_corpus
from tests.embedding_fakes import FakeEmbedder

TENANT, MATTER, WALL = "eval", "gold", "wall"


@pytest.fixture(scope="module")
def ingested() -> tuple[SqlStore, object]:
    """Ingest the full gold corpus once (the expensive step) and share it across the module's
    assertions."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    store = SqlStore(sessionmaker(bind=engine, future=True))
    inv = ingest_gold_corpus(
        store, FakeEmbedder(), tenant=TENANT, matter=MATTER, scope=WALL, actor="eval")
    return store, inv


def test_the_full_gold_corpus_ingests_and_the_denominator_holds(ingested) -> None:  # noqa: ANN001
    _, inv = ingested
    assert len(load_manifest()["items"]) == 139  # the full design target, not a sample
    # SM-3: the denominator is consistent — every submitted unit is in EXACTLY ONE of
    # corpus / register, none lost or double-counted, verified at the full run.
    assert inv.is_consistent()
    assert inv.excluded_as_noise == 0  # the eval corpus carries no filesystem-noise-named files
    assert inv.submitted_pieces == inv.in_corpus + inv.open_register_entries  # AD-38 identity
    # The specific design-target run, pinned so a corpus or pipeline drift is a detectable event:
    # 136 indexed, 2 register (the two 0-byte edge-case files), and the one deliberate content
    # duplicate (doc_dupuis_contrat_DUP) counted ONCE by idempotent identity (AD-8) — 138 of 139.
    assert (inv.in_corpus, inv.open_register_entries, inv.excluded_as_noise) == (136, 2, 0)
    assert inv.submitted_pieces == 138


def test_the_empty_edge_case_files_are_register_entries_by_class(ingested) -> None:  # noqa: ANN001
    # the corpus's edge cases are honestly classified, never silently indexed as empty pièces
    store, _ = ingested
    classes = sorted(e.error_class for e in store.register(MATTER, TENANT, {WALL}))
    assert classes == ["extracted-empty", "unreadable"]


def test_recall_at_the_line_is_deferred_to_a_ranker_not_faked() -> None:
    # SM-2's recall needs a ranker and *the line* (Epic 3/4); the harness RAISES rather than fake a
    # number (no invented target, PRD §7). The merge gate is what makes Epic 4 wire this before it
    # can merge — so the metric that matters (that it runs at all) is guaranteed to.
    from eval.harness import recall_at_the_line
    with pytest.raises(NotImplementedError, match="ranker"):
        recall_at_the_line(object())
