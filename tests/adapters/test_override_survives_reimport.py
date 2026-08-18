"""An *override* is a person's decision, and neither a re-import nor a count may undo it.

Retro action **B2** — the Epic-5 retrospective's re-review of story 5.6 by the adversarial
fleet. Defects H1 and H2, both reproduced by hand before this file was written.

**H2:** ``save`` merged every submitted failure back as ``open``, so re-importing the same folder
turned ``overridden`` into ``open`` again — no audit entry, no conditional commit, and nothing on
any surface to show that a signed decision had been reversed. Story 5.6's review considered exactly
this question and placed its guard on ``retry_failure``, the one route it walked.

**H1 (the half that lives down here):** ``unknown_cardinality_entries`` counted only the *open*
unopened containers, so an override on one took the count to zero and every surface stopped saying
*contents unknown* — the qualification disappeared at the moment somebody decided to live without
the archive, which is the moment it is worth the most.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apx.adapters.store_postgres.models import AuditRecord, Base, Failure
from apx.adapters.store_postgres.store import SqlStore, _failure_id
from apx.core.app.ingest import IngestedFailure, IngestedPiece, IngestionResult
from apx.core.domain.failures import ErrorClass

TENANT, MATTER, WALL, ACTOR = "cabinet", "affaire-a", "mur-a", "Me Dupont"
SEALED = "/dossier/scelle.pdf"


def _piece(pid: str) -> IngestedPiece:
    return IngestedPiece(
        id=pid, matter=MATTER, tenant=TENANT, content_hash=f"h-{pid}", text_key=f"t-{pid}",
        provenance_path=f"/dossier/{pid}.pdf", custodian="Me Martin", extraction_method="pdf",
        extractor_version="1", schema_version="slice-a",
        ingestion_timestamp=datetime(2026, 8, 1, tzinfo=UTC),
        full_text=f"texte {pid}", text_version="1")


def _result(error_class: ErrorClass = ErrorClass.PASSWORD_PROTECTED) -> IngestionResult:
    """The same folder, submitted again: one readable pièce and one document that fails."""
    return IngestionResult(
        pieces=[_piece("lisible")],
        failures=[IngestedFailure(
            filename="scelle.pdf", submitted_path=SEALED, matter=MATTER, tenant=TENANT,
            error_class=error_class, detail="mot de passe", custodian="Me Martin")])


@pytest.fixture
def store() -> SqlStore:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return SqlStore(sessionmaker(bind=engine, future=True))


def _states(store: SqlStore) -> dict[str, str]:
    return {e.submitted_path: e.resolution_state
            for e in store.register_all(TENANT, {WALL}, is_admin=False)}


def _audit_actions(store: SqlStore) -> list[str]:
    with store._sf() as session:
        return [a.action for a in session.scalars(select(AuditRecord)).all()]


# ── B2/H2 — a re-import never reverses an override ────────────────────────────────────────────

def test_a_re_import_does_not_reopen_an_overridden_entry(store: SqlStore) -> None:
    """The defect, end to end. A person wrote a reason and closed the entry; the folder is dropped
    on the tool again and the decision is still there."""
    store.save(_result(), scope=WALL, actor=ACTOR, matter=MATTER, tenant=TENANT)
    entry_id = _failure_id(TENANT, MATTER, SEALED)
    assert store.override_register_entry(
        entry_id=entry_id, tenant=TENANT, actor=ACTOR, scopes={WALL},
        reason="scellé restitué au greffe, le client renonce") == "overridden"

    before = len(_audit_actions(store))
    store.save(_result(), scope=WALL, actor=ACTOR, matter=MATTER, tenant=TENANT)

    assert _states(store)[SEALED] == "overridden", "a re-import reversed a signed decision"
    # and it did so SILENTLY: the only new entry is the ingest itself, never a reversal
    assert _audit_actions(store)[before:] == ["ingest"]


def test_a_re_import_changes_nothing_at_all_about_an_overridden_entry(store: SqlStore) -> None:
    """Not merely the state. The entry records what failed and why; an override closes it over
    THAT fact, and the reason a person wrote attaches to it. A re-import that rewrote the class
    underneath the decision would leave the reason pointing at something else."""
    store.save(_result(), scope=WALL, actor=ACTOR, matter=MATTER, tenant=TENANT)
    entry_id = _failure_id(TENANT, MATTER, SEALED)
    store.override_register_entry(
        entry_id=entry_id, tenant=TENANT, actor=ACTOR, scopes={WALL},
        reason="scellé restitué au greffe, le client renonce")
    with store._sf() as session:
        row = session.get(Failure, entry_id)
        was = (row.error_class, row.cardinality, row.detail, row.timestamp)

    # the same document, failing DIFFERENTLY this time
    store.save(
        _result(ErrorClass.CORRUPT_FILE), scope=WALL, actor=ACTOR, matter=MATTER, tenant=TENANT)

    with store._sf() as session:
        row = session.get(Failure, entry_id)
        assert (row.error_class, row.cardinality, row.detail, row.timestamp) == was


def test_a_re_import_still_refreshes_an_OPEN_entry(store: SqlStore) -> None:
    """The unchanged half, pinned so the guard cannot be widened by accident. An `open` entry is
    still the register's live report of what a document is doing, and a re-import refreshes it."""
    store.save(_result(), scope=WALL, actor=ACTOR, matter=MATTER, tenant=TENANT)
    store.save(
        _result(ErrorClass.CORRUPT_FILE), scope=WALL, actor=ACTOR, matter=MATTER, tenant=TENANT)
    with store._sf() as session:
        row = session.get(Failure, _failure_id(TENANT, MATTER, SEALED))
    assert row.resolution_state == "open"
    assert row.error_class == str(ErrorClass.CORRUPT_FILE)


