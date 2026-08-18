"""The bounded runtime probe: never hard-delete (Story 4.12, FR-21/FR-5/AD-7).

Every story so far kept this promise **about itself** — the register resolves by state change (2.6),
the index never wipes itself (2.8), a withdrawn *case theory* is an appended version (4.1), a label
reverts by a new ledger entry (4.5), retained/discarded are VIEWS (4.7), **the line** moves by a new
placement (4.8/4.9), a pin is removed by a ``removed`` entry (4.11), a justification is rejected
reversibly (4.6). This probe stops asking each story to be trusted separately and proves the
property **over the whole enumerated action surface at once**.

It builds a real *matter* — real *pièces*, real *chunks*, a real *failure register* entry, a real
ranking, a real label / line / pin / justification — then **executes every state-changing action in
:data:`apx.checks.user_actions.USER_ACTIONS`** and, after each one, asserts that no **evidential**
table lost a row. Evidential means *every mapped table except the written transient allow-list*, so
a table a later story adds is protected without anyone remembering to protect it.

The bound is the registry, and the registry's completeness is a structural property
(``user_action_registry_is_complete``) — so "we exercised everything" is checked, not claimed. The
probe additionally asserts its own coverage: an action it forgets to exercise fails the test.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select
from sqlalchemy.engine import Engine

from apx.adapters.extraction.files import FileExtractor
from apx.adapters.store_postgres.models import Base, Chunk, TruncationMarker
from apx.adapters.store_postgres.queue import _run_import
from apx.adapters.store_postgres.store import SqlStore
from apx.api.app import app
from apx.checks.user_actions import TRANSIENT_TABLES, USER_ACTIONS, evidential_tables
from apx.core.app.ingest import IngestedFailure, IngestionResult, ingest_one_file
from apx.core.app.justification import (
    record_justification,
    reject_justification,
    restore_justification,
)
from apx.core.app.label import assign_taxonomy_label, revert_taxonomy_label
from apx.core.app.line import move_line, place_line, price_line_move
from apx.core.app.pin import pin_piece, remove_pin
from apx.core.app.rank import produce_ranking, rank_and_draw_the_line
from apx.core.app.register_override import (
    override_register_entry as core_override_register_entry,
)
from apx.core.domain.cascade import CascadeUnit, IntrinsicSignal
from apx.core.domain.config import CascadeConfig
from apx.core.domain.failures import ErrorClass
from apx.core.domain.justification import EvidenceExtract, JustificationBasis
from apx.core.domain.ranking import RankingIdentityInputs
from apx.core.domain.triage import Label, PieceLabel, TriageOutcome
from apx.core.domain.triage_sets import PinSide
from tests.api.test_ingest_api import _login, _prepare, _reset_state  # noqa: F401 — autouse fixture
from tests.embedding_fakes import FakeEmbedder
from tests.scoring_fakes import FakeScorer, FixedJudge

TENANT, WALL, WALL2, MATTER = "t", "wall", "wall-2", "m"
ADMIN, OTHER, UNSCOPED = "admin@cab.fr", "confrere@cab.fr", "stagiaire@cab.fr"
_QUOTE = "Contrat de bail commercial"
_TEXTS = {
    "bail.txt": "Contrat de bail commercial signé le 3 mars, avec clause résolutoire.",
    "facture.txt": "Facture EDF, 150 euros, échéance avril.",
    "note.txt": "Note interne sur la clause résolutoire du bail.",
}


# ── the census ───────────────────────────────────────────────────────────────────────────────────
def _census(store: SqlStore) -> dict[str, int]:
    """Row counts for EVERY mapped table — not a hand-picked five, so a ledger a later story adds
    is under the probe from the day it exists."""
    with store._sf() as s:
        return {t.name: s.scalar(select(func.count()).select_from(t)) for t in
                Base.metadata.sorted_tables}


def _assert_nothing_lost(action: str, before: dict[str, int], after: dict[str, int]) -> None:
    """FR-21: after a user-reachable action, no evidential table has fewer rows than before it."""
    for table in sorted(evidential_tables(before)):
        assert after[table] >= before[table], (
            f"{action} reduced {table} from {before[table]} to {after[table]} — no control in the "
            "product performs a hard deletion of evidential material; anything a user could read "
            "as deletion is a reversible, labelled, recorded state change (FR-21/AD-7). If this "
            "deletion is legitimate, the table belongs in TRANSIENT_TABLES with a written reason.")


# The ONE written residual of this probe, named here so it is not a silent skip. These two actions
# write their evidential row (the audited open, FR-45) only when they actually SERVE content, and
# serving needs material this SQLite harness does not produce: a renderable office document, and a
# scanned page carrying an OCR layer. The probe still EXECUTES them — on their honest not-served
# path, which is the FR-14 non-disclosing behaviour — and still asserts they delete nothing. What it
# cannot observe here is the write, so the "declared True really writes" leg is asserted for them by
# tests/api/test_piece_render_endpoint.py and tests/api/test_scan_endpoints.py instead.
_WRITE_NOT_OBSERVABLE_HERE = {
    "open-piece-render": "needs a renderable office document; a .txt pièce serves no render",
    "open-piece-page": "needs a scanned page with a stored OCR layer",
}


@dataclass
class _Step:
    """One probe step: the registered action names it exercises, and the call that exercises them.
    A step may cover more than one name — driving ``POST /api/ingest`` also drives
    ``ingest.ingest_folder`` — but every state-changing action must be covered by some step."""

    covers: tuple[str, ...]
    run: Callable[[], None]


# ── the write recorder: what the action ACTUALLY did to the database ─────────────────────────────
_WRITE_SQL = re.compile(r"^\s*(insert\s+into|update|delete\s+from)\s+[\"'`\[]?(\w+)", re.IGNORECASE)


@contextmanager
def _writes_recorded() -> Iterator[dict[str, set[str]]]:
    """Record every INSERT / UPDATE / DELETE issued by ANY engine while the block runs.

    Listening at the ``Engine`` class level (not on one instance) is what makes this honest: the
    TestClient's app builds its own store and its own engine, so an instance listener would watch
    the wrong connection and see nothing. Reading the raw SQL — rather than ORM mapper events —
    catches the bulk form ``session.execute(delete(X))`` as well as ``session.delete(obj)``: the
    v1-era wipe used exactly the form the ORM events do not fire for."""
    seen: dict[str, set[str]] = {"insert": set(), "update": set(), "delete": set()}

    def _listen(conn, cursor, statement, parameters, context, executemany) -> None:  # noqa: ANN001
        match = _WRITE_SQL.match(statement)
        if match:
            seen[match.group(1).split()[0].lower()].add(match.group(2))

    event.listen(Engine, "before_cursor_execute", _listen)
    try:
        yield seen
    finally:
        event.remove(Engine, "before_cursor_execute", _listen)


def _assert_no_evidential_delete(
    action: str, writes: dict[str, set[str]], tables: set[str]
) -> None:
    """FR-21, stated as FR-21 actually states it: **no hard deletion**, not "no net loss of rows".

    A per-table count comparison is not enough — an action that deletes evidential rows and inserts
    at least as many in the same call leaves the counts flat, and the ordinary ORM refactor of an
    upsert ("delete the children for this parent, then re-add them") is exactly that shape. So the
    probe watches the statements, not the totals."""
    hit = sorted(writes["delete"] & tables)
    assert not hit, (
        f"{action} issued a DELETE against evidential table(s) {hit} — no control in the product "
        "performs a hard deletion of a pièce, a chunk, an audit record entry, a change log entry "
        "or a failure register entry; anything a user could read as deletion is a reversible, "
        "labelled, recorded state change (FR-21/AD-7). If this deletion is legitimate, the table "
        "belongs in TRANSIENT_TABLES with a written reason.")


# ── the world the probe acts on ──────────────────────────────────────────────────────────────────
def _cfg() -> CascadeConfig:
    return CascadeConfig(uncertain_low=0.35, uncertain_high=0.65, calibration_sample=0,
                         stage3_max_share=1.0)


def _inputs() -> RankingIdentityInputs:
    return RankingIdentityInputs(
        case_theory_version_id=None, model_provider="mistral",
        model_endpoint="https://api.mistral.ai/v1", model_name="mistral-small-latest",
        prompt_version="cascade-question-v1", temperature=0.0, sampling={"top_p": 1.0},
        embedder_model_id="bge-m3", embedder_model_version="1.5",
        chunking_config_version="chunk-v1", schema_version="slice-a")


def _folder(root: Path, name: str) -> Path:
    """A folder of real *pièces*. The content is salted with the folder name so two folders are
    never byte-identical: identity is (content hash, matter) (AD-8), so a second ingestion of the
    same bytes would deduplicate to nothing and the probed step would persist NOTHING — a step that
    does nothing proves nothing."""
    d = root / name
    d.mkdir()
    for filename, text in _TEXTS.items():
        (d / filename).write_text(f"{text} [{name}]", encoding="utf-8")
    return d


def _units(store: SqlStore, matter: str) -> list[CascadeUnit]:
    """Real cascade units over the matter's real pièces and their real chunk ids."""
    with store._sf() as s:
        rows = list(s.execute(
            select(Chunk.piece_id, Chunk.chunk_id).where(Chunk.matter == matter)
            .order_by(Chunk.piece_id, Chunk.position)))
    by_piece: dict[str, list[str]] = {}
    for piece, chunk in rows:
        by_piece.setdefault(piece, []).append(chunk)
    return [CascadeUnit(piece_id=p, text=p, chunk_ids=tuple(c))
            for p, c in sorted(by_piece.items())]


