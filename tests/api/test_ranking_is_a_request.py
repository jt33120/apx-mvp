"""The ranking act becomes a request, and its cost is stated before it is paid (story 7.6).

Retro action **C11**: seven Epic-4 acts had no HTTP route, so Epic 5's surfaces answered *« pas de
classement, pas de ligne »* over a precondition only an operator's shell could create. AD-6 names
ranking by name as a **queued job** — validate, authorise, enqueue, return — and there was no ledger
to enqueue against.

Retro action **C17**, in the same story because the button is what makes it reachable: a new
*ranking version* moves ``ranking_version_no``, ``INPUTS_BY_KIND[KIND_SAMPLING_RUN]`` is every
observable, so **every open sampling run in the matter is invalidated**. ``_guard_open_run`` is a
*write* guard with two callers, both writes — it fires after the cascade has been paid for and can
only refuse to commit. What the lawyer met was a 409 on her *next verdict*, after which
``abandon_sampling_run`` audited ``verdicts_kept=`` the count of the hour she had just lost.
"""

from __future__ import annotations

import ast
from pathlib import Path

from fastapi.testclient import TestClient

from apx.adapters.store_postgres import queue as queue_module
from apx.core.app.pin import pin_piece
from apx.core.domain.sampling import RerankCost
from apx.core.domain.triage_sets import PinSide
from tests.api.test_ingest_api import _login, _prepare, _reset_state  # noqa: F401 — autouse
from tests.api.test_sampling_api import (
    MATTER,
    TENANT,
    WALL,
    _judge_all,
    _matter,
    _start,
)

OTHER_WALL = "autre"


def _enqueue(client: TestClient, **body) -> tuple[int, dict]:  # noqa: ANN003
    r = client.post(f"/api/matters/{MATTER}/ranking", json=body)
    return r.status_code, (r.json() if r.headers.get("content-type", "").startswith(
        "application/json") else {})


def _preview(client: TestClient) -> tuple[int, dict]:
    r = client.post(f"/api/matters/{MATTER}/ranking/preview")
    return r.status_code, r.json()


# ── AC1 — the request enqueues; the cascade is the worker's ───────────────────────────────────

