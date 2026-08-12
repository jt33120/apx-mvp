"""The estimator end to end (Story 5.2, OQ-4 / FR-22 / FR-23 / FR-38).

Every test drives the product's own routes against a real *matter* with a real ranked order and a
real committed line. What is tested is not the hypergeometric — that is ``test_confidence.py``, and
this story deliberately did not touch it — but the five design decisions AROUND it: the unit, the
crossover, the multiplicity, the freeze, and what the number is not allowed to become.
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from apx.adapters.store_postgres.models import SamplingRun
from apx.core.app.line import place_line
from apx.core.domain.confidence import ESTIMATOR_METHOD
from tests.api.test_ingest_api import _login, _prepare, _reset_state  # noqa: F401 — autouse
from tests.api.test_sampling_api import (
    ADMIN,
    MATTER,
    TENANT,
    WALL,
    _complete,
    _current,
    _cut_to,
    _judge_all,
    _matter,
    _rank,
    _ranked_order,
    _start,
    app,
)


def _duplicated_matter(tmp_path: Path, monkeypatch):  # noqa: ANN001,ANN201
    """A *matter* whose discarded set holds one LARGE near-duplicate family and several singletons
    — the shape OQ-4's first hard input is about. Without it every family holds one *pièce* and the
    worst case and the rescale agree by accident."""
    store = _prepare(tmp_path, monkeypatch)
    store.create_user(TENANT, ADMIN, "motdepasse", "Me Durand", {WALL}, is_admin=True)
    folder = tmp_path / "dossier"
    folder.mkdir()
    thread = "Courriel du gérant au bailleur, refus de la mise en demeure du 3 mars."
    for i in range(4):                                    # one family of four near-copies
        (folder / f"fil-{i}.txt").write_text(thread + " " * i, encoding="utf-8")
    (folder / "bail.txt").write_text(
        "Contrat de bail commercial signé le 3 mars, clause résolutoire.", encoding="utf-8")
    (folder / "facture.txt").write_text(
        "Facture EDF, cent cinquante euros, échéance avril.", encoding="utf-8")
    (folder / "constat.txt").write_text(
        "Constat d'huissier du 12 juin, état des lieux de sortie.", encoding="utf-8")
    client = TestClient(app())
    _login(client, ADMIN, pw="motdepasse")
    client.post("/api/ingest", json={"folder": str(folder), "matter": MATTER, "scope": WALL})
    _rank(store)
    place_line(store, tenant=TENANT, matter=MATTER, actor="me.durand", scopes={WALL})
    order = _ranked_order(store)
    _cut_to(store, order[0])                              # retain one, discard the rest
    return store, client, order


def _frozen_sizes(store, run_id: str) -> str | None:  # noqa: ANN001
    with store._sf() as session:
        row = session.get(SamplingRun, run_id)
        return row.population_family_sizes


# ── input 1: the unit is the family, and the pièce figure is a worst case ────────────────────────

def test_a_family_really_holds_more_than_one_piece(tmp_path: Path, monkeypatch) -> None:
    """CONFIRMED [HIGH] by the review — and the reason every other test in this block is worth
    anything. The ranked order holds ONE entry per near-duplicate cluster (``representatives``
    groups by ``text_key``; the cascade rejects the members at stage 1, AD-36), so before this
    story ``member_piece_ids`` was a singleton forever, ``population_pieces`` equalled
    ``population_families``, and the *pièce* worst case was an identity wearing a statistic's
    clothes. The twins are attached from the same ``text_key`` the ranking collapsed by."""
    _store, client, _order = _duplicated_matter(tmp_path, monkeypatch)
    run = _start(client, sample_size=99)
    sizes = sorted(len(d["unit"]["member_piece_ids"]) for d in run["drawn"])
    assert sizes[-1] > 1, "the near-duplicate family apparatus is inert"
    assert run["population_pieces"] > run["population_families"]
    assert sum(sizes) == run["population_pieces"]
    for drawn in run["drawn"]:                            # the proxy is what the lawyer reads
        assert drawn["unit"]["member_piece_ids"][0] == drawn["unit"]["proxy_piece_id"]


def test_a_family_is_one_draw_however_many_copies_it_holds(
    tmp_path: Path, monkeypatch
) -> None:
    """FR-38 in one assertion: forty copies of one thread are one draw, not forty. Here four are."""
    _store, client, _order = _duplicated_matter(tmp_path, monkeypatch)
    run = _start(client, sample_size=99)
    assert run["is_census"] is True and run["sample_size"] == run["population_families"]
    big = max(run["drawn"], key=lambda d: len(d["unit"]["member_piece_ids"]))
    assert len(big["unit"]["member_piece_ids"]) == 4
    done = _complete(client, _judge_all(client, run)["run_id"])
    assert done["population_families"] == 3 and done["population_pieces"] == 6


def test_the_run_freezes_the_size_of_every_family_not_only_the_drawn_ones(
    tmp_path: Path, monkeypatch
) -> None:
    """The worst case needs the D LARGEST families in the POPULATION. Freezing only what was drawn
    would make the answer depend on the draw, which is the one thing a bound may not do."""
    store, client, _order = _duplicated_matter(tmp_path, monkeypatch)
    run = _start(client, sample_size=1)
    assert len(run["drawn"]) == 1
    sizes = [int(n) for n in (_frozen_sizes(store, run["run_id"]) or "").split(",") if n]
    assert len(sizes) == run["population_families"] > 1     # every family, not just the drawn one
    assert sizes == sorted(sizes, reverse=True)             # sorted at the freeze
    assert sum(sizes) == run["population_pieces"]


def test_the_piece_figure_is_the_largest_families_and_never_a_rescale(
    tmp_path: Path, monkeypatch
) -> None:
    store, client, _order = _duplicated_matter(tmp_path, monkeypatch)
    run = _start(client, sample_size=1)
    done = _complete(client, _judge_all(client, run)["run_id"])
    sizes = [int(n) for n in (_frozen_sizes(store, run["run_id"]) or "").split(",") if n]
    expected = sum(sorted(sizes, reverse=True)[:done["count_upper"]])
    assert done["count_upper_pieces"] == expected
    rescale = (done["prevalence_upper"] or 0.0) * done["population_pieces"]
    assert done["count_upper_pieces"] >= rescale, (
        "the worst case is never below the average-size rescale — that is the whole point")


def test_the_copied_bound_states_the_worst_case_in_pieces(tmp_path: Path, monkeypatch) -> None:
    """So the reader does not perform the forbidden arithmetic herself: the sentence already showed
    her a family count and a pièce count, and the product of the two is wrong."""
    _store, client, _order = _duplicated_matter(tmp_path, monkeypatch)
    run = _start(client, sample_size=1)
    done = _complete(client, _judge_all(client, run)["run_id"])
    body = client.get(f"/api/matters/{MATTER}/bound").json()
    assert body["count_upper_pieces"] == done["count_upper_pieces"]
    assert f"au plus {done['count_upper_pieces']} pièces au pire" in body["copy_text"]


# ── input 2: the census crossover — an exact count, never a percentage ───────────────────────────

def test_a_census_states_an_exact_count_and_carries_no_bound(tmp_path: Path, monkeypatch) -> None:
    _store, client, _order = _matter(tmp_path, monkeypatch, cut_at_rank=1)
    run = _start(client, sample_size=99)                  # everything → a census
    assert run["is_census"] is True
    done = _complete(client, _judge_all(client, run, relevant=1)["run_id"])
    assert done["estimate_kind"] == "census"
    assert done["count_upper_pieces"] is None             # nothing is bounded
    assert done["relevant_pieces"] is not None            # everything is known
    assert done["statement_fr"] is not None and "%" not in done["statement_fr"]


def test_the_copied_sentence_of_a_census_never_states_a_percentage(
    tmp_path: Path, monkeypatch
) -> None:
    """FR-22's named failure, at the one place it would be said out loud: the clipboard."""
    _store, client, _order = _matter(tmp_path, monkeypatch, cut_at_rank=1)
    run = _start(client, sample_size=99)
    _complete(client, _judge_all(client, run)["run_id"])
    text = client.get(f"/api/matters/{MATTER}/bound").json()["copy_text"]
    assert text.lower().startswith("recensement")
    assert "%" not in text
    assert "prévalence" not in text