def _seed_failure(store: SqlStore, matter: str) -> None:
    """Real failure-register entries, so the probe has some to protect (FR-5/FR-21).

    Three, because three registered actions act on one each and each consumes it: the retry, and
    Story 5.6's two override steps (the seam and the route). An override closes an OPEN entry and
    refuses one that moved, so they cannot share."""
    store.save(
        IngestionResult(failures=[
            IngestedFailure(
                filename=name, submitted_path=path, matter=matter, tenant=TENANT,
                error_class=ErrorClass.PASSWORD_PROTECTED, detail="mot de passe",
                custodian="Me Martin")
            for name, path in (
                ("scelle.pdf", "/dossier/scelle.pdf"),
                ("scelle-2.pdf", "/dossier/scelle-2.pdf"),
            )
        ]), actor="Me Dupont", scope=WALL, matter=matter, tenant=TENANT)


def _open_entry(store: SqlStore, submitted_path: str) -> str:
    """The id of the still-OPEN register entry at ``submitted_path`` — resolved at step time, so a
    step never assumes what an earlier step left behind."""
    for e in store.register_all(TENANT, {WALL, WALL2}, is_admin=True):
        if e.submitted_path == submitted_path and e.resolution_state == "open":
            return e.id
    raise AssertionError(f"no open register entry at {submitted_path}")