def test_the_denominator_still_reconciles_after_a_re_import(store: SqlStore) -> None:
    """SM-3, over the sequence that broke it. The override was being counted as `open` again, so
    `overridden_register_entries` fell to zero while the watermark stayed — the identity held only
    because the watermark is recomputed from the same wrong counts."""
    store.save(_result(), scope=WALL, actor=ACTOR, matter=MATTER, tenant=TENANT)
    store.override_register_entry(
        entry_id=_failure_id(TENANT, MATTER, SEALED), tenant=TENANT, actor=ACTOR, scopes={WALL},
        reason="scellé restitué au greffe")
    store.save(_result(), scope=WALL, actor=ACTOR, matter=MATTER, tenant=TENANT)

    inv = store.inventory(MATTER, TENANT, {WALL})
    assert inv.is_consistent()
    assert inv.overridden_register_entries == 1
    assert inv.open_register_entries == 0
    assert inv.submitted_pieces == 2


# ── B2/H1 — an override does not make an archive's contents known ─────────────────────────────

def _with_unopened_container(store: SqlStore) -> str:
    """One readable pièce and one archive nobody could open — an entry standing for an UNKNOWN
    number of pièces (AD-38)."""
    result = IngestionResult(
        pieces=[_piece("lisible")],
        failures=[IngestedFailure(
            filename="archive.zip", submitted_path="/dossier/archive.zip", matter=MATTER,
            tenant=TENANT, error_class=ErrorClass.CONTAINER_UNOPENABLE,
            detail="profondeur maximale atteinte", custodian="Me Martin")])
    store.save(result, scope=WALL, actor=ACTOR, matter=MATTER, tenant=TENANT)
    return _failure_id(TENANT, MATTER, "/dossier/archive.zip")


def test_an_override_does_not_make_the_contents_known(store: SqlStore) -> None:
    """The count survives the decision. Before this story it went to zero, and with it every
    surface's *"dont N au contenu inconnu"* — so the strongest claim the product makes got quieter
    at the exact moment a firm decided to live without an archive of unknown size."""
    entry_id = _with_unopened_container(store)
    assert store.inventory(MATTER, TENANT, {WALL}).unknown_cardinality_entries == 1

    store.override_register_entry(
        entry_id=entry_id, tenant=TENANT, actor=ACTOR, scopes={WALL},
        reason="archive chiffrée, mot de passe perdu, le client renonce")

    inv = store.inventory(MATTER, TENANT, {WALL})
    assert inv.unknown_cardinality_entries == 1, "an override is not a discovery about contents"
    assert inv.open_register_entries == 0 and inv.overridden_register_entries == 1
    assert inv.is_consistent(), "the subset is taken over BOTH register terms"
    assert inv.unknown_cardinality_phrase()


def test_the_scoped_denominator_agrees_with_the_matter_s_own(store: SqlStore) -> None:
    """Two queries compute this count — the per-matter one and the scoped one the search engine
    reads. They are the sort of pair that drifts, and only one of them was fixed by hand."""
    entry_id = _with_unopened_container(store)
    store.override_register_entry(
        entry_id=entry_id, tenant=TENANT, actor=ACTOR, scopes={WALL},
        reason="archive chiffrée, mot de passe perdu")
    with store._sf() as session:
        scoped = store._scoped_inventory(session, TENANT, {WALL})
    assert scoped.unknown_cardinality_entries == 1
    assert scoped == store.inventory(MATTER, TENANT, {WALL})
