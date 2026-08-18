"""A *tenant* backup reaches every table the model has — proven over the model, not over a list.

Story 7.2 (retro action **C2**). The list that used to say what a backup captured named 20 of the
model's 35 tables. Nine tenant-scoped tables were missing — ``ranking_version``, ``ranked_entry``,
``sampling_run``, ``validation_act``, ``register_override``, ``case_theory_version``,
``piece_open``, ``import_job``, ``artefact_stamp`` — and three more one layer down, keyed by a
parent rather than by *tenant* and so invisible to the question the list was asking:
``import_unit``, ``sampling_run_item``, ``sampling_verdict``.

A restore therefore returned a *matter* with no ranked order, no *sampling run* and therefore no
*confidence bound*, and no *validation act* — **while the audit record survived and attested every
one of them**.

The tests here are driven by :func:`backup_plan`, so a table added to the model tomorrow is covered
by them without anybody editing this file. That is the whole difference: the property is *every
table*, and a test that named the tables would have exactly the weakness the tuple had.
"""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import CheckConstraint, Table, create_engine
from sqlalchemy.orm import sessionmaker

from apx.adapters.store_postgres.backup_plan import _WRITTEN, backup_plan
from apx.adapters.store_postgres.models import EMBEDDING_DIM, Base
from apx.adapters.store_postgres.store import SqlStore

TENANT, OTHER = "cabinet", "autre-cabinet"

#: The two tables the synthetic seed leaves alone, because ``provision_tenant`` fills them for real
#: and ``restore_tenant`` RE-VERIFIES the AD-43 chain inside its transaction — a synthetic entry
#: would be rejected as a tampered record, which is the guard working. They are still asserted
#: non-empty below, so the coverage claim stays total.
_SEEDED_FOR_REAL = ("audit_record", "audit_chain_head")

#: The link the model does not declare, mirroring ``backup_plan._WRITTEN``. Asserted against it, so
#: a second hand-written predicate cannot appear in the product without this seed noticing.
_UNDECLARED_LINKS = {("user_scope", "user_id"): ("user_account", "id")}

#: CHECK constraints the seed cannot satisfy by reading an ``IN`` list — a *paired* invariant, where
#: one column's legal value depends on another's. Written out, because guessing at one would make
#: the seed silently skip the table it guarded.
_PAIRED = {
    # (piece_date IS NOT NULL) = (piece_date_status = 'determined'); the seed fills the date.
    ("piece", "piece_date_status"): "determined",
}


def _categorical() -> dict[tuple[str, str], str]:
    """The first legal value of every column a CHECK pins to an ``IN`` list, read off the model."""
    legal: dict[tuple[str, str], str] = {}
    for table in Base.metadata.sorted_tables:
        for constraint in table.constraints:
            if not isinstance(constraint, CheckConstraint):
                continue
            found = re.search(
                r"(\w+)\s+in\s*\(([^)]*)\)", str(constraint.sqltext), re.IGNORECASE)
            if found is None:
                continue
            values = re.findall(r"'([^']*)'", found.group(2))
            if values:
                legal[(table.name, found.group(1))] = values[0]
    return legal


_CATEGORICAL = _categorical()


def _store(tmp_path, name: str) -> SqlStore:  # noqa: ANN001
    engine = create_engine(f"sqlite:///{tmp_path / name}.db", future=True)
    Base.metadata.create_all(engine)
    return SqlStore(sessionmaker(bind=engine, future=True))


def _value(tenant: str, table: str, col) -> object:  # noqa: ANN001
    """A value of the column's own type. An unknown type on a NOT NULL column raises rather than
    being skipped: a seed that quietly leaves a column out is how a round-trip test passes over the
    thing it was written to check."""
    pinned = _PAIRED.get((table, col.name), _CATEGORICAL.get((table, col.name)))
    if pinned is not None:
        return pinned
    kind = type(col.type).__name__
    if kind == "Halfvec":
        return [0.0] * EMBEDDING_DIM
    if kind == "Boolean":
        return False
    if kind == "Date":
        return date(2026, 1, 1)
    if kind == "DateTime":
        return datetime(2026, 1, 1, tzinfo=UTC)
    if kind == "Float":
        return 0.5
    if kind == "Integer":
        return 1
    if kind in ("String", "Text", "EncryptedText"):
        value = f"{tenant}.{table}.{col.name}"   # tenant-qualified: two firms coexist
        length = getattr(col.type, "length", None)
        if length is not None and len(value) > length:
            value = hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]
        return value
    if col.nullable:
        return None
    raise AssertionError(
        f"the seed cannot fill {table}.{col.name} ({kind}) and the column is NOT NULL — teach it "
        "the type rather than letting the table go untested")


