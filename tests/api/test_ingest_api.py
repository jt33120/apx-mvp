"""The API over a real folder (TestClient, no network), with owned auth enforced.

Every scoped call authenticates first; the session — not the request — carries the
tenant and the held scopes, so a caller cannot claim a wall. Persistence is a SQLite
file via DATABASE_URL; the Postgres path is CI's.
"""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from apx.adapters.store_postgres.models import Base
from apx.adapters.store_postgres.queue import _run_import
from apx.adapters.store_postgres.store import SqlStore
from apx.api import app as app_module
from apx.api.app import app
from apx.core.app.ingest import IngestedPiece, IngestionResult
from tests.embedding_fakes import FakeEmbedder

_FAKE = FakeEmbedder()  # story 2.8: the embedder injected at the port boundary (never the real one)


def _run_upload(store: SqlStore, resp) -> None:
    """Drive the enqueued import to completion (the worker's resumable orchestration, run
    directly). Story 2.2 made /api/ingest-upload non-blocking: the POST returns a job handle
    (202); the worker fills the corpus."""
    assert resp.status_code == 202, resp.text
    _run_import(store, resp.json()["job_id"], embedder=_FAKE)

SECRET = "test-secret"


def _matter(root: Path) -> None:
    (root / "letter.txt").write_text("Maître, ci-joint…", encoding="utf-8")
    (root / "empty.txt").write_text("", encoding="utf-8")
    (root / "photo.jpg").write_bytes(b"not an image")
    (root / ".DS_Store").write_bytes(b"noise")


@pytest.fixture(autouse=True)
def _reset_state():
    app_module._store.cache_clear()
    app_module._login_limiter._fails.clear()
    app_module._EMBEDDER = _FAKE   # story 2.8: the fake embedder, injected at the port (AD-11)
    yield
    app_module._store.cache_clear()
    app_module._login_limiter._fails.clear()
    app_module._EMBEDDER = None


def _prepare(tmp_path: Path, monkeypatch) -> SqlStore:
    """Configure a SQLite DB + a session secret, and return a store to seed users."""
    url = f"sqlite:///{tmp_path / 'apx.db'}"
    Base.metadata.create_all(create_engine(url))
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("APX_SECRET_KEY", SECRET)
    # Story 3.5a: both ingest paths now retain originals from_env — pin APX_DATA_PATH to this test's
    # tmp dir so blobs stay isolated here, not written to a shared global temp dir.
    monkeypatch.setenv("APX_DATA_PATH", str(tmp_path))
    return SqlStore(sessionmaker(bind=create_engine(url), future=True))


def _login(c: TestClient, email: str, pw: str = "pw", tenant: str = "t"):
    r = c.post("/api/login", json={"tenant": tenant, "email": email, "password": pw})
    assert r.status_code == 200, r.text
    return r


def test_health_is_open() -> None:
    with TestClient(app) as c:
        assert c.get("/api/health").json() == {"status": "ok"}


def test_login_requires_totp_when_the_tenant_enables_mfa(tmp_path: Path, monkeypatch) -> None:
    store = _prepare(tmp_path, monkeypatch)
    uid = store.create_user("t", "a@a.test", "pw", "Avocat A", {"w"})
    store.set_mfa_required("t", True)
    secret = pyotp.random_base32()
    store.set_mfa_secret(uid, secret)
    with TestClient(app) as c:
        # password alone is refused once MFA is required + enrolled
        r = c.post("/api/login", json={"tenant": "t", "email": "a@a.test", "password": "pw"})
        assert r.status_code == 401
        # password + a correct TOTP succeeds
        ok = c.post("/api/login", json={
            "tenant": "t", "email": "a@a.test", "password": "pw", "totp": pyotp.TOTP(secret).now(),
        })
        assert ok.status_code == 200


