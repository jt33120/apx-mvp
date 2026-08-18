"""An act whose record cannot be written does not happen (Story 5.9, FR-53 AC-1 / AD-22).

FR-53's first consequence names six acts and names its own instrument: *"moving the line, committing
an override, completing a sampling run, performing a validation act, granting a scope and changing
configuration are each atomic with their record: either both happen or neither does. **Asserted by
test with the audit store made read-only mid-action.**"*

Nothing in the suite had ever failed an audit write. Every test that said *atomic* asserted the
happy path — the entry is there beside the write — which is the CONVERSE proposition and would pass
unchanged on an implementation that committed the act and swallowed the audit failure.

**The database refuses, not a Python double.** ``_read_only_audit_store`` installs SQLite triggers
that abort any INSERT into ``audit_record`` and any INSERT or UPDATE of ``audit_chain_head``. No
application code is patched, no method is wrapped: the store is simply unable to write the record,
which is the condition the requirement describes. What each test then asserts is the NEGATIVE half —
the ledger row, the placement, the verdict, the grant and the configuration value must be **absent**
afterwards — because "the act raised" is satisfied by an act that raised after committing.

A second harness, ``_unwritable_audit_store``, fails those same statements with a non-integrity
database error, which is what distinguishes *the store cannot be written at all* (FR-53's fourth
consequence: refuse) from *the store is busy* (AD-22's named trap: wait). The first must produce
``AuditUnwritable``; the second must not.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime

import pytest
from sqlalchemy import Engine, create_engine, event, func, select, text
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apx.adapters.store_postgres.models import (
    AuditRecord,
    Base,
    LinePlacement,
    RegisterOverride,
    TenantSetting,
    UserScope,
    ValidationActEntry,
)
from apx.adapters.store_postgres.store import AuditUnwritable, SqlStore
from apx.core.app.ingest import IngestedFailure, IngestedPiece, IngestionResult
from apx.core.domain.cascade import Band, CascadeResult, PieceJudgement, Stage
from apx.core.domain.config import CascadeConfig
from apx.core.domain.failures import ErrorClass
from apx.core.domain.ranking import RankingIdentityInputs, assemble_identity, rank_cascade

TENANT, MATTER, WALL, ACTOR = "cabinet", "affaire-a", "mur-a", "Me Dupont"

_CFG = CascadeConfig(uncertain_low=0.35, uncertain_high=0.65, calibration_sample=20,
                     stage3_max_share=0.5)

#: The statements a read-only audit store refuses. Both tables, because "the record cannot be
#: written" is not only the entry: the allocator advances in the same transaction, and a harness
#: that blocked one and not the other would leave a path where the act could still complete.
_AUDIT_TABLES = ("audit_record", "audit_chain_head")


def _is_audit_write(statement: str) -> bool:
    """A WRITE against an audit table. Reads are deliberately left alone: *read-only* is the state
    under test, and a harness that also blocked the allocator's ``SELECT … FOR UPDATE`` would be
    testing an unreachable database rather than an unwritable record."""
    lowered = statement.lower().lstrip()
    if not lowered.startswith(("insert", "update", "delete")):
        return False
    return any(table in lowered for table in _AUDIT_TABLES)


# ── the harnesses ─────────────────────────────────────────────────────────────────────────────

@contextmanager
def _read_only_audit_store(engine: Engine) -> Iterator[None]:
    """Make the audit store read-only **in the database**, for the duration.

    SQLite triggers raising ``ABORT``: the write is refused by the storage engine itself, so what is
    under test is the store's real transaction boundary and not a stub standing in for it."""
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TRIGGER apx_ro_audit_insert BEFORE INSERT ON audit_record "
            "BEGIN SELECT RAISE(ABORT, 'audit store is read-only'); END"))
        conn.execute(text(
            "CREATE TRIGGER apx_ro_head_insert BEFORE INSERT ON audit_chain_head "
            "BEGIN SELECT RAISE(ABORT, 'audit store is read-only'); END"))
        conn.execute(text(
            "CREATE TRIGGER apx_ro_head_update BEFORE UPDATE ON audit_chain_head "
            "BEGIN SELECT RAISE(ABORT, 'audit store is read-only'); END"))
    try:
        yield
    finally:
        with engine.begin() as conn:
            for name in ("apx_ro_audit_insert", "apx_ro_head_insert", "apx_ro_head_update"):
                conn.execute(text(f"DROP TRIGGER IF EXISTS {name}"))


