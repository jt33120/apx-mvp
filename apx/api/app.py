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

from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from apx.adapters.extraction.files import FileExtractor
from apx.core.app.ingest import ingest_folder

app = FastAPI(title="APX", version="0.0.0")


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
    inv = result.inventory
    return IngestResponse(
        matter=req.matter,
        inventory=InventoryOut(
            submitted=inv.submitted,
            in_corpus=inv.in_corpus,
            failures=inv.failures,
            exclusions=inv.exclusions,
            consistent=inv.is_consistent(),
        ),
        failure_list=[
            FailureOut(filename=f.filename, path=f.submitted_path, error_class=str(f.error_class))
            for f in result.failures
        ],
        exclusion_list=result.exclusions,
    )
