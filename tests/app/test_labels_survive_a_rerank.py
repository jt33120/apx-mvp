"""Edits survive an explicit re-rank, marked human-set (Story 4.10 AC-2/AC-4, FR-20/FR-16).

*"Correcting the machine never costs me the correction I made a minute ago."* The reason this holds
is structural, not procedural: the taxonomy-label ledger is **version-INDEPENDENT** (Story 4.5), so
producing a new *ranking version* writes `ranking_version` + `ranked_entry` rows and **cannot**
touch `taxonomy_label_entry`. Re-ranking is an explicit, user-initiated act (never a side effect
of an edit), and what it produces is a new version beside the old one — never an overwrite of
anyone's values.

Asserted at the seam, over a real store: the property lives in the schema, and this is where it can
be shown rather than asserted.
"""

from __future__ import annotations

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apx.adapters.store_postgres.models import Base, TaxonomyLabelEntry
from apx.adapters.store_postgres.store import SqlStore
from apx.core.app.ingest import IngestionResult
from apx.core.app.label import assign_taxonomy_label
from apx.core.app.rank import produce_ranking
from apx.core.domain.cascade import Band, CascadeResult, CascadeUnit, PieceJudgement, Stage
from apx.core.domain.config import CascadeConfig
from apx.core.domain.ranking import RankingIdentityInputs, assemble_identity, rank_cascade
from tests.scoring_fakes import FakeScorer, FixedJudge

TENANT, WALL, MATTER = "t", "w", "m"
PIECES = ("p-alpha", "p-beta", "p-gamma")
TAXONOMY = ["Contrats", "Correspondance", "Jurisprudence"]


def _store() -> SqlStore:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    store = SqlStore(sessionmaker(bind=engine, future=True))
    store.save(IngestionResult(), scope=WALL, actor="setup", matter=MATTER, tenant=TENANT,
               audit=False)
    store.set_config(TENANT, "admin", "taxonomy", TAXONOMY)
    return store


def _inputs(prompt_version: str) -> RankingIdentityInputs:
    return RankingIdentityInputs(
        case_theory_version_id=None, model_provider="mistral",
        model_endpoint="https://api.mistral.ai/v1", model_name="mistral-small-latest",
        prompt_version=prompt_version, temperature=0.0, sampling={"top_p": 1.0},
        embedder_model_id="bge-m3", embedder_model_version="1.5",
        chunking_config_version="chunk-v1", schema_version="slice-a")


_CFG = CascadeConfig(uncertain_low=0.35, uncertain_high=0.65, calibration_sample=0,
                     stage3_max_share=1.0)


def _rank(store: SqlStore, scores: dict[str, float], *, prompt_version: str) -> int:
    """Run the real ranking act (Story 4.3) end to end through its use case."""
    version = produce_ranking(
        [CascadeUnit(piece_id=p, text=p, chunk_ids=("c",)) for p in PIECES],
        case_theory=None, scorer=FakeScorer(scores), judge=FixedJudge(), config=_CFG,
        inputs=_inputs(prompt_version), tenant=TENANT, matter=MATTER, actor="me.durand",
        scopes={WALL}, recorder=store)
    return version.version_no


def _record_order(store: SqlStore, bands: dict[str, tuple[Band, float]], *,
                  prompt_version: str) -> int:
    """Record a ranking whose ORDER is chosen explicitly, so a re-rank can be shown to really
    reorder. (The fake cascade lands every pièce in one band, where the deterministic tie-break
    then keeps the order stable — true to the engine, but useless for showing a reorder.)"""
    judgements = tuple(
        PieceJudgement.judged(
            piece_id=pid, family_id=f"fam-{pid}", is_representative=True,
            stage_reached=Stage.STAGE_2, band=band, score=score)
        for pid, (band, score) in bands.items())
    result = CascadeResult(
        judgements=judgements, families={j.family_id: (j.piece_id,) for j in judgements},
        unscored=(), stage3_share=0.0, over_stage3_floor=False, basis="intrinsic")
    identity = assemble_identity(
        inputs=_inputs(prompt_version), basis="intrinsic", uncertain_low=0.35,
        uncertain_high=0.65, calibration_sample=0, stage3_max_share=1.0)
    version = store.record_ranking(
        tenant=TENANT, matter=MATTER, actor="me.durand", identity=identity,
        order=rank_cascade(result, _CFG))
    return version.version_no


def _labels(store: SqlStore) -> dict[str, tuple[str, str | None]]:
    out = {}
    for piece in PIECES:
        current = store.read_current_label(
            tenant=TENANT, matter=MATTER, piece_id=piece, scopes={WALL})
        assert current is not None
        out[piece] = (current.label, current.source)
    return out


