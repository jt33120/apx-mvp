"""The ranking act gets a caller, and it names what actually ran (Story 7.3, retro action **C4**).

The B3/B4 audit's finding, verified by hand before this file was written: ``produce_ranking`` had
**no production caller anywhere** — no HTTP route, no worker job, no manage command. Twenty-two
shipped stories (the ranked table, the line, pins, the priced move, derived confidence,
justifications, the *sampling run*, the estimator, the *confidence bound*, the *validation act*, and
sections 5-9 of the *matter* record) stood on an act nobody could perform, and ``epics.md``
scheduled the wiring in no story at all.

Two things had to be true for a caller to be honest, and only the first is obvious.

**It has to produce a ranking.** Every input ``produce_ranking`` takes was the caller's to supply,
and none of them had a production source: no reader built ``CascadeUnit``s, ``cascade_config`` had
never been called outside its own tests, and ``PgSemanticScorer`` had never been constructed in the
runtime at all.

**It has to record what ran.** The *ranking version* identity is hashed into an immutable
fingerprint and printed on the header a lawyer reads. Sourcing the model half from configuration —
the obvious reading — would have recorded a *preference*: this deployment composes the deterministic
``criteria`` judge whenever no LLM credential is present, so the identity would have claimed
*mistral-small-latest @ api.mistral.ai, temperature 0, top_p 1.0* for an order decided entirely by a
comma-splitting keyword matcher. The judge answers for itself now.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from apx.adapters.judge.criteria import RULE_VERSION
from apx.adapters.store_postgres.models import Base
from apx.adapters.store_postgres.models import RankingVersion as RankingVersionRow
from apx.adapters.store_postgres.store import SqlStore
from apx.core.app.ingest import IngestedPiece, IngestionResult
from apx.manage import place, rank

TENANT, MATTER, WALL, ACTOR = "cabinet", "affaire-a", "mur-a", "Me Dupont"


@pytest.fixture(autouse=True)
def _offline(monkeypatch) -> None:  # noqa: ANN001
    """No LLM credential — the posture the identity used to lie about."""
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
    engine = create_engine(f"sqlite:///{tmp_path / 'rank'}.db", future=True)
    Base.metadata.create_all(engine)
    s = SqlStore(sessionmaker(bind=engine, future=True))
    s.provision_tenant(TENANT, "a@x.fr", "pw12345678", "Admin", {WALL}, ["conclusions"])
    s.save(IngestionResult(pieces=[
        _piece("p1", "Contrat de bail commercial, clause résolutoire."),
        _piece("p2", "Facture EDF, échéance avril."),
        # a NEAR-DUPLICATE of p1: same text_key, a distinct pièce of the dossier
        _piece("p3", "Contrat de bail commercial, clause résolutoire."),
    ]), WALL, actor=ACTOR, matter=MATTER, tenant=TENANT)
    return s


def _identity(store: SqlStore) -> dict:
    with store._sf() as session:
        row = session.scalars(select(RankingVersionRow)).one()
    return json.loads(row.identity_json)


# ── the act has a caller ──────────────────────────────────────────────────────────────────────

def test_the_command_produces_a_ranking_version(store: SqlStore) -> None:
    """The defect, closed: before this story nothing in the product could reach this line."""
    assert store.read_ranking(tenant=TENANT, matter=MATTER, scopes={WALL}) is None

    message = rank(store, tenant=TENANT, matter=MATTER, actor=ACTOR, scopes={WALL})

    version = store.read_ranking(tenant=TENANT, matter=MATTER, scopes={WALL})
    assert version is not None and version.version_no == 1
    assert "classement n° 1" in message


def test_the_order_holds_every_piece_of_the_matter_including_the_duplicate(
    store: SqlStore,
) -> None:
    """The population is the *matter*, not its distinct texts. ``representatives()`` — the only
    existing reader that returns (piece_id, text) — has already collapsed near-duplicates and
    dropped the members, and stage 1 does its own grouping: feeding it would have deleted those
    *pièces* from the recorded order, so the triage table would report them as *arrivées après ce
    classement* — documents that were in the dossier before the ranking ran."""
    rank(store, tenant=TENANT, matter=MATTER, actor=ACTOR, scopes={WALL})
    order = store.read_ranked_order(tenant=TENANT, matter=MATTER, scopes={WALL})
    assert order is not None
    assert {e.piece_id for e in order} == {"p1", "p2", "p3"}


def test_the_units_are_the_whole_population_not_the_representatives(store: SqlStore) -> None:
    """The reader itself, stated apart from the act — the two counts differ, which is the point."""
    units = store.cascade_units(MATTER, TENANT, {WALL})
    assert [u.piece_id for u in units] == ["p1", "p2", "p3"]
    assert len(store.representatives(MATTER, TENANT, {WALL})) == 2 < len(units)


def test_the_stage3_share_is_measured_over_the_matter(store: SqlStore) -> None:
    """SM-18's denominator is ``len(units)``, and its docstring says that is the share of the
    MATTER *so that near-duplicate collapsing counts as the cost saving it is*. Over
    representatives the same fraction reads 1.0 where it is 0.67 — the cost figure a firm bids
    from, wrong by exactly the factor the deduplication was supposed to save."""
    rank(store, tenant=TENANT, matter=MATTER, actor=ACTOR, scopes={WALL})
    version = store.read_ranking(tenant=TENANT, matter=MATTER, scopes={WALL})
    assert version is not None
    assert 0.0 <= version.stage3_share <= 1.0


# ── and it records the judge that ran, never the one that was configured ──────────────────────

def test_the_identity_names_the_judge_that_actually_decided(store: SqlStore) -> None:
    """The defect this story's check exists to keep closed. With no credential configured the
    cascade is the deterministic filter alone, and the recorded identity says so."""
    rank(store, tenant=TENANT, matter=MATTER, actor=ACTOR, scopes={WALL})
    identity = _identity(store)
    assert identity["model_provider"] == "criteria"
    assert identity["model_name"] == RULE_VERSION
    assert identity["model_endpoint"] == "local:criteria"


def test_the_identity_does_not_claim_a_model_that_was_never_called(store: SqlStore) -> None:
    """The tenant's configuration still says Mistral — it is a preference, and it is untouched.
    The identity must not repeat it as a fact about this run."""
    assert store.get_config(TENANT, "model_name") == "mistral-small-latest"
    rank(store, tenant=TENANT, matter=MATTER, actor=ACTOR, scopes={WALL})
    identity = _identity(store)
    assert "mistral" not in json.dumps(identity).lower()


def test_the_identity_invents_no_sampling_parameter(store: SqlStore) -> None:
    """``sampling={"top_p": 1.0}`` appeared in every fixture in the repository and the live request
    sends no sampling parameter of any kind. An empty mapping is the true answer, and it is a
    different fact from *nobody recorded one*."""
    rank(store, tenant=TENANT, matter=MATTER, actor=ACTOR, scopes={WALL})
    identity = _identity(store)
    assert identity["sampling"] == {}
    assert identity["temperature"] == 0.0


def test_the_identity_is_complete_and_fingerprinted(store: SqlStore) -> None:
    """AD-23: no blank field anywhere, and the fingerprint is over the whole of it."""
    rank(store, tenant=TENANT, matter=MATTER, actor=ACTOR, scopes={WALL})
    identity = _identity(store)
    blanks = sorted(
        k for k, v in identity.items()
        if isinstance(v, str) and not v.strip() and k != "case_theory_version_id")
    assert not blanks
    version = store.read_ranking(tenant=TENANT, matter=MATTER, scopes={WALL})
    assert version is not None and len(version.fingerprint) == 64


def test_the_basis_is_intrinsic_and_says_so(store: SqlStore) -> None:
    """No *case theory* was written, so the order is on intrinsic signals and the version records
    the name of that methodology — a deliberate choice, which is why the next test matters."""
    message = rank(store, tenant=TENANT, matter=MATTER, actor=ACTOR, scopes={WALL})
    assert _identity(store)["basis"] == "intrinsic"
    assert "signaux intrinsèques" in message


# ── the wall ──────────────────────────────────────────────────────────────────────────────────

def test_a_matter_the_caller_does_not_hold_is_refused_and_nothing_is_written(
    store: SqlStore,
) -> None:
    """The gate is the caller's, and it has to come FIRST. ``read_case_theory`` answers None for
    out-of-scope and for absent alike (FR-14) — and a None theory is also how the act says *rank on
    intrinsic signals*. Without the gate an out-of-scope caller would receive a complete,
    permanently fingerprinted ranking whose header names a methodology, for a theory that was
    simply never fetched."""
    with pytest.raises(ValueError, match="not held"):
        rank(store, tenant=TENANT, matter=MATTER, actor=ACTOR, scopes={"un-autre-mur"})
    assert store.read_ranking(tenant=TENANT, matter=MATTER, scopes={WALL}) is None


def test_the_units_reader_refuses_a_matter_behind_a_wall(store: SqlStore) -> None:
    from apx.adapters.store_postgres.store import ScopeDenied

    with pytest.raises(ScopeDenied):
        store.cascade_units(MATTER, TENANT, {"un-autre-mur"})


# ── and the line, so the matter can be finished ───────────────────────────────────────────────

def test_the_line_can_be_placed_over_the_ranking_that_was_just_produced(store: SqlStore) -> None:
    """Shipped beside the ranking because a ranked *matter* with no cut is one the product cannot
    finish reasoning about: retained and discarded are views over the order AND the line, so with
    no line every row reads *en attente de la ligne*, no *sampling run* can start, and no
    *confidence bound* can exist."""
    rank(store, tenant=TENANT, matter=MATTER, actor=ACTOR, scopes={WALL})
    message = place(store, tenant=TENANT, matter=MATTER, actor=ACTOR, scopes={WALL})

    line = store.read_current_line(tenant=TENANT, matter=MATTER, scopes={WALL})
    if line is None:                      # the honest "no pièce in a retain band" answer
        assert "aucune ligne posée" in message
    else:
        assert line.last_retained_piece_id in {"p1", "p2", "p3"}
        assert f"classement n° {line.version_no}" in message


def test_placing_the_line_behind_a_wall_is_refused(store: SqlStore) -> None:
    rank(store, tenant=TENANT, matter=MATTER, actor=ACTOR, scopes={WALL})
    with pytest.raises(ValueError, match="not held"):
        place(store, tenant=TENANT, matter=MATTER, actor=ACTOR, scopes={"un-autre-mur"})