def test_a_census_that_found_something_names_both_units_exactly(
    tmp_path: Path, monkeypatch
) -> None:
    _store, client, _order = _duplicated_matter(tmp_path, monkeypatch)
    run = _start(client, sample_size=99)
    done = _complete(client, _judge_all(client, run, relevant=1)["run_id"])
    assert done["estimate_kind"] == "census"
    drawn_relevant = [d for d in done["drawn"] if d["relevant"] is True]
    exact = sum(len(d["unit"]["member_piece_ids"]) for d in drawn_relevant)
    assert done["relevant_pieces"] == exact
    text = client.get(f"/api/matters/{MATTER}/bound").json()["copy_text"]
    assert f"{exact} pièce" in text and "%" not in text


def test_the_stored_census_flag_is_a_record_and_nothing_reads_it(
    tmp_path: Path, monkeypatch
) -> None:
    """A stored boolean and a derived one are two referents for one fact, and the surface would
    eventually render one while the sentence spoke the other. Corrupting the stored flag changes
    nothing the lawyer sees."""
    store, client, _order = _matter(tmp_path, monkeypatch, cut_at_rank=1)
    run = _start(client, sample_size=99)
    with store._sf() as session, session.begin():
        session.get(SamplingRun, run["run_id"]).is_census = False   # a writer that lied
    done = _complete(client, _judge_all(client, run)["run_id"])
    assert done["is_census"] is True and done["estimate_kind"] == "census"
    assert "%" not in client.get(f"/api/matters/{MATTER}/bound").json()["copy_text"]


