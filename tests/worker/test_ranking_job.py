"""The queued ranking job (story 7.6, AD-6/AD-17), tested against in-memory SQLite.

``_run_ranking`` is pure of Procrastinate, so the load-bearing mechanics are driven directly, the
way ``_run_import``'s are: the attempt counter advanced BEFORE the work, one cascade per job ever,
every failure a terminal ledger state rather than a raise, and the half-done act — the order
committed and the cut not drawn, which story 7.5 exists to prevent and which two transactions can
still reach — recorded with the version it minted, so the remedy is reachable rather than inferable
from *the latest*.
"""

from __future__ import annotations

import ast
from datetime import UTC, datetime
from pathlib import Path

import pytest

from apx.adapters.store_postgres.queue import _RANKING_MAX_ATTEMPTS, _run_ranking
from apx.checks.queue_open import every_defer_opens_the_queue
from apx.core.app.line import place_line
from tests.api.test_ingest_api import _login, _prepare, _reset_state  # noqa: F401 — autouse
from tests.api.test_sampling_api import MATTER, TENANT, WALL, _matter
from tests.scoring_fakes import FailingJudge, FakeScorer, FixedJudge

ACTOR = "Me Durand"


class _Embedder:
    """The identity halves ``identity_inputs`` stamps into the immutable fingerprint. A fake is
    substituted at the composition root's seam (AD-11) — a local model is not something a test
    carries, and the scorer seam beside it is why this job never needs pgvector."""

    model_id = "bge-m3"
    model_version = "1.5"

    def embed(self, texts):  # noqa: ANN001, ANN201
        return [[0.0] * 8 for _ in texts]


def _ready(tmp_path: Path, monkeypatch):  # noqa: ANN001, ANN202
    """A real *matter* with a real corpus, ranked once, and a queued ranking job over it."""
    store, _client, order = _matter(tmp_path, monkeypatch)
    job_id = "job-1"
    store.create_ranking_job(
        job_id=job_id, tenant=TENANT, matter=MATTER, scope=WALL, actor=ACTOR,
        now=datetime.now(UTC))
    return store, job_id, order


def _scorer(order: list[str]) -> FakeScorer:
    return FakeScorer({p: 0.95 - 0.1 * i for i, p in enumerate(order)})


class _RefusingToPlace:
    """The real store in every respect but one: drawing the cut raises. That is the second of the
    act's two transactions, and it is deliberately separate — a placement failure must not roll back
    an order that cost one model call per uncertain *pièce*."""

    def __init__(self, real) -> None:  # noqa: ANN001
        self._real = real

    def __getattr__(self, name: str) -> object:
        return getattr(self._real, name)

    def place_line(self, **_kw: object) -> None:
        raise RuntimeError("le disque est plein")


def _run(store, job_id, order, *, judge=None, placer_raises=False) -> None:  # noqa: ANN001
    _run_ranking(
        _RefusingToPlace(store) if placer_raises else store, job_id, embedder=_Embedder(),
        judge=judge or FixedJudge(), scorer=_scorer(order))


# ── the ordinary path ─────────────────────────────────────────────────────────────────────────

