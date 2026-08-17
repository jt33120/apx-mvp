"""`POST /api/ingest` is confined to a declared root (Story 7.1, FR-1 / C1).

The defect this closes, verified by hand before the story: the route took `folder` as a bare string
from the request body and validated it with `if not folder.is_dir()`. Any authenticated user could
name any directory the API process could read and have it walked, extracted and **persisted into
their own matter under their own RBAC scope** — including `$APX_DATA_PATH/originals`, every other
matter's retained source documents.

These drive the fail-closed branches with explicit environment, the way the encryption gate's
branches are driven in `test_startup_gate.py`. The suite-wide `_ingest_root` fixture in
`tests/conftest.py` provides the ordinary configured case for every other test.
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
from tests.embedding_fakes import FakeEmbedder

_FAKE = FakeEmbedder()
SECRET = "test-secret"


@pytest.fixture(autouse=True)
def _reset_state():  # noqa: ANN201
    app_module._store.cache_clear()
    app_module._login_limiter._fails.clear()
    app_module._EMBEDDER = _FAKE
    yield
    app_module._store.cache_clear()
    app_module._login_limiter._fails.clear()
    app_module._EMBEDDER = None


def _prepare(tmp_path: Path, monkeypatch) -> SqlStore:  # noqa: ANN001
    url = f"sqlite:///{tmp_path / 'apx.db'}"
    Base.metadata.create_all(create_engine(url))
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("APX_SECRET_KEY", SECRET)
    # BESIDE the ingestable tree: APX_INGEST_ROOT is tmp_path (the suite fixture), and a root that
    # can reach $APX_DATA_PATH/originals is refused outright — which is the point of the rule.
    data = tmp_path.parent / f"{tmp_path.name}-data"
    data.mkdir(exist_ok=True)
    monkeypatch.setenv("APX_DATA_PATH", str(data))
    store = SqlStore(sessionmaker(bind=create_engine(url), future=True))
    store.create_user("t", "me@cab.fr", "pw", "Me Dupont", {"wall-A"})
    return store


def _login(c: TestClient) -> None:
    assert c.post("/api/login",
                  json={"tenant": "t", "email": "me@cab.fr", "password": "pw"}).status_code == 200


def _post(c: TestClient, folder: Path) -> object:
    return c.post("/api/ingest",
                  json={"folder": str(folder), "matter": "m", "scope": "wall-A",
                        "custodian": "Me Martin"})


def test_a_folder_outside_the_root_is_refused(tmp_path: Path, monkeypatch) -> None:
    """The whole point. `elsewhere` exists and is readable; it is simply not ours to read."""
    _prepare(tmp_path, monkeypatch)
    elsewhere = tmp_path.parent / f"{tmp_path.name}-elsewhere"
    elsewhere.mkdir(exist_ok=True)
    (elsewhere / "confidentiel.txt").write_text("le dossier d'un autre", encoding="utf-8")

    with TestClient(app) as c:
        _login(c)
        refused = _post(c, elsewhere)

    assert refused.status_code == 400, refused.text
    assert "confidentiel" not in refused.text
    assert str(elsewhere) not in refused.text


def test_the_originals_store_is_refused_by_name(tmp_path: Path, monkeypatch) -> None:
    """The predictable target: every matter's retained source documents live here."""
    _prepare(tmp_path, monkeypatch)
    originals = tmp_path.parent / f"{tmp_path.name}-data" / "originals"
    originals.mkdir(parents=True, exist_ok=True)
    (originals / "piece-d-un-autre.txt").write_text("confidentiel", encoding="utf-8")

    with TestClient(app) as c:
        _login(c)
        refused = _post(c, originals)

    assert refused.status_code == 400, refused.text


