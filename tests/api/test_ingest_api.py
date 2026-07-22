"""The ingest API over a real folder (TestClient, no network). Persistence is
exercised against a SQLite file via DATABASE_URL; the Postgres path is CI's.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from apx.adapters.store_postgres.models import Base
from apx.api import app as app_module
from apx.api.app import app


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


def test_health() -> None:
    with TestClient(app) as c:
        assert c.get("/api/health").json() == {"status": "ok"}


def test_ingest_without_a_db_computes_but_does_not_persist(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    _matter(tmp_path)
    with TestClient(app) as c:
        r = c.post("/api/ingest", json={"folder": str(tmp_path), "matter": "m", "tenant": "t"})
    body = r.json()
    assert r.status_code == 200
    assert body["persisted"] is False  # transparent, not a silent fixture
    inv = body["inventory"]
    assert inv["consistent"] and inv["submitted"] == 4
    assert inv["in_corpus"] == 1 and inv["failures"] == 2 and inv["exclusions"] == 1


def test_read_back_without_a_database_is_503(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with TestClient(app) as c:
        r = c.get("/api/matters/m/inventory", params={"tenant": "t", "scopes": "m"})
    assert r.status_code == 503


def test_ingest_persists_and_reads_back(tmp_path: Path, monkeypatch) -> None:
    # Keep the DB file OUT of the folder being ingested (else ingestion counts it).
    url = f"sqlite:///{tmp_path / 'apx.db'}"
    Base.metadata.create_all(create_engine(url))
    monkeypatch.setenv("DATABASE_URL", url)
    matter_dir = tmp_path / "matter"
    matter_dir.mkdir()
    _matter(matter_dir)

    with TestClient(app) as c:
        r = c.post("/api/ingest", json={"folder": str(matter_dir), "matter": "m", "tenant": "t"})
        assert r.json()["persisted"] is True
        back = c.get("/api/matters/m/inventory", params={"tenant": "t", "scopes": "m"}).json()

    # Durable inventory = corpus + failures (exclusions are a per-run detail).
    assert back["in_corpus"] == 1
    assert back["failures"] == 2
    assert back["consistent"] is True


def test_ingest_upload_reconstructs_the_tree_and_counts(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with TestClient(app) as c:
        r = c.post(
            "/api/ingest-upload",
            data={"matter": "m", "tenant": "t"},
            files=[
                ("files", ("emails/letter.txt", b"Ma\xc3\xaetre, ci-joint", "text/plain")),
                ("files", ("pieces/empty.txt", b"", "text/plain")),
                ("files", ("pieces/photo.jpg", b"not an image", "image/jpeg")),
            ],
        )
    assert r.status_code == 200
    inv = r.json()["inventory"]
    assert inv["consistent"] and inv["submitted"] == 3
    assert inv["in_corpus"] == 1  # letter.txt
    assert inv["failures"] == 2  # empty.txt (extracted-empty), photo.jpg (unsupported)


def test_chinese_wall_over_http(tmp_path: Path, monkeypatch) -> None:
    url = f"sqlite:///{tmp_path / 'apx.db'}"
    Base.metadata.create_all(create_engine(url))
    monkeypatch.setenv("DATABASE_URL", url)
    da, db = tmp_path / "a", tmp_path / "b"
    da.mkdir()
    db.mkdir()
    (da / "x.txt").write_text("dossier A", encoding="utf-8")
    (db / "y.txt").write_text("dossier B", encoding="utf-8")

    def _read(c, matter, scope):
        return c.get(f"/api/matters/{matter}/inventory", params={"tenant": "t", "scopes": scope})

    def _ingest(c, folder, matter, scope):
        return c.post(
            "/api/ingest",
            json={"folder": str(folder), "matter": matter, "tenant": "t", "scope": scope},
        )

    with TestClient(app) as c:
        _ingest(c, da, "m-a", "wall-A")
        _ingest(c, db, "m-b", "wall-B")

        # A user holding wall-A sees only m-a.
        listed = c.get("/api/matters", params={"tenant": "t", "scopes": "wall-A"}).json()
        assert {m["matter"] for m in listed} == {"m-a"}

        # Reading m-b with the wrong wall is refused (403); with the right wall, 200.
        assert _read(c, "m-b", "wall-A").status_code == 403
        assert _read(c, "m-b", "wall-B").status_code == 200


def test_audit_trail_over_http(tmp_path: Path, monkeypatch) -> None:
    url = f"sqlite:///{tmp_path / 'apx.db'}"
    Base.metadata.create_all(create_engine(url))
    monkeypatch.setenv("DATABASE_URL", url)
    matter_dir = tmp_path / "matter"
    matter_dir.mkdir()
    _matter(matter_dir)

    with TestClient(app) as c:
        c.post(
            "/api/ingest",
            json={"folder": str(matter_dir), "matter": "m", "tenant": "t",
                  "scope": "wall-A", "actor": "me.durupt"},
        )
        # In scope: the ingestion is on the trail, under the actor, and it verifies.
        ok = c.get("/api/matters/m/audit", params={"tenant": "t", "scopes": "wall-A"})
        body = ok.json()
        assert ok.status_code == 200
        assert body["verified"] is True
        assert [e["action"] for e in body["entries"]] == ["ingest"]
        assert body["entries"][0]["actor"] == "me.durupt"
        # Out of scope: refused, existence not disclosed (same 403 as a missing matter).
        denied = c.get("/api/matters/m/audit", params={"tenant": "t", "scopes": "wall-B"})
        assert denied.status_code == 403
