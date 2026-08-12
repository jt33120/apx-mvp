"""The sentence on the wire (Story 5.4, FR-23 / FR-58).

What the surfaces actually receive: the copied string with the wall and the staleness inside it,
FR-23's accompanying record beside it, and the unfitness declaration where the sample came back
mostly relevant. Driven through the product's own routes against a real *matter*.
"""

from __future__ import annotations

from pathlib import Path

from apx.core.domain.confidence import ESTIMATOR_METHOD
from tests.api.test_ingest_api import _login, _prepare, _reset_state  # noqa: F401 — autouse
from tests.api.test_sampling_api import (
    ADMIN,
    MATTER,
    TENANT,
    WALL,
    _complete,
    _judge_all,
    _matter,
    _start,
)


def _bound_after_a_run(client, sample_size: int = 3, relevant: int = 0) -> dict:  # noqa: ANN001
    run = _start(client, sample_size=sample_size)
    _judge_all(client, run, relevant=relevant)
    _complete(client, run["run_id"])
    return client.get(f"/api/matters/{MATTER}/bound").json()


# ── what travels inside the copied string ───────────────────────────────────────────────────────

def test_the_copied_string_names_the_wall_the_number_was_computed_under(
    tmp_path: Path, monkeypatch
) -> None:
    """FR-23. A payload does not travel with a paste — only the characters do. The wall is in the
    string AND in the accompanying record; only the first survives a copy into an email."""
    _store, client, _ = _matter(tmp_path, monkeypatch)
    bound = _bound_after_a_run(client)
    assert f"périmètre « {WALL} »" in bound["copy_text"]
    assert bound["scope"] == WALL


def test_the_copied_string_carries_its_freshness_state(tmp_path: Path, monkeypatch) -> None:
    _store, client, _ = _matter(tmp_path, monkeypatch)
    bound = _bound_after_a_run(client)
    assert bound["status_fr"] in bound["copy_text"]


def test_the_copied_string_states_the_draw_before_the_bound(tmp_path: Path, monkeypatch) -> None:
    """§0.2's corrected form: the evidence, then the inference."""
    _store, client, _ = _matter(tmp_path, monkeypatch)
    bound = _bound_after_a_run(client)
    text = bound["copy_text"]
    assert "tirées au hasard" in text
    if bound["kind"] == "bound":
        assert text.index("tirées au hasard") < text.index("Avec une confiance")


# ── FR-23's accompanying record ─────────────────────────────────────────────────────────────────

def test_the_bound_carries_the_accompanying_record_FR_23_asks_for(
    tmp_path: Path, monkeypatch
) -> None:
    """FR-23: the sentence names the matter, the ranking version, the case-theory version, the
    position of the line and the RBAC scope *"or carries them in the accompanying record"*. This is
    that record, and it rides beside the sentence rather than one click away."""
    _store, client, _ = _matter(tmp_path, monkeypatch)
    bound = _bound_after_a_run(client)
    assert bound["ranking_version_no"] is not None
    assert bound["last_retained_piece_id"] is not None
    assert bound["method"] == ESTIMATOR_METHOD
    # the case theory is None on the intrinsic ranking path, and is left None rather than invented
    assert "case_theory_version_id" in bound


# ── FR-23's unfitness declaration ───────────────────────────────────────────────────────────────

def test_a_sample_that_comes_back_mostly_relevant_declares_the_ranking_unfit(
    tmp_path: Path, monkeypatch
) -> None:
    """FR-23's seventh consequence. The finding is about the ORDER, not about where it was cut."""
    _store, client, _ = _matter(tmp_path, monkeypatch)
    run = _start(client, sample_size=3)
    _judge_all(client, run, relevant=3)                     # every drawn family came back relevant
    done = _complete(client, run["run_id"])

    assert done["unfit_fr"] is not None
    assert "ne trie pas ce dossier" in done["unfit_fr"]
    assert "déplacer la ligne ne corrigerait rien" in done["unfit_fr"]

    bound = client.get(f"/api/matters/{MATTER}/bound").json()
    assert bound["unfit_fr"] is not None
    assert bound["unfit_relevant_share"] == 1.0
    assert bound["unfit_threshold"] == 0.5


def test_a_clean_sample_declares_nothing_and_the_fields_stay_null(
    tmp_path: Path, monkeypatch
) -> None:
    """The declaration is a finding, not a decoration: no finding, no share, no threshold."""
    _store, client, _ = _matter(tmp_path, monkeypatch)
    bound = _bound_after_a_run(client)
    assert bound["unfit_fr"] is None
    assert bound["unfit_relevant_share"] is None and bound["unfit_threshold"] is None


def test_the_declaration_names_the_ranking_version_it_accuses(
    tmp_path: Path, monkeypatch
) -> None:
    """AD-23 — no unqualified reference to a *ranking version*. A finding naming no version would
    be an accusation with no defendant."""
    _store, client, _ = _matter(tmp_path, monkeypatch)
    run = _start(client, sample_size=3)
    _judge_all(client, run, relevant=3)
    done = _complete(client, run["run_id"])
    assert f"classement v{done['version_no']}".lower() in done["unfit_fr"].lower()


def test_the_bound_is_still_stated_beneath_an_unfit_declaration(
    tmp_path: Path, monkeypatch
) -> None:
    """FR-23: the product never suppresses or reframes an unfavourable result. The declaration
    QUALIFIES the sentence; it does not replace it."""
    _store, client, _ = _matter(tmp_path, monkeypatch)
    run = _start(client, sample_size=3)
    _judge_all(client, run, relevant=3)
    _complete(client, run["run_id"])
    bound = client.get(f"/api/matters/{MATTER}/bound").json()
    assert bound["unfit_fr"] is not None
    assert bound["copy_text"] and "tirées au hasard" in bound["copy_text"]


