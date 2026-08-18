"""AD-32's own success criterion, asserted through the read surfaces (Story 7.2, C2).

    a restore into an empty installation reproduces a *tenant* whose *denominator*, ranked orders,
    audit sequence and *confidence bounds* are identical

Two of those four were impossible before this story: ``ranking_version``, ``ranked_entry``,
``sampling_run``, ``sampling_run_item`` and ``sampling_verdict`` were absent from the backup, so a
restored *matter* had no ranked order at all and no draw from which a bound could be recomputed —
**while the audit record survived and attested both**. The tamper-evident chain verified perfectly
over a *matter* that no longer existed.

Read back through the product rather than off the rows on purpose. A restore that returns rows and
leaves a read broken is not a restore, and the row-level identity is already asserted, table by
table and driven by the plan, in ``tests/adapters/test_backup_captures_every_table.py``.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from apx.adapters.store_postgres.models import Base
from apx.adapters.store_postgres.store import SqlStore
from apx.core.app.read.sampling import read_sampling_runs
from tests.api.test_ingest_api import _login, _prepare, _reset_state  # noqa: F401 — autouse
from tests.api.test_sampling_api import (
    MATTER,
    TENANT,
    WALL,
    _complete,
    _judge_all,
    _matter,
    _start,
)


def _empty_store(tmp_path: Path) -> SqlStore:
    engine = create_engine(f"sqlite:///{tmp_path / 'restored'}.db", future=True)
    Base.metadata.create_all(engine)
    return SqlStore(sessionmaker(bind=engine, future=True))


def _bound(store: SqlStore) -> tuple[str | None, ...]:
    readings = read_sampling_runs(
        tenant=TENANT, matter=MATTER, scopes={WALL}, store=store,
        config_get=lambda key: store.get_config(TENANT, key))
    assert readings is not None
    return tuple(r.statement_fr for r in readings)


def _restored(tmp_path: Path, monkeypatch):  # noqa: ANN001, ANN202
    """A real *matter* — ingested, ranked, its line cut, one census drawn and completed so the run
    carries a bound — backed up and restored into an empty installation."""
    src, client, _order = _matter(tmp_path, monkeypatch, cut_at_rank=1)
    run = _start(client, sample_size=99)
    _judge_all(client, run, relevant=1)
    _complete(client, run["run_id"])

    dst = _empty_store(tmp_path)
    dst.restore_tenant(src.backup_tenant(TENANT))
    return src, dst


def test_the_denominator_is_identical(tmp_path, monkeypatch) -> None:  # noqa: ANN001
    src, dst = _restored(tmp_path, monkeypatch)
    before = src.inventory(MATTER, TENANT, {WALL})
    after = dst.inventory(MATTER, TENANT, {WALL})
    assert after == before
    assert after.is_consistent() and after.in_corpus > 0


def test_the_ranked_order_and_its_version_are_identical(tmp_path, monkeypatch) -> None:  # noqa: ANN001
    """The one AD-32 names that the backup could not carry. ``read_ranking`` returned ``None`` after
    a restore, which is the same answer this product gives for *out of scope* and for *absent*
    (FR-14) — so the loss was indistinguishable from a wall."""
    src, dst = _restored(tmp_path, monkeypatch)
    before = src.read_ranking(tenant=TENANT, matter=MATTER, scopes={WALL})
    after = dst.read_ranking(tenant=TENANT, matter=MATTER, scopes={WALL})
    assert after is not None, "the restored matter had no ranking version at all"
    assert (after.version_id, after.version_no) == (before.version_id, before.version_no)

    order_before = src.read_ranked_order(tenant=TENANT, matter=MATTER, scopes={WALL})
    order_after = dst.read_ranked_order(tenant=TENANT, matter=MATTER, scopes={WALL})
    assert order_before and order_after
    assert [(e.piece_id, e.rank) for e in order_after] == [
        (e.piece_id, e.rank) for e in order_before]


def test_the_line_survives_as_the_identity_of_its_last_retained_piece(  # noqa: D103
    tmp_path, monkeypatch,  # noqa: ANN001
) -> None:
    """FR-17's line is stored by *pièce* identity, not as an integer, and it lives on
    ``line_placement`` — which points at ``ranking_version``. Both were outside the backup, so the
    triage a firm committed to came back as nothing."""
    src, dst = _restored(tmp_path, monkeypatch)
    before = src.read_current_line(tenant=TENANT, matter=MATTER, scopes={WALL})
    after = dst.read_current_line(tenant=TENANT, matter=MATTER, scopes={WALL})
    assert after.last_retained_piece_id == before.last_retained_piece_id
    assert after.seq == before.seq


def test_the_audit_sequence_is_identical_and_still_verifies(tmp_path, monkeypatch) -> None:  # noqa: ANN001
    src, dst = _restored(tmp_path, monkeypatch)
    before = src.read_audit(MATTER, TENANT, {WALL})
    after = dst.read_audit(MATTER, TENANT, {WALL})
    assert after.verified
    assert after.entries_total == before.entries_total
    assert [(e.seq, e.action) for e in after.entries] == [(e.seq, e.action) for e in before.entries]


def test_the_confidence_bound_is_identical(tmp_path, monkeypatch) -> None:  # noqa: ANN001
    """The sentence a firm says to a judge. The run, its frozen population, its drawn families and
    its verdicts were all outside the backup — so the restored *matter* could not state its own
    result, on a record that went on attesting the draw had happened."""
    src, dst = _restored(tmp_path, monkeypatch)
    before, after = _bound(src), _bound(dst)
    assert after and after[0]
    assert after == before
