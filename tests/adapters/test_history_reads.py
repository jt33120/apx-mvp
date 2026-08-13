"""The two history reads the *matter* export cannot be written without (Story 5.7, FR-24/FR-26).

FR-24 records **every position** of **the line** *with author and priced statement*, and FR-26 asks
the export for the position history and for **all** pins. Until this story the store answered only
the two *current-state* questions: `read_current_line` and `read_current_pins`. Neither is the
history, and the difference is not academic — a pin posed and later lifted is a decision that was
taken, and an export that omitted it would let a reader conclude it never happened.

Against the real SQLite store: the history is complete and ordered, it carries the author and the
priced statement (which Story 5.7 moved onto the ledger — it lived only inside a formatted audit
detail before), the first placement is distinguishable from a priced move, and both reads are
scope-checked and non-disclosing.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apx.adapters.store_postgres.models import Base
from apx.adapters.store_postgres.store import SqlStore
from apx.core.app.ingest import IngestionResult
from apx.core.app.line import read_line_history
from apx.core.app.pin import read_pin_log
from apx.core.domain.cascade import Band, CascadeResult, PieceJudgement, Stage
from apx.core.domain.config import CascadeConfig
from apx.core.domain.pin import PinAction
from apx.core.domain.ranking import RankingIdentityInputs, assemble_identity, rank_cascade
from apx.core.domain.triage_sets import PinSide

TENANT, MATTER, WALL = "t", "m", "w"
_CFG = CascadeConfig(uncertain_low=0.35, uncertain_high=0.65, calibration_sample=20,
                     stage3_max_share=0.5)
_PAIRS = [("a", Band.CONFIDENT_RELEVANT, 0.9), ("b", Band.CONFIDENT_RELEVANT, 0.7),
          ("c", Band.CONFIDENT_DISCARD, 0.2), ("d", Band.CONFIDENT_DISCARD, 0.1)]


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


def _order():  # noqa: ANN202
    judgements = [
        PieceJudgement.judged(piece_id=pid, family_id=f"fam-{pid}", is_representative=True,
                              stage_reached=Stage.STAGE_2, band=band, score=score)
        for pid, band, score in _PAIRS
    ]
    result = CascadeResult(
        judgements=tuple(judgements), families={j.family_id: (j.piece_id,) for j in judgements},
        unscored=(), stage3_share=0.5, over_stage3_floor=False, basis="intrinsic")
    return rank_cascade(result, _CFG)


@pytest.fixture
def store() -> SqlStore:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    s = SqlStore(sessionmaker(bind=engine, future=True))
    s.save(IngestionResult(), scope=WALL, actor="seed", matter=MATTER, tenant=TENANT, audit=False)
    s.record_ranking(
        tenant=TENANT, matter=MATTER, actor="a", identity=_identity(), order=_order())
    return s


# ── the line's position history ───────────────────────────────────────────────────────────────
PRICE = "400 pièces de plus à lire ; part estimée ≈3 % → ≈0,4 %"


def test_the_history_is_every_position_oldest_first(store: SqlStore) -> None:
    placed = store.place_line(tenant=TENANT, matter=MATTER, actor="claire", scopes={WALL})
    assert placed is not None
    store.move_line(
        tenant=TENANT, matter=MATTER, actor="claire", scopes={WALL},
        last_retained_piece_id="c", expected_seq=placed.seq, priced_statement=PRICE)

    history = store.read_line_history(tenant=TENANT, matter=MATTER, scopes={WALL})
    assert history is not None
    assert [h.seq for h in history] == [1, 2]                    # oldest first, nothing dropped
    assert [h.last_retained_piece_id for h in history] == [placed.last_retained_piece_id, "c"]
    assert store.read_current_line(
        tenant=TENANT, matter=MATTER, scopes={WALL}).seq == 2    # the state read is unchanged


def test_the_history_carries_the_author_the_current_read_deliberately_drops(
    store: SqlStore,
) -> None:
    store.place_line(tenant=TENANT, matter=MATTER, actor="Claire Fontaine", scopes={WALL})
    history = store.read_line_history(tenant=TENANT, matter=MATTER, scopes={WALL})
    assert history[0].placed_by == "Claire Fontaine"             # decrypted, and attributable
    assert not hasattr(
        store.read_current_line(tenant=TENANT, matter=MATTER, scopes={WALL}), "placed_by")


def test_a_first_placement_has_no_price_and_a_move_carries_the_one_it_was_shown(
    store: SqlStore,
) -> None:
    # NULL means "this was not a move", which is a different fact from "a move whose price nobody
    # showed" — an empty string would have conflated them
    placed = store.place_line(tenant=TENANT, matter=MATTER, actor="claire", scopes={WALL})
    store.move_line(
        tenant=TENANT, matter=MATTER, actor="claire", scopes={WALL},
        last_retained_piece_id="c", expected_seq=placed.seq, priced_statement=PRICE)
    history = store.read_line_history(tenant=TENANT, matter=MATTER, scopes={WALL})
    assert history[0].priced_statement is None
    assert history[1].priced_statement == PRICE                  # verbatim, on the ledger


def test_the_priced_statement_is_on_the_ledger_not_only_in_a_formatted_detail(
    store: SqlStore,
) -> None:
    # the Story 5.7 finding: before this, the statement existed ONLY inside the `line_moved` audit
    # entry's detail string, so the export would have had to recover it by parsing prose out of an
    # encrypted column, matching entries to placements by a `seq=` substring
    placed = store.place_line(tenant=TENANT, matter=MATTER, actor="claire", scopes={WALL})
    store.move_line(
        tenant=TENANT, matter=MATTER, actor="claire", scopes={WALL},
        last_retained_piece_id="c", expected_seq=placed.seq, priced_statement=PRICE)
    history = store.read_line_history(tenant=TENANT, matter=MATTER, scopes={WALL})
    assert history[1].priced_statement == PRICE                  # read straight off the row


def test_a_version_with_no_line_answers_empty_not_none(store: SqlStore) -> None:
    # an empty tuple is a real answer — "this version exists and no line was ever placed" — and it
    # must not read like "you may not look" (None)
    assert store.read_line_history(tenant=TENANT, matter=MATTER, scopes={WALL}) == ()


def test_the_line_history_is_non_disclosing_out_of_scope(store: SqlStore) -> None:
    store.place_line(tenant=TENANT, matter=MATTER, actor="claire", scopes={WALL})
    assert store.read_line_history(tenant=TENANT, matter=MATTER, scopes={"other"}) is None
    assert store.read_line_history(tenant=TENANT, matter="absent", scopes={WALL}) is None


def test_the_line_history_reaches_the_core_through_the_port(store: SqlStore) -> None:
    store.place_line(tenant=TENANT, matter=MATTER, actor="claire", scopes={WALL})
    through = read_line_history(store, tenant=TENANT, matter=MATTER, scopes={WALL})
    assert through is not None and len(through) == 1


# ── the pin ledger ────────────────────────────────────────────────────────────────────────────

def test_the_log_keeps_a_pin_that_was_lifted(store: SqlStore) -> None:
    # the whole reason this read exists: `read_current_pins` would show NOTHING here, and an export
    # built on it would let a reader conclude the pin was never posed
    store.pin_piece(tenant=TENANT, matter=MATTER, actor="claire", scopes={WALL}, piece_id="c",
                    side=PinSide.RETAIN, reason="aveu au §4 — décisif malgré le rang")
    store.remove_pin(tenant=TENANT, matter=MATTER, actor="claire", scopes={WALL}, piece_id="c")

    assert store.read_current_pins(tenant=TENANT, matter=MATTER, scopes={WALL}) == ()
    log = store.read_pin_log(tenant=TENANT, matter=MATTER, scopes={WALL})
    assert [(e.seq, e.action) for e in log] == [(1, PinAction.RETAIN), (2, PinAction.REMOVED)]


def test_the_log_carries_the_actor_and_the_mandatory_reason_verbatim(store: SqlStore) -> None:
    reason = "aveu implicite au §4 — décisif malgré le rang"
    store.pin_piece(tenant=TENANT, matter=MATTER, actor="Claire Fontaine", scopes={WALL},
                    piece_id="c", side=PinSide.RETAIN, reason=reason)
    log = store.read_pin_log(tenant=TENANT, matter=MATTER, scopes={WALL})
    assert log[0].set_by == "Claire Fontaine" and log[0].reason == reason


def test_lifting_a_pin_carries_no_reason_because_it_owes_none(store: SqlStore) -> None:
    store.pin_piece(tenant=TENANT, matter=MATTER, actor="claire", scopes={WALL}, piece_id="c",
                    side=PinSide.RETAIN, reason="motif")
    store.remove_pin(tenant=TENANT, matter=MATTER, actor="claire", scopes={WALL}, piece_id="c")
    log = store.read_pin_log(tenant=TENANT, matter=MATTER, scopes={WALL})
    assert log[1].action is PinAction.REMOVED and log[1].reason == ""


def test_the_log_is_ordered_by_piece_then_seq(store: SqlStore) -> None:
    store.pin_piece(tenant=TENANT, matter=MATTER, actor="c", scopes={WALL}, piece_id="d",
                    side=PinSide.RETAIN, reason="r1")
    store.pin_piece(tenant=TENANT, matter=MATTER, actor="c", scopes={WALL}, piece_id="a",
                    side=PinSide.DISCARD, reason="r2")
    store.remove_pin(tenant=TENANT, matter=MATTER, actor="c", scopes={WALL}, piece_id="a")
    log = store.read_pin_log(tenant=TENANT, matter=MATTER, scopes={WALL})
    assert [(e.piece_id, e.seq) for e in log] == [("a", 1), ("a", 2), ("d", 1)]


def test_a_matter_with_no_pin_answers_empty_not_none(store: SqlStore) -> None:
    assert store.read_pin_log(tenant=TENANT, matter=MATTER, scopes={WALL}) == ()


def test_the_pin_log_is_non_disclosing_out_of_scope(store: SqlStore) -> None:
    store.pin_piece(tenant=TENANT, matter=MATTER, actor="c", scopes={WALL}, piece_id="c",
                    side=PinSide.RETAIN, reason="motif")
    assert store.read_pin_log(tenant=TENANT, matter=MATTER, scopes={"other"}) is None
    assert store.read_pin_log(tenant=TENANT, matter="absent", scopes={WALL}) is None


def test_the_pin_log_reaches_the_core_through_the_port(store: SqlStore) -> None:
    store.pin_piece(tenant=TENANT, matter=MATTER, actor="c", scopes={WALL}, piece_id="c",
                    side=PinSide.RETAIN, reason="motif")
    through = read_pin_log(store, tenant=TENANT, matter=MATTER, scopes={WALL})
    assert through is not None and len(through) == 1