def _seed_discards(store: SqlStore, matter: str) -> None:
    """Label every pièce discarded (Story 2.x). Since Story 5.1 this is NOT the population a
    *sampling run* draws over — that is the Epic-4 derived view (decision A1) — but it is still
    real arrangement: it gives the label ledger rows the probe must prove nothing destroys."""
    reps = store.representatives(matter, TENANT, {WALL})
    labels = tuple(PieceLabel(pid, Label.DISCARD, "mise à l'écart") for pid, _ in reps)
    store.save_labels(matter, TENANT, {WALL}, TriageOutcome(labels), "criteria", actor="seed")


# ── the probe ────────────────────────────────────────────────────────────────────────────────────
def test_no_registered_action_reduces_any_evidential_count(tmp_path: Path, monkeypatch) -> None:
    """AC-2/AC-3: execute every state-changing registered action against a real seeded *matter* and
    assert no evidential table loses a row — the FR-21 property, proven by exercise."""
    store = _prepare(tmp_path, monkeypatch)
    store.create_user(TENANT, ADMIN, "motdepasse", "Me Durand", {WALL, WALL2}, is_admin=True)
    # a colleague holding NO wall — the fail-closed path the Postgres-only semantic engine
    # is driven through on this SQLite harness (its audit of the query happens either way).
    store.create_user(TENANT, UNSCOPED, "motdepasse", "Le stagiaire", set())
    folder, second = _folder(tmp_path, "dossier"), _folder(tmp_path, "dossier-2")
    single = tmp_path / "seule.txt"
    single.write_text("Une pièce isolée, versée à part.", encoding="utf-8")
    state: dict[str, object] = {}

    with TestClient(app) as client:
        # ── arrangement: a real corpus, a real failure entry, a real ranking ──
        _login(client, ADMIN, pw="motdepasse")
        client.post("/api/ingest",
                    json={"folder": str(folder), "matter": MATTER, "scope": WALL})
        _seed_failure(store, MATTER)
        _seed_discards(store, MATTER)
        pieces = [pid for pid, _ in store.representatives(MATTER, TENANT, {WALL})]
        assert pieces, "the probe needs a real corpus to act on"
        chunk_of = {u.piece_id: u.chunk_ids[0] for u in _units(store, MATTER)}

        def _rank() -> None:
            produce_ranking(
                _units(store, MATTER), case_theory=None,
                scorer=FakeScorer({p: 0.9 - 0.3 * i for i, p in enumerate(pieces)}),
                judge=FixedJudge(), config=_cfg(), inputs=_inputs(), tenant=TENANT, matter=MATTER,
                actor="me.durand", scopes={WALL}, recorder=store)

        def _rank_and_draw() -> None:
            """The paired act (Story 7.5): a second version, WITH its cut. The probe walks it as
            its own step because it writes both a ranking and a placement, and the question this
            probe asks — did anything evidential disappear — is exactly the one a re-rank raises:
            version 1's rows and its placements must still be there afterwards."""
            rank_and_draw_the_line(
                _units(store, MATTER), case_theory=None,
                scorer=FakeScorer({p: 0.9 - 0.3 * i for i, p in enumerate(pieces)}),
                judge=FixedJudge(), config=_cfg(), inputs=_inputs(), tenant=TENANT, matter=MATTER,
                actor="me.durand", scopes={WALL}, recorder=store, placer=store)

        def _place() -> None:
            line = place_line(
                store, tenant=TENANT, matter=MATTER, actor="me.durand", scopes={WALL})
            assert line is not None, "the tool must commit to a line for the move step to act on"
            state["line"] = line

        def _move() -> None:
            line = state["line"]
            target = pieces[-1]
            priced = price_line_move(
                store, tenant=TENANT, matter=MATTER, scopes={WALL},
                candidate_last_retained_piece_id=target)
            move_line(
                store, tenant=TENANT, matter=MATTER, actor="me.durand", scopes={WALL},
                last_retained_piece_id=target, expected_seq=line.seq,  # type: ignore[union-attr]
                priced_statement=str(priced))

        def _ingest_one() -> None:
            result = ingest_one_file(
                single, "seule.txt", MATTER, TENANT, FileExtractor(), custodian="Me Durand")
            store.save(result, actor="Me Dupont", scope=WALL, matter=MATTER, tenant=TENANT)

        def _upload() -> None:
            resp = client.post(
                "/api/ingest-upload",
                files=[("files", (n, f"{t} [upload]".encode(), "text/plain"))
                       for n, t in _TEXTS.items()],
                data={"matter": "m-2", "scope": WALL, "custodian": "Me Durand"})
            assert resp.status_code == 202, resp.text
            state["job_id"] = resp.json()["job_id"]
            _run_import(store, resp.json()["job_id"], embedder=FakeEmbedder())

        # ── Story 5.1: the sampling run over the DERIVED discarded set ──
        _BOTH = {WALL, WALL2}   # the matter is rescoped late in the probe; hold both walls

        def _cut_the_line_for_sampling() -> None:
            """ARRANGEMENT: move the line to the TOP-ranked pièce so the derived discarded set is
            non-empty. On this tiny corpus the tool's own recall-first placement retains
            everything, and a run over an empty discarded set is correctly refused (no bound
            applies — never a flattering 0%)."""
            order = store.read_ranked_order(tenant=TENANT, matter=MATTER, scopes=_BOTH)
            top = order[0].piece_id
            current = store.read_current_line(tenant=TENANT, matter=MATTER, scopes=_BOTH)
            assert current is not None
            if current.last_retained_piece_id == top:
                return
            priced = price_line_move(
                store, tenant=TENANT, matter=MATTER, scopes=_BOTH,
                candidate_last_retained_piece_id=top)
            move_line(
                store, tenant=TENANT, matter=MATTER, actor="me.durand", scopes=_BOTH,
                last_retained_piece_id=top, expected_seq=current.seq,
                priced_statement=str(priced))

        def _start_run() -> None:
            r = client.post(f"/api/matters/{MATTER}/sampling/runs", json={"sample_size": 2})
            assert r.status_code == 200, r.text
            state["run"] = r.json()

        def _judge_one() -> None:
            run = state["run"]
            family = run["drawn"][0]["unit"]["family_id"]   # type: ignore[index]
            r = client.post(
                f"/api/matters/{MATTER}/sampling/runs/{run['run_id']}/verdicts",  # type: ignore[index]
                json={"family_id": family, "relevant": False})
            assert r.status_code == 200, r.text
            state["run"] = r.json()

        def _complete_run() -> None:
            run = state["run"]
            for drawn in run["drawn"]:                      # type: ignore[index]
                if drawn["relevant"] is None:
                    v = client.post(
                        f"/api/matters/{MATTER}/sampling/runs/{run['run_id']}/verdicts",  # type: ignore[index]
                        json={"family_id": drawn["unit"]["family_id"], "relevant": False})
                    assert v.status_code == 200, v.text
            r = client.post(
                f"/api/matters/{MATTER}/sampling/runs/{run['run_id']}/complete")  # type: ignore[index]
            assert r.status_code == 200, r.text

        def _abandon_run() -> None:
            """Start a run and give it up. Its draw and verdicts stay readable forever (AD-7) —
            which is exactly the property this probe measures."""
            r = client.post(f"/api/matters/{MATTER}/sampling/runs", json={"sample_size": 1})
            assert r.status_code == 200, r.text
            run_id = r.json()["run_id"]
            a = client.post(f"/api/matters/{MATTER}/sampling/runs/{run_id}/abandon")
            assert a.status_code == 200, a.text

        def _fresh_bound() -> None:
            """A completed run over the CURRENT population — the bound the export step needs."""
            _start_run()
            _complete_run()

        def _create_user() -> None:
            r = client.post("/api/admin/users", json={
                "email": OTHER, "password": "motdepasse", "display_name": "Me Martin",
                "scopes": [WALL], "is_admin": False})
            assert r.status_code == 200, r.text
            state["other_id"] = r.json()["id"]

        def _change_password() -> None:
            r = client.post("/api/me/password", json={
                "current_password": "motdepasse", "new_password": "motdepasse2"})
            assert r.status_code == 200, r.text
            _login(client, ADMIN, pw="motdepasse2")  # the change reaps every live session (AD-15)

        def _override_register_seam() -> None:
            """Story 5.6 — FR-5's other exit through the core/app seam, on its OWN entry."""
            entry = _open_entry(store, "/dossier/scelle.pdf")
            core_override_register_entry(
                store, entry_id=entry, tenant=TENANT, actor="me.durand",
                reason="scellé jamais ouvert, mot de passe perdu chez le client",
                scopes={WALL, WALL2}, is_admin=True)

        def _override_register_route() -> None:
            """The same act over HTTP, on a SECOND entry — an override closes an OPEN entry and
            never re-closes one that moved, so each step needs its own."""
            entry = _open_entry(store, "/dossier/scelle-2.pdf")
            _post(f"/api/register/{entry}/override",
                  {"reason": "support physique détruit, jamais versé"})

        def _clear_truncation() -> None:
            with store._sf() as s, s.begin():   # arrange an active truncation to override
                s.add(TruncationMarker(
                    tenant=TENANT, detected_at=datetime.now(UTC), journal_seq=5, live_seq=2))
            r = client.post("/api/admin/dr/truncation/clear",
                            json={"reason": "restauration partielle acceptée par le bâtonnier"})
            assert r.status_code == 200, r.text

        def _post(path: str, payload: dict | None = None) -> None:
            r = client.post(path, json=payload or {})
            assert r.status_code == 200, r.text   # a step that silently 4xx'd would prove nothing

        def _put(path: str, payload: dict) -> None:
            r = client.put(path, json=payload)
            assert r.status_code == 200, r.text

        def _delete(path: str) -> None:
            r = client.delete(path)
            assert r.status_code == 200, r.text

        def _get(path: str, ok: tuple[int, ...] = (200,), **params: object) -> None:
            r = client.get(path, params=params)
            assert r.status_code in ok, f"{path} -> {r.status_code} {r.text[:200]}"

        piece, page = pieces[0], 1
        read_steps: list[_Step] = [
            # every GET endpoint, so `changes_state=False` is a VERIFIED claim and not a hand flag:
            # each of these is asserted to write nothing at all.
            _Step(("read-health",), lambda: _get("/api/health")),
            _Step(("read-own-identity",), lambda: _get("/api/me")),
            _Step(("read-users",), lambda: _get("/api/admin/users")),
            _Step(("read-config",), lambda: _get("/api/admin/config")),
            _Step(("read-config-provenance",), lambda: _get("/api/admin/config/provenance")),
            _Step(("read-diagnostics",), lambda: _get("/api/admin/diagnostics")),
            _Step(("read-dr-status",), lambda: _get("/api/admin/dr")),
            _Step(("read-matters",), lambda: _get("/api/matters")),
            _Step(("read-audit-trail",), lambda: _get(f"/api/matters/{MATTER}/audit")),
            _Step(("read-case-theory",), lambda: _get(f"/api/matters/{MATTER}/case-theory")),
            _Step(("read-case-theory-history",),
                  lambda: _get(f"/api/matters/{MATTER}/case-theory/versions")),
            _Step(("read-matter-register",), lambda: _get(f"/api/matters/{MATTER}/register")),
            _Step(("read-register",), lambda: _get("/api/register")),
            _Step(("read-triage",), lambda: _get(f"/api/matters/{MATTER}/triage")),
            _Step(("read-labels",), lambda: _get(f"/api/matters/{MATTER}/labels")),
            # Story 5.7 — the audit drawer: a pure read that proposes rows and commits nothing
            _Step(("read-piece-drawer",),
                  lambda: _get(f"/api/matters/{MATTER}/pieces/{pieces[0]}/drawer")),
            # Story 5.8 — the validation ledger's read, and the bulk confirmation's own content.
            # The preview is a POST because it carries a selection, and it writes NOTHING: it is
            # what the dialog says, not a step of the act.
            _Step(("read-validations",), lambda: _get(f"/api/matters/{MATTER}/validations")),
            _Step(("preview-validation-batch",), lambda: _post(
                f"/api/matters/{MATTER}/validate-batch/preview?version_no=1",
                {"piece_ids": list(pieces[:2]), "confirmed_count": 2})),
            _Step(("read-inventory",), lambda: _get(f"/api/matters/{MATTER}/inventory")),
            # Story 5.1 — the sampling run's reads. Pure: they render the DERIVED
            # invalidated-in-flight verdict and write nothing.
            _Step(("sampling-sizing",),
                  lambda: _get(f"/api/matters/{MATTER}/sampling/sizing", target=0.2)),
            _Step(("read-sampling-run",),
                  lambda: _get(f"/api/matters/{MATTER}/sampling/runs/current")),
            _Step(("list-sampling-runs",),
                  lambda: _get(f"/api/matters/{MATTER}/sampling/runs")),
            _Step(("read-piece-meta",), lambda: _get(f"/api/pieces/{piece}")),
            # a text pièce carries no OCR layer: the honest non-disclosing 404 IS the served path
            _Step(("read-piece-layout",),
                  lambda: _get(f"/api/pieces/{piece}/layout", ok=(200, 404))),
            _Step(("search-corpus",), lambda: _get("/api/search", q="bail")),
            _Step(("read-import-progress",),
                  lambda: _get(f"/api/imports/{state['job_id']}")),
            # Story 4.10 — the triage surface reads. Pure: they render derived views and write
            # nothing, which the flag verification below asserts rather than assumes.
            _Step(("read-triage-table",), lambda: _get(f"/api/matters/{MATTER}/triage-table")),
            _Step(("read-piece-change-log",),
                  lambda: _get(f"/api/matters/{MATTER}/pieces/{pieces[0]}/label/log")),
            _Step(("read-matter-change-log",), lambda: _get(f"/api/matters/{MATTER}/change-log")),
            # Story 4.13 — freshness. All three are pure reads: staleness is a COMPARISON of the
            # stamp an artefact was produced under against the current observables, and reading it
            # resolves nothing (FR-58). The flag verification below asserts they write nothing.
            _Step(("read-freshness",), lambda: _get(f"/api/matters/{MATTER}/freshness")),
            _Step(("read-worklist",), lambda: _get(f"/api/matters/{MATTER}/worklist")),
            _Step(("read-bound",), lambda: _get(f"/api/matters/{MATTER}/bound")),
        ]

        def _export_bound() -> None:
            """Exercise the bound export on its SUCCESS path.

            Every write step above moved an input, so the bound recorded early in this probe is
            stale by now and the export would (correctly) refuse it with 409 — writing nothing, and
            leaving `changes_state=True` unverified. So a FRESH bound is recorded first, as
            arrangement. The proof that the export really happened is the 200 assertion, not the
            census: had it refused, this step would fail loudly here rather than pass because the
            arrangement happened to write."""
            _fresh_bound()
            _get(f"/api/matters/{MATTER}/bound/export")
        def _as_unscoped(path: str) -> None:
            """Drive a SUGGESTIVE endpoint. Its vector query is Postgres-only (``<=>``), so on this
            SQLite harness it is exercised through the fail-closed empty-scope short-circuit — the
            same path ``tests/api/test_search_endpoints.py`` uses. That is not a dodge: the audit
            of the query (FR-45), which is the only evidential write these routes make, happens
            either way, so what the probe is here to verify is fully exercised."""
            _login(client, UNSCOPED, pw="motdepasse")
            try:
                _get(path, q="bail")
            finally:
                _login(client, ADMIN, pw="motdepasse2")  # the password step already ran

        audited_read_steps: list[_Step] = [
            # the reads that DO write — an audit entry on serve (FR-45). Declared
            # `changes_state=True`, so the probe asserts each really wrote one.
            _Step(("search-suggestive",), lambda: _as_unscoped("/api/search/suggestive")),
            _Step(("export-suggestive",), lambda: _as_unscoped("/api/search/suggestive/export")),
            _Step(("search-exhaustive",), lambda: _get("/api/search/exhaustive", q="bail")),
            _Step(("export-exhaustive",), lambda: _get("/api/search/exhaustive/export", q="bail")),
            _Step(("export-register",), lambda: _get("/api/register/export")),
            _Step(("export-bound",), _export_bound),
            _Step(("open-piece-original",), lambda: _get(f"/api/pieces/{piece}/original")),
            _Step(("open-piece-render",), lambda: _get(f"/api/pieces/{piece}/render")),
            _Step(("open-piece-page",),
                  lambda: _get(f"/api/pieces/{piece}/page/{page}", ok=(200, 409))),
        ]

        steps: list[_Step] = [
            _Step(("login",), lambda: _login(client, ADMIN, pw="motdepasse")),
            _Step(("ingest-folder-route", "ingest.ingest_folder"),
                  lambda: _post("/api/ingest",
                                {"folder": str(second), "matter": MATTER, "scope": WALL})),
            _Step(("ingest-upload-route",), _upload),
            _Step(("ingest.ingest_one_file",), _ingest_one),
            _Step(("set-case-theory",), lambda: _put(
                f"/api/matters/{MATTER}/case-theory", {"text": "Le bail est nul."})),
            _Step(("withdraw-case-theory",),
                  lambda: _delete(f"/api/matters/{MATTER}/case-theory")),
            _Step(("judge-matter",),
                  lambda: _post(f"/api/matters/{MATTER}/judge", {"question": "bail"})),
            _Step(("rank.produce_ranking",), _rank),
            _Step(("rank.rank_and_draw_the_line",), _rank_and_draw),
            _Step(("line.place_line",), _place),
            _Step(("line.move_line",), _move),
            # Story 5.1 — the sampling run. AFTER the order and the line exist: its population is
            # derive_triage_sets(order, line, pins).discarded, so there is nothing to draw before.
            # The line cut is its OWN step, declaring no action: arrangement inside a probed step
            # would let the arrangement's write satisfy the step's changes_state assertion, and the
            # probe would be measuring itself.
            _Step((), _cut_the_line_for_sampling),
            _Step(("start-sampling-run", "sampling.start_sampling_run"), _start_run),
            _Step(("record-sampling-verdict", "sampling.record_sampling_verdict"), _judge_one),
            _Step(("complete-sampling-run", "sampling.complete_sampling_run"), _complete_run),
            _Step(("abandon-sampling-run", "sampling.abandon_sampling_run"), _abandon_run),
            _Step(("pin.pin_piece",), lambda: pin_piece(
                store, tenant=TENANT, matter=MATTER, actor="me.durand", piece_id=pieces[-1],
                side=PinSide.RETAIN, reason="pièce décisive", scopes={WALL})),
            _Step(("pin.remove_pin",), lambda: remove_pin(
                store, tenant=TENANT, matter=MATTER, actor="me.durand", piece_id=pieces[-1],
                scopes={WALL})),
            _Step(("set-config-key",), lambda: _put(
                "/api/admin/config/taxonomy", {"value": ["Contrats", "Jurisprudence"]})),
            _Step(("label.assign_taxonomy_label",), lambda: assign_taxonomy_label(
                store, tenant=TENANT, matter=MATTER, actor="me.durand", piece_id=pieces[0],
                label="Contrats", scopes={WALL})),
            _Step(("label.revert_taxonomy_label",), lambda: revert_taxonomy_label(
                store, tenant=TENANT, matter=MATTER, actor="me.durand", piece_id=pieces[0],
                to_seq=1, scopes={WALL})),
            # Story 4.10 — the table's one editable cell, over HTTP. On a DIFFERENT pièce, so the
            # seam steps above keep their own seq history.
            _Step(("set-piece-label",), lambda: _put(
                f"/api/matters/{MATTER}/pieces/{pieces[-1]}/label", {"label": "Contrats"})),
            _Step(("revert-piece-label",), lambda: _post(
                f"/api/matters/{MATTER}/pieces/{pieces[-1]}/label/revert", {"to_seq": 1})),
            _Step(("justification.record_justification",), lambda: record_justification(
                store, tenant=TENANT, matter=MATTER, actor="me.durand", piece_id=pieces[0],
                sentence="Le bail porte la clause invoquée.",
                basis=JustificationBasis.intrinsic((IntrinsicSignal.DOCUMENT_TYPE,)),
                evidence=(EvidenceExtract(chunk_of[pieces[0]], _QUOTE),), source_language="fr",
                scopes={WALL})),
            _Step(("justification.reject_justification",), lambda: reject_justification(
                store, tenant=TENANT, matter=MATTER, actor="me.durand", piece_id=pieces[0],
                scopes={WALL}, reason="appréciation contestée")),
            _Step(("justification.restore_justification",), lambda: restore_justification(
                store, tenant=TENANT, matter=MATTER, actor="me.durand", piece_id=pieces[0],
                scopes={WALL}, reason="rétablie après relecture")),
            _Step(("create-user",), _create_user),
            _Step(("grant-scope",), lambda: _post(
                f"/api/admin/users/{state['other_id']}/grant", {"scope": WALL2})),
            _Step(("revoke-scope",), lambda: _post(
                f"/api/admin/users/{state['other_id']}/revoke", {"scope": WALL2})),
            _Step(("set-admin-flag",), lambda: _post(
                f"/api/admin/users/{state['other_id']}/admin", {"is_admin": True})),
            _Step(("change-own-password",), _change_password),
            _Step(("rescope-matter",), lambda: _post(
                f"/api/admin/matters/{MATTER}/rescope", {"scope": WALL2})),
            _Step(("register_override.override_register_entry",), _override_register_seam),
            _Step(("override-register-entry",), _override_register_route),
            # Story 5.7 — the THIRD named egress path. It writes exactly ONE evidential row (its
            # own audit entry) and removes nothing: the record it produces is a read of everything
            # else. Numbers-only, deliberately: the probe should not need client content to prove
            # that producing a document destroys nothing.
            _Step(("export-matter-record",), lambda: _post(
                f"/api/matters/{MATTER}/record/export?tier=numbers-only")),
            # Story 5.8 — the validation act, its bulk form and its reversal. All three APPEND:
            # `withdraw` is declared deletion-SHAPED in the registry because "retirer ma
            # validation" reads like taking something away to the only person it could mislead, and
            # this is where that reading is proven false — the ledger grows by one row, the
            # validation entry it withdraws is still there, and no evidential count falls.
            _Step(("validate-piece",), lambda: _post(
                f"/api/matters/{MATTER}/pieces/{pieces[0]}/validate?version_no=1")),
            _Step(("withdraw-validation",), lambda: _post(
                f"/api/matters/{MATTER}/pieces/{pieces[0]}/validation/withdraw")),
            _Step(("validate-pieces-in-batch",), lambda: _post(
                f"/api/matters/{MATTER}/validate-batch?version_no=1",
                {"piece_ids": list(pieces[:2]), "confirmed_count": 2})),
            _Step(("clear-truncation",), _clear_truncation),
        ]

        # Ordering: the writes build the world, the reads then run over it (so `/api/imports/{id}`
        # has a job to report on and `/api/pieces/{id}` a pièce to open) — and `logout` is LAST,
        # because it ends the session every other step needs.
        all_steps = [
            *steps, *read_steps, *audited_read_steps,
            _Step(("logout",), lambda: _post("/api/logout")),
        ]

        # ── AC-2, second half: the probe's own coverage, asserted BEFORE it runs ──
        declared = {a.name: a for a in USER_ACTIONS}
        must_cover = (
            {a.name for a in USER_ACTIONS if a.changes_state}
            | {a.name for a in USER_ACTIONS if a.route is not None})
        covered = {name for step in all_steps for name in step.covers}
        assert covered == must_cover, (
            f"the probe does not walk the whole registry — missing: "
            f"{sorted(must_cover - covered)}; unknown: {sorted(covered - must_cover)}. The bound "
            "of this probe IS the registry: an action it skips is an action nothing proves "
            "anything about (FR-21).")

        # ── AC-2, first half: execute every action; assert what it did, not what it claims ──
        evidential = set(evidential_tables(_census(store)))
        mislabelled: list[str] = []
        for step in all_steps:
            label = " + ".join(step.covers)
            before = _census(store)
            with _writes_recorded() as writes:
                step.run()
            _assert_no_evidential_delete(label, writes, evidential)
            _assert_nothing_lost(label, before, _census(store))  # belt as well as braces
            # `changes_state` means "writes an EVIDENTIAL row". Every authenticated request also
            # refreshes its `session` row (the idle-timeout slide) — that is transient auth
            # bookkeeping, on the written allow-list, and it is not what FR-21 is about.
            touched = sorted(
                (writes["insert"] | writes["update"] | writes["delete"]) & evidential)
            wrote = bool(touched)
            rows = [declared[n] for n in step.covers if n in declared]
            # AC-1's third rule, at runtime: `changes_state` is the one field the probe's bound
            # rests on, so the probe VERIFIES it rather than trusting the author.
            residual = any(n in _WRITE_NOT_OBSERVABLE_HERE for n in step.covers)
            if rows and all(r.changes_state for r in rows) and not wrote and not residual:
                mislabelled.append(
                    f"{label}: registered changes_state=True but wrote nothing evidential — "
                    "either the step is a no-op (and proves nothing) or the flag is wrong")
            if rows and not any(r.changes_state for r in rows) and wrote:
                mislabelled.append(
                    f"{label}: registered changes_state=False but wrote {touched} — a "
                    "state-changing action declared stateless would be silently exempted from "
                    "this probe's bound")
        assert not mislabelled, (
            "the registry's changes_state flags disagree with what the actions actually did — the "
            "flag the probe's bound rests on is verified by execution, never trusted:\n  "
            + "\n  ".join(mislabelled))


