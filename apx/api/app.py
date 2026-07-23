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
from apx.adapters.store_postgres.store import ScopeDenied, SqlStore
from apx.core.app.ingest import IngestionResult, ingest_folder

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
    scope: str = ""  # the Chinese-wall scope; defaults to the matter itself (its own wall)
    actor: str = "unknown"  # who acted; the real identity comes from auth (story 1.5)
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


class AuditEntryOut(BaseModel):
    seq: int
    actor: str
    action: str
    detail: str
    timestamp: str


class AuditTrailOut(BaseModel):
    entries: list[AuditEntryOut]
    verified: bool


class DuplicateGroupOut(BaseModel):
    representative: str      # the copy shown (and judged) on behalf of the group
    members: list[str]       # every copy's provenance path, representative included
    size: int


class TriageOut(BaseModel):
    submitted: int           # corpus pieces
    distinct: int            # what remains to examine — submitted = distinct + duplicates
    duplicates: int          # copies collapsed (kept, not deleted — reversible)
    groups: list[DuplicateGroupOut]


class MatterOut(BaseModel):
    matter: str
    scope: str
    inventory: InventoryOut


def _inventory_out(inv) -> InventoryOut:  # noqa: ANN001
    return InventoryOut(
        submitted=inv.submitted, in_corpus=inv.in_corpus, failures=inv.failures,
        exclusions=inv.exclusions, consistent=inv.is_consistent(),
    )


def _persist(result: IngestionResult, scope: str, actor: str) -> bool:
    """Persist under the given Chinese-wall scope, if a database is configured.
    The ingestion is recorded in the audit trail, atomically, under `actor`."""
    store = _store()
    if store is None:
        return False
    store.save(result, scope, actor)
    return True


def _parse_scopes(scopes: str) -> set[str]:
    return {s.strip() for s in scopes.split(",") if s.strip()}


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
    persisted = _persist(result, req.scope or req.matter, req.actor)
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
    scope: str = Form(""),
    actor: str = Form("unknown"),
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
    persisted = _persist(result, scope or matter, actor)
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


@app.get("/api/matters", response_model=list[MatterOut])
def list_matters(tenant: str, scopes: str) -> list[MatterOut]:
    """Every matter the caller may see — pre-filtered by their RBAC scope (the
    Chinese wall, AD-13/AD-14). `scopes` is comma-separated; empty means none."""
    store = _store()
    if store is None:
        raise HTTPException(status_code=503, detail="no database configured (set DATABASE_URL)")
    return [
        MatterOut(matter=m.matter, scope=m.scope, inventory=_inventory_out(m.inventory))
        for m in store.matters(tenant, _parse_scopes(scopes))
    ]


@app.get("/api/matters/{matter}/audit", response_model=AuditTrailOut)
def read_audit(matter: str, tenant: str, scopes: str) -> AuditTrailOut:
    """The audit trail for a matter — 403 if its scope is not held. `verified` is
    the tamper-evidence: the tenant's audit chain recomputes cleanly."""
    store = _store()
    if store is None:
        raise HTTPException(status_code=503, detail="no database configured (set DATABASE_URL)")
    try:
        trail = store.read_audit(matter, tenant, _parse_scopes(scopes))
    except ScopeDenied as exc:
        raise HTTPException(status_code=403, detail="outside your scope") from exc
    return AuditTrailOut(
        entries=[
            AuditEntryOut(seq=e.seq, actor=e.actor, action=e.action, detail=e.detail,
                          timestamp=e.timestamp)
            for e in trail.entries
        ],
        verified=trail.verified,
    )


@app.get("/api/matters/{matter}/triage", response_model=TriageOut)
def read_triage(matter: str, tenant: str, scopes: str) -> TriageOut:
    """The deterministic triage for a matter — near-duplicate clustering, the cheap
    first tier of the judgment cascade (403 outside the scope). `submitted = distinct
    + duplicates`: nothing lost, copies collapsed to one piece to examine."""
    store = _store()
    if store is None:
        raise HTTPException(status_code=503, detail="no database configured (set DATABASE_URL)")
    try:
        summary = store.deduplicate(matter, tenant, _parse_scopes(scopes))
    except ScopeDenied as exc:
        raise HTTPException(status_code=403, detail="outside your scope") from exc
    return TriageOut(
        submitted=summary.submitted,
        distinct=summary.distinct,
        duplicates=summary.duplicates,
        groups=[
            DuplicateGroupOut(representative=g.representative, members=list(g.members), size=g.size)
            for g in summary.groups
        ],
    )


@app.get("/api/matters/{matter}/inventory", response_model=InventoryOut)
def read_inventory(matter: str, tenant: str, scopes: str) -> InventoryOut:
    """The durable inventory for a matter — 403 if its scope is not held (fail
    closed, and the matter's existence is not disclosed)."""
    store = _store()
    if store is None:
        raise HTTPException(status_code=503, detail="no database configured (set DATABASE_URL)")
    try:
        inv = store.inventory(matter, tenant, _parse_scopes(scopes))
    except ScopeDenied as exc:
        raise HTTPException(status_code=403, detail="outside your scope") from exc
    return _inventory_out(inv)