def test_one_family_short_of_a_census_is_a_sample(tmp_path: Path, monkeypatch) -> None:
    _store, client, _order = _matter(tmp_path, monkeypatch, cut_at_rank=1)
    everything = _start(client, sample_size=99)
    population = everything["population_families"]
    client.post(f"/api/matters/{MATTER}/sampling/runs/{everything['run_id']}/abandon")
    run = _start(client, sample_size=population - 1)
    done = _complete(client, _judge_all(client, run)["run_id"])
    assert done["is_census"] is False and done["estimate_kind"] == "bound"
    assert done["relevant_pieces"] is None


# ── input 3: repeated sampling — declared, never pooled, never cherry-picked ─────────────────────

def test_a_second_run_over_the_same_population_carries_its_ordinal(
    tmp_path: Path, monkeypatch
) -> None:
    _store, client, _order = _matter(tmp_path, monkeypatch, cut_at_rank=1)
    first = _start(client, sample_size=2)
    assert first["run_ordinal"] == 1 and first["repeated_draw_fr"] is None
    _complete(client, _judge_all(client, first)["run_id"])
    second = _start(client, sample_size=2)
    assert second["run_ordinal"] == 2
    done = _complete(client, _judge_all(client, second)["run_id"])
    assert "tirage n° 2" in (done["repeated_draw_fr"] or "")
    assert "jamais fusionnés" in (done["repeated_draw_fr"] or "")


def test_an_abandoned_run_still_counts_toward_the_ordinal(tmp_path: Path, monkeypatch) -> None:
    """Abandon-and-redraw is the cheapest route to a favourable number. A count that ignored the
    abandoned runs would be blind to exactly the behaviour it exists to make visible."""
    _store, client, _order = _matter(tmp_path, monkeypatch, cut_at_rank=1)
    first = _start(client, sample_size=2)
    client.post(f"/api/matters/{MATTER}/sampling/runs/{first['run_id']}/abandon")
    second = _start(client, sample_size=2)
    assert second["run_ordinal"] == 2


def test_moving_the_line_starts_a_new_population_and_the_ordinal_resets(
    tmp_path: Path, monkeypatch
) -> None:
    """The ordinal is about ONE frozen population. A different line is a different population, and
    a first draw over it is a first draw."""
    store, client, order = _matter(tmp_path, monkeypatch, cut_at_rank=1)
    first = _start(client, sample_size=2)
    client.post(f"/api/matters/{MATTER}/sampling/runs/{first['run_id']}/abandon")
    _cut_to(store, order[1])
    second = _start(client, sample_size=2)
    assert second["last_retained_piece_id"] != first["last_retained_piece_id"]
    assert second["run_ordinal"] == 1


def test_the_matters_bound_is_the_most_recent_run_not_the_most_flattering(
    tmp_path: Path, monkeypatch
) -> None:
    """The multiple-comparisons defence that actually bites. The first run finds nothing (the nice
    number); the second finds something (the unwelcome one). The product shows the second."""
    _store, client, _order = _matter(tmp_path, monkeypatch, cut_at_rank=1)
    flattering = _complete(client, _judge_all(client, _start(client, sample_size=3))["run_id"])
    unwelcome = _complete(
        client, _judge_all(client, _start(client, sample_size=3), relevant=2)["run_id"])
    assert unwelcome["prevalence_upper"] > flattering["prevalence_upper"]
    body = client.get(f"/api/matters/{MATTER}/bound").json()
    assert body["artefact_id"] == unwelcome["run_id"]
    assert body["prevalence_upper"] == unwelcome["prevalence_upper"]


# ── input 4: the numbers come from the freeze, and the method travels with them ──────────────────

def test_a_completed_run_records_the_method_that_produced_its_number(
    tmp_path: Path, monkeypatch
) -> None:
    _store, client, _order = _matter(tmp_path, monkeypatch, cut_at_rank=1)
    run = _start(client, sample_size=3)
    assert run["estimator_method"] is None                # nothing produced yet
    done = _complete(client, _judge_all(client, run)["run_id"])
    assert done["estimator_method"] == ESTIMATOR_METHOD
    assert client.get(f"/api/matters/{MATTER}/bound").json()["method"] == ESTIMATOR_METHOD