def test_the_threshold_is_configuration_as_data_and_a_tenant_can_move_it(
    tmp_path: Path, monkeypatch
) -> None:
    """AD-24. The rule that fires is the tenant's, not a constant compiled into the read seam."""
    store, client, _ = _matter(tmp_path, monkeypatch)
    run = _start(client, sample_size=3)
    _judge_all(client, run, relevant=1)                     # one of three: 33 %, under the default
    _complete(client, run["run_id"])
    assert client.get(f"/api/matters/{MATTER}/bound").json()["unfit_fr"] is None

    store.set_config(TENANT, ADMIN, "unfit_relevant_share", 0.3)
    again = client.get(f"/api/matters/{MATTER}/bound").json()
    assert again["unfit_fr"] is not None and again["unfit_threshold"] == 0.3


# ══ the adversarial review's confirmed defects on the wire, each proven fixed ════════════════════

def test_an_in_flight_run_declares_nothing_about_the_ranking(tmp_path: Path, monkeypatch) -> None:
    """CONFIRMED [HIGH] by five independent lenses. The declaration divided by
    ``verdicts_recorded`` — the tally so far — so a draw whose first verdict came back relevant
    declared the whole ranking version unfit at 1/1, and then said « sur les 1 familles tirées au
    hasard » about a draw of four. FR-23 speaks about *the sample*, and only a completed run has
    one."""
    _store, client, _ = _matter(tmp_path, monkeypatch)
    run = _start(client, sample_size=4)
    first = client.post(
        f"/api/matters/{MATTER}/sampling/runs/{run['run_id']}/verdicts",
        json={"family_id": run["drawn"][0]["unit"]["family_id"], "relevant": True}).json()
    assert first["verdicts_recorded"] == 1
    assert first["unfit_fr"] is None


def test_the_two_surfaces_never_disagree_about_the_finding(tmp_path: Path, monkeypatch) -> None:
    """One rule needs one denominator. The run screen divided by the verdicts recorded and the
    matter's constat by the draw, so the same run read UNFIT on one surface and FIT on the other —
    this project's recurring defect, in the code this story added to state a finding about it."""
    _store, client, _ = _matter(tmp_path, monkeypatch)
    run = _start(client, sample_size=4)
    done = _judge_all(client, run, relevant=1)          # 1 of 4 = 25 %, under the 50 % default
    done = _complete(client, run["run_id"])
    bound = client.get(f"/api/matters/{MATTER}/bound").json()
    assert done["unfit_fr"] is None and bound["unfit_fr"] is None

    run2 = _start(client, sample_size=4)
    _judge_all(client, run2, relevant=3)                # 3 of 4 = 75 %, over it
    done2 = _complete(client, run2["run_id"])
    bound2 = client.get(f"/api/matters/{MATTER}/bound").json()
    assert done2["unfit_fr"] is not None and bound2["unfit_fr"] is not None
    assert done2["unfit_fr"] == bound2["unfit_fr"]      # the same finding, worded once
    assert done2["unfit_fr"].lower().startswith("sur les 4 ")   # the DRAW, not the tally


def test_the_finding_produces_the_worklist_line_FR_23_requires(
    tmp_path: Path, monkeypatch
) -> None:
    """FR-23's third clause: *"produces a worklist line offering a re-rank with a revised or newly
    written case theory (FR-37)"*. CONFIRMED by three lenses to have no code anywhere — three of
    four clauses built reads, from the outside, exactly like four."""
    _store, client, _ = _matter(tmp_path, monkeypatch)
    run = _start(client, sample_size=3)
    _judge_all(client, run, relevant=3)
    _complete(client, run["run_id"])

    lines = client.get(f"/api/matters/{MATTER}/worklist").json()
    unfit = [line for line in lines if line["kind"] == "ranking_unfit"]
    assert len(unfit) == 1
    assert unfit[0]["offer"] == "re-rank-revised-theory"
    assert "théorie du cas révisée" in unfit[0]["offer_fr"]
    # FR-23: the remedy on offer is a re-rank, NEVER a line move.
    assert "re-line" not in [line["offer"] for line in lines]
    assert "déplacer la ligne ne corrigerait rien" in unfit[0]["offer_fr"]


def test_a_fit_ranking_produces_no_unfitness_line(tmp_path: Path, monkeypatch) -> None:
    _store, client, _ = _matter(tmp_path, monkeypatch)
    _bound_after_a_run(client)
    lines = client.get(f"/api/matters/{MATTER}/worklist").json()
    assert not [line for line in lines if line["kind"] == "ranking_unfit"]


def test_an_unfit_ranking_removes_the_line_move_offer_from_the_worklist(
    tmp_path: Path, monkeypatch
) -> None:
    """FR-23: the system *"does not offer a line move as the remedy"*. Raised by the review — the
    offer lives in ``worklist.OFFER_REPLACE_LINE``, which the structural check was not looking at,
    and a stale line already produces it. A matter whose ranking carries no signal AND whose line
    has moved would otherwise hand the lawyer both remedies at once."""
    _store, client, _ = _matter(tmp_path, monkeypatch)
    run = _start(client, sample_size=3)
    _judge_all(client, run, relevant=3)
    _complete(client, run["run_id"])
    lines = client.get(f"/api/matters/{MATTER}/worklist").json()
    assert any(line["kind"] == "ranking_unfit" for line in lines)
    assert all(line["offer"] != "re-line" for line in lines)