def test_the_request_returns_a_handle_and_runs_no_cascade(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    """202, a handle, and the *matter*'s ranking is untouched by the request. Before this story the
    only way to produce a ranking was ``manage rank`` in an operator's shell."""
    store, client, _order = _matter(tmp_path, monkeypatch)
    before = store.read_ranking(tenant=TENANT, matter=MATTER, scopes={WALL}).version_no

    code, body = _enqueue(client)

    assert code == 202, body
    assert body["state"] == "queued" and body["matter"] == MATTER and body["job_id"]
    assert store.read_ranking(
        tenant=TENANT, matter=MATTER, scopes={WALL}).version_no == before, (
        "the request itself produced a ranking — the cascade is one model call per uncertain "
        "pièce and does not belong in a request (AD-6)")


def test_the_api_module_imports_no_ranking_act() -> None:
    """AD-6, stated over the source. A route that called ``produce_ranking`` or
    ``rank_and_draw_the_line`` inline would answer 202 and still have paid for the cascade."""
    tree = ast.parse(
        (Path(__file__).resolve().parents[2] / "apx" / "api" / "app.py").read_text("utf-8"))
    ranking_imports = [
        n.module for n in ast.walk(tree)
        if isinstance(n, ast.ImportFrom) and (n.module or "").startswith("apx.core.app.rank")]
    assert ranking_imports == [], f"the API imports the ranking act: {ranking_imports}"


# ── AC2 — the poll reads the LEDGER, never the queue (AD-17) ──────────────────────────────────

def test_the_poll_route_never_reads_the_queue(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    """The application-owned ledger is the sole authority (AD-17), so two readers can never
    disagree. Asserted by making the queue unusable and reading anyway."""
    _store, client, _order = _matter(tmp_path, monkeypatch)
    _code, started = _enqueue(client)

    class _Exploding:
        def __getattr__(self, name: str) -> object:
            raise AssertionError(f"the poll route touched the queue: app.{name}")

    monkeypatch.setattr(queue_module, "app", _Exploding())
    r = client.get(f"/api/rankings/{started['job_id']}")
    assert r.status_code == 200, r.text
    assert r.json()["state"] in ("queued", "running")


# ── AC8 — the version is minted at completion, never predicted at enqueue (AD-23) ─────────────

def test_the_handle_names_no_version_while_the_job_is_in_flight(
    tmp_path: Path, monkeypatch,  # noqa: ANN001
) -> None:
    """``version_no`` is minted inside ``record_ranking``'s transaction as ``max+1``. A number
    written at enqueue would be a prediction, and two jobs would both predict n+1 — leaving one
    permanently wrong on a row a lawyer's status panel reads."""
    _store, client, _order = _matter(tmp_path, monkeypatch)
    _code, started = _enqueue(client)
    body = client.get(f"/api/rankings/{started['job_id']}").json()
    assert body["version_no"] is None
    assert body["detail_fr"] is None


# ── AC4 — a queue that cannot be reached is a fact about THIS job, not a 503 ──────────────────

def test_a_failed_enqueue_is_recorded_on_the_job_never_answered_as_unavailable(
    tmp_path: Path, monkeypatch,  # noqa: ANN001
) -> None:
    """Story 7.4 closed this exact shape at the upload route, by a different cause: a 503 is a claim
    about *availability* over what is usually a permanent cause, in the direction a caller retries
    rather than reports. The ledger says what happened, in French."""
    _store, client, _order = _matter(tmp_path, monkeypatch)

    async def _boom(_job_id: str) -> None:
        raise RuntimeError("procrastinate_jobs does not exist")

    monkeypatch.setattr("apx.api.app.enqueue_ranking", _boom)
    code, body = _enqueue(client)

    assert code == 202, body
    assert body["state"] == "failed", "a permanent cause was answered as a retryable one"
    job = client.get(f"/api/rankings/{body['job_id']}").json()
    assert job["state"] == "failed"
    assert "file d'attente" in job["detail_fr"]


def test_a_failed_job_does_not_wedge_the_matter(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    """The open-job index is ``state NOT IN ('done','failed')``, not the import ledger's
    ``state != 'done'``. Under the import's form a failed job would hold the *matter*'s re-rank shut
    for ever, with no way back."""
    _store, client, _order = _matter(tmp_path, monkeypatch)

    async def _boom(_job_id: str) -> None:
        raise RuntimeError("nope")

    monkeypatch.setattr("apx.api.app.enqueue_ranking", _boom)
    first = _enqueue(client)[1]
    monkeypatch.undo()

    code, second = _enqueue(client)
    assert code == 202 and second["job_id"] != first["job_id"]


# ── AC7 — one open job per matter, and never the running job's handle ─────────────────────────

def test_a_second_request_while_one_is_open_is_refused_and_not_handed_the_handle(
    tmp_path: Path, monkeypatch,  # noqa: ANN001
) -> None:
    """``ingest_upload`` returns the existing handle on this race, and that is right for an import —
    a re-submitted folder is the same act. A second rank is a different one: the case theory may
    have moved, which is what ``record_ranking``'s conditional commit raises over. Returning the
    in-flight handle would tell a lawyer her re-rank was accepted while the running job computes on
    the old theory."""
    _store, client, _order = _matter(tmp_path, monkeypatch)
    first = _enqueue(client)[1]

    code, body = _enqueue(client)
    assert code == 409
    assert first["job_id"] not in str(body)


# ── AC6 / C17 — the cost is stated, and the confirmation names it ─────────────────────────────

def _run_with_verdicts(client: TestClient, *, relevant: int = 0) -> dict:
    run = _start(client, sample_size=2)
    return _judge_all(client, run, relevant=relevant)


def test_a_rerank_over_an_open_run_is_refused_until_the_count_is_named(
    tmp_path: Path, monkeypatch,  # noqa: ANN001
) -> None:
    """The defect, reversed. Nothing warned: the lawyer met the consequence on her next verdict."""
    _store, client, _order = _matter(tmp_path, monkeypatch, cut_at_rank=2)
    _run_with_verdicts(client)

    code, body = _enqueue(client)
    assert code == 409, body
    assert "tirage" in body["detail"]

    code, body = _enqueue(client, confirmed_open_runs=1)
    assert code == 202, body


def test_a_confirmation_naming_the_wrong_count_is_refused(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    """FR-45(a)'s lesson applied to runs: a count that does not match confirms a different act."""
    _store, client, _order = _matter(tmp_path, monkeypatch, cut_at_rank=2)
    _run_with_verdicts(client)
    code, body = _enqueue(client, confirmed_open_runs=4)
    assert code == 409 and "4 tirage(s)" in body["detail"]


def test_the_sentence_names_the_cause_in_french_never_the_stamp_key(
    tmp_path: Path, monkeypatch,  # noqa: ANN001
) -> None:
    """The 409 a lawyer meets on a verdict today ends in the raw ``ranking_version_no``, because it
    interpolates the exception's comma-joined keys. The French has existed since FR-58."""
    _store, client, _order = _matter(tmp_path, monkeypatch, cut_at_rank=2)
    _run_with_verdicts(client)
    _code, cost = _preview(client)
    assert "un nouveau classement" in cost["sentence_fr"]
    assert "ranking_version_no" not in cost["sentence_fr"]


def test_the_verdicts_at_risk_count_families_not_rows(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    """The nearly-right referent, in the one sentence about what her work cost.
    ``abandon_sampling_run`` audits ``verdicts_kept=len(_current_verdicts(...))``, which is max-seq
    **per family**: a lawyer who corrected one family wrote two rows and contributes one. Promising
    fourteen and auditing eleven is the defect this project keeps making."""
    _store, client, _order = _matter(tmp_path, monkeypatch, cut_at_rank=2)
    run = _start(client, sample_size=2)
    family = run["drawn"][0]["unit"]["family_id"]
    for relevant in (True, False):                      # two ROWS on ONE family
        assert client.post(
            f"/api/matters/{MATTER}/sampling/runs/{run['run_id']}/verdicts",
            json={"family_id": family, "relevant": relevant}).status_code == 200

    _code, cost = _preview(client)
    assert cost["verdicts_at_risk"] == 1, "a row count, not a judged-family count"


def test_a_matter_with_no_open_run_says_so_and_is_not_refused(
    tmp_path: Path, monkeypatch,  # noqa: ANN001
) -> None:
    """The clause appears only when there is something to say — the ordinary first ranking must not
    be made harder, and a warning that always fires trains the reader to skip it."""
    _store, client, _order = _matter(tmp_path, monkeypatch)
    _code, cost = _preview(client)
    assert cost["open_runs"] == 0 and cost["verdicts_at_risk"] == 0
    assert "Aucun tirage en cours" in cost["sentence_fr"]
    assert _enqueue(client)[0] == 202


def test_an_already_invalidated_run_is_not_counted_as_about_to_be_lost(
    tmp_path: Path, monkeypatch,  # noqa: ANN001
) -> None:
    """The cost counts the DERIVED state, never the stored status. A run stored ``open`` may already
    be invalidated by an earlier act, and promising *"you will invalidate one run"* over a run that
    is already dead over-states the loss — in a number the server then re-checks."""
    store, client, order = _matter(tmp_path, monkeypatch, cut_at_rank=2)
    _run_with_verdicts(client)
    assert _preview(client)[1]["open_runs"] == 1

    pin_piece(store, tenant=TENANT, matter=MATTER, actor="me.durand", piece_id=order[-1],
              side=PinSide.RETAIN, reason="pièce décisive", scopes={WALL})

    _code, cost = _preview(client)
    assert cost["open_runs"] == 0, "an already-invalidated run was counted as about to be lost"
    assert _enqueue(client)[0] == 202


def test_a_cost_that_could_not_be_read_refuses_rather_than_reading_as_free() -> None:
    """``None`` means **not read** — empty scopes, a walled or absent *matter*, a freshness read
    that failed mid-sweep. Coerced to a zero cost, every one of those becomes *nothing at risk,
    proceed silently*. Only ``()`` means read-and-none, and that is a real ``RerankCost``."""
    assert RerankCost(open_runs=0, verdicts_at_risk=0).is_free
    assert "Aucun tirage" in RerankCost(0, 0).sentence_fr()


# ── AC5 — absent and walled answer identically (FR-14) ────────────────────────────────────────

def test_every_route_answers_a_walled_matter_exactly_as_an_absent_one(
    tmp_path: Path, monkeypatch,  # noqa: ANN001
) -> None:
    """A 403 here would be the one place a caller could learn that another firm's dossier exists by
    being refused differently (the reasoning ``start_run`` writes out in source)."""
    store, client, _order = _matter(tmp_path, monkeypatch)
    started = _enqueue(client)[1]
    store.create_user(TENANT, "autre@cab.fr", "motdepasse", "Me Autre", {OTHER_WALL})
    outsider = TestClient(client.app)
    _login(outsider, "autre@cab.fr", pw="motdepasse")

    walled = [
        outsider.post(f"/api/matters/{MATTER}/ranking/preview"),
        outsider.post(f"/api/matters/{MATTER}/ranking", json={}),
        outsider.get(f"/api/rankings/{started['job_id']}"),
        outsider.post(f"/api/matters/{MATTER}/line", params={"version_no": 1}),
    ]
    absent = [
        outsider.post("/api/matters/inconnu/ranking/preview"),
        outsider.post("/api/matters/inconnu/ranking", json={}),
        outsider.get("/api/rankings/00000000000000000000000000000000"),
        outsider.post("/api/matters/inconnu/line", params={"version_no": 1}),
    ]
    for w, a in zip(walled, absent, strict=True):
        assert w.status_code == a.status_code == 404, (w.text, a.text)
        assert w.json()["detail"] == a.json()["detail"]


def test_a_walled_request_writes_no_job(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    """Nothing is written on the refused path — the wall gate comes before the ledger."""
    store, client, _order = _matter(tmp_path, monkeypatch)
    store.create_user(TENANT, "autre@cab.fr", "motdepasse", "Me Autre", {OTHER_WALL})
    outsider = TestClient(client.app)
    _login(outsider, "autre@cab.fr", pw="motdepasse")
    outsider.post(f"/api/matters/{MATTER}/ranking", json={})
    assert store.open_ranking_job(TENANT, MATTER) is None


# ── AC9 — the remedy places a cut over a NAMED version ────────────────────────────────────────

def test_the_line_route_places_the_cut_over_the_version_it_is_given(
    tmp_path: Path, monkeypatch,  # noqa: ANN001
) -> None:
    """The route exists to place a cut over the version a FAILED job already recorded, so the number
    is the request's and never the server's guess at *the latest* — which story 7.5 calls right by
    accident today and catastrophic the moment two acts overlap."""
    store, client, _order = _matter(tmp_path, monkeypatch)
    current = store.read_ranking(tenant=TENANT, matter=MATTER, scopes={WALL})
    r = client.post(f"/api/matters/{MATTER}/line", params={"version_no": current.version_no})
    assert r.status_code == 200, r.text
    assert r.json()["placed"] is True and r.json()["last_retained_piece_id"]


def test_the_line_route_requires_a_version(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    """Fail closed at the edge. ``place_line``'s own signature defaults to ``None`` (the latest),
    and a route that inherited that default would silently place a cut over whichever version
    happened to be current when the request landed."""
    _store, client, _order = _matter(tmp_path, monkeypatch)
    assert client.post(f"/api/matters/{MATTER}/line").status_code == 422
