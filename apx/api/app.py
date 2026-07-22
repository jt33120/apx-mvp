"""The HTTP surface (AD-6). Validate, run the use case, return.

This edge wires the Extractor adapter to the ingestion use case (the core imports
no adapter — the composition happens here, at the edge). Slice A ships the
inventory path: drop a folder → the denominator and the failure list. Every data
access is an HTTP call to this one API (AD-14); there is no second data path.

Two intake paths through the SAME ingestion: POST /api/ingest (a server-side
folder — the on-prem / USB-key model) and POST /api/ingest-upload (a browser
folder upload — the hosted model). Persistence is transparent (`persisted`).
Not yet (their stories): RBAC (1.4/3.3), audit (5.x), idempotent job semantics,
container expansion. No fixtures, no demo override (FR-33).
"""

from __future__ import annotations

import tempfile
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, UploadFile
from pydantic import BaseModel

from apx.adapters.extraction.files import FileExtractor
from apx.adapters.store_postgres.engine import make_session_factory
from apx.adapters.store_postgres.store import SqlStore
from apx.core.app.ingest import ingest_folder

app = FastAPI(title="APX", version="0.0.0")


@lru_cache(maxsize=1)
def _store() -> SqlStore | None:
    """The durable store, built from DATABASE_URL. None when no database is
    configured — the ingest path still computes and returns; only read-back and
    persistence need it. This is transparent (the response says whether it
    persisted), never a silent fixture (FR-33)."""
    try:
        return SqlStore(make_session_factory())
    except RuntimeError:
        return None


class IngestRequest(BaseModel):
    folder: str
    matter: str
    tenant: str
    custodian: str = "custodian-undeclared"


class FailureOut(BaseModel):
    filename: str
    path: str
    error_class: str


class InventoryOut(BaseModel):
    submitted: int
    in_corpus: int
    failures: int
    exclusions: int
    consistent: bool


class IngestResponse(BaseModel):
    matter: str
    inventory: InventoryOut
    failure_list: list[FailureOut]
    exclusion_list: list[str]
    persisted: bool  # transparent: whether the result was written to the durable store


def _inventory_out(inv) -> InventoryOut:  # noqa: ANN001
    return InventoryOut(
        submitted=inv.submitted, in_corpus=inv.in_corpus, failures=inv.failures,
        exclusions=inv.exclusions, consistent=inv.is_consistent(),
    )


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/ingest", response_model=IngestResponse)
def ingest(req: IngestRequest) -> IngestResponse:
    folder = Path(req.folder)
    if not folder.is_dir():
        raise HTTPException(status_code=400, detail=f"not a folder: {req.folder}")
    result = ingest_folder(
        folder, matter=req.matter, tenant=req.tenant,
        extractor=FileExtractor(), custodian=req.custodian,
    )
    store = _store()
    persisted = False
    if store is not None:
        store.save(result)
        persisted = True
    return IngestResponse(
        matter=req.matter,
        inventory=_inventory_out(result.inventory),
        failure_list=[
            FailureOut(filename=f.filename, path=f.submitted_path, error_class=str(f.error_class))
            for f in result.failures
        ],
        exclusion_list=result.exclusions,
        persisted=persisted,
    )


@app.post("/api/ingest-upload", response_model=IngestResponse)
async def ingest_upload(
    matter: str = Form(...),
    tenant: str = Form(...),
    files: list[UploadFile] = Form(...),
) -> IngestResponse:
    """The browser path: a lawyer drops files (or a folder) and sees the inventory.
    Uploaded files are written to a per-request temp directory — reconstructing the
    submitted folder tree from each file's relative path — then ingested through the
    same one path (FR-33). The temp dir is discarded; only the piece text (and
    failures) persist to the store."""
    if not files:
        raise HTTPException(status_code=400, detail="no files uploaded")
    with tempfile.TemporaryDirectory(prefix="apx-upload-") as tmp:
        root = Path(tmp)
        for f in files:
            # The SPA sends the folder-relative path as the filename; rebuild the tree.
            rel = Path(f.filename or "unnamed").as_posix().lstrip("/")
            dest = root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(await f.read())
        result = ingest_folder(root, matter=matter, tenant=tenant, extractor=FileExtractor())
    store = _store()
    persisted = False
    if store is not None:
        store.save(result)
        persisted = True
    return IngestResponse(
        matter=matter,
        inventory=_inventory_out(result.inventory),
        failure_list=[
            FailureOut(filename=f.filename, path=f.submitted_path, error_class=str(f.error_class))
            for f in result.failures
        ],
        exclusion_list=result.exclusions,
        persisted=persisted,
    )


@app.get("/api/matters/{matter}/inventory", response_model=InventoryOut)
def read_inventory(matter: str, tenant: str) -> InventoryOut:
    """The durable inventory for a matter (corpus + open failures). Requires a
    database — a read-back has nowhere to read from otherwise."""
    store = _store()
    if store is None:
        raise HTTPException(status_code=503, detail="no database configured (set DATABASE_URL)")
    return _inventory_out(store.inventory(matter, tenant))
