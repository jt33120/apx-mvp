"""The pièce render endpoint over HTTP (Story 3.5c-2): an in-scope ``.docx``/``.xlsx`` renders to
SANITISED inline HTML, the render is the audited open (FR-45), out-of-scope is byte-identical to
absent (FR-14/FR-44), and over-bound / unrenderable offers the original (``renderable:false``, no
audit). Every rendered response is ``Cache-Control: no-store`` (AD-29)."""

from __future__ import annotations

import hashlib
import io
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from apx.adapters.originals_fs import FilesystemOriginalStore
from apx.adapters.store_postgres.models import AuditRecord, Base
from apx.adapters.store_postgres.store import SqlStore
from apx.api import app as app_module
from apx.api.app import app
from apx.core.app.ingest import IngestedPiece, IngestionResult

SECRET = "test-secret"
TENANT, WALL, OTHER_WALL = "t", "wall-a", "wall-b"

_CT = (
    '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/'
    'content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-'
    'package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-'
    'officedocument.wordprocessingml.document.main+xml"/></Types>')
_RELS = (
    '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/'
    'relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/'
    '2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')


def _docx(text: str) -> bytes:
    body = (f'<w:p><w:r><w:t>{text}</w:t></w:r></w:p>')
    doc = (
        '<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/'
        f'wordprocessingml/2006/main"><w:body>{body}</w:body></w:document>')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", _CT)
        z.writestr("_rels/.rels", _RELS)
        z.writestr("word/document.xml", doc)
    return buf.getvalue()


