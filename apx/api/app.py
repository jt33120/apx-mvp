"""The HTTP surface (AD-6). Validate, run the use case, return.

This edge wires the Extractor adapter to the ingestion use case (the core imports
no adapter — the composition happens here, at the edge). Slice A ships the
inventory path: drop a folder → the denominator and the failure list. Every data
access is an HTTP call to this one API (AD-14); there is no second data path.

Not yet (their stories): persistence of the result (the store writer), RBAC
(1.4/3.3), audit (5.x), upload/USB transport (a server-side folder path stands in
for the USB key here). No fixtures, no demo override (FR-33).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException
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


@app.get("/api/matters/{matter}/inventory", response_model=InventoryOut)
def read_inventory(matter: str, tenant: str) -> InventoryOut:
    """The durable inventory for a matter (corpus + open failures). Requires a
    database — a read-back has nowhere to read from otherwise."""
    store = _store()
    if store is None:
        raise HTTPException(status_code=503, detail="no database configured (set DATABASE_URL)")
    return _inventory_out(store.inventory(matter, tenant))
