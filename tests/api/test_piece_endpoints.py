"""The pièce viewer read path over HTTP (Story 3.5b): a pièce's metadata and original bytes are
served ONLY within the caller's scope, the open is audited (FR-45), and an out-of-scope pièce is
byte-identical to an absent one (FR-14/FR-44). The original is served as an attachment + nosniff
(never inline-executable), decrypted within the tenant boundary (3.5a); a missing blob is an honest
409, never a 500."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from apx.adapters.originals_fs import FilesystemOriginalStore
from apx.adapters.store_postgres.models import AuditRecord, Base
from apx.adapters.store_postgres.store import SqlStore
from apx.api import app as app_module
from apx.api.app import app
from apx.core.app.ingest import IngestedPiece, IngestionResult


def _data(tmp_path):  # noqa: ANN001, ANN202
    """The data volume, in its own subdirectory.

    Story 7.1: APX_INGEST_ROOT is the test's tmp_path, and a root that can reach
    $APX_DATA_PATH/originals or /spool is refused — those hold another matter's
    retained documents and another user's upload. So the data volume sits BESIDE the
    ingestable tree rather than inside it, which is also how a deployment separates them.
    """
    d = tmp_path.parent / f"{tmp_path.name}-data"
    d.mkdir(exist_ok=True)
    return d


SECRET = "test-secret"
TENANT, WALL, OTHER_WALL = "t", "wall-a", "wall-b"


@pytest.fixture(autouse=True)
def _reset_state():
    app_module._store.cache_clear()
    app_module._login_limiter._fails.clear()
    yield
    app_module._store.cache_clear()
    app_module._login_limiter._fails.clear()


def _prepare(tmp_path: Path, monkeypatch) -> SqlStore:
    url = f"sqlite:///{tmp_path / 'apx.db'}"
    Base.metadata.create_all(create_engine(url))
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("APX_SECRET_KEY", SECRET)
    monkeypatch.setenv("APX_DATA_PATH", str(_data(tmp_path)))  # isolate retained originals here
    return SqlStore(sessionmaker(bind=create_engine(url), future=True))


def _piece(matter: str, content_hash: str, filename: str, method: str = "pypdf") -> IngestedPiece:
    pid = hashlib.sha256(f"{TENANT}\0{content_hash}\0{matter}".encode()).hexdigest()
    return IngestedPiece(
        id=pid, matter=matter, tenant=TENANT, content_hash=content_hash, text_key=content_hash,
        provenance_path=f"dossier/{filename}", custodian="c", extraction_method=method,
        extractor_version="v", schema_version="s", ingestion_timestamp=datetime.now(UTC),
        full_text="le contenu", text_version="v")


def _seed(store: SqlStore, matter: str, scope: str, data: bytes, filename: str,
          method: str = "pypdf", *, retain: bool = True) -> str:
    """Persist a pièce under ``scope`` and (optionally) retain its original; return its piece_id."""
    ch = hashlib.sha256(data).hexdigest()
    p = _piece(matter, ch, filename, method)
    store.save(IngestionResult(pieces=[p]), scope=scope, actor="sys")
    if retain:
        FilesystemOriginalStore.from_env().put(TENANT, ch, data)
    return p.id


def _login(c: TestClient, email: str = "me@cab.fr", pw: str = "password1") -> None:
    r = c.post("/api/login", json={"tenant": TENANT, "email": email, "password": pw})
    assert r.status_code == 200, r.text


def _audit_actions(store: SqlStore) -> list[str]:
    with store._sf() as s:
        return list(s.scalars(select(AuditRecord.action).where(AuditRecord.tenant == TENANT)))


def test_metadata_is_served_for_an_in_scope_piece(tmp_path, monkeypatch) -> None:
    store = _prepare(tmp_path, monkeypatch)
    pid = _seed(store, "m-in", WALL, b"%PDF-1.7 bail commercial", "bail.pdf")
    store.create_user(TENANT, "me@cab.fr", "password1", "Me Durand", {WALL})
    c = TestClient(app)
    _login(c)
    body = c.get(f"/api/pieces/{pid}").json()
    assert body["media_kind"] == "pdf" and body["ocr"] is False
    assert body["filename"] == "bail.pdf"                    # the basename, not the full provenance
    assert body["byte_size"] == len(b"%PDF-1.7 bail commercial")
    assert body["renderable_inline"] is True                 # under the render bound


def test_the_original_is_served_as_a_safe_attachment_and_is_audited(tmp_path, monkeypatch) -> None:
    store = _prepare(tmp_path, monkeypatch)
    data = b"%PDF-1.7 clause de cession"
    pid = _seed(store, "m-in", WALL, data, "acte.pdf")
    store.create_user(TENANT, "me@cab.fr", "password1", "Me Durand", {WALL})
    c = TestClient(app)
    _login(c)
    r = c.get(f"/api/pieces/{pid}/original")
    assert r.status_code == 200 and r.content == data       # decrypted original bytes
    assert r.headers["content-type"] == "application/octet-stream"       # never inline-executable
    assert r.headers["x-content-type-options"] == "nosniff"
    assert 'attachment; filename="acte.pdf"' in r.headers["content-disposition"]
    assert _audit_actions(store).count("open-piece") == 1   # opening the content is audited (FR-45)


def test_ocr_piece_declares_its_honesty_flag(tmp_path, monkeypatch) -> None:
    store = _prepare(tmp_path, monkeypatch)
    pid = _seed(store, "m-in", WALL, b"scan bytes", "attestation.pdf", method="tesseract")
    store.create_user(TENANT, "me@cab.fr", "password1", "Me Durand", {WALL})
    c = TestClient(app)
    _login(c)
    assert c.get(f"/api/pieces/{pid}").json()["ocr"] is True   # its text came from OCR


def test_out_of_scope_is_byte_identical_to_absent(tmp_path, monkeypatch) -> None:
    store = _prepare(tmp_path, monkeypatch)
    out = _seed(store, "m-out", OTHER_WALL, b"secret adverse", "confidentiel.pdf")
    store.create_user(TENANT, "me@cab.fr", "password1", "Me Durand", {WALL})  # holds WALL only
    c = TestClient(app)
    _login(c)
    r_out = c.get(f"/api/pieces/{out}")
    r_absent = c.get(f"/api/pieces/{'0' * 64}")               # a piece that does not exist
    assert r_out.status_code == r_absent.status_code == 404
    assert r_out.json() == r_absent.json()                   # existence not disclosed (FR-14/FR-44)
    # and the original is likewise not served, and writes NO audit entry
    assert c.get(f"/api/pieces/{out}/original").status_code == 404
    assert _audit_actions(store).count("open-piece") == 0


def test_empty_scope_reads_nothing(tmp_path, monkeypatch) -> None:
    store = _prepare(tmp_path, monkeypatch)
    pid = _seed(store, "m-in", WALL, b"data", "x.pdf")
    store.create_user(TENANT, "me@cab.fr", "password1", "Me Durand", set())   # no scope
    c = TestClient(app)
    _login(c)
    assert c.get(f"/api/pieces/{pid}").status_code == 404     # fail-closed (AD-12)


def test_a_missing_original_is_an_honest_409_not_a_500(tmp_path, monkeypatch) -> None:
    store = _prepare(tmp_path, monkeypatch)
    pid = _seed(store, "m-in", WALL, b"never retained", "orphan.pdf", retain=False)  # no blob
    store.create_user(TENANT, "me@cab.fr", "password1", "Me Durand", {WALL})
    c = TestClient(app)
    _login(c)
    assert c.get(f"/api/pieces/{pid}").json()["byte_size"] is None        # metadata still served
    assert c.get(f"/api/pieces/{pid}/original").status_code == 409        # honest unavailable
    assert _audit_actions(store).count("open-piece") == 0                 # nothing was read


def test_the_open_audit_keeps_the_chain_verifiable(tmp_path, monkeypatch) -> None:
    store = _prepare(tmp_path, monkeypatch)
    pid = _seed(store, "m-in", WALL, b"content", "p.pdf")
    store.create_user(TENANT, "me@cab.fr", "password1", "Me Durand", {WALL})
    c = TestClient(app)
    _login(c)
    assert c.get(f"/api/pieces/{pid}/original").status_code == 200
    assert store.read_audit("m-in", TENANT, {WALL}).verified is True      # AD-43 chain intact


def test_an_accented_filename_is_preserved_via_rfc6266(tmp_path, monkeypatch) -> None:
    # a real FR/LU pièce name keeps its accents on download (RFC 6266 filename*), with an ASCII
    # fallback for old clients — the review flagged the ASCII-only header as lossy for these users.
    store = _prepare(tmp_path, monkeypatch)
    pid = _seed(store, "m-in", WALL, b"data", "reçu-créance-étude.pdf")
    store.create_user(TENANT, "me@cab.fr", "password1", "Me Durand", {WALL})
    c = TestClient(app)
    _login(c)
    cd = c.get(f"/api/pieces/{pid}/original").headers["content-disposition"]
    assert "filename*=UTF-8''" in cd and "re%C3%A7u" in cd    # 'reçu' preserved, %-encoded UTF-8
    assert 'filename="' in cd                                 # an ASCII fallback is still present


def test_a_crafted_filename_cannot_inject_a_header(tmp_path, monkeypatch) -> None:
    store = _prepare(tmp_path, monkeypatch)
    pid = _seed(store, "m-in", WALL, b"data", 'evil".pdf')   # a quote that could break the param
    store.create_user(TENANT, "me@cab.fr", "password1", "Me Durand", {WALL})
    c = TestClient(app)
    _login(c)
    cd = c.get(f"/api/pieces/{pid}/original").headers["content-disposition"]
    assert "\r" not in cd and "\n" not in cd                  # no header break
    assert cd.count("filename=") == 1                         # the quote did not spawn a 2nd param