def _xlsx(rows: list[list[object]]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    for row in rows:
        sheet.append(row)
    buf = io.BytesIO()
    workbook.save(buf)
    return buf.getvalue()


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
    monkeypatch.setenv("APX_DATA_PATH", str(tmp_path))  # isolate retained originals here
    return SqlStore(sessionmaker(bind=create_engine(url), future=True))


def _piece(matter: str, content_hash: str, filename: str, method: str = "pypdf") -> IngestedPiece:
    pid = hashlib.sha256(f"{TENANT}\0{content_hash}\0{matter}".encode()).hexdigest()
    return IngestedPiece(
        id=pid, matter=matter, tenant=TENANT, content_hash=content_hash, text_key=content_hash,
        provenance_path=f"dossier/{filename}", custodian="c", extraction_method=method,
        extractor_version="v", schema_version="s", ingestion_timestamp=datetime.now(UTC),
        full_text="le contenu", text_version="v")


def _seed(store: SqlStore, matter: str, scope: str, data: bytes, filename: str) -> str:
    ch = hashlib.sha256(data).hexdigest()
    p = _piece(matter, ch, filename)
    store.save(IngestionResult(pieces=[p]), scope=scope, actor="sys")
    FilesystemOriginalStore.from_env().put(TENANT, ch, data)
    return p.id


def _login(c: TestClient) -> None:
    r = c.post("/api/login", json={"tenant": TENANT, "email": "me@cab.fr", "password": "password1"})
    assert r.status_code == 200, r.text


def _audit_actions(store: SqlStore) -> list[str]:
    with store._sf() as s:
        return list(s.scalars(select(AuditRecord.action).where(AuditRecord.tenant == TENANT)))


def test_an_in_scope_xlsx_renders_to_sanitized_html_and_is_audited(tmp_path, monkeypatch) -> None:
    store = _prepare(tmp_path, monkeypatch)
    pid = _seed(store, "m-in", WALL, _xlsx([["Poste", "Montant"], ["Dépôt", 0]]), "annexe.xlsx")
    store.create_user(TENANT, "me@cab.fr", "password1", "Me Durand", {WALL})
    c = TestClient(app)
    _login(c)
    r = c.get(f"/api/pieces/{pid}/render")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["renderable"] is True and body["format"] == "html"
    assert "<td>Poste</td>" in body["html"] and "Dépôt" in body["html"]
    assert r.headers["cache-control"] == "no-store"                 # AD-29: tenant data uncached
    assert _audit_actions(store).count("open-piece") == 1           # rendering IS opening (FR-45)


def test_an_in_scope_docx_renders_its_text(tmp_path, monkeypatch) -> None:
    store = _prepare(tmp_path, monkeypatch)
    pid = _seed(store, "m-in", WALL, _docx("Article 4 : dépôt de garantie"), "bail.docx")
    store.create_user(TENANT, "me@cab.fr", "password1", "Me Durand", {WALL})
    c = TestClient(app)
    _login(c)
    body = c.get(f"/api/pieces/{pid}/render").json()
    assert body["renderable"] is True and "Article 4" in body["html"]


def test_an_in_scope_msg_renders_via_the_worker_and_is_audited(tmp_path, monkeypatch) -> None:
    from apx.adapters.extraction import msg as msgmod
    store = _prepare(tmp_path, monkeypatch)
    pid = _seed(store, "m-in", WALL, b"OLE-ish .msg bytes", "courriel.msg")
    store.create_user(TENANT, "me@cab.fr", "password1", "Me Durand", {WALL})
    # the GPL-isolated worker is mocked (a valid .msg cannot be synthesised); the composite routes
    # .msg to MsgRenderer, which spools the bytes and calls the worker's render mode.
    monkeypatch.setattr(msgmod, "_run_msg_worker", lambda p, m: {
        "ok": True, "from": "adverse@x.fr", "subject": "Mise en demeure",
        "body": "Bonjour Maître,\nvoir ci-joint.", "attachments": ["contrat.pdf"]})
    c = TestClient(app)
    _login(c)
    r = c.get(f"/api/pieces/{pid}/render")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["renderable"] is True and body["title"] == "Mise en demeure"
    assert "adverse@x.fr" in body["html"] and "contrat.pdf" in body["html"]
    assert "<script" not in body["html"].lower()
    assert r.headers["cache-control"] == "no-store"
    assert _audit_actions(store).count("open-piece") == 1   # a .msg render audits like any open


def test_an_adversarial_xlsx_carries_no_active_content(tmp_path, monkeypatch) -> None:
    store = _prepare(tmp_path, monkeypatch)
    data = _xlsx([["<script>alert(1)</script>", "<img src=x onerror=y()>"]])
    pid = _seed(store, "m-in", WALL, data, "evil.xlsx")
    store.create_user(TENANT, "me@cab.fr", "password1", "Me Durand", {WALL})
    c = TestClient(app)
    _login(c)
    html = c.get(f"/api/pieces/{pid}/render").json()["html"].lower()
    # no LIVE tag from the cell data (escaped inert text may still carry the word "onerror")
    assert "<script" not in html and "<img" not in html and "<iframe" not in html
    assert "&lt;script&gt;" in html                          # the cell value was escaped, inert


def test_out_of_scope_render_is_byte_identical_to_absent(tmp_path, monkeypatch) -> None:
    store = _prepare(tmp_path, monkeypatch)
    out = _seed(store, "m-out", OTHER_WALL, _xlsx([["secret"]]), "confidentiel.xlsx")
    store.create_user(TENANT, "me@cab.fr", "password1", "Me Durand", {WALL})  # holds WALL only
    c = TestClient(app)
    _login(c)
    r_out = c.get(f"/api/pieces/{out}/render")
    r_absent = c.get(f"/api/pieces/{'0' * 64}/render")
    assert r_out.status_code == r_absent.status_code == 404
    assert r_out.json() == r_absent.json()                          # existence not disclosed
    assert _audit_actions(store).count("open-piece") == 0           # no audit on a denied render


def test_over_the_render_bound_offers_the_original_without_audit(tmp_path, monkeypatch) -> None:
    store = _prepare(tmp_path, monkeypatch)
    pid = _seed(store, "m-in", WALL, _xlsx([["Poste", "Montant"]]), "gros.xlsx")
    store.create_user(TENANT, "me@cab.fr", "password1", "Me Durand", {WALL})
    monkeypatch.setenv("APX_PIECE_RENDER_MAX_BYTES", "10")          # force over-bound
    c = TestClient(app)
    _login(c)
    body = c.get(f"/api/pieces/{pid}/render").json()
    assert body["renderable"] is False and body["reason"]          # offer the original
    assert _audit_actions(store).count("open-piece") == 0          # nothing served → no audit


def test_an_unrenderable_format_offers_the_original(tmp_path, monkeypatch) -> None:
    store = _prepare(tmp_path, monkeypatch)
    pid = _seed(store, "m-in", WALL, b"%PDF-1.7 a scanned bail", "scan.pdf")
    store.create_user(TENANT, "me@cab.fr", "password1", "Me Durand", {WALL})
    c = TestClient(app)
    _login(c)
    body = c.get(f"/api/pieces/{pid}/render").json()
    assert body["renderable"] is False and body["reason"]   # a .pdf renders client-side (3.5d)
    assert _audit_actions(store).count("open-piece") == 0
