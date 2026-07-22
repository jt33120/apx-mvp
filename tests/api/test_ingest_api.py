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
        r = c.get("/api/matters/m/inventory", params={"tenant": "t"})
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
        back = c.get("/api/matters/m/inventory", params={"tenant": "t"}).json()

    # Durable inventory = corpus + failures (exclusions are a per-run detail).
    assert back["in_corpus"] == 1
    assert back["failures"] == 2
    assert back["consistent"] is True