def _synthetic_row(table: Table, planted: dict[str, dict], tenant: str) -> dict:
    row: dict[str, object] = {}
    for col in table.columns:
        if col.name == "tenant":
            row[col.name] = tenant
            continue
        link = next(iter(col.foreign_keys), None)
        if link is not None and link.column.table.name in planted:
            row[col.name] = planted[link.column.table.name][link.column.name]
            continue
        undeclared = _UNDECLARED_LINKS.get((table.name, col.name))
        if undeclared is not None and undeclared[0] in planted:
            row[col.name] = planted[undeclared[0]][undeclared[1]]
            continue
        row[col.name] = _value(tenant, table.name, col)
    return row


def _seed_everything(store: SqlStore, tenant: str) -> None:
    """One real tenant, then one synthetic row in every other captured table — in plan order, so a
    child's foreign key carries its parent's planted value."""
    store.provision_tenant(tenant, f"admin@{tenant}.fr", "pw12345678", "Admin", {"w"}, ["concl"])
    planted: dict[str, dict] = {}
    with store._sf() as session, session.begin():
        conn = session.connection()
        for cap in backup_plan():
            if cap.table in _SEEDED_FOR_REAL:
                continue
            table = Base.metadata.tables[cap.table]
            row = _synthetic_row(table, planted, tenant)
            conn.execute(table.insert(), row)
            planted[cap.table] = row


def _rows(store: SqlStore, tenant: str) -> dict[str, list]:
    return {name: sorted(repr(sorted(r.items())) for r in rows)
            for name, rows in store.backup_tenant(tenant).tables.items()}


# ── the capture is total ──────────────────────────────────────────────────────────────────────

def test_the_backup_carries_a_row_from_every_table_in_the_model(tmp_path) -> None:  # noqa: ANN001
    """The defect, stated as the property it violated. Before this story the assertion below failed
    on twelve tables at once, and nothing else in the suite said a word about it."""
    store = _store(tmp_path, "src")
    _seed_everything(store, TENANT)

    captured = store.backup_tenant(TENANT).tables
    assert set(captured) == {cap.table for cap in backup_plan()}
    empty = sorted(name for name, rows in captured.items() if not rows)
    assert not empty, f"the backup reached no row of: {empty}"


def test_the_seed_and_the_plan_cannot_drift_apart() -> None:
    """The one link the model does not declare is written in two places — the product's predicate
    and this seed's — and they must name the same tables, or a table would be captured in
    production and untested here (or the reverse)."""
    assert {table for table, _ in _UNDECLARED_LINKS} == set(_WRITTEN)


def test_the_plan_refuses_a_model_it_cannot_classify() -> None:
    """Fail closed. A table with no tenant, no foreign key and no written reason stops the backup —
    it does not get dropped from it, which is precisely how the twelve went missing."""
    from sqlalchemy import Column, MetaData, String
    from sqlalchemy import Table as SaTable

    md = MetaData()
    SaTable("piece", md, Column("id", String, primary_key=True), Column("tenant", String))
    SaTable("orphan", md, Column("id", String, primary_key=True), Column("note", String))
    with pytest.raises(Exception, match="orphan"):
        backup_plan(md)


# ── and it round-trips, every table, into an empty store ──────────────────────────────────────

def test_every_captured_table_returns_identically_after_a_restore(tmp_path) -> None:  # noqa: ANN001
    """AD-32's exercised restore, over the whole model rather than over the four tables somebody
    thought to check. Compared table by table, driven by the plan."""
    src = _store(tmp_path, "src")
    _seed_everything(src, TENANT)
    before = _rows(src, TENANT)
    # The denominator is pinned to the plan, not to whatever the backup happened to carry. Without
    # this line the comparison shrinks with the defect: a backup that captured 20 tables and a
    # re-backup of the restore that captured the same 20 agree perfectly, which is the wrong
    # referent — the flattering side of exactly the comparison this story exists to fix.
    assert set(before) == {cap.table for cap in backup_plan()}
    for name in _SEEDED_FOR_REAL:
        assert before[name], f"{name} must be seeded for real — the chain is re-verified on restore"

    dst = _store(tmp_path, "dst")
    dst.restore_tenant(src.backup_tenant(TENANT))

    after = _rows(dst, TENANT)
    assert set(after) == set(before)
    for name in sorted(before):
        assert after[name] == before[name], f"{name} did not survive the round trip"


def test_the_capture_never_reaches_another_tenant(tmp_path) -> None:  # noqa: ANN001
    """Every predicate the plan derives is tenant-bound, including the ones that reach their tenant
    through a parent. A child captured by an unbound predicate would put one firm's drawn families
    and verdicts into another firm's backup."""
    store = _store(tmp_path, "both")
    _seed_everything(store, TENANT)
    _seed_everything(store, OTHER)

    mine = store.backup_tenant(TENANT).tables
    theirs = store.backup_tenant(OTHER).tables
    assert set(mine) == {cap.table for cap in backup_plan()}       # the denominator, pinned
    for name in sorted(mine):
        assert mine[name], name
        overlap = [row for row in mine[name] if row in theirs[name]]
        assert not overlap, f"{name}: {len(overlap)} row(s) appear in BOTH tenants' backups"