def test_a_run_frozen_before_the_sizes_existed_says_not_computable_never_zero(
    tmp_path: Path, monkeypatch
) -> None:
    """AC-7 / AD-19. A Story-5.1 row has no size list. Answering 0 would be a claim that no *pièce*
    is at risk — the flattering direction, and false."""
    store, client, _order = _matter(tmp_path, monkeypatch, cut_at_rank=1)
    run = _start(client, sample_size=3)
    with store._sf() as session, session.begin():         # as 5.1 left it
        session.get(SamplingRun, run["run_id"]).population_family_sizes = None
    done = _complete(client, _judge_all(client, run)["run_id"])
    assert done["estimate_kind"] == "bound"
    assert done["count_upper"] is not None
    assert done["count_upper_pieces"] is None
    body = client.get(f"/api/matters/{MATTER}/bound").json()
    assert body["count_upper_pieces"] is None
    assert "au pire" not in body["copy_text"]


def test_the_bound_is_computed_over_the_frozen_population_not_the_current_one(
    tmp_path: Path, monkeypatch
) -> None:
    """The freeze is what the number is about. A completed run's bound never moves afterwards, even
    though the *matter*'s discarded set has."""
    store, client, order = _matter(tmp_path, monkeypatch, cut_at_rank=1)
    run = _start(client, sample_size=99)
    done = _complete(client, _judge_all(client, run)["run_id"])
    frozen = (done["population_families"], done["count_upper"], done["prevalence_upper"])
    _cut_to(store, order[-1])                             # retain everything: the set is now empty
    after = _current(client)
    assert (after["population_families"], after["count_upper"], after["prevalence_upper"]) == frozen


# ── Story 5.3: the register that can say no, over HTTP ───────────────────────────────────────────

def _unproven(monkeypatch) -> None:  # noqa: ANN001
    """Flip the proven flag everywhere it is READ. Both modules import the predicate by name."""
    import apx.api.app as api
    import apx.core.app.read.freshness as read_freshness
    import apx.core.domain.sampling as sampling
    for module in (sampling, read_freshness, api):
        monkeypatch.setattr(module, "estimator_is_proven", lambda: False)


def test_an_unproven_estimator_ships_no_bound_on_any_surface(
    tmp_path: Path, monkeypatch
) -> None:
    """CONFIRMED [HIGH] ×2 by the review, on two different payloads. `/sampling/runs` read its
    numbers off the frozen ROW and `/bound` passed the worst-case pièce figure through ungated, so
    both announced `counts_only` and carried a bound anyway. The register is now disjoint on
    the WIRE, not only in the sentence."""
    _store, client, _order = _duplicated_matter(tmp_path, monkeypatch)
    run = _start(client, sample_size=1)
    done = _complete(client, _judge_all(client, run)["run_id"])
    assert done["estimate_kind"] == "bound" and done["count_upper"] is not None

    _unproven(monkeypatch)
    again = client.get(f"/api/matters/{MATTER}/sampling/runs/current").json()
    assert again["estimate_kind"] == "counts_only"
    for field in ("count_upper", "prevalence_upper", "count_upper_pieces", "relevant_pieces"):
        assert again[field] is None, f"/sampling/runs leaked {field} in the counts-only register"
    # the counts themselves survive — they are what was observed, not what was inferred
    assert again["sample_size"] >= 1 and again["relevant_found"] is not None

    bound = client.get(f"/api/matters/{MATTER}/bound").json()
    assert bound["kind"] == "counts_only"
    for field in ("count_upper", "prevalence_upper", "count_upper_pieces", "relevant_pieces"):
        assert bound[field] is None, f"/bound leaked {field} in the counts-only register"
    assert "%" not in bound["copy_text"]
    assert "Aucune borne" in bound["copy_text"]

    export = client.get(f"/api/matters/{MATTER}/bound/export")
    if export.status_code == 200:
        for field in ("count_upper", "prevalence_upper", "count_upper_pieces"):
            assert export.json()[field] is None, f"/bound/export leaked {field}"


def test_the_sizing_plan_says_when_the_bound_it_promises_will_not_be_stated(
    tmp_path: Path, monkeypatch
) -> None:
    """CONFIRMED [LOW] by the review. A sizing is a plan, but it is a quantitative promise about the
    bound the run will yield — offering "n familles suffisent pour 5 %" and then refusing to say
    5 % is a promise broken after an evening of verdicts."""
    _store, client, _order = _duplicated_matter(tmp_path, monkeypatch)
    ok = client.get(f"/api/matters/{MATTER}/sampling/sizing", params={"target": 0.6}).json()
    assert ok["bound_will_be_stated"] is True and ok["caveat_fr"] is None

    _unproven(monkeypatch)
    refused = client.get(f"/api/matters/{MATTER}/sampling/sizing", params={"target": 0.6}).json()
    assert refused["bound_will_be_stated"] is False
    assert refused["caveat_fr"] is not None and "pas de borne" in refused["caveat_fr"]
    assert refused["size"] == ok["size"], "the reading burden is unchanged; only the promise is"
