"""The API over a real folder (TestClient, no network), with owned auth enforced.

Every scoped call authenticates first; the session — not the request — carries the
tenant and the held scopes, so a caller cannot claim a wall. Persistence is a SQLite
file via DATABASE_URL; the Postgres path is CI's.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from apx.adapters.store_postgres.models import Base
from apx.adapters.store_postgres.store import SqlStore
from apx.api import app as app_module
from apx.api.app import app

SECRET = "test-secret"


def _matter(root: Path) -> None:
    (root / "letter.txt").write_text("Maître, ci-joint…", encoding="utf-8")
    (root / "empty.txt").write_text("", encoding="utf-8")
    (root / "photo.jpg").write_bytes(b"not an image")
    (root / ".DS_Store").write_bytes(b"noise")


@pytest.fixture(autouse=True)
def _reset_store_cache():
    app_module._store.cache_clear()
    yield
    app_module._store.cache_clear()


def _prepare(tmp_path: Path, monkeypatch) -> SqlStore:
    """Configure a SQLite DB + a session secret, and return a store to seed users."""
    url = f"sqlite:///{tmp_path / 'apx.db'}"
    Base.metadata.create_all(create_engine(url))
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("APX_SECRET_KEY", SECRET)
    return SqlStore(sessionmaker(bind=create_engine(url), future=True))


def _login(c: TestClient, email: str, pw: str = "pw", tenant: str = "t"):
    r = c.post("/api/login", json={"tenant": tenant, "email": email, "password": pw})
    assert r.status_code == 200, r.text
    return r


def test_health_is_open() -> None:
    with TestClient(app) as c:
        assert c.get("/api/health").json() == {"status": "ok"}


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
    assert back["in_corpus"] == 1 and back["failures"] == 2 and back["consistent"] is True


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
            data={"matter": "m", "scope": "wall-A"},
            files=[
                ("files", ("emails/letter.txt", b"Ma\xc3\xaetre, ci-joint", "text/plain")),
                ("files", ("pieces/empty.txt", b"", "text/plain")),
                ("files", ("pieces/photo.jpg", b"not an image", "image/jpeg")),
            ],
        )
    assert r.status_code == 200
    inv = r.json()["inventory"]
    assert inv["consistent"] and inv["submitted"] == 3
    assert inv["in_corpus"] == 1 and inv["failures"] == 2


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
