"""The HTTP surface (AD-6). Validate, authenticate, run the use case, return.

This edge wires the adapters (extraction, judge) to the use cases — the core imports
no adapter; composition happens here. Every data access is an HTTP call to this one
API (AD-14). Access is by an owned session (AD-15): a signed cookie identifies the
user, and the Chinese-wall scope (AD-13) is resolved from the authoritative
`user_scope` grants on the server at request time — the client never supplies a
scope, so a request cannot claim a wall it does not hold. The actor recorded on the
audit trail is the session user. No fixtures, no demo override (FR-33).
"""

from __future__ import annotations

import os
import tempfile
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from fastapi import Cookie, Depends, FastAPI, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel

from apx.adapters.extraction.files import FileExtractor
from apx.adapters.judge.criteria import CriteriaJudge
from apx.adapters.llm_openai_compat.judge import CascadeJudge, LLMJudge
from apx.adapters.store_postgres.engine import make_session_factory
from apx.adapters.store_postgres.store import ScopeDenied, SqlStore
from apx.core.app.ingest import IngestionResult, ingest_folder
from apx.core.app.triage import triage_pieces
from apx.core.domain.auth import sign_token, verify_token
from apx.core.ports.judge import Judge

app = FastAPI(title="APX", version="0.0.0")

SESSION_COOKIE = "apx_session"


@lru_cache(maxsize=1)
def _store() -> SqlStore | None:
    """The durable store, built from DATABASE_URL. None when unset — the stateless
    ingest computation still runs, but persistence, read-back and auth need it."""
    try:
        return SqlStore(make_session_factory())
    except RuntimeError:
        return None


def _require_store() -> SqlStore:
    store = _store()
    if store is None:
        raise HTTPException(status_code=503, detail="no database configured (set DATABASE_URL)")
    return store


def _secret() -> str:
    """The local key that signs sessions (APX_SECRET_KEY). Required — there is no
    insecure default; without it, auth fails closed."""
    secret = os.environ.get("APX_SECRET_KEY")
    if not secret:
        raise HTTPException(status_code=503, detail="no session secret (set APX_SECRET_KEY)")
    return secret


@dataclass
class Identity:
    user_id: str
    tenant: str
    actor: str            # the session user's display name — the audit actor
    scopes: set[str]      # resolved live from user_scope; never client-supplied


def current_identity(apx_session: str | None = Cookie(default=None)) -> Identity:
    """Resolve the caller from their session cookie, or 401. Scopes are read from the
    authoritative grants at request time (AD-13), so the client cannot claim a wall."""
    secret = _secret()
    if not apx_session:
        raise HTTPException(status_code=401, detail="not authenticated")
    claims = verify_token(secret, apx_session, now=int(time.time()))
    if claims is None:
        raise HTTPException(status_code=401, detail="invalid or expired session")
    store = _require_store()
    return Identity(
        user_id=claims["user_id"], tenant=claims["tenant"], actor=claims["actor"],
        scopes=store.scopes_for(claims["user_id"]),
    )


class LoginRequest(BaseModel):
    tenant: str
    email: str
    password: str


class IdentityOut(BaseModel):
    actor: str
    tenant: str
    scopes: list[str]


class IngestRequest(BaseModel):
    folder: str
    matter: str
    scope: str  # which wall to file the matter under — must be one you hold
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


class JudgeRequest(BaseModel):
    question: str            # the triage criteria (comma-separated terms for the criteria judge)


class JudgeResultOut(BaseModel):
    judged: int              # distinct pieces judged (one per near-duplicate cluster)
    relevant: int
    uncertain: int
    discarded: int
    judge: str               # which judge decided (transparency, FR-33)


class LabelledPieceOut(BaseModel):
    provenance: str
    label: str
    rationale: str


class LabelsOut(BaseModel):
    relevant: int
    uncertain: int
    discarded: int
    judged: int
    pieces: list[LabelledPieceOut]


class SearchHitOut(BaseModel):
    matter: str
    provenance: str
    snippet: str


class SearchResultsOut(BaseModel):
    query: str
    total: int               # true number of matching pieces, even if `hits` is capped
    returned: int            # how many hits are in this response
    hits: list[SearchHitOut]


class SampledDiscardOut(BaseModel):
    piece_id: str
    provenance: str
    excerpt: str


class RecallSampleOut(BaseModel):
    population: int          # the whole discard pile
    sample: list[SampledDiscardOut]


class RecallVerdictIn(BaseModel):
    piece_id: str
    relevant: bool           # true = the piece was actually relevant (a false discard)


class RecallReviewIn(BaseModel):
    verdicts: list[RecallVerdictIn]
    confidence: float = 0.95


class RecallBoundOut(BaseModel):
    population: int
    sample_size: int
    relevant_found: int
    confidence: float
    count_upper: int         # at most this many of the pile were wrongly discarded
    prevalence_upper: float


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


def _held_wall(req_scope: str, ident: Identity) -> str:
    """The wall to file a matter under: required, and only one the caller holds — you
    cannot file into a scope you do not have."""
    wall = req_scope.strip()
    if not wall:
        raise HTTPException(status_code=400, detail="a scope (wall) is required")
    if wall not in ident.scopes:
        raise HTTPException(status_code=403, detail="you do not hold that scope")
    return wall


