"""assign_label / revert_label + the label reads (Story 4.5, FR-40/FR-20/AD-37/AD-22/AD-7).

The per-pièce taxonomy label is an append-only, version-independent ledger: an assignment or a
reversal is a new entry (never an overwrite); the current label is a VIEW (never null — `unlabelled`
by default); an out-of-taxonomy label can never leak; a taxonomy change never silently remaps an
existing label; and the edit is scope-gated and audited. Deterministic SQLite, no network."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apx.adapters.store_postgres.models import AuditRecord, Base, TaxonomyLabelEntry
from apx.adapters.store_postgres.store import ScopeDenied, SqlStore, StaleLabel
from apx.core.app.ingest import IngestionResult
from apx.core.domain.taxonomy_label import UNLABELLED, OutOfTaxonomyLabel


@pytest.fixture
def engine():  # noqa: ANN201
    e = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(e)
    return e


@pytest.fixture
def store(engine) -> SqlStore:  # noqa: ANN001
    s = SqlStore(sessionmaker(bind=engine, future=True))
    s.save(IngestionResult(), scope="w", actor="setup", matter="m", tenant="t", audit=False)
    s.set_config("t", "admin", "taxonomy", ["Contrats", "Jurisprudence"])
    return s


def _entry_count(store: SqlStore) -> int:
    with store._sf() as s:
        return s.scalar(select(func.count()).select_from(TaxonomyLabelEntry))


def _actions(store: SqlStore) -> list[str]:
    with store._sf() as s:
        return list(s.scalars(
            select(AuditRecord.action).where(AuditRecord.tenant == "t").order_by(AuditRecord.seq)))


def test_assign_writes_one_entry_and_one_audit_and_reads_back_as_human_set(store: SqlStore) -> None:
    seq = store.assign_label(
        tenant="t", matter="m", actor="me.durand", piece_id="p1", label="Contrats", scopes={"w"})
    assert seq == 1
    cur = store.read_current_label(tenant="t", matter="m", piece_id="p1", scopes={"w"})
    assert cur.label == "Contrats" and cur.source == "human" and cur.seq == 1
    assert cur.in_current_taxonomy is True
    assert "piece_labelled" in _actions(store)  # audit atomic with the write (AD-22)


def test_an_unlabelled_piece_reads_as_the_sentinel_never_null(store: SqlStore) -> None:
    cur = store.read_current_label(tenant="t", matter="m", piece_id="never-set", scopes={"w"})
    assert cur.label == UNLABELLED and cur.source is None and cur.seq is None
    assert cur.in_current_taxonomy is True  # the sentinel is not "out of taxonomy"


def test_an_out_of_taxonomy_label_can_never_leak(store: SqlStore) -> None:
    with pytest.raises(OutOfTaxonomyLabel):
        store.assign_label(
            tenant="t", matter="m", actor="a", piece_id="p1", label="Autre", scopes={"w"})
    assert _entry_count(store) == 0  # nothing written


def test_unlabelled_is_an_explicit_assignable_value(store: SqlStore) -> None:
    seq = store.assign_label(
        tenant="t", matter="m", actor="a", piece_id="p1", label=UNLABELLED, scopes={"w"})
    assert seq == 1
    cur = store.read_current_label(tenant="t", matter="m", piece_id="p1", scopes={"w"})
    assert cur.label == UNLABELLED and cur.seq == 1  # an explicit unlabelling, not the default


def test_a_second_assign_is_a_new_entry_never_an_overwrite(store: SqlStore) -> None:
    store.assign_label(tenant="t", matter="m", actor="a", piece_id="p1", label="Contrats",
                       scopes={"w"})
    store.assign_label(tenant="t", matter="m", actor="a", piece_id="p1", label="Jurisprudence",
                       scopes={"w"})
    assert _entry_count(store) == 2  # append-only — the first entry is not overwritten
    log = store.read_label_change_log(tenant="t", matter="m", piece_id="p1", scopes={"w"})
    assert [(e.seq, e.label) for e in log] == [(1, "Contrats"), (2, "Jurisprudence")]
    cur = store.read_current_label(tenant="t", matter="m", piece_id="p1", scopes={"w"})
    assert cur.label == "Jurisprudence" and cur.seq == 2


def test_revert_appends_a_new_entry_restoring_a_prior_value(store: SqlStore) -> None:
    store.assign_label(tenant="t", matter="m", actor="a", piece_id="p1", label="Contrats",
                       scopes={"w"})
    store.assign_label(tenant="t", matter="m", actor="a", piece_id="p1", label="Jurisprudence",
                       scopes={"w"})
    new_seq = store.revert_label(
        tenant="t", matter="m", actor="a", piece_id="p1", to_seq=1, scopes={"w"})
    assert new_seq == 3  # a reversal is a NEW entry (AD-7), never a destructive undo
    cur = store.read_current_label(tenant="t", matter="m", piece_id="p1", scopes={"w"})
    assert cur.label == "Contrats" and cur.seq == 3
    log = store.read_label_change_log(tenant="t", matter="m", piece_id="p1", scopes={"w"})
    assert [e.label for e in log] == ["Contrats", "Jurisprudence", "Contrats"]


def test_a_conditional_commit_refuses_a_moved_label(store: SqlStore) -> None:
    store.assign_label(tenant="t", matter="m", actor="a", piece_id="p1", label="Contrats",
                       scopes={"w"})  # seq now 1
    with pytest.raises(StaleLabel):
        # the caller thinks the pièce is still unlabelled (expected_seq=0) but it moved to 1
        store.assign_label(tenant="t", matter="m", actor="b", piece_id="p1", label="Jurisprudence",
                           scopes={"w"}, expected_seq=0)
    assert _entry_count(store) == 1  # nothing written on the stale edit


def test_a_conditional_commit_accepts_the_observed_seq(store: SqlStore) -> None:
    store.assign_label(tenant="t", matter="m", actor="a", piece_id="p1", label="Contrats",
                       scopes={"w"})
    seq = store.assign_label(
        tenant="t", matter="m", actor="a", piece_id="p1", label="Jurisprudence",
        scopes={"w"}, expected_seq=1)
    assert seq == 2


def test_a_label_edit_is_scope_gated_and_non_disclosing(store: SqlStore) -> None:
    with pytest.raises(ScopeDenied):
        store.assign_label(tenant="t", matter="m", actor="a", piece_id="p1", label="Contrats",
                           scopes={"other"})
    # a read out of scope is indistinguishable from an absent matter (None), never a disclosure
    assert store.read_current_label(tenant="t", matter="m", piece_id="p1", scopes={"other"}) is None
    assert store.read_label_change_log(tenant="t", matter="m", piece_id="p1", scopes={"other"}) \
        is None


def test_a_taxonomy_change_never_silently_remaps_an_existing_label(store: SqlStore) -> None:
    store.assign_label(tenant="t", matter="m", actor="a", piece_id="p1", label="Contrats",
                       scopes={"w"})
    # the admin drops "Contrats" from the taxonomy (config-as-data, AD-25)
    store.set_config("t", "admin", "taxonomy", ["Jurisprudence"])
    cur = store.read_current_label(tenant="t", matter="m", piece_id="p1", scopes={"w"})
    assert cur.label == "Contrats"           # kept — not nulled, not remapped
    assert cur.in_current_taxonomy is False  # shown as out-of-current-taxonomy (drives a worklist)
    assert _entry_count(store) == 1          # the label ledger was not touched by the config change


def test_coverage_is_zeroed_when_the_matter_has_no_ranking(store: SqlStore) -> None:
    cov = store.read_label_coverage(tenant="t", matter="m", scopes={"w"})
    assert cov is not None
    assert (cov.total, cov.labelled, cov.unlabelled, cov.out_of_taxonomy, cov.without_label) \
        == (0, 0, 0, 0, 0)
