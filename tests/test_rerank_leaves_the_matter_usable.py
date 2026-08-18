"""A re-rank leaves the *matter* finishable, and the record keeps every position of the line.

Story 7.5. Two defects, both of which a ranking gesture would have turned from a rare operator
condition into the routine one.

**The line vanished, and nothing said so.** The line in force is read over the *latest* ranking
version only. So the instant version 2 exists, version 1's committed placement reads *superseded* —
and a superseded artefact deliberately emits no *worklist* line, because the worklist offers to
supersede an artefact, never to produce one that does not exist. The result was an empty worklist
(*read, and nothing to do*) over a *matter* where every ranked *pièce* had fallen into the unsplit
set, no *sampling run* could start and no *confidence bound* could exist. Producing a ranking made
the *matter* strictly less usable, silently.

**§3 of the exported record emptied.** ``read_line_history`` is version-scoped and honest about it;
the export's call site passed no version, so it resolved the latest and read only its placements. On
a *matter* with two rankings the section a *bâtonnier* receives was empty — which is the same bytes
as *no line was ever placed*, and that is a false statement about what a lawyer decided.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from apx.adapters.store_postgres.models import Base
from apx.adapters.store_postgres.store import SqlStore
from apx.core.app.ingest import IngestedPiece, IngestionResult
from apx.core.app.read.freshness import read_worklist
from apx.core.domain.matter_record import Tier
from apx.manage import rank

TENANT, MATTER, WALL, ACTOR = "cabinet", "affaire-a", "mur-a", "Me Dupont"


@pytest.fixture(autouse=True)
def _offline(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)


def _piece(pid: str, text: str) -> IngestedPiece:
    return IngestedPiece(
        id=pid, matter=MATTER, tenant=TENANT, content_hash=f"h-{pid}", text_key=text.lower(),
        provenance_path=f"/dossier/{pid}.pdf", custodian="Me Martin", extraction_method="text",
        extractor_version="v1", schema_version="slice-a",
        ingestion_timestamp=datetime(2026, 8, 1, tzinfo=UTC), full_text=text, text_version="v")


@pytest.fixture
def store(tmp_path) -> SqlStore:  # noqa: ANN001
    engine = create_engine(f"sqlite:///{tmp_path / 'rr'}.db", future=True)
    Base.metadata.create_all(engine)
    s = SqlStore(sessionmaker(bind=engine, future=True))
    s.provision_tenant(TENANT, "a@x.fr", "pw12345678", "Admin", {WALL}, ["conclusions"])
    s.save(IngestionResult(pieces=[
        _piece("p1", "Contrat de bail commercial, clause résolutoire."),
        _piece("p2", "Facture EDF, échéance avril."),
        _piece("p3", "Constat d'huissier du 12 juin, état des lieux."),
    ]), WALL, actor=ACTOR, matter=MATTER, tenant=TENANT)
    return s


def _line(store: SqlStore):  # noqa: ANN202
    return store.read_current_line(tenant=TENANT, matter=MATTER, scopes={WALL})


# ── the act draws the cut ─────────────────────────────────────────────────────────────────────

def test_the_first_ranking_arrives_with_its_line(store: SqlStore) -> None:
    rank(store, tenant=TENANT, matter=MATTER, actor=ACTOR, scopes={WALL})
    line = _line(store)
    assert line is not None and line.version_no == 1


def test_a_re_rank_leaves_a_line_over_the_new_version(store: SqlStore) -> None:
    """The defect. Before this story the second ranking produced an order and no cut, and the
    committed cut of version 1 became unreachable at the same instant."""
    rank(store, tenant=TENANT, matter=MATTER, actor=ACTOR, scopes={WALL})
    rank(store, tenant=TENANT, matter=MATTER, actor=ACTOR, scopes={WALL})

    line = _line(store)
    assert line is not None, "a re-ranked matter was left with no line at all"
    assert line.version_no == 2


def test_the_line_is_drawn_over_the_version_that_was_just_minted(store: SqlStore) -> None:
    """Named explicitly rather than resolved as *the latest*. Resolving would be right by accident
    today and wrong the moment two acts overlap — and the failure direction is the catastrophic
    one, a stamp whose line_seq belongs to another version reading FRESH."""
    rank(store, tenant=TENANT, matter=MATTER, actor=ACTOR, scopes={WALL})
    rank(store, tenant=TENANT, matter=MATTER, actor=ACTOR, scopes={WALL})
    version = store.read_ranking(tenant=TENANT, matter=MATTER, scopes={WALL})
    line = _line(store)
    assert version is not None and line is not None
    assert line.version_id == version.version_id


def test_the_re_ranked_matter_has_no_silent_empty_worklist(store: SqlStore) -> None:
    """The consequence a lawyer would have met: *read, and nothing to do* over a matter that could
    not start a sampling run. The worklist may legitimately be empty — what it may not be is empty
    BECAUSE the line disappeared, which is what this pins by asserting the line is there."""
    rank(store, tenant=TENANT, matter=MATTER, actor=ACTOR, scopes={WALL})
    rank(store, tenant=TENANT, matter=MATTER, actor=ACTOR, scopes={WALL})

    lines = read_worklist(
        tenant=TENANT, matter=MATTER, scopes={WALL}, reader=store,
        config_get=lambda key: store.get_config(TENANT, key))
    assert lines is not None                     # read, not a failed read
    assert _line(store) is not None


# ── and the record keeps every position ───────────────────────────────────────────────────────

def test_the_record_carries_the_line_history_of_every_version(store: SqlStore) -> None:
    """FR-24 says *every* position. §3 used to hold only the latest version's, so a matter with two
    rankings exported an empty section — the same bytes as *no line was ever placed*."""
    rank(store, tenant=TENANT, matter=MATTER, actor=ACTOR, scopes={WALL})
    rank(store, tenant=TENANT, matter=MATTER, actor=ACTOR, scopes={WALL})

    history = store.read_line_history_all_versions(
        tenant=TENANT, matter=MATTER, scopes={WALL})
    assert history is not None
    assert {r.version_no for r in history} == {1, 2}
    assert [r.version_no for r in history] == sorted(r.version_no for r in history)

    scoped = store.read_line_history(tenant=TENANT, matter=MATTER, scopes={WALL})
    assert scoped is not None
    assert {r.version_no for r in scoped} == {2}, "the version-scoped reader keeps its meaning"


def test_the_exported_record_reports_both_versions_positions(store: SqlStore) -> None:
    rank(store, tenant=TENANT, matter=MATTER, actor=ACTOR, scopes={WALL})
    rank(store, tenant=TENANT, matter=MATTER, actor=ACTOR, scopes={WALL})

    record = store.export_matter_record(
        tenant=TENANT, matter=MATTER, scopes={WALL}, actor=ACTOR, tier=Tier.NUMBERS_ONLY)
    positions = record["line_history"] if isinstance(record, dict) else record.line_history
    assert len({p["version_no"] if isinstance(p, dict) else p.version_no for p in positions}) == 2


def test_the_all_versions_reader_refuses_a_matter_behind_a_wall(store: SqlStore) -> None:
    rank(store, tenant=TENANT, matter=MATTER, actor=ACTOR, scopes={WALL})
    assert store.read_line_history_all_versions(
        tenant=TENANT, matter=MATTER, scopes={"un-autre-mur"}) is None
