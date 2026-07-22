"""The ingest API returns a real inventory over a real folder (TestClient, no DB, no network)."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from apx.api.app import app


def _matter(root: Path) -> None:
    (root / "letter.txt").write_text("Maître, ci-joint…", encoding="utf-8")
    (root / "empty.txt").write_text("", encoding="utf-8")
    (root / "photo.jpg").write_bytes(b"not an image")
    (root / ".DS_Store").write_bytes(b"noise")


def test_health() -> None:
    with TestClient(app) as c:
        assert c.get("/api/health").json() == {"status": "ok"}


def test_ingest_returns_a_consistent_inventory(tmp_path: Path) -> None:
    _matter(tmp_path)
    with TestClient(app) as c:
        r = c.post(
            "/api/ingest",
            json={"folder": str(tmp_path), "matter": "m", "tenant": "t"},
        )
    assert r.status_code == 200
    body = r.json()
    inv = body["inventory"]
    assert inv["consistent"] is True
    assert inv["submitted"] == 4
    assert inv["in_corpus"] == 1  # letter.txt
    assert inv["failures"] == 2  # empty.txt, photo.jpg
    assert inv["exclusions"] == 1  # .DS_Store
    classes = {f["path"]: f["error_class"] for f in body["failure_list"]}
    assert classes["empty.txt"] == "extracted-empty"
    assert classes["photo.jpg"] == "unsupported-format"


def test_ingest_rejects_a_non_folder(tmp_path: Path) -> None:
    with TestClient(app) as c:
        r = c.post(
            "/api/ingest",
            json={"folder": str(tmp_path / "nope"), "matter": "m", "tenant": "t"},
        )
    assert r.status_code == 400