def _llm_judge() -> Judge | None:
    """The LLM tier, configured from the environment (provider-agnostic). None when no
    model is configured — then the cascade is the deterministic filter alone and the
    system stays fully offline. LLM_BASE_URL / LLM_MODEL default to Mistral (EU-hosted);
    LLM_API_KEY (or MISTRAL_API_KEY) is the credential, read from the environment only
    and never stored in the repo. Point LLM_BASE_URL at an on-prem model to stay offline."""
    key = os.environ.get("LLM_API_KEY") or os.environ.get("MISTRAL_API_KEY")
    if not key:
        return None
    return LLMJudge(
        base_url=os.environ.get("LLM_BASE_URL", "https://api.mistral.ai/v1/chat/completions"),
        api_key=key,
        model=os.environ.get("LLM_MODEL", "mistral-small-latest"),
    )


def _judge() -> Judge:
    """The judgment cascade, composed at the edge: the deterministic criteria filter
    first, and — when a model is configured — the LLM only on the uncertain band it
    leaves. The core imports neither an LLM SDK nor these adapters (AD-27)."""
    criteria = CriteriaJudge()
    llm = _llm_judge()
    return CascadeJudge(criteria, llm) if llm is not None else criteria


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/login", response_model=IdentityOut)
def login(req: LoginRequest, response: Response) -> IdentityOut:
    """Exchange credentials for a signed session cookie. Fails closed (401) on a bad
    password or unknown user, at the same speed either way (no account enumeration)."""
    secret = _secret()
    store = _require_store()
    user = store.authenticate(req.tenant, req.email, req.password)
    if user is None:
        raise HTTPException(status_code=401, detail="identifiants invalides")
    token = sign_token(
        secret, {"user_id": user.id, "tenant": user.tenant, "actor": user.display_name},
        now=int(time.time()),
    )
    # HttpOnly so JS cannot read it; SameSite=Lax against CSRF. Secure should be True
    # behind HTTPS in production (set via a reverse proxy / env in deployment).
    response.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="lax", path="/")
    return IdentityOut(
        actor=user.display_name, tenant=user.tenant, scopes=sorted(store.scopes_for(user.id))
    )


@app.post("/api/logout")
def logout(response: Response) -> dict[str, str]:
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"status": "logged out"}


@app.get("/api/me", response_model=IdentityOut)
def me(ident: Identity = Depends(current_identity)) -> IdentityOut:
    return IdentityOut(actor=ident.actor, tenant=ident.tenant, scopes=sorted(ident.scopes))


@app.post("/api/ingest", response_model=IngestResponse)
def ingest(req: IngestRequest, ident: Identity = Depends(current_identity)) -> IngestResponse:
    wall = _held_wall(req.scope, ident)
    folder = Path(req.folder)
    if not folder.is_dir():
        raise HTTPException(status_code=400, detail=f"not a folder: {req.folder}")
    result = ingest_folder(
        folder, matter=req.matter, tenant=ident.tenant,
        extractor=FileExtractor(), custodian=req.custodian,
    )
    persisted = _persist(result, wall, ident.actor)
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
    scope: str = Form(...),
    files: list[UploadFile] = Form(...),
    ident: Identity = Depends(current_identity),
) -> IngestResponse:
    """The browser path: a lawyer drops files (or a folder) and sees the inventory.
    Uploaded files are written to a per-request temp directory — reconstructing the
    submitted folder tree from each file's relative path — then ingested through the
    same one path (FR-33). The temp dir is discarded; only the piece text (and
    failures) persist to the store."""
    wall = _held_wall(scope, ident)
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
        result = ingest_folder(root, matter=matter, tenant=ident.tenant, extractor=FileExtractor())
    persisted = _persist(result, wall, ident.actor)
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
def list_matters(ident: Identity = Depends(current_identity)) -> list[MatterOut]:
    """Every matter the caller may see — pre-filtered by their granted scope (the
    Chinese wall, AD-13/AD-14), resolved from the session, not the request."""
    store = _require_store()
    return [
        MatterOut(matter=m.matter, scope=m.scope, inventory=_inventory_out(m.inventory))
        for m in store.matters(ident.tenant, ident.scopes)
    ]


@app.get("/api/search", response_model=SearchResultsOut)
def search_corpus(
    q: str, limit: int = 100, ident: Identity = Depends(current_identity)
) -> SearchResultsOut:
    """Deterministic exhaustive search over the caller's scope (FR-13) — every piece
    whose stored text contains `q` (case-insensitive), scope-constrained (the wall
    pre-filters search too). `total` is honest even when the hits are capped."""
    store = _require_store()
    results = store.search(ident.tenant, ident.scopes, q, limit=max(1, min(limit, 500)))
    return SearchResultsOut(
        query=results.query,
        total=results.total,
        returned=len(results.hits),
        hits=[
            SearchHitOut(matter=h.matter, provenance=h.provenance, snippet=h.snippet)
            for h in results.hits
        ],
    )