def test_a_queued_job_produces_a_version_and_draws_its_cut(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    """The act is ``rank_and_draw_the_line``, never ``produce_ranking``: a version with no cut
    leaves the *matter* worse than before the re-rank, and silently (story 7.5)."""
    store, job_id, order = _ready(tmp_path, monkeypatch)
    before = store.read_ranking(tenant=TENANT, matter=MATTER, scopes={WALL}).version_no

    _run(store, job_id, order)

    job = store.read_ranking_job(job_id)
    assert job.state == "done" and job.detail is None
    assert job.version_no == before + 1
    line = store.read_current_line(
        tenant=TENANT, matter=MATTER, scopes={WALL}, version_no=job.version_no)
    assert line is not None, "the version was minted with no cut — the state 7.5 exists to close"


# ── the half-done act ─────────────────────────────────────────────────────────────────────────

def test_a_cut_that_could_not_be_drawn_is_recorded_with_the_version_it_left_behind(
    tmp_path: Path, monkeypatch,  # noqa: ANN001
) -> None:
    """Two transactions, deliberately — a placement failure must not roll back an order that cost
    one model call per uncertain *pièce*. So the half-done state is reachable, and the ledger NAMES
    it: without the number the only remedy would be *place a line over the latest*, the referent
    this codebase refuses."""
    store, job_id, order = _ready(tmp_path, monkeypatch)

    _run(store, job_id, order, placer_raises=True)

    job = store.read_ranking_job(job_id)
    assert job.state == "failed"
    assert job.version_no is not None, "the failure lost the number the remedy needs"
    assert f"classement n° {job.version_no}" in job.detail
    # and the remedy actually works over that version
    assert place_line(
        store, tenant=TENANT, matter=MATTER, actor=ACTOR, scopes={WALL},
        version_no=job.version_no) is not None


# ── every failure is a ledger state ───────────────────────────────────────────────────────────

def test_a_failing_judge_ends_the_job_rather_than_raising(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    """A raise would reach Procrastinate as a retryable error and re-pay the whole cascade. It is
    also the shape story 7.4 closed: an availability answer over a permanent cause."""
    store, job_id, order = _ready(tmp_path, monkeypatch)

    _run(store, job_id, order, judge=FailingJudge())

    job = store.read_ranking_job(job_id)
    assert job.state in ("done", "failed")
    if job.state == "failed":
        assert job.detail and job.detail.startswith("le classement")


def test_a_job_whose_matter_is_no_longer_held_reads_nothing(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    """The wall is re-checked in the worker, BEFORE anything is read. ``read_case_theory`` answers
    ``None`` for out-of-scope and for absent alike, and a ``None`` theory is also how the act says
    *rank on intrinsic signals* — so without the gate a job that lost its wall would produce a
    complete, permanently fingerprinted ranking whose header names a deliberate methodology for a
    theory that was simply never fetched."""
    store, open_job, order = _ready(tmp_path, monkeypatch)
    # the open-job index is real: terminate the fixture's job before opening another on this matter
    store.fail_ranking_job(open_job, detail="abandonné par le test", now=datetime.now(UTC))
    job_id = "job-walled"
    store.create_ranking_job(
        job_id=job_id, tenant=TENANT, matter=MATTER, scope="un-mur-que-personne-ne-tient",
        actor=ACTOR, now=datetime.now(UTC))
    before = store.read_ranking(tenant=TENANT, matter=MATTER, scopes={WALL}).version_no

    _run(store, job_id, order)

    assert store.read_ranking_job(job_id).state == "failed"
    assert store.read_ranking(
        tenant=TENANT, matter=MATTER, scopes={WALL}).version_no == before


# ── one cascade per job, ever ─────────────────────────────────────────────────────────────────

def test_a_re_dispatch_never_pays_for_a_second_cascade(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    """The import's hundred attempts are safe only because a re-dispatch processes ONLY still-
    pending units. ``run_cascade`` is one monolithic in-memory pass with no checkpoint, so a retry
    re-pays one model call per uncertain *pièce* over the whole *matter*."""
    store, job_id, order = _ready(tmp_path, monkeypatch)
    assert _RANKING_MAX_ATTEMPTS == 1

    first = FixedJudge()
    _run(store, job_id, order, judge=first)
    done = store.read_ranking_job(job_id)
    assert done.state == "done"

    # a terminal job is a no-op; and a job re-dispatched before it terminated is capped
    second = FixedJudge()
    _run(store, job_id, order, judge=second)
    assert second.calls == [], "a re-dispatch re-ran the cascade"

    store.create_ranking_job(
        job_id="job-2", tenant=TENANT, matter=MATTER, scope=WALL, actor=ACTOR,
        now=datetime.now(UTC))
    store.bump_ranking_attempt("job-2", datetime.now(UTC))     # as if a dispatch had begun
    third = FixedJudge()
    _run(store, "job-2", order, judge=third)
    assert store.read_ranking_job("job-2").state == "failed"
    assert third.calls == [], "the ledger cap let a second dispatch pay for the cascade again"


def test_the_attempt_counter_advances_before_the_work(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    """AD-17's mechanic: committed in its own transaction BEFORE the work, so an OS-level kill
    still advances it and a resume can never loop onto the same expensive pass for ever."""
    store, job_id, order = _ready(tmp_path, monkeypatch)
    assert store.read_ranking_job(job_id).attempts == 0
    _run(store, job_id, order)
    assert store.read_ranking_job(job_id).attempts == 1


# ── AC3 — the enqueue helper opens the queue, and the check would say so if it did not ─────────

def test_the_ranking_enqueue_is_seen_by_the_defer_check() -> None:
    """Two enqueue helpers now, each opening the queue in its own body. ``PsycopgConnector.pool``
    raises ``AppNotOpen`` until ``open_async`` has been called, and the suite cannot see it: the
    connector is chosen from ``DATABASE_URL`` at import time and SQLite yields the in-memory
    connector, the one implementation with no such guard."""
    result = every_defer_opens_the_queue()
    assert result.ok, result.detail
    assert "2 enqueue helper(s)" in result.detail


def test_removing_the_open_call_turns_the_check_red(tmp_path: Path) -> None:
    """The negative proof. A green suite is not evidence here — it is evidence in the one
    configuration where the defect cannot appear — so the check is exercised against a tree that
    has the call removed."""
    src = (Path(__file__).resolve().parents[2]
           / "apx" / "adapters" / "store_postgres" / "queue" / "__init__.py").read_text("utf-8")
    broken = src.replace(
        "    await ensure_open()\n    await run_ranking.defer_async(job_id=job_id)",
        "    await run_ranking.defer_async(job_id=job_id)")
    assert broken != src, "the enqueue helper's shape changed; this proof no longer proves anything"

    root = tmp_path / "apx" / "adapters" / "store_postgres" / "queue"
    root.mkdir(parents=True)
    (root / "__init__.py").write_text(broken, encoding="utf-8")
    ast.parse(broken)                                   # the fixture is still valid Python

    result = every_defer_opens_the_queue([tmp_path])
    assert not result.ok
    assert "enqueue_ranking" in result.detail


@pytest.mark.parametrize("state", ["done", "failed"])
def test_a_terminal_job_is_never_reopened(tmp_path: Path, monkeypatch, state: str) -> None:  # noqa: ANN001
    """A re-dispatch of a terminal job is a no-op — the import ledger's rule, and the reason a
    failed job does not silently become a running one."""
    store, job_id, order = _ready(tmp_path, monkeypatch)
    now = datetime.now(UTC)
    if state == "done":
        store.finish_ranking_job(job_id, version_no=99, now=now)
    else:
        store.fail_ranking_job(job_id, detail="déjà échoué", now=now)

    judge = FixedJudge()
    _run(store, job_id, order, judge=judge)

    assert store.read_ranking_job(job_id).state == state
    assert judge.calls == []