def test_an_absent_folder_and_an_out_of_root_folder_answer_identically(
    tmp_path: Path, monkeypatch,
) -> None:
    """Non-disclosure: a caller must not be able to map the server's filesystem one call at a time.

    This is the assertion that makes the refusal useful rather than merely present — a distinct
    message for "exists but forbidden" is a directory oracle.
    """
    _prepare(tmp_path, monkeypatch)
    real_but_forbidden = tmp_path.parent / f"{tmp_path.name}-elsewhere"
    real_but_forbidden.mkdir(exist_ok=True)

    with TestClient(app) as c:
        _login(c)
        forbidden = _post(c, real_but_forbidden)
        absent = _post(c, tmp_path.parent / "nexistepas")

    assert forbidden.status_code == absent.status_code
    assert forbidden.json() == absent.json()


def test_an_unset_root_refuses_every_ingestion(tmp_path: Path, monkeypatch) -> None:
    """Fail closed. Before this story an unset root meant 'anywhere', which was the defect."""
    _prepare(tmp_path, monkeypatch)
    monkeypatch.delenv("APX_INGEST_ROOT", raising=False)
    folder = tmp_path / "dossier"
    folder.mkdir(exist_ok=True)
    (folder / "a.txt").write_text("texte", encoding="utf-8")

    with TestClient(app) as c:
        _login(c)
        refused = _post(c, folder)

    assert refused.status_code == 503, refused.text
    assert "APX_INGEST_ROOT" in refused.text


def test_a_root_that_can_reach_the_originals_refuses_every_ingestion(
    tmp_path: Path, monkeypatch,
) -> None:
    """A confinement that admits the originals grants exactly what it exists to deny."""
    _prepare(tmp_path, monkeypatch)
    volume = tmp_path.parent / f"{tmp_path.name}-data"
    (volume / "originals").mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("APX_INGEST_ROOT", str(volume))   # a root that CAN reach the originals
    folder = volume / "dossier"
    folder.mkdir(exist_ok=True)
    (folder / "a.txt").write_text("texte", encoding="utf-8")

    with TestClient(app) as c:
        _login(c)
        refused = _post(c, folder)

    assert refused.status_code == 503, refused.text
    assert "originals" in refused.text


def test_a_folder_inside_the_root_is_ingested_as_before(tmp_path: Path, monkeypatch) -> None:
    """The confinement must not break the gesture it guards."""
    _prepare(tmp_path, monkeypatch)
    folder = tmp_path / "dossier"
    folder.mkdir(exist_ok=True)
    (folder / "lettre.txt").write_text("Maître, ci-joint…", encoding="utf-8")

    with TestClient(app) as c:
        _login(c)
        accepted = _post(c, folder)

    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["inventory"]["submitted_pieces"] == 1


def test_a_link_out_of_the_subtree_is_registered_not_ingested(
    tmp_path: Path, monkeypatch,
) -> None:
    """FR-1's clause, end to end: the class that had no producer finally has one."""
    import os

    _prepare(tmp_path, monkeypatch)
    folder = tmp_path / "dossier"
    folder.mkdir(exist_ok=True)
    (folder / "lettre.txt").write_text("Maître, ci-joint…", encoding="utf-8")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "secret.txt").write_text("le dossier d'un autre", encoding="utf-8")
    os.symlink(elsewhere / "secret.txt", folder / "piege.txt")

    with TestClient(app) as c:
        _login(c)
        result = _post(c, folder)
        assert result.status_code == 200, result.text
        body = result.json()
        register = c.get("/api/register").json()

    inventory = body["inventory"]
    # The link is not ingested — but it WAS submitted, so it is accounted for in exactly one place
    # (AD-38/FR-6: nothing vanishes from the denominator). Its place is the register, and the
    # identity still reconciles: submitted == in_corpus + open + overridden.
    assert inventory["in_corpus"] == 1, "the link must not become a pièce"
    assert inventory["submitted_pieces"] == 2, "and it must not vanish from the denominator either"
    assert (inventory["in_corpus"] + inventory["open_register_entries"]
            + inventory["overridden_register_entries"] == inventory["submitted_pieces"])
    classes = {e["error_class"] for e in register["entries"]}
    assert "traversal-out-of-scope" in classes
    breach = next(e for e in register["entries"] if e["error_class"] == "traversal-out-of-scope")
    assert breach["filename"] == "piege.txt"
