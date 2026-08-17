"""The scan viewer endpoints (Story 3.5c-4). `/page/{n}` rasterises a scanned-PDF page to a PNG and
IS the audited open (FR-45: serving readable content is an open, like /original & /render); it
requires a stored OCR layer, so a born-digital / no-layout PDF, an out-of-range or pixel-bomb page,
or an over-bound scan → 409 (client renders the original), never an unaudited read. `/layout` serves
the OCR box coordinates (overlay METADATA) and is NOT audited. Out-of-scope, absent, and no-layout
are the same non-disclosing 404; a tampered layout → 409. Both carry no-store + nosniff (AD-29)."""

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
from apx.core.domain.ocr_layout import OcrLayout, OcrPage


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
_LAYOUT = OcrLayout(
    pages=tuple(OcrPage(1000, 1200, ()) for _ in range(3)), dpi=200).to_json().encode()  # 3 pages
_BOMB = OcrLayout(pages=(OcrPage(20000, 20000, ()),), dpi=200).to_json().encode()   # 400 Mpx


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
    monkeypatch.setenv("APX_DATA_PATH", str(_data(tmp_path)))
    return SqlStore(sessionmaker(bind=create_engine(url), future=True))


def _piece(matter: str, content_hash: str, filename: str) -> IngestedPiece:
    pid = hashlib.sha256(f"{TENANT}\0{content_hash}\0{matter}".encode()).hexdigest()
    return IngestedPiece(
        id=pid, matter=matter, tenant=TENANT, content_hash=content_hash, text_key=content_hash,
        provenance_path=f"dossier/{filename}", custodian="c", extraction_method="tesseract",
        extractor_version="v", schema_version="s", ingestion_timestamp=datetime.now(UTC),
        full_text="le contenu", text_version="v")


def _seed_scan(store: SqlStore, matter: str, scope: str, data: bytes, filename: str, *,
               layout: bytes | None = None) -> str:
    ch = hashlib.sha256(data).hexdigest()
    p = _piece(matter, ch, filename)
    store.save(IngestionResult(pieces=[p]), scope=scope, actor="sys")
    fs = FilesystemOriginalStore.from_env()
    fs.put(TENANT, ch, data)
    if layout is not None:
        fs.put(TENANT, ch, layout, kind="ocr-layout")
    return p.id


def _corrupt_layout(tmp_path: Path) -> None:
    # The blobs live on the data volume, which sits BESIDE the ingestable tree since story 7.1.
    for f in _data(tmp_path).rglob("*.ocr-layout"):
        f.write_bytes(b"garbage that will not authenticate under AES-GCM")
        return


def _login(c: TestClient) -> None:
    r = c.post("/api/login", json={"tenant": TENANT, "email": "me@cab.fr", "password": "password1"})
    assert r.status_code == 200, r.text


def _audit_actions(store: SqlStore) -> list[str]:
    with store._sf() as s:
        return list(s.scalars(select(AuditRecord.action).where(AuditRecord.tenant == TENANT)))


class _FakeRasterizer:
    def rasterize(self, *, data: bytes, page: int) -> bytes | None:
        return b"\x89PNG-page-" + str(page).encode()


def _user(store: SqlStore) -> None:
    store.create_user(TENANT, "me@cab.fr", "password1", "Me Durand", {WALL})


# ── /layout — overlay metadata, NOT audited ──
def test_layout_is_served_but_not_audited(tmp_path, monkeypatch) -> None:
    store = _prepare(tmp_path, monkeypatch)
    pid = _seed_scan(store, "m-in", WALL, b"%PDF scan bytes", "scan.pdf", layout=_LAYOUT)
    _user(store)
    c = TestClient(app)
    _login(c)
    r = c.get(f"/api/pieces/{pid}/layout")
    assert r.status_code == 200 and r.content == _LAYOUT
    assert r.headers["content-type"] == "application/json"
    assert r.headers["cache-control"] == "no-store"
    assert r.headers["x-content-type-options"] == "nosniff"
    assert _audit_actions(store).count("open-piece") == 0   # the layout is metadata, not content


def test_layout_absent_for_a_non_ocr_piece_is_404(tmp_path, monkeypatch) -> None:
    store = _prepare(tmp_path, monkeypatch)
    pid = _seed_scan(store, "m-in", WALL, b"%PDF born-digital", "doc.pdf")  # no layout stored
    _user(store)
    c = TestClient(app)
    _login(c)
    assert c.get(f"/api/pieces/{pid}/layout").status_code == 404   # non-disclosing


def test_layout_out_of_scope_is_byte_identical_to_absent(tmp_path, monkeypatch) -> None:
    store = _prepare(tmp_path, monkeypatch)
    out = _seed_scan(store, "m-out", OTHER_WALL, b"%PDF secret", "s.pdf", layout=_LAYOUT)
    _user(store)
    c = TestClient(app)
    _login(c)
    r_out = c.get(f"/api/pieces/{out}/layout")
    r_absent = c.get(f"/api/pieces/{'0' * 64}/layout")
    assert r_out.status_code == r_absent.status_code == 404
    assert r_out.json() == r_absent.json()                # existence not disclosed


