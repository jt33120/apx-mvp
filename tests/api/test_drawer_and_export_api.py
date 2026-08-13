"""The *audit drawer* and the *matter* export over HTTP (Story 5.7, FR-26/FR-11).

The edge is where the contract's promises become observable to a client: the drawer's four bands
arrive in order with the proposed rows and their reversals, an unresolved extract arrives with its
cause and without its text, the tier is required and refused when unknown, and producing a document
is an act that is recorded while a refusal writes nothing.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from apx.api import app as app_module
from apx.api.app import app
from apx.core.app.ingest import IngestionResult
from apx.core.domain import audit as AUDIT
from apx.core.domain.cascade import Band, CascadeResult, PieceJudgement, Stage
from apx.core.domain.config import CascadeConfig
from apx.core.domain.ranking import RankingIdentityInputs, assemble_identity, rank_cascade
from tests.api.test_ingest_api import _login, _prepare

MATTER, WALL = "m", "wall"
_CFG = CascadeConfig(uncertain_low=0.35, uncertain_high=0.65, calibration_sample=20,
                     stage3_max_share=0.5)
_PAIRS = [("a", Band.CONFIDENT_RELEVANT, 0.9), ("b", Band.CONFIDENT_DISCARD, 0.2)]


@pytest.fixture(autouse=True)
def _reset_state():  # noqa: ANN202
    app_module._store.cache_clear()
    app_module._login_limiter._fails.clear()
    yield
    app_module._store.cache_clear()
    app_module._login_limiter._fails.clear()


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


def _seed(store, *, scope: str = WALL, matter: str = MATTER) -> None:  # noqa: ANN001
    store.save(IngestionResult(), actor="Me Dupont", scope=scope, matter=matter, tenant="t")
    store.record_ranking(
        tenant="t", matter=matter, actor="Claire Fontaine", identity=_identity(), order=_order())


# ── the drawer (AC-1..AC-4) ───────────────────────────────────────────────────────────────────

def test_the_drawer_offers_reversible_actions_each_naming_its_reversal(
    tmp_path: Path, monkeypatch,  # noqa: ANN001
) -> None:
    store = _prepare(tmp_path, monkeypatch)
    store.create_user("t", "me@x.fr", "pw", "Me Durand", {WALL})
    _seed(store)
    with TestClient(app) as c:
        _login(c, "me@x.fr")
        body = c.get(f"/api/matters/{MATTER}/pieces/a/drawer").json()
    assert body["piece_id"] == "a" and body["matter"] == MATTER
    assert body["actions"], "the drawer must offer something to do"
    for a in body["actions"]:
        assert a["reversal_fr"], a["action"]          # FR-26: every action names its reversal
        assert a["action_fr"] != a["action"]          # in the lawyer's language


def test_a_proposed_row_names_its_chain_and_invents_no_timestamp(
    tmp_path: Path, monkeypatch,  # noqa: ANN001
) -> None:
    store = _prepare(tmp_path, monkeypatch)
    store.create_user("t", "me@x.fr", "pw", "Me Durand", {WALL})
    _seed(store)
    with TestClient(app) as c:
        _login(c, "me@x.fr")
        body = c.get(f"/api/matters/{MATTER}/pieces/a/drawer").json()
    for a in body["actions"]:
        proposed = a["proposed"]
        assert proposed["actor"] == "Me Durand"
        assert proposed["chain_label_fr"]
        # the entry does not exist yet; a shown time that is not the one written is a lie
        assert "timestamp" not in proposed and "seq" not in proposed


def test_the_pin_is_proposed_as_an_override_owing_a_reason(
    tmp_path: Path, monkeypatch,  # noqa: ANN001
) -> None:
    store = _prepare(tmp_path, monkeypatch)
    store.create_user("t", "me@x.fr", "pw", "Me Durand", {WALL})
    _seed(store)
    with TestClient(app) as c:
        _login(c, "me@x.fr")
        body = c.get(f"/api/matters/{MATTER}/pieces/a/drawer").json()
    pin = next(a for a in body["actions"] if a["action"] == AUDIT.ACT_PIN_OVERRIDE)
    assert pin["proposed"]["reason_required"]          # FR-25, visible BEFORE the act
    assert pin["proposed"]["override_ground_fr"]
    lift = next(a for a in body["actions"] if a["action"] == AUDIT.ACT_PIN_REMOVED)
    assert not lift["proposed"]["reason_required"]     # lifting owes nothing


def test_the_validation_act_is_disabled_with_its_story_never_hidden(
    tmp_path: Path, monkeypatch,  # noqa: ANN001
) -> None:
    # a hidden control cannot be asked about; a disabled one that says why tells the truth about
    # the build to the only person either could mislead
    store = _prepare(tmp_path, monkeypatch)
    store.create_user("t", "me@x.fr", "pw", "Me Durand", {WALL})
    _seed(store)
    with TestClient(app) as c:
        _login(c, "me@x.fr")
        body = c.get(f"/api/matters/{MATTER}/pieces/a/drawer").json()
    pending = body["pending_actions"]
    assert len(pending) == 1
    assert pending[0]["story"] == "5.8" and "5.8" in pending[0]["disabled_reason_fr"]
    assert "lu cette pièce" in pending[0]["label_fr"]


def test_a_piece_with_no_justification_says_so_rather_than_showing_an_empty_band(
    tmp_path: Path, monkeypatch,  # noqa: ANN001
) -> None:
    store = _prepare(tmp_path, monkeypatch)
    store.create_user("t", "me@x.fr", "pw", "Me Durand", {WALL})
    _seed(store)
    with TestClient(app) as c:
        _login(c, "me@x.fr")
        body = c.get(f"/api/matters/{MATTER}/pieces/a/drawer").json()
    assert body["sentence"] is None and body["extracts"] == []
    assert not body["is_unverified"] and body["unresolved_extracts"] == 0


def test_the_drawer_is_non_disclosing_outside_the_wall(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    store = _prepare(tmp_path, monkeypatch)
    store.create_user("t", "a@x.fr", "pw", "Me A", {"wall-a"})
    _seed(store, scope="wall-b", matter="m-b")
    with TestClient(app) as c:
        _login(c, "a@x.fr")
        walled = c.get("/api/matters/m-b/pieces/a/drawer")
        absent = c.get("/api/matters/inexistante/pieces/a/drawer")
    assert walled.status_code == absent.status_code == 404
    assert walled.json() == absent.json()          # the same answer, byte for byte


# ── the export (AC-6, AC-7, AC-10) ────────────────────────────────────────────────────────────

def test_the_tier_is_required_and_an_unknown_one_is_refused(
    tmp_path: Path, monkeypatch,  # noqa: ANN001
) -> None:
    store = _prepare(tmp_path, monkeypatch)
    store.create_user("t", "me@x.fr", "pw", "Me Durand", {WALL})
    _seed(store)
    with TestClient(app) as c:
        _login(c, "me@x.fr")
        assert c.post(f"/api/matters/{MATTER}/record/export").status_code == 422   # no tier
        bad = c.post(f"/api/matters/{MATTER}/record/export?tier=tout")
        assert bad.status_code == 400 and "niveau inconnu" in bad.json()["detail"]


def test_producing_the_document_is_recorded_and_the_cover_states_its_limits(
    tmp_path: Path, monkeypatch,  # noqa: ANN001
) -> None:
    store = _prepare(tmp_path, monkeypatch)
    store.create_user("t", "me@x.fr", "pw", "Me Durand", {WALL})
    _seed(store)
    with TestClient(app) as c:
        _login(c, "me@x.fr")
        res = c.post(f"/api/matters/{MATTER}/record/export?tier=numbers-only")
        assert res.status_code == 200
        doc = res.json()
        trail = c.get(f"/api/matters/{MATTER}/audit").json()

    cover = doc["cover"]
    assert cover["scope"] == WALL and cover["tier"] == "numbers-only"
    assert cover["produced_by"] == "Me Durand" and cover["produced_at"]
    assert len(doc["denominator"]) == 7
    assert [p["story"] for p in doc["pending"]] == ["5.8", "5.8"]
    assert any(e["action"] == AUDIT.ACT_EXPORT_MATTER_RECORD for e in trail["entries"])


def test_the_two_tiers_are_different_documents(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    store = _prepare(tmp_path, monkeypatch)
    store.create_user("t", "me@x.fr", "pw", "Me Durand", {WALL})
    _seed(store)
    store.append_case_theory_version(
        tenant="t", matter=MATTER, actor="Me Durand", text="Stratégie confidentielle du cabinet.")
    with TestClient(app) as c:
        _login(c, "me@x.fr")
        numbers = c.post(f"/api/matters/{MATTER}/record/export?tier=numbers-only").text
        full = c.post(f"/api/matters/{MATTER}/record/export?tier=full").text
    assert "Stratégie confidentielle" in full
    assert "Stratégie confidentielle" not in numbers


def test_an_export_outside_the_wall_is_refused_and_writes_nothing(
    tmp_path: Path, monkeypatch,  # noqa: ANN001
) -> None:
    store = _prepare(tmp_path, monkeypatch)
    store.create_user("t", "a@x.fr", "pw", "Me A", {"wall-a"})
    _seed(store, scope="wall-b", matter="m-b")
    with TestClient(app) as c:
        _login(c, "a@x.fr")
        assert c.post("/api/matters/m-b/record/export?tier=full").status_code == 403
    trail = store.read_audit("m-b", "t", {"wall-b"})
    assert not any(e.action == AUDIT.ACT_EXPORT_MATTER_RECORD for e in trail.entries)


def test_the_drawer_checks_the_wall_itself_and_never_infers_it(
    tmp_path: Path, monkeypatch,  # noqa: ANN001
) -> None:
    # the defect this pins: `read_justification` returns None both for "out of scope" and for
    # "nothing recorded", so a drawer that inferred scope from it answered 200 — with a list of
    # proposed acts — for a matter behind a wall the caller does not hold
    store = _prepare(tmp_path, monkeypatch)
    store.create_user("t", "a@x.fr", "pw", "Me A", {"wall-a"})
    _seed(store, scope="wall-b", matter="m-b")          # a real matter, with NO justification
    assert not store.matter_is_held(tenant="t", matter="m-b", scopes={"wall-a"})
    with TestClient(app) as c:
        _login(c, "a@x.fr")
        denied = c.get("/api/matters/m-b/pieces/a/drawer")
    assert denied.status_code == 404
    assert "actions" not in denied.text                  # not even the shape of a panel leaks