def test_every_deletion_shaped_action_adds_rather_than_removes(
    tmp_path: Path, monkeypatch
) -> None:
    """AC-3: for each act a user could read as deletion, name the ledger it writes to and prove the
    act is an **insert** — not merely "no count fell". This is the sentence FR-21 actually makes:
    *anything a user could read as deletion is a reversible, labelled, recorded state change*."""
    store = _prepare(tmp_path, monkeypatch)
    store.create_user(TENANT, ADMIN, "motdepasse", "Me Durand", {WALL, WALL2}, is_admin=True)
    folder = _folder(tmp_path, "dossier")

    with TestClient(app) as client:
        _login(client, ADMIN, pw="motdepasse")
        client.post("/api/ingest", json={"folder": str(folder), "matter": MATTER, "scope": WALL})
        pieces = [pid for pid, _ in store.representatives(MATTER, TENANT, {WALL})]
        chunk_of = {u.piece_id: u.chunk_ids[0] for u in _units(store, MATTER)}
        produce_ranking(
            _units(store, MATTER), case_theory=None,
            scorer=FakeScorer({p: 0.9 - 0.3 * i for i, p in enumerate(pieces)}),
            judge=FixedJudge(), config=_cfg(), inputs=_inputs(), tenant=TENANT, matter=MATTER,
            actor="me.durand", scopes={WALL}, recorder=store)
        client.put("/api/admin/config/taxonomy", json={"value": ["Contrats"]})
        client.put(f"/api/matters/{MATTER}/case-theory", json={"text": "Le bail est nul."})
        assign_taxonomy_label(store, tenant=TENANT, matter=MATTER, actor="me.durand",
                              piece_id=pieces[0], label="Contrats", scopes={WALL})
        pin_piece(store, tenant=TENANT, matter=MATTER, actor="me.durand", piece_id=pieces[-1],
                  side=PinSide.RETAIN, reason="pièce décisive", scopes={WALL})
        record_justification(
            store, tenant=TENANT, matter=MATTER, actor="me.durand", piece_id=pieces[0],
            sentence="Le bail porte la clause invoquée.",
            basis=JustificationBasis.intrinsic((IntrinsicSignal.DOCUMENT_TYPE,)),
            evidence=(EvidenceExtract(chunk_of[pieces[0]], _QUOTE),), scopes={WALL})
        other = client.post("/api/admin/users", json={
            "email": OTHER, "password": "motdepasse", "display_name": "Me Martin",
            "scopes": [WALL, WALL2], "is_admin": False}).json()["id"]
        with store._sf() as s, s.begin():
            s.add(TruncationMarker(tenant=TENANT, detected_at=datetime.now(UTC), journal_seq=5,
                                   live_seq=2))

        # (the deletion-shaped act, the ledger it writes to, how to perform it)
        acts: list[tuple[str, str, Callable[[], object]]] = [
            ("withdraw-case-theory", "case_theory_version",
             lambda: client.delete(f"/api/matters/{MATTER}/case-theory")),
            ("label.revert_taxonomy_label", "taxonomy_label_entry",
             lambda: revert_taxonomy_label(store, tenant=TENANT, matter=MATTER, actor="me.durand",
                                           piece_id=pieces[0], to_seq=1, scopes={WALL})),
            ("pin.remove_pin", "pin_entry",
             lambda: remove_pin(store, tenant=TENANT, matter=MATTER, actor="me.durand",
                                piece_id=pieces[-1], scopes={WALL})),
            ("justification.reject_justification", "justification_rejection",
             lambda: reject_justification(store, tenant=TENANT, matter=MATTER, actor="me.durand",
                                          piece_id=pieces[0], scopes={WALL}, reason="contestée")),
            ("clear-truncation", "audit_record",
             lambda: client.post("/api/admin/dr/truncation/clear",
                                 json={"reason": "restauration acceptée"})),
            ("revoke-scope", "audit_record",
             lambda: client.post(f"/api/admin/users/{other}/revoke", json={"scope": WALL2})),
        ]
        for action, ledger, perform in acts:
            before = _census(store)
            perform()
            after = _census(store)
            assert after[ledger] == before[ledger] + 1, (
                f"{action} did not APPEND to {ledger} — a deletion-shaped act is a recorded state "
                "change, so it leaves a new entry behind it (FR-21/FR-5/AD-7)")
            _assert_nothing_lost(action, before, after)

        # the truncation marker is CLEARED, never removed — the act stamps it and it stays
        with store._sf() as s:
            marker = s.get(TruncationMarker, TENANT)
        assert marker is not None and marker.cleared_at is not None and marker.reason