def test_an_admin_is_not_a_data_superuser(tmp_path: Path, monkeypatch) -> None:
    # A matter exists behind wall-x; the admin holds NO scope. The app layer must not widen an
    # admin's scopes (AD-12/AD-48) — /me shows no scopes, /matters shows nothing.
    from datetime import UTC, datetime
    store = _prepare(tmp_path, monkeypatch)
    piece = IngestedPiece(
        id="p", matter="mx", tenant="t", content_hash="p", text_key="p", provenance_path="/p.txt",
        custodian="c", extraction_method="text", extractor_version="v", schema_version="s",
        ingestion_timestamp=datetime.now(UTC), full_text="secret", text_version="v")
    store.save(IngestionResult(pieces=[piece]), scope="wall-x", actor="sys")
    store.create_user("t", "admin@c.fr", "password1", "Admin", set(), is_admin=True)
    with TestClient(app) as c:
        _login(c, "admin@c.fr", pw="password1")
        me = c.get("/api/me").json()
        assert me["is_admin"] is True and me["scopes"] == []   # not widened for the admin
        assert c.get("/api/matters").json() == []              # sees no matter it lacks a wall for


def test_mfa_required_but_unenrolled_is_refused(tmp_path: Path, monkeypatch) -> None:
    # FAIL CLOSED: enabling MFA for a tenant must not let an unenrolled user in on password
    # alone (the dangerous downgrade). They are refused (403) until enrolled.
    store = _prepare(tmp_path, monkeypatch)
    store.create_user("t", "a@a.test", "pw", "Avocat A", {"w"})  # no mfa_secret
    store.set_mfa_required("t", True)
    with TestClient(app) as c:
        r = c.post("/api/login", json={"tenant": "t", "email": "a@a.test", "password": "pw"})
        assert r.status_code == 403


def test_spa_is_served_at_root_when_built() -> None:
    dist = Path(app_module.__file__).resolve().parent.parent / "web" / "dist"
    if not dist.is_dir():
        pytest.skip("web not built (npm run build)")
    with TestClient(app) as c:
        r = c.get("/")
    assert r.status_code == 200 and "text/html" in r.headers.get("content-type", "")