def test_a_tampered_layout_blob_is_an_honest_409(tmp_path, monkeypatch) -> None:
    store = _prepare(tmp_path, monkeypatch)
    pid = _seed_scan(store, "m-in", WALL, b"%PDF scan", "scan.pdf", layout=_LAYOUT)
    _user(store)
    _corrupt_layout(tmp_path)                             # the ocr-layout blob no longer decrypts
    c = TestClient(app)
    _login(c)
    assert c.get(f"/api/pieces/{pid}/layout").status_code == 409   # honest unavailable, not a 500


# ── /page — readable content, AUDITED; requires a scan ──
def test_a_page_is_served_as_png_and_is_audited(tmp_path, monkeypatch) -> None:
    store = _prepare(tmp_path, monkeypatch)
    pid = _seed_scan(store, "m-in", WALL, b"%PDF scan bytes", "scan.pdf", layout=_LAYOUT)
    _user(store)
    monkeypatch.setattr(app_module, "_page_rasterizer", lambda: _FakeRasterizer())
    c = TestClient(app)
    _login(c)
    r = c.get(f"/api/pieces/{pid}/page/2")
    assert r.status_code == 200 and r.content == b"\x89PNG-page-2"
    assert r.headers["content-type"] == "image/png"
    assert r.headers["cache-control"] == "no-store"
    assert r.headers["x-content-type-options"] == "nosniff"
    assert _audit_actions(store).count("open-piece") == 1   # serving readable content is audited


def test_a_born_digital_pdf_via_page_is_409_and_unaudited(tmp_path, monkeypatch) -> None:
    store = _prepare(tmp_path, monkeypatch)
    pid = _seed_scan(store, "m-in", WALL, b"%PDF born-digital", "doc.pdf")  # NO layer → not a scan
    _user(store)
    monkeypatch.setattr(app_module, "_page_rasterizer", lambda: _FakeRasterizer())
    c = TestClient(app)
    _login(c)
    assert c.get(f"/api/pieces/{pid}/page/0").status_code == 409   # client renders the original
    assert _audit_actions(store).count("open-piece") == 0          # nothing readable served


def test_a_pixel_bomb_page_is_409(tmp_path, monkeypatch) -> None:
    store = _prepare(tmp_path, monkeypatch)
    pid = _seed_scan(store, "m-in", WALL, b"%PDF tiny file huge page", "bomb.pdf", layout=_BOMB)
    _user(store)
    monkeypatch.setattr(app_module, "_page_rasterizer", lambda: _FakeRasterizer())
    c = TestClient(app)
    _login(c)
    assert c.get(f"/api/pieces/{pid}/page/0").status_code == 409   # 400 Mpx > default 100 Mpx cap
    assert _audit_actions(store).count("open-piece") == 0


def test_page_out_of_scope_is_404(tmp_path, monkeypatch) -> None:
    store = _prepare(tmp_path, monkeypatch)
    out = _seed_scan(store, "m-out", OTHER_WALL, b"%PDF secret", "s.pdf", layout=_LAYOUT)
    _user(store)
    monkeypatch.setattr(app_module, "_page_rasterizer", lambda: _FakeRasterizer())
    c = TestClient(app)
    _login(c)
    assert c.get(f"/api/pieces/{out}/page/0").status_code == 404   # discloses nothing
    assert _audit_actions(store).count("open-piece") == 0


def test_a_non_rasterisable_page_is_409(tmp_path, monkeypatch) -> None:
    class _NoneRasterizer:
        def rasterize(self, *, data: bytes, page: int) -> bytes | None:
            return None
    store = _prepare(tmp_path, monkeypatch)
    pid = _seed_scan(store, "m-in", WALL, b"%PDF a scan", "scan.pdf", layout=_LAYOUT)
    _user(store)
    monkeypatch.setattr(app_module, "_page_rasterizer", lambda: _NoneRasterizer())
    c = TestClient(app)
    _login(c)
    assert c.get(f"/api/pieces/{pid}/page/0").status_code == 409   # in-scope — offer the original
    assert _audit_actions(store).count("open-piece") == 0          # nothing served → no audit


def test_a_page_over_the_scan_byte_bound_is_409_without_loading(tmp_path, monkeypatch) -> None:
    store = _prepare(tmp_path, monkeypatch)
    pid = _seed_scan(store, "m-in", WALL, b"%PDF a scan of some size", "scan.pdf", layout=_LAYOUT)
    _user(store)
    monkeypatch.setenv("APX_SCAN_RENDER_MAX_BYTES", "5")   # force over-bound
    monkeypatch.setattr(app_module, "_page_rasterizer", lambda: _FakeRasterizer())
    c = TestClient(app)
    _login(c)
    assert c.get(f"/api/pieces/{pid}/page/0").status_code == 409
    assert _audit_actions(store).count("open-piece") == 0