def test_the_probe_is_not_vacuous_a_real_deletion_fires(tmp_path: Path, monkeypatch) -> None:
    """The probe's own failure path: a step that DOES destroy evidential material must fail the
    assertion. Without this, a green probe would prove nothing about the assertion itself."""
    store = _prepare(tmp_path, monkeypatch)
    store.create_user(TENANT, ADMIN, "motdepasse", "Me Durand", {WALL}, is_admin=True)
    folder = _folder(tmp_path, "dossier")
    with TestClient(app) as client:
        _login(client, ADMIN, pw="motdepasse")
        client.post("/api/ingest", json={"folder": str(folder), "matter": MATTER, "scope": WALL})

    before = _census(store)
    with store._sf() as s, s.begin():           # a hard delete of an audit-record entry — the exact
        s.execute(Base.metadata.tables["audit_record"].delete())   # act AD-7 makes unrepresentable
    with pytest.raises(AssertionError, match="reduced audit_record"):
        _assert_nothing_lost("a deliberately destructive step", before, _census(store))


def test_every_transient_table_is_real_and_carries_a_written_reason() -> None:
    """AC-4: the allow-list names real tables with real reasons, and everything else is evidential
    by default — so a table a later story adds is protected without an edit here."""
    mapped = {t.name for t in Base.metadata.sorted_tables}
    unknown = set(TRANSIENT_TABLES) - mapped
    assert not unknown, f"TRANSIENT_TABLES names tables that do not exist: {sorted(unknown)}"
    assert all(reason.strip() for reason in TRANSIENT_TABLES.values())
    evidential = evidential_tables(mapped)
    # the five FR-21 names are evidential, and so is every ledger the triage stories added
    assert {"piece", "chunk", "audit_record", "failure", "taxonomy_label_entry", "line_placement",
            "pin_entry", "piece_justification", "justification_rejection", "case_theory_version",
            "recall_review", "ranked_entry", "ranking_version"} <= evidential
    assert not (evidential & set(TRANSIENT_TABLES))