def test_security_headers_are_present() -> None:
    with TestClient(app) as c:
        r = c.get("/api/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in r.headers["content-security-policy"]


def test_login_is_rate_limited_after_repeated_failures(tmp_path: Path, monkeypatch) -> None:
    store = _prepare(tmp_path, monkeypatch)
    store.create_user("t", "me@cab.fr", "right-pass", "Me", {"wall-A"})
    with TestClient(app) as c:
        for _ in range(10):
            bad = c.post("/api/login", json={"tenant": "t", "email": "me@cab.fr", "password": "X"})
            assert bad.status_code == 401
        # the 11th attempt is blocked — even correct credentials are refused while blocked
        blocked = c.post("/api/login", json={"tenant": "t", "email": "me@cab.fr", "password": "X"})
        assert blocked.status_code == 429
        good = c.post("/api/login",
                      json={"tenant": "t", "email": "me@cab.fr", "password": "right-pass"})
        assert good.status_code == 429


def test_protected_endpoint_requires_authentication(tmp_path: Path, monkeypatch) -> None:
    _prepare(tmp_path, monkeypatch)
    with TestClient(app) as c:
        assert c.get("/api/matters").status_code == 401       # no session cookie
        assert c.get("/api/me").status_code == 401


def test_login_me_and_bad_password(tmp_path: Path, monkeypatch) -> None:
    store = _prepare(tmp_path, monkeypatch)
    store.create_user("t", "me@cab.fr", "pw", "Me Durand", {"wall-A"})
    with TestClient(app) as c:
        body = _login(c, "me@cab.fr").json()
        assert body["actor"] == "Me Durand" and body["scopes"] == ["wall-A"]
        me = c.get("/api/me").json()
        assert me["actor"] == "Me Durand" and me["tenant"] == "t"
    with TestClient(app) as c:  # fresh client, no cookie
        bad = c.post("/api/login", json={"tenant": "t", "email": "me@cab.fr", "password": "nope"})
        assert bad.status_code == 401


def test_ingest_persists_and_reads_back(tmp_path: Path, monkeypatch) -> None:
    store = _prepare(tmp_path, monkeypatch)
    store.create_user("t", "me@cab.fr", "pw", "Me Durand", {"wall-A"})
    matter_dir = tmp_path / "matter"
    matter_dir.mkdir()
    _matter(matter_dir)

    with TestClient(app) as c:
        _login(c, "me@cab.fr")
        r = c.post("/api/ingest",
                   json={"folder": str(matter_dir), "matter": "m", "scope": "wall-A"})
        assert r.json()["persisted"] is True
        back = c.get("/api/matters/m/inventory").json()
    assert back["in_corpus"] == 1 and back["open_register_entries"] == 2 \
        and back["consistent"] is True
    # Story 3.5a: the SYNC /api/ingest path retains the original at rest too (AC1 — every pièce),
    # openable by (tenant, content_hash) from the same data volume, decrypting to real bytes.
    from sqlalchemy import select

    from apx.adapters.originals_fs import FilesystemOriginalStore
    from apx.adapters.store_postgres.models import Piece
    with store._sf() as s:
        ch = s.scalars(select(Piece.content_hash).where(Piece.matter == "m")).one()
    assert FilesystemOriginalStore.from_env().open("t", ch)  # non-empty decrypted original


def test_cannot_ingest_into_a_wall_you_do_not_hold(tmp_path: Path, monkeypatch) -> None:
    store = _prepare(tmp_path, monkeypatch)
    store.create_user("t", "me@cab.fr", "pw", "Me Durand", {"wall-A"})
    matter_dir = tmp_path / "matter"
    matter_dir.mkdir()
    _matter(matter_dir)
    with TestClient(app) as c:
        _login(c, "me@cab.fr")
        r = c.post("/api/ingest",
                   json={"folder": str(matter_dir), "matter": "m", "scope": "wall-B"})
        assert r.status_code == 403  # holds wall-A, not wall-B


def test_ingest_upload_reconstructs_the_tree_and_counts(tmp_path: Path, monkeypatch) -> None:
    store = _prepare(tmp_path, monkeypatch)
    store.create_user("t", "me@cab.fr", "pw", "Me Durand", {"wall-A"})
    with TestClient(app) as c:
        _login(c, "me@cab.fr")
        r = c.post(
            "/api/ingest-upload",
            data={"matter": "m", "scope": "wall-A", "custodian": "M. Martin"},
            files=[
                ("files", ("emails/letter.txt", b"Ma\xc3\xaetre, ci-joint", "text/plain")),
                ("files", ("pieces/empty.txt", b"", "text/plain")),
                ("files", ("pieces/photo.jpg", b"not an image", "image/jpeg")),
            ],
        )
        _run_upload(store, r)                         # async now: the worker fills the corpus
        inv = c.get("/api/matters/m/inventory").json()
    assert inv["consistent"] and inv["in_corpus"] == 1 and inv["open_register_entries"] == 2


def test_chinese_wall_over_http(tmp_path: Path, monkeypatch) -> None:
    store = _prepare(tmp_path, monkeypatch)
    store.create_user("t", "all@cab.fr", "pw", "Associé", {"wall-A", "wall-B"})
    store.create_user("t", "a@cab.fr", "pw", "Me A", {"wall-A"})
    da, db = tmp_path / "a", tmp_path / "b"
    da.mkdir()
    db.mkdir()
    (da / "x.txt").write_text("dossier A", encoding="utf-8")
    (db / "y.txt").write_text("dossier B", encoding="utf-8")

    with TestClient(app) as c:
        _login(c, "all@cab.fr")  # holds both walls — sets up both matters
        c.post("/api/ingest", json={"folder": str(da), "matter": "m-a", "scope": "wall-A"})
        c.post("/api/ingest", json={"folder": str(db), "matter": "m-b", "scope": "wall-B"})

        _login(c, "a@cab.fr")  # now the caller holds only wall-A (cookie overwritten)
        listed = c.get("/api/matters").json()
        assert {m["matter"] for m in listed} == {"m-a"}
        assert c.get("/api/matters/m-b/inventory").status_code == 403  # existence not disclosed
        assert c.get("/api/matters/m-a/inventory").status_code == 200


def test_triage_deduplicates_over_http(tmp_path: Path, monkeypatch) -> None:
    store = _prepare(tmp_path, monkeypatch)
    store.create_user("t", "me@cab.fr", "pw", "Me Durand", {"wall-A"})
    matter_dir = tmp_path / "matter"
    matter_dir.mkdir()
    (matter_dir / "a.txt").write_text("Le contrat est signé.", encoding="utf-8")
    (matter_dir / "b.txt").write_text("le   CONTRAT  est signé.", encoding="utf-8")  # a copy
    (matter_dir / "c.txt").write_text("Autre pièce.", encoding="utf-8")

    with TestClient(app) as c:
        _login(c, "me@cab.fr")
        c.post("/api/ingest", json={"folder": str(matter_dir), "matter": "m", "scope": "wall-A"})
        body = c.get("/api/matters/m/triage").json()
    assert body["submitted"] == 3 and body["distinct"] == 2 and body["duplicates"] == 1
    assert len(body["groups"]) == 1 and body["groups"][0]["size"] == 2


def test_search_over_http_is_scope_constrained(tmp_path: Path, monkeypatch) -> None:
    store = _prepare(tmp_path, monkeypatch)
    store.create_user("t", "all@cab.fr", "pw", "Associé", {"wall-A", "wall-B"})
    store.create_user("t", "a@cab.fr", "pw", "Me A", {"wall-A"})
    da, db = tmp_path / "a", tmp_path / "b"
    da.mkdir()
    db.mkdir()
    (da / "x.txt").write_text("terme confidentiel alpha", encoding="utf-8")
    (db / "y.txt").write_text("terme confidentiel beta", encoding="utf-8")

    with TestClient(app) as c:
        _login(c, "all@cab.fr")
        c.post("/api/ingest", json={"folder": str(da), "matter": "m-a", "scope": "wall-A"})
        c.post("/api/ingest", json={"folder": str(db), "matter": "m-b", "scope": "wall-B"})

        _login(c, "a@cab.fr")  # holds only wall-A
        a = c.get("/api/search", params={"q": "confidentiel"}).json()
        assert a["total"] == 1 and a["hits"][0]["matter"] == "m-a"
        assert all(h["matter"] != "m-b" for h in a["hits"])  # no leak across the wall


def test_judge_labels_and_scope_over_http(tmp_path: Path, monkeypatch) -> None:
    store = _prepare(tmp_path, monkeypatch)
    store.create_user("t", "all@cab.fr", "pw", "Associé", {"wall-A", "wall-B"})
    store.create_user("t", "a@cab.fr", "pw", "Me A", {"wall-A"})
    da, db = tmp_path / "a", tmp_path / "b"
    da.mkdir()
    db.mkdir()
    (da / "bail.txt").write_text("Contrat de bail commercial signé.", encoding="utf-8")
    (da / "facture.txt").write_text("Facture EDF, 150 euros.", encoding="utf-8")
    (db / "z.txt").write_text("dossier B", encoding="utf-8")

    with TestClient(app) as c:
        _login(c, "all@cab.fr")
        c.post("/api/ingest", json={"folder": str(da), "matter": "m-a", "scope": "wall-A"})
        c.post("/api/ingest", json={"folder": str(db), "matter": "m-b", "scope": "wall-B"})

        _login(c, "a@cab.fr")  # holds only wall-A
        r = c.post("/api/matters/m-a/judge", json={"question": "bail"})
        body = r.json()
        assert r.status_code == 200
        assert body["judged"] == 2 and body["relevant"] == 1 and body["uncertain"] == 1
        assert body["judge"] == "criteria"
        pieces = c.get("/api/matters/m-a/labels").json()["pieces"]
        provs = {p["provenance"]: p["label"] for p in pieces}
        assert provs["bail.txt"] == "relevant" and provs["facture.txt"] == "uncertain"
        # judging a matter outside the wall is refused
        assert c.post("/api/matters/m-b/judge", json={"question": "x"}).status_code == 403


def test_recall_sample_and_bound_over_http(tmp_path: Path, monkeypatch) -> None:
    from apx.adapters.extraction.files import FileExtractor
    from apx.core.app.ingest import ingest_folder
    from apx.core.domain.triage import Label, PieceLabel, TriageOutcome

    store = _prepare(tmp_path, monkeypatch)
    store.create_user("t", "me@cab.fr", "pw", "Me Durand", {"wall-A"})
    mdir = tmp_path / "m"  # NOT tmp_path itself — the sqlite file lives there
    mdir.mkdir()
    for i in range(8):
        (mdir / f"p{i}.txt").write_text(f"pièce {i}", encoding="utf-8")
    result = ingest_folder(mdir, matter="m", tenant="t", extractor=FileExtractor())
    store.save(result, scope="wall-A")
    reps = store.representatives("m", "t", {"wall-A"})
    labels = tuple(PieceLabel(pid, Label.DISCARD, "x") for pid, _ in reps)
    store.save_labels("m", "t", {"wall-A"}, TriageOutcome(labels), "criteria", actor="seed")

    with TestClient(app) as c:
        _login(c, "me@cab.fr")
        s = c.get("/api/matters/m/recall/sample", params={"n": 4}).json()
        assert s["population"] == 8 and len(s["sample"]) == 4
        verdicts = [{"piece_id": sd["piece_id"], "relevant": False} for sd in s["sample"]]
        b = c.post("/api/matters/m/recall/review",
                   json={"verdicts": verdicts, "confidence": 0.95}).json()
        assert b["population"] == 8 and b["sample_size"] == 4 and b["relevant_found"] == 0
        assert 0 < b["prevalence_upper"] <= 1


def test_cockpit_is_admin_only_and_manages_users(tmp_path: Path, monkeypatch) -> None:
    store = _prepare(tmp_path, monkeypatch)
    store.create_user("t", "admin@c.fr", "pw", "Admin", {"wall-A"}, is_admin=True)
    store.create_user("t", "reg@c.fr", "pw", "Reg", {"wall-A"})  # not an admin

    with TestClient(app) as c:
        _login(c, "reg@c.fr")
        assert c.get("/api/admin/users").status_code == 403  # non-admin refused

        _login(c, "admin@c.fr")
        assert c.get("/api/me").json()["is_admin"] is True
        assert {u["email"] for u in c.get("/api/admin/users").json()} == {"admin@c.fr", "reg@c.fr"}

        created = c.post("/api/admin/users", json={
            "email": "new@c.fr", "password": "password2",
            "display_name": "New", "scopes": ["wall-B"]})
        assert created.status_code == 200
        uid = created.json()["id"]
        assert c.post(f"/api/admin/users/{uid}/grant", json={"scope": "wall-C"}).status_code == 200
        assert c.post(f"/api/admin/users/{uid}/revoke", json={"scope": "wall-B"}).status_code == 200
        # duplicate email is refused
        dup = c.post("/api/admin/users",
                     json={"email": "new@c.fr", "password": "password2", "display_name": "Dup"})
        assert dup.status_code == 400

        # the newly-created user can log in and holds exactly the granted wall
        _login(c, "new@c.fr", pw="password2")
        assert sorted(c.get("/api/me").json()["scopes"]) == ["wall-C"]


def test_change_password_over_http(tmp_path: Path, monkeypatch) -> None:
    store = _prepare(tmp_path, monkeypatch)
    store.create_user("t", "me@cab.fr", "old-pass", "Me", {"wall-A"})
    with TestClient(app) as c:
        _login(c, "me@cab.fr", pw="old-pass")
        short = c.post("/api/me/password",
                       json={"current_password": "old-pass", "new_password": "short"})
        assert short.status_code == 422
        wrong = c.post("/api/me/password",
                       json={"current_password": "WRONG", "new_password": "a-good-password"})
        assert wrong.status_code == 400
        ok = c.post("/api/me/password",
                    json={"current_password": "old-pass", "new_password": "a-good-password"})
        assert ok.status_code == 200
    # the new password works; the old one no longer does
    with TestClient(app) as c:
        assert _login(c, "me@cab.fr", pw="a-good-password").status_code == 200
        old = c.post("/api/login",
                     json={"tenant": "t", "email": "me@cab.fr", "password": "old-pass"})
        assert old.status_code == 401


def test_audit_trail_over_http(tmp_path: Path, monkeypatch) -> None:
    store = _prepare(tmp_path, monkeypatch)
    store.create_user("t", "me@cab.fr", "pw", "Me Durand", {"wall-A"})
    matter_dir = tmp_path / "matter"
    matter_dir.mkdir()
    _matter(matter_dir)

    with TestClient(app) as c:
        _login(c, "me@cab.fr")
        c.post("/api/ingest", json={"folder": str(matter_dir), "matter": "m", "scope": "wall-A"})
        body = c.get("/api/matters/m/audit").json()
        assert body["verified"] is True
        assert [e["action"] for e in body["entries"]] == ["ingest"]
        assert body["entries"][0]["actor"] == "Me Durand"  # the session user, not a typed field


# ── Story 2.1: the onboarding gesture (custodian, scope, the two failure paths, provenance) ──

def test_upload_requires_a_custodian(tmp_path: Path, monkeypatch) -> None:
    # AC3: the custodian is mandatory at import; missing or blank fails the job loudly (400).
    store = _prepare(tmp_path, monkeypatch)
    store.create_user("t", "me@cab.fr", "pw", "Me Durand", {"wall-A"})
    with TestClient(app) as c:
        _login(c, "me@cab.fr")
        missing = c.post("/api/ingest-upload", data={"matter": "m", "scope": "wall-A"},
                         files=[("files", ("a.txt", b"x", "text/plain"))])
        assert missing.status_code == 400
        blank = c.post(
            "/api/ingest-upload", data={"matter": "m", "scope": "wall-A", "custodian": "   "},
            files=[("files", ("a.txt", b"x", "text/plain"))])
        assert blank.status_code == 400
        # a visually-blank custodian (a zero-width space) is not a value either — never blank
        zw = c.post(
            "/api/ingest-upload", data={"matter": "m", "scope": "wall-A", "custodian": "​"},
            files=[("files", ("a.txt", b"x", "text/plain"))])
        assert zw.status_code == 400


def test_upload_fails_loudly_on_an_empty_scope(tmp_path: Path, monkeypatch) -> None:
    # AC6 (API edge): a blank RBAC scope fails the job loudly, never defaults permissive.
    # A whitespace scope reaches _held_wall → 400; a missing/empty field is a 422 — both loud 4xx.
    store = _prepare(tmp_path, monkeypatch)
    store.create_user("t", "me@cab.fr", "pw", "Me Durand", {"wall-A"})
    with TestClient(app) as c:
        _login(c, "me@cab.fr")
        blank = c.post("/api/ingest-upload",
                       data={"matter": "m", "scope": "   ", "custodian": "M. Martin"},
                       files=[("files", ("a.txt", b"x", "text/plain"))])
        assert blank.status_code == 400                       # _held_wall strips → empty → loud
        empty = c.post("/api/ingest-upload",
                       data={"matter": "m", "scope": "", "custodian": "M. Martin"},
                       files=[("files", ("a.txt", b"x", "text/plain"))])
        assert empty.status_code in (400, 422)                # never a permissive default


def test_upload_rejects_a_path_traversal_filename(tmp_path: Path, monkeypatch) -> None:
    # Security: a crafted "../" filename must never write outside the upload sandbox → 400.
    store = _prepare(tmp_path, monkeypatch)
    store.create_user("t", "me@cab.fr", "pw", "Me Durand", {"wall-A"})
    with TestClient(app) as c:
        _login(c, "me@cab.fr")
        r = c.post("/api/ingest-upload",
                   data={"matter": "m", "scope": "wall-A", "custodian": "M. Martin"},
                   files=[("files", ("../../escape.txt", b"pwn", "text/plain"))])
        assert r.status_code == 400


def test_upload_returns_before_the_worker_does_the_work(tmp_path: Path, monkeypatch) -> None:
    # AD-6 (AC1): the request enqueues and returns — it does NOT do the ingest work. The corpus is
    # still empty at the 202; it fills only after the worker runs.
    store = _prepare(tmp_path, monkeypatch)
    store.create_user("t", "me@cab.fr", "pw", "Me Durand", {"wall-A"})
    with TestClient(app) as c:
        _login(c, "me@cab.fr")
        r = c.post("/api/ingest-upload",
                   data={"matter": "m", "scope": "wall-A", "custodian": "M. Martin"},
                   files=[("files", ("a.txt", b"lettre", "text/plain"))])
        assert r.status_code == 202
        assert c.get("/api/matters/m/inventory").json()["in_corpus"] == 0   # empty at return
        _run_upload(store, r)                                                # the worker fills it
        assert c.get("/api/matters/m/inventory").json()["in_corpus"] == 1


def test_upload_threads_the_custodian_and_the_explicit_unknown(tmp_path: Path, monkeypatch) -> None:
    # AC3: a real custodian, and the explicit "custodian-undeclared" choice, both reach the piece.
    from sqlalchemy import select

    from apx.adapters.store_postgres.models import Piece
    store = _prepare(tmp_path, monkeypatch)
    store.create_user("t", "me@cab.fr", "pw", "Me Durand", {"wall-A"})
    with TestClient(app) as c:
        _login(c, "me@cab.fr")
        _run_upload(store, c.post(
            "/api/ingest-upload",
            data={"matter": "m", "scope": "wall-A", "custodian": "M. Martin"},
            files=[("files", ("dir/a.txt", b"lettre", "text/plain")),
                   ("files", ("dir/b.txt", b"autre piece", "text/plain"))]))  # multi-file
        _run_upload(store, c.post(
            "/api/ingest-upload",
            data={"matter": "m2", "scope": "wall-A", "custodian": "custodian-undeclared"},
            files=[("files", ("b.txt", b"note", "text/plain"))]))
    with store._sf() as s:
        rows = s.scalars(select(Piece)).all()
    # custodianship is the CUSTODIAN_LINK set now (Story 2.5), read via store.custodians()
    m_pieces = [p for p in rows if p.matter == "m"]
    assert len(m_pieces) == 2
    assert all(store.custodians(p.id) == {"M. Martin"} for p in m_pieces)  # EVERY piece
    m2_pieces = [p for p in rows if p.matter == "m2"]
    assert all(store.custodians(p.id) == {"custodian-undeclared"} for p in m2_pieces)  # not blank


def test_upload_cannot_file_into_a_wall_you_do_not_hold(tmp_path: Path, monkeypatch) -> None:
    # AC4 (cannot broaden): the wall must be one the caller holds; wall-B is refused (403).
    store = _prepare(tmp_path, monkeypatch)
    store.create_user("t", "me@cab.fr", "pw", "Me Durand", {"wall-A"})
    with TestClient(app) as c:
        _login(c, "me@cab.fr")
        r = c.post("/api/ingest-upload",
                   data={"matter": "m", "scope": "wall-B", "custodian": "M. Martin"},
                   files=[("files", ("a.txt", b"x", "text/plain"))])
        assert r.status_code == 403
        # cannot narrow via a new private wall either: an invented wall is simply not held → 403
        invented = c.post("/api/ingest-upload",
                          data={"matter": "m2", "scope": "wall-SECRET", "custodian": "M. Martin"},
                          files=[("files", ("a.txt", b"x", "text/plain"))])
        assert invented.status_code == 403


def test_a_folder_of_zero_readable_files_is_a_completed_0_0_matter(
    tmp_path: Path, monkeypatch
) -> None:
    # AC5: a zero-readable folder is a completed 0/0 matter (durable), not an error, not a no-op.
    store = _prepare(tmp_path, monkeypatch)
    store.create_user("t", "me@cab.fr", "pw", "Me Durand", {"wall-A"})
    with TestClient(app) as c:
        _login(c, "me@cab.fr")
        r = c.post("/api/ingest-upload",
                   data={"matter": "vide", "scope": "wall-A", "custodian": "M. Martin"})
        _run_upload(store, r)
        back = c.get("/api/matters/vide/inventory")           # durable 0/0, reads back
        assert back.status_code == 200 and back.json()["submitted_pieces"] == 0
        assert back.json()["in_corpus"] == 0 and back.json()["consistent"] is True
        # AC3: the denominator carries every AD-38 named count + the unknown-cardinality words.
        body = back.json()
        assert set(body) >= {
            "submitted_pieces", "in_corpus", "open_register_entries", "excluded_as_noise",
            "retired", "unknown_cardinality_entries", "unknown_cardinality_phrase", "consistent"}
        assert body["unknown_cardinality_phrase"] == ""  # no unopened container here
        audit = c.get("/api/matters/vide/audit").json()       # one job-level ingest audit entry
        assert [e["action"] for e in audit["entries"]] == ["ingest"] and audit["verified"] is True


def test_upload_reconstructs_a_deep_tree_from_provenance(tmp_path: Path, monkeypatch) -> None:
    # AC2: subfolders to arbitrary depth; the structure is reconstructible from provenance alone.
    from sqlalchemy import select

    from apx.adapters.store_postgres.models import Piece
    store = _prepare(tmp_path, monkeypatch)
    store.create_user("t", "me@cab.fr", "pw", "Me Durand", {"wall-A"})
    with TestClient(app) as c:
        _login(c, "me@cab.fr")
        r = c.post(
            "/api/ingest-upload",
            data={"matter": "m", "scope": "wall-A", "custodian": "M. Martin"},
            files=[
                ("files", ("emails/2021/mars/letter.txt", b"un", "text/plain")),
                ("files", ("pieces/annexes/plan.txt", b"deux", "text/plain")),
            ],
        )
        _run_upload(store, r)
    with store._sf() as s:
        provs = {p.provenance_path for p in s.scalars(select(Piece)).all()}
    assert "emails/2021/mars/letter.txt" in provs   # full folder-relative path (≥3 levels)
    assert "pieces/annexes/plan.txt" in provs


def test_upload_persists_the_optional_case_theory(tmp_path: Path, monkeypatch) -> None:
    # AC7: the case theory, when given, is persisted on the matter; when skipped it is NULL.
    from sqlalchemy import select

    from apx.adapters.store_postgres.models import MatterScope
    store = _prepare(tmp_path, monkeypatch)
    store.create_user("t", "me@cab.fr", "pw", "Me Durand", {"wall-A"})
    with TestClient(app) as c:
        _login(c, "me@cab.fr")
        _run_upload(store, c.post(
            "/api/ingest-upload",
            data={"matter": "avec", "scope": "wall-A", "custodian": "M. Martin",
                  "case_theory": "contestation d'un licenciement pour insuffisance"},
            files=[("files", ("a.txt", b"x", "text/plain"))]))
        _run_upload(store, c.post(
            "/api/ingest-upload",
            data={"matter": "sans", "scope": "wall-A", "custodian": "M. Martin"},
            files=[("files", ("b.txt", b"y", "text/plain"))]))
    with store._sf() as s:
        theories = {ms.matter: ms.case_theory for ms in s.scalars(select(MatterScope)).all()}
    assert theories["avec"] == "contestation d'un licenciement pour insuffisance"
    assert theories["sans"] is None  # skipped blocks nothing and leaves NULL