@contextmanager
def _unwritable_audit_store(engine: Engine) -> Iterator[None]:
    """Fail the audit statements with a NON-integrity database error — the shape of a revoked
    INSERT, a read-only tablespace or a full disk, as opposed to a collision or a lock wait."""
    def _refuse(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001, ANN202
        if _is_audit_write(statement):
            raise OperationalError(statement, parameters, Exception("audit store is unwritable"))

    event.listen(engine, "before_cursor_execute", _refuse)
    try:
        yield
    finally:
        event.remove(engine, "before_cursor_execute", _refuse)


# ── the arrangement ───────────────────────────────────────────────────────────────────────────

def _identity():  # noqa: ANN202
    inputs = RankingIdentityInputs(
        case_theory_version_id=None, model_provider="mistral",
        model_endpoint="https://api.mistral.ai/v1", model_name="mistral-small-latest",
        prompt_version="cascade-question-v1", temperature=0.0, sampling={"top_p": 1.0},
        embedder_model_id="bge-m3", embedder_model_version="1.5",
        chunking_config_version="chunk-v1", schema_version="slice-a")
    return assemble_identity(
        inputs=inputs, basis="intrinsic", uncertain_low=0.35, uncertain_high=0.65,
        calibration_sample=20, stage3_max_share=0.5)


def _judged(pid: str, band: Band, score: float) -> PieceJudgement:
    return PieceJudgement.judged(piece_id=pid, family_id=f"fam-{pid}", is_representative=True,
                                 stage_reached=Stage.STAGE_2, band=band, score=score)


def _order(pairs):  # noqa: ANN001, ANN202
    judgements = [_judged(pid, band, score) for pid, band, score in pairs]
    families = {j.family_id: (j.piece_id,) for j in judgements}
    return rank_cascade(CascadeResult(
        judgements=tuple(judgements), families=families, unscored=(), stage3_share=0.5,
        over_stage3_floor=False, basis="intrinsic"), _CFG)


def _piece(piece_id: str) -> IngestedPiece:
    """One ingested *pièce*, carrying the id the ranking names it by."""
    return IngestedPiece(
        id=piece_id, matter=MATTER, tenant=TENANT, content_hash=f"hash-{piece_id}",
        text_key=f"key-{piece_id}", provenance_path=f"/dossier/{piece_id}.pdf",
        custodian="Me Martin", extraction_method="native", extractor_version="1",
        schema_version="slice-a", ingestion_timestamp=datetime(2026, 8, 1, tzinfo=UTC),
        full_text=f"texte de la pièce {piece_id}", text_version="1")


@pytest.fixture
def engine() -> Engine:
    e = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(e)
    return e


@pytest.fixture
def store(engine: Engine) -> SqlStore:
    """A matter with a corpus, a ranking, a placed line, an open register entry, a user, and a
    started, fully-judged sampling run — everything the six acts need, all committed BEFORE the
    audit store is made read-only."""
    store = SqlStore(sessionmaker(bind=engine, future=True))
    store.save(
        IngestionResult(
            # The three pièces the ranking below is over. A validation act reads the triage table,
            # which refuses a dossier smaller than its own ranking (FR-58) — so a ranking over
            # pièces the corpus does not hold is not an arrangement, it is a different bug.
            pieces=[_piece(pid) for pid in ("rel", "mid", "dis")],
            failures=[IngestedFailure(
                filename="scelle.pdf", submitted_path="/d/scelle.pdf", matter=MATTER,
                tenant=TENANT, error_class=ErrorClass.PASSWORD_PROTECTED, detail="mot de passe",
                custodian="Me Martin")]),
        scope=WALL, actor=ACTOR, matter=MATTER, tenant=TENANT, audit=False)
    store.record_ranking(
        tenant=TENANT, matter=MATTER, actor=ACTOR, identity=_identity(),
        order=_order([
            ("rel", Band.CONFIDENT_RELEVANT, 0.9),
            ("mid", Band.UNCERTAIN, 0.5),
            ("dis", Band.CONFIDENT_DISCARD, 0.1),
        ]))
    store.place_line(tenant=TENANT, matter=MATTER, actor=ACTOR, scopes={WALL})
    store.create_user(TENANT, "greffe@cabinet.fr", "motdepasse", "Le greffe", set())
    run = store.start_sampling_run(
        tenant=TENANT, matter=MATTER, actor=ACTOR, scopes={WALL}, sample_size=1)
    assert run is not None, "the arrangement needs a real sampling run to complete"
    for drawn in run.drawn:
        store.record_sampling_verdict(
            tenant=TENANT, matter=MATTER, actor=ACTOR, scopes={WALL}, run_id=run.run_id,
            family_id=drawn.unit.family_id, relevant=False)
    store.open_run_id = run.run_id  # type: ignore[attr-defined]
    return store


def _count(store: SqlStore, model: object) -> int:
    with store._sf() as session:
        return int(session.scalar(select(func.count()).select_from(model)) or 0)


def _user_id(store: SqlStore) -> str:
    users = store.list_users(TENANT)
    return next(u.id for u in users if u.email == "greffe@cabinet.fr")


def _open_entry_id(store: SqlStore) -> str:
    return next(
        e.id for e in store.register_all(TENANT, {WALL}, is_admin=True)
        if e.resolution_state == "open")


def _line(store: SqlStore):  # noqa: ANN202
    return store.read_current_line(tenant=TENANT, matter=MATTER, scopes={WALL})


# ── AC-1 — the six acts FR-53 names, each with the audit store read-only ───────────────────────

def test_moving_the_line_leaves_no_placement_when_the_record_cannot_be_written(
    engine: Engine, store: SqlStore
) -> None:
    current = _line(store)
    assert current is not None
    before = _count(store, LinePlacement)
    with _read_only_audit_store(engine), pytest.raises(SQLAlchemyError):
        store.move_line(
            tenant=TENANT, matter=MATTER, actor=ACTOR, scopes={WALL},
            last_retained_piece_id="mid", expected_seq=current.seq,
            priced_statement="2 pièces changent de côté")
    assert _count(store, LinePlacement) == before          # nothing appended
    assert _line(store).last_retained_piece_id == current.last_retained_piece_id  # nothing moved


def test_an_override_leaves_no_ledger_row_when_the_record_cannot_be_written(
    engine: Engine, store: SqlStore
) -> None:
    entry_id = _open_entry_id(store)
    before = _count(store, RegisterOverride)
    with _read_only_audit_store(engine), pytest.raises(SQLAlchemyError):
        store.override_register_entry(
            entry_id=entry_id, tenant=TENANT, actor=ACTOR, scopes={WALL}, is_admin=True,
            reason="le scellé restera fermé, décision du bâtonnier")
    assert _count(store, RegisterOverride) == before
    # AND the entry it would have closed is still OPEN — the override's whole effect is undone
    assert _open_entry_id(store) == entry_id


def test_completing_a_sampling_run_leaves_it_open_when_the_record_cannot_be_written(
    engine: Engine, store: SqlStore
) -> None:
    run_id = store.open_run_id  # type: ignore[attr-defined]
    with _read_only_audit_store(engine), pytest.raises(SQLAlchemyError):
        store.complete_sampling_run(
            tenant=TENANT, matter=MATTER, actor=ACTOR, scopes={WALL}, run_id=run_id)
    after = store.read_sampling_run(
        tenant=TENANT, matter=MATTER, scopes={WALL}, run_id=run_id)
    assert after is not None
    # The run is the one act of the six whose row already exists: what must not happen is the
    # TRANSITION. A completed run carries a bound, and a bound with no audit entry behind it is
    # exactly the statistical claim FR-23 refuses to let anyone make.
    assert after.status != "completed"
    # ... and no bound: a prevalence bound with no audit entry behind it is exactly the
    # statistical claim FR-23 refuses to let anybody make.
    assert after.prevalence_upper is None and after.count_upper is None


def test_a_validation_act_leaves_no_ledger_entry_when_the_record_cannot_be_written(
    engine: Engine, store: SqlStore
) -> None:
    before = _count(store, ValidationActEntry)
    with _read_only_audit_store(engine), pytest.raises(SQLAlchemyError):
        store.validate_pieces(
            tenant=TENANT, matter=MATTER, actor=ACTOR, piece_ids=["rel"], scopes={WALL},
            version_no=1)
    assert _count(store, ValidationActEntry) == before
    assert store.read_validation_log(tenant=TENANT, matter=MATTER, scopes={WALL}) == ()


def test_granting_a_scope_grants_nothing_when_the_record_cannot_be_written(
    engine: Engine, store: SqlStore
) -> None:
    user_id = _user_id(store)
    before = _count(store, UserScope)
    with _read_only_audit_store(engine), pytest.raises(SQLAlchemyError):
        store.grant_scope(TENANT, ACTOR, user_id, WALL)
    assert _count(store, UserScope) == before
    assert WALL not in store.scopes_for(user_id)


def test_changing_configuration_changes_nothing_when_the_record_cannot_be_written(
    engine: Engine, store: SqlStore
) -> None:
    before = store.get_config(TENANT, "backup_interval_hours")
    assert before != 999
    with _read_only_audit_store(engine), pytest.raises(SQLAlchemyError):
        store.set_config(TENANT, ACTOR, "backup_interval_hours", 999)
    assert store.get_config(TENANT, "backup_interval_hours") == before
    # …and no setting ROW was written. The disjunction this replaced ("no row OR the value is
    # unchanged") could not fail: its second arm is the line above it, so the assertion held
    # whatever the row did — a tautology wearing the shape of a check (review, confirmed).
    with store._sf() as session:
        rows = session.scalars(
            select(TenantSetting).where(TenantSetting.key == "backup_interval_hours")).all()
    assert not rows, "a refused configuration change left a setting row behind"


def test_no_audit_entry_survives_any_of_the_six(engine: Engine, store: SqlStore) -> None:
    """The other half of atomicity, and the one a happy-path test cannot see: not a single entry is
    appended by six refused acts. A partial write here would be a record of acts that did not
    happen — the mirror image of the acts-with-no-record this story exists to prevent."""
    before = _count(store, AuditRecord)
    user_id, entry_id, current = _user_id(store), _open_entry_id(store), _line(store)
    run_id = store.open_run_id  # type: ignore[attr-defined]
    with _read_only_audit_store(engine):
        for act in (
            lambda: store.move_line(
                tenant=TENANT, matter=MATTER, actor=ACTOR, scopes={WALL},
                last_retained_piece_id="mid", expected_seq=current.seq,
                priced_statement="2 pièces changent de côté"),
            lambda: store.override_register_entry(
                entry_id=entry_id, tenant=TENANT, actor=ACTOR, scopes={WALL}, is_admin=True,
                reason="décision motivée"),
            lambda: store.complete_sampling_run(
                tenant=TENANT, matter=MATTER, actor=ACTOR, scopes={WALL}, run_id=run_id),
            lambda: store.validate_pieces(
                tenant=TENANT, matter=MATTER, actor=ACTOR, piece_ids=["rel"], scopes={WALL},
                version_no=1),
            lambda: store.grant_scope(TENANT, ACTOR, user_id, WALL),
            lambda: store.set_config(TENANT, ACTOR, "backup_interval_hours", 999),
        ):
            with pytest.raises(SQLAlchemyError):
                act()
    assert _count(store, AuditRecord) == before


# ── AC-2 — a refusal, and a wait, are not the same state (AD-22's named trap) ──────────────────

def test_an_unwritable_audit_store_refuses_the_act_by_name(
    engine: Engine, store: SqlStore
) -> None:
    """A non-integrity failure on an audit statement is FR-53's fourth consequence: the store cannot
    be written at all, so the act is refused — by a named exception the boundary can turn into a
    503, rather than a generic error that reads as *the server broke*."""
    with _unwritable_audit_store(engine), pytest.raises(AuditUnwritable):
        store.grant_scope(TENANT, ACTOR, _user_id(store), WALL)
    assert WALL not in store.scopes_for(_user_id(store))


def test_contention_is_not_an_unwritable_store(engine: Engine, store: SqlStore) -> None:
    """AD-22 in as many words: *a lock timeout or write contention is not "cannot be written at all"
    and does not open that escape*. Story 5.5 added the head-row lock precisely so two writers queue
    instead of one dying; a classification that called that queue an unwritable store would turn
    ordinary busy-ness into a product-wide refusal — the inversion of the rule, not the rule."""
    def _busy(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001, ANN202
        if "audit_record" in statement.lower():
            raise OperationalError(
                statement, parameters, Exception("database is locked"))

    event.listen(engine, "before_cursor_execute", _busy)
    try:
        with pytest.raises(OperationalError) as caught:
            store.grant_scope(TENANT, ACTOR, _user_id(store), WALL)
    finally:
        event.remove(engine, "before_cursor_execute", _busy)
    assert not isinstance(caught.value, AuditUnwritable)


def test_a_business_constraint_keeps_its_own_identity(engine: Engine, store: SqlStore) -> None:
    """A failure on a statement that is NOT an audit table is somebody else's bug. Dressing it as an
    unwritable record would make an ordinary constraint violation read as a tamper alarm."""
    def _fail_business(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001, ANN202
        if "insert into user_scope" in statement.lower():
            raise OperationalError(statement, parameters, Exception("disk full"))

    event.listen(engine, "before_cursor_execute", _fail_business)
    try:
        with pytest.raises(OperationalError) as caught:
            store.grant_scope(TENANT, ACTOR, _user_id(store), WALL)
    finally:
        event.remove(engine, "before_cursor_execute", _fail_business)
    assert not isinstance(caught.value, AuditUnwritable)


def test_a_read_still_answers_while_the_audit_store_is_unwritable(
    engine: Engine, store: SqlStore
) -> None:
    """FR-53: *read-only functions may continue*. The refusal is scoped to the acts that must record
    themselves; a product that stopped answering questions because it could not write would have
    turned a durability condition into an outage."""
    with _unwritable_audit_store(engine):
        line = store.read_current_line(tenant=TENANT, matter=MATTER, scopes={WALL})
        assert line is not None and line.last_retained_piece_id
        assert store.get_config(TENANT, "backup_interval_hours")
        assert store.list_users(TENANT)