def test_human_set_labels_survive_a_new_ranking_version_and_stay_marked_human() -> None:
    """AC-2/AC-4: the explicit re-rank produces a NEW version and preserves every human-set value,
    marked as such — never replacing it with a fresh machine value."""
    store = _store()
    first = _record_order(store, {
        "p-alpha": (Band.CONFIDENT_RELEVANT, 0.9), "p-beta": (Band.UNCERTAIN, 0.5),
        "p-gamma": (Band.CONFIDENT_DISCARD, 0.1)}, prompt_version="v1")
    for piece, label in zip(PIECES, TAXONOMY, strict=True):
        assign_taxonomy_label(
            store, tenant=TENANT, matter=MATTER, actor="Me Durand", piece_id=piece, label=label,
            scopes={WALL})
    before = _labels(store)
    assert before == {p: (lbl, "human") for p, lbl in zip(PIECES, TAXONOMY, strict=True)}

    # the explicit, user-initiated act — a genuinely DIFFERENT order, so this is a real re-rank
    second = _record_order(store, {
        "p-alpha": (Band.CONFIDENT_DISCARD, 0.1), "p-beta": (Band.CONFIDENT_RELEVANT, 0.95),
        "p-gamma": (Band.UNCERTAIN, 0.5)}, prompt_version="v2")
    assert second == first + 1                                   # a new version beside the old one

    assert _labels(store) == before                              # every value held, still human-set
    order = store.read_ranked_order(
        tenant=TENANT, matter=MATTER, scopes={WALL}, version_no=second)
    assert order is not None
    assert [e.piece_id for e in order][0] == "p-beta"             # the ORDER did change
    old = store.read_ranked_order(
        tenant=TENANT, matter=MATTER, scopes={WALL}, version_no=first)
    assert old is not None and [e.piece_id for e in old][0] == "p-alpha"  # v1 still readable


def test_a_re_rank_writes_no_label_entry_at_all() -> None:
    """The structural reason AC-2 holds: the label ledger is version-INDEPENDENT, so a re-rank
    cannot touch it. Counted, not assumed."""
    store = _store()
    _rank(store, {"p-alpha": 0.9, "p-beta": 0.6, "p-gamma": 0.2}, prompt_version="v1")
    assign_taxonomy_label(
        store, tenant=TENANT, matter=MATTER, actor="Me Durand", piece_id="p-alpha",
        label="Contrats", scopes={WALL})

    def _entries() -> int:
        with store._sf() as s:
            return s.scalar(select(func.count()).select_from(TaxonomyLabelEntry))

    before = _entries()
    _rank(store, {"p-alpha": 0.1, "p-beta": 0.95, "p-gamma": 0.5}, prompt_version="v2")
    assert _entries() == before                     # not one entry written, rewritten or removed


def test_an_edit_never_produces_a_new_ranking_version() -> None:
    """The converse of AC-2: editing is not a re-rank. No edit regenerates or re-ranks anything."""
    store = _store()
    version = _rank(store, {"p-alpha": 0.9, "p-beta": 0.6, "p-gamma": 0.2}, prompt_version="v1")
    for piece in PIECES:
        assign_taxonomy_label(
            store, tenant=TENANT, matter=MATTER, actor="Me Durand", piece_id=piece,
            label="Contrats", scopes={WALL})
    latest = store.read_ranking(tenant=TENANT, matter=MATTER, scopes={WALL})
    assert latest is not None and latest.version_no == version   # still the same one version


def test_a_label_set_before_a_rerank_still_reads_on_the_new_version_table() -> None:
    """The surface-level consequence: the table of the NEW version shows the human-set values —
    the lawyer's corrections are not stranded on the version she made them against."""
    store = _store()
    _rank(store, {"p-alpha": 0.9, "p-beta": 0.6, "p-gamma": 0.2}, prompt_version="v1")
    assign_taxonomy_label(
        store, tenant=TENANT, matter=MATTER, actor="Me Durand", piece_id="p-gamma",
        label="Jurisprudence", scopes={WALL})
    second = _record_order(store, {
        "p-alpha": (Band.CONFIDENT_DISCARD, 0.1), "p-beta": (Band.CONFIDENT_RELEVANT, 0.95),
        "p-gamma": (Band.UNCERTAIN, 0.5)}, prompt_version="v2")

    table = store.read_triage_table(
        tenant=TENANT, matter=MATTER, scopes={WALL}, version_no=second)
    assert table is not None and table.version_no == second
    row = next(r for r in table.rows if r.piece_id == "p-gamma")
    assert (row.label, row.label_source) == ("Jurisprudence", "human")