@app.get("/api/matters/{matter}/audit", response_model=AuditTrailOut)
def read_audit(matter: str, ident: Identity = Depends(current_identity)) -> AuditTrailOut:
    """The audit trail for a matter — 403 if its scope is not held. `verified` is
    the tamper-evidence: the tenant's audit chain recomputes cleanly."""
    store = _require_store()
    try:
        trail = store.read_audit(matter, ident.tenant, ident.scopes)
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
def read_triage(matter: str, ident: Identity = Depends(current_identity)) -> TriageOut:
    """The deterministic triage for a matter — near-duplicate clustering, the cheap
    first tier of the judgment cascade (403 outside the scope). `submitted = distinct
    + duplicates`: nothing lost, copies collapsed to one piece to examine."""
    store = _require_store()
    try:
        summary = store.deduplicate(matter, ident.tenant, ident.scopes)
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


@app.post("/api/matters/{matter}/judge", response_model=JudgeResultOut)
def judge_matter(
    matter: str, req: JudgeRequest, ident: Identity = Depends(current_identity)
) -> JudgeResultOut:
    """Run the triage judge over the matter's distinct band, persist the reversible
    labels, and record the act on the audit trail under the session user (403 outside
    scope). The response names the judge that decided; a discard is never silent."""
    store = _require_store()
    judge = _judge()
    try:
        reps = store.representatives(matter, ident.tenant, ident.scopes)
        outcome = triage_pieces(reps, req.question, judge)
        store.save_labels(matter, ident.tenant, ident.scopes, outcome, judge.name, ident.actor)
    except ScopeDenied as exc:
        raise HTTPException(status_code=403, detail="outside your scope") from exc
    return JudgeResultOut(
        judged=outcome.judged, relevant=outcome.relevant,
        uncertain=outcome.uncertain, discarded=outcome.discarded, judge=judge.name,
    )


@app.get("/api/matters/{matter}/labels", response_model=LabelsOut)
def read_labels(matter: str, ident: Identity = Depends(current_identity)) -> LabelsOut:
    """The current triage labels for a matter — counts plus each piece with its
    rationale (403 outside scope)."""
    store = _require_store()
    try:
        summary = store.labels(matter, ident.tenant, ident.scopes)
    except ScopeDenied as exc:
        raise HTTPException(status_code=403, detail="outside your scope") from exc
    return LabelsOut(
        relevant=summary.relevant, uncertain=summary.uncertain,
        discarded=summary.discarded, judged=summary.judged,
        pieces=[
            LabelledPieceOut(provenance=p.provenance, label=p.label, rationale=p.rationale)
            for p in summary.pieces
        ],
    )


@app.get("/api/matters/{matter}/recall/sample", response_model=RecallSampleOut)
def recall_sample(
    matter: str, n: int = 30, ident: Identity = Depends(current_identity)
) -> RecallSampleOut:
    """Draw a random sample of the matter's discard pile to review (403 outside scope).
    A sound recall bound needs a random sample, so the server draws it."""
    store = _require_store()
    try:
        result = store.sample_discards(matter, ident.tenant, ident.scopes, max(1, min(n, 500)))
    except ScopeDenied as exc:
        raise HTTPException(status_code=403, detail="outside your scope") from exc
    return RecallSampleOut(
        population=result.population,
        sample=[
            SampledDiscardOut(piece_id=s.piece_id, provenance=s.provenance, excerpt=s.excerpt)
            for s in result.sample
        ],
    )


@app.post("/api/matters/{matter}/recall/review", response_model=RecallBoundOut)
def recall_review(
    matter: str, req: RecallReviewIn, ident: Identity = Depends(current_identity)
) -> RecallBoundOut:
    """Record a reviewed sample of the discard pile and return the recall bound: with
    confidence c, at most `count_upper` of the discards were wrongly discarded. The act
    is audited (403 outside scope; 400 if a reviewed piece is not discarded)."""
    store = _require_store()
    verdicts = {v.piece_id: v.relevant for v in req.verdicts}
    try:
        result = store.record_recall_review(
            matter, ident.tenant, ident.scopes, verdicts, ident.actor, confidence=req.confidence
        )
    except ScopeDenied as exc:
        raise HTTPException(status_code=403, detail="outside your scope") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RecallBoundOut(
        population=result.population, sample_size=result.sample_size,
        relevant_found=result.relevant_found, confidence=result.confidence,
        count_upper=result.count_upper, prevalence_upper=result.prevalence_upper,
    )


@app.get("/api/matters/{matter}/inventory", response_model=InventoryOut)
def read_inventory(matter: str, ident: Identity = Depends(current_identity)) -> InventoryOut:
    """The durable inventory for a matter — 403 if its scope is not held (fail
    closed, and the matter's existence is not disclosed)."""
    store = _require_store()
    try:
        inv = store.inventory(matter, ident.tenant, ident.scopes)
    except ScopeDenied as exc:
        raise HTTPException(status_code=403, detail="outside your scope") from exc
    return _inventory_out(inv)
