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
import shutil
import tempfile
import threading
import time
import unicodedata
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

import pyotp
from fastapi import Cookie, Depends, FastAPI, Form, HTTPException, Request, Response, UploadFile
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError

from apx.adapters.expansion.archives import ZipExpander
from apx.adapters.expansion.composite import CompositeExpander
from apx.adapters.expansion.mail import EmlExpander
from apx.adapters.extraction.files import FileExtractor
from apx.adapters.judge.criteria import CriteriaJudge
from apx.adapters.llm_openai_compat.judge import CascadeJudge, LLMJudge
from apx.adapters.ocr_tesseract.tesseract import TesseractExtractor, WithOcr
from apx.adapters.store_postgres.engine import make_session_factory
from apx.adapters.store_postgres.store import ScopeConflict, ScopeDenied, SqlStore
from apx.api.logging import install_secret_redaction
from apx.api.startup import startup_gate
from apx.core.app.ingest import IngestionResult, ingest_folder
from apx.core.app.triage import triage_pieces
from apx.core.domain import capacity
from apx.core.domain.config import ConfigError, default_of
from apx.core.domain.head_journal import open_journal
from apx.core.ports.extraction import Extractor
from apx.core.ports.judge import Judge
from apx.core.projection import project_all


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Fail closed on start-up unless BOTH encryption layers are in place (AD-31): the
    application key and the attested data volume. Raising here refuses the boot — no
    permissive default, no warning-and-continue. Runs on a real start (and under
    `with TestClient(app)`), never at import, so the module stays importable in collection.
    Also install log redaction (AD-47) so a configured secret can never reach a log line."""
    startup_gate()
    install_secret_redaction()
    store = _store()
    if store is not None:
        # AD-35: reconcile the live head against the journal at boot (a live head behind the journal
        # is a restore-truncation), then advance the journal to the current live head.
        store.reconcile_heads()
        store.record_current_heads()
    yield


app = FastAPI(title="APX", version="0.1.0", lifespan=_lifespan)

SESSION_COOKIE = "apx_session"

# ── hardening ──────────────────────────────────────────────────────────────────
_MAX_UPLOAD_BYTES = 500 * 1024 * 1024
_CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; connect-src 'self'; font-src 'self'; base-uri 'self'; "
    "form-action 'self'; frame-ancestors 'none'"
)


def _cookie_secure() -> bool:
    """Mark the session cookie Secure behind HTTPS (APX_COOKIE_SECURE=1 in the image)."""
    return os.environ.get("APX_COOKIE_SECURE", "").strip().lower() in ("1", "true", "yes")


def _trust_forwarded_for() -> bool:
    return os.environ.get("APX_TRUST_FORWARDED_FOR", "").strip().lower() in ("1", "true", "yes")


def _client_ip(request: Request) -> str:
    """The client IP for rate-limiting and the audit. Behind a trusted proxy
    (APX_TRUST_FORWARDED_FOR — set in the deployed image), use the RIGHTMOST
    X-Forwarded-For entry: the one the trusted proxy appended (the client as it saw it).
    The LEFTMOST is client-supplied and spoofable, so trusting it would let an attacker
    rotate the header to evade the per-IP lockout (AC5) and forge the audited IP. Without a
    trusted proxy, use the direct socket peer, which a client cannot forge."""
    if _trust_forwarded_for():
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


class _LoginRateLimiter:
    """Per-IP sliding window over FAILED login attempts — a success clears the counter,
    so legitimate users are never throttled, only brute force is. In-memory (single
    instance); a shared store would be the multi-instance step."""

    def __init__(self, limit: int, window_seconds: float) -> None:
        self._limit = limit
        self._window = window_seconds
        self._fails: dict[str, list[float]] = {}
        self._lock = threading.Lock()  # login runs in the threadpool — guard the shared dict

    def blocked(self, key: str) -> bool:
        now = time.time()
        with self._lock:
            recent = [t for t in self._fails.get(key, []) if now - t < self._window]
            self._fails[key] = recent
            return len(recent) >= self._limit

    def record_failure(self, key: str) -> None:
        with self._lock:
            self._fails.setdefault(key, []).append(time.time())

    def reset(self, key: str) -> None:
        with self._lock:
            self._fails.pop(key, None)


_login_limiter = _LoginRateLimiter(limit=10, window_seconds=300.0)


@app.middleware("http")
async def _security_headers(request: Request, call_next):  # noqa: ANN001, ANN201
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = _CSP
    if _cookie_secure():  # behind HTTPS
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response


@lru_cache(maxsize=1)
def _store() -> SqlStore | None:
    """The durable store, built from DATABASE_URL, wired to the head journal (AD-35) so every
    audited write records its chain head outside the restorable store. None when DATABASE_URL is
    unset — the stateless ingest computation still runs, but persistence, read-back and auth need
    it. The journal's presence is enforced at start-up (the gate); here it is opened best-effort."""
    try:
        journal = open_journal(dict(os.environ), required=False)
        return SqlStore(make_session_factory(), head_journal=journal)
    except RuntimeError:
        return None


def _require_store() -> SqlStore:
    store = _store()
    if store is None:
        raise HTTPException(status_code=503, detail="no database configured (set DATABASE_URL)")
    return store


def _int_env(name: str, default: int) -> int:
    """An int from the environment, or the default on absence or a malformed value (never a
    500 on a typo in a config value)."""
    try:
        return int(os.environ.get(name, "") or default)
    except ValueError:
        return default


def _session_ttls() -> tuple[timedelta, timedelta]:
    """The session's absolute and idle lifetimes — configuration-as-data (AD-15). Defaults:
    8h absolute, 30min idle."""
    return (
        timedelta(seconds=_int_env("APX_SESSION_ABSOLUTE_SECONDS", 8 * 3600)),
        timedelta(seconds=_int_env("APX_SESSION_IDLE_SECONDS", 30 * 60)),
    )


@dataclass
class Identity:
    user_id: str
    tenant: str
    actor: str            # the session user's display name — the audit actor
    scopes: set[str]      # resolved live from user_scope; never client-supplied
    is_admin: bool = False


def current_identity(apx_session: str | None = Cookie(default=None)) -> Identity:
    """Resolve the caller from their opaque session cookie, or 401. Authority is the
    server-side session row, not a self-verifying token (AD-15): the actor, admin flag and
    scopes are re-resolved LIVE from the user's rows, so a revocation takes effect on the
    next request and a signed-out or expired session is refused."""
    if not apx_session:
        raise HTTPException(status_code=401, detail="not authenticated")
    _, idle_ttl = _session_ttls()
    who = _require_store().resolve_session(apx_session, idle_ttl=idle_ttl)
    if who is None:
        raise HTTPException(status_code=401, detail="invalid or expired session")
    return Identity(
        user_id=who.user_id, tenant=who.tenant, actor=who.actor,
        scopes=who.scopes, is_admin=who.is_admin,
    )


def require_admin(ident: Identity = Depends(current_identity)) -> Identity:
    """Gate the cockpit: the caller must be an administrator (403 otherwise). The flag
    is already resolved on the identity, so this adds no query."""
    if not ident.is_admin:
        raise HTTPException(status_code=403, detail="réservé aux administrateurs")
    return ident


class LoginRequest(BaseModel):
    tenant: str
    email: str
    password: str
    totp: str | None = None  # the second factor, when the tenant requires MFA


class IdentityOut(BaseModel):
    actor: str
    tenant: str
    scopes: list[str]
    is_admin: bool = False


class AdminUserOut(BaseModel):
    id: str
    email: str
    display_name: str
    is_admin: bool
    scopes: list[str]


class CreateUserIn(BaseModel):
    email: str
    password: str
    display_name: str
    scopes: list[str] = []
    is_admin: bool = False


class ScopeIn(BaseModel):
    scope: str


class IngestRequest(BaseModel):
    folder: str
    matter: str
    scope: str  # which wall to file the matter under — must be one you hold
    custodian: str = "custodian-undeclared"
    case_theory: str | None = None  # optional (FR-37): the lawyer's own words, or skipped


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


def _persist(
    result: IngestionResult,
    scope: str,
    actor: str,
    *,
    matter: str,
    tenant: str,
    case_theory: str | None = None,
) -> bool:
    """Persist under the given Chinese-wall scope, if a database is configured.
    The ingestion is recorded in the audit trail, atomically, under `actor`. matter/tenant
    are passed explicitly so a folder of zero readable files still creates a durable matter
    at a 0/0 inventory (Story 2.1 AC5); an empty scope fails closed at the store (AC6)."""
    store = _store()
    if store is None:
        return False
    try:
        store.save(result, scope, actor, matter=matter, tenant=tenant, case_theory=case_theory)
    except ScopeConflict as exc:
        # a re-ingest may not move a matter's wall — that is the admin re-scope path (409)
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return True


def _extractor() -> Extractor:
    """The text extractor composed at the edge. With APX_OCR enabled (the Docker image
    sets it, where Tesseract is installed), scans and images fall back to OCR; the fast
    born-digital path is unchanged and never pays the OCR cost."""
    base = FileExtractor()
    if os.environ.get("APX_OCR", "").strip().lower() in ("1", "true", "yes"):
        return WithOcr(base, TesseractExtractor())
    return base


def _expander() -> CompositeExpander:
    """Container expansion composed at the edge: a .zip is unpacked and its members
    ingested individually; an email adds its attachments (its body is a piece too)."""
    return CompositeExpander([ZipExpander(), EmlExpander()])


def _held_wall(req_scope: str, ident: Identity) -> str:
    """The wall to file a matter under: required, and only one the caller holds — you
    cannot file into a scope you do not have. Lawyer-language details (EXPERIENCE.md voice)."""
    wall = req_scope.strip()
    if not wall:
        raise HTTPException(status_code=400, detail="un périmètre est requis")
    if wall not in ident.scopes:
        raise HTTPException(status_code=403, detail="vous ne détenez pas ce périmètre")
    return wall


def _is_blank(s: str) -> bool:
    """True if s carries no meaningful character — only whitespace and format/zero-width
    (Unicode categories Z* / C*). So a custodian of "​" or a non-breaking space is
    blank, never a silent pass of AC3's "never blank"."""
    return not any(unicodedata.category(ch)[0] not in ("Z", "C") for ch in s)


def _chat_url(base: str) -> str:
    """Normalise a base endpoint to the OpenAI-compatible chat-completions URL the judge posts."""
    base = base.rstrip("/")
    return base if base.endswith("/chat/completions") else base + "/chat/completions"


def _llm_judge(store: SqlStore, tenant: str) -> Judge | None:
    """The LLM tier (provider-agnostic, AD-27). None when no credential is configured — then the
    cascade is the deterministic filter alone and the system stays fully offline. The API **key**
    is a SECRET, read from the environment only (LLM_API_KEY/MISTRAL_API_KEY), never stored as
    config-as-data. The **endpoint** and **model** ARE configuration-as-data (AD-24): a tenant's
    non-default `model_endpoint`/`model_name` is honoured live; otherwise the deployment default
    (LLM_BASE_URL/LLM_MODEL env) applies, then the Mistral EU default. The `model_provider` key is
    config-as-data too, but the code never branches on it (AD-27: application code never knows
    which engine serves it) — it is recorded/displayed, not a switch."""
    key = os.environ.get("LLM_API_KEY") or os.environ.get("MISTRAL_API_KEY")
    if not key:
        return None
    endpoint = store.get_config(tenant, "model_endpoint")
    base_url = (
        _chat_url(str(endpoint)) if endpoint != default_of("model_endpoint")
        else os.environ.get("LLM_BASE_URL", "https://api.mistral.ai/v1/chat/completions"))
    model = store.get_config(tenant, "model_name")
    if model == default_of("model_name"):
        model = os.environ.get("LLM_MODEL", "mistral-small-latest")
    return LLMJudge(base_url=base_url, api_key=key, model=str(model))


def _judge(store: SqlStore, tenant: str) -> Judge:
    """The judgment cascade, composed at the edge: the deterministic criteria filter
    first, and — when a model is configured — the LLM only on the uncertain band it
    leaves, at the tenant's configured endpoint/model. The core imports neither an LLM
    SDK nor these adapters (AD-27)."""
    criteria = CriteriaJudge()
    llm = _llm_judge(store, tenant)
    return CascadeJudge(criteria, llm) if llm is not None else criteria


def _judge_workers() -> int:
    """How many judgments run concurrently (JUDGE_WORKERS, default 8). The LLM tier is
    network-bound, so concurrency — not CPU — is what makes a large band tractable."""
    try:
        return max(1, int(os.environ.get("JUDGE_WORKERS", "8")))
    except ValueError:
        return 8


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/login", response_model=IdentityOut)
def login(req: LoginRequest, request: Request, response: Response) -> IdentityOut:
    """Exchange credentials for an opaque server-side session (AD-15). Rate-limited per IP
    on failed attempts (429 once too many); fails closed (401) at the same speed whether or
    not the account exists (no enumeration)."""
    ip = _client_ip(request)
    if _login_limiter.blocked(ip):
        raise HTTPException(status_code=429, detail="trop de tentatives — réessayez plus tard")
    store = _require_store()
    user = store.authenticate(req.tenant, req.email, req.password)
    if user is None:
        # Durably audit the failure (FR-48), not only throttle in memory; audit the lockout
        # once, when this failure crosses the threshold.
        store.record_auth_event(
            req.tenant, "system:auth", "login_failed", f"email={req.email} ip={ip}")
        _login_limiter.record_failure(ip)
        if _login_limiter.blocked(ip):
            store.record_auth_event(req.tenant, "system:auth", "login_locked_out", f"ip={ip}")
        raise HTTPException(status_code=401, detail="identifiants invalides")
    # Password ok — demand the second factor when the tenant requires MFA (config-as-data).
    # FAIL CLOSED: an MFA-required tenant whose user is not enrolled cannot log in with a
    # password alone. Enrolment is out-of-band (set_mfa_secret) — [ASSUMPTION] carried.
    requires_mfa, secret = store.mfa_status(user.tenant, user.id)
    if requires_mfa:
        if not secret:  # not enrolled (or an empty secret) — refuse, never downgrade to 1FA
            store.record_auth_event(
                user.tenant, "system:auth", "login_mfa_unenrolled", f"user={user.id} ip={ip}")
            raise HTTPException(
                status_code=403, detail="MFA requis mais non configuré")
        if not req.totp or not pyotp.TOTP(secret).verify(req.totp, valid_window=1):
            store.record_auth_event(
                user.tenant, "system:auth", "login_mfa_failed", f"user={user.id} ip={ip}")
            _login_limiter.record_failure(ip)
            raise HTTPException(status_code=401, detail="code MFA invalide")
    _login_limiter.reset(ip)  # a success clears the counter — legitimate use is never throttled
    absolute_ttl, _ = _session_ttls()
    sid = store.create_session(user.id, user.tenant, absolute_ttl=absolute_ttl)
    # HttpOnly so JS cannot read it; SameSite=Lax against CSRF; Secure behind HTTPS. The
    # value is an opaque server-side session id, never a self-verifying token (AD-15).
    response.set_cookie(
        SESSION_COOKIE, sid, httponly=True, samesite="lax", secure=_cookie_secure(), path="/")
    is_admin, scopes = store.identity(user.id)
    return IdentityOut(
        actor=user.display_name, tenant=user.tenant, scopes=sorted(scopes), is_admin=is_admin
    )


@app.post("/api/logout")
def logout(response: Response, apx_session: str | None = Cookie(default=None)) -> dict[str, str]:
    if apx_session:
        _require_store().delete_session(apx_session)  # the id is not reusable afterwards
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"status": "logged out"}


@app.get("/api/me", response_model=IdentityOut)
def me(ident: Identity = Depends(current_identity)) -> IdentityOut:
    return IdentityOut(
        actor=ident.actor, tenant=ident.tenant, scopes=sorted(ident.scopes), is_admin=ident.is_admin
    )


class PasswordChangeIn(BaseModel):
    current_password: str
    new_password: str


@app.post("/api/me/password")
def change_password(
    req: PasswordChangeIn, ident: Identity = Depends(current_identity)
) -> dict[str, str]:
    """Change your own password: confirm the current one, then set the new (min 8).
    400 if the current password is wrong, 422 if the new one is too short."""
    store = _require_store()
    if len(req.new_password) < 8:
        raise HTTPException(
            status_code=422, detail="le mot de passe doit faire au moins 8 caractères"
        )
    if not store.verify_user_password(ident.user_id, req.current_password):
        raise HTTPException(status_code=400, detail="mot de passe actuel incorrect")
    store.set_password(ident.user_id, req.new_password)
    store.delete_user_sessions(ident.user_id)  # invalidate every live session (AD-15/AC3)
    return {"status": "changed"}


@app.get("/api/admin/users", response_model=list[AdminUserOut])
def admin_list_users(ident: Identity = Depends(require_admin)) -> list[AdminUserOut]:
    """Every user in the caller's tenant with their scopes (admin only)."""
    store = _require_store()
    return [
        AdminUserOut(id=u.id, email=u.email, display_name=u.display_name,
                     is_admin=u.is_admin, scopes=list(u.scopes))
        for u in store.list_users(ident.tenant)
    ]


@app.post("/api/admin/users", response_model=AdminUserOut)
def admin_create_user(req: CreateUserIn, ident: Identity = Depends(require_admin)) -> AdminUserOut:
    """Create a user in the caller's tenant (admin only). 400 if the email is taken."""
    store = _require_store()
    if len(req.password) < 8:
        raise HTTPException(
            status_code=422, detail="le mot de passe doit faire au moins 8 caractères")
    try:
        uid = store.create_user(ident.tenant, req.email, req.password, req.display_name,
                                set(req.scopes), is_admin=req.is_admin, actor=ident.actor)
    except IntegrityError as exc:
        raise HTTPException(
            status_code=400, detail="un utilisateur existe déjà pour ce courriel"
        ) from exc
    return AdminUserOut(id=uid, email=req.email.strip().lower(), display_name=req.display_name,
                        is_admin=req.is_admin, scopes=sorted(set(req.scopes)))


@app.post("/api/admin/users/{user_id}/grant")
def admin_grant(
    user_id: str, req: ScopeIn, ident: Identity = Depends(require_admin)
) -> dict[str, str]:
    """Grant a wall to a user in the caller's tenant (admin only)."""
    store = _require_store()
    scope = req.scope.strip()
    if not scope:
        raise HTTPException(status_code=400, detail="périmètre requis")
    try:
        store.grant_scope(ident.tenant, ident.actor, user_id, scope)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="utilisateur inconnu") from exc
    return {"status": "granted"}


@app.post("/api/admin/users/{user_id}/revoke")
def admin_revoke(
    user_id: str, req: ScopeIn, ident: Identity = Depends(require_admin)
) -> dict[str, str]:
    """Revoke a wall from a user in the caller's tenant (admin only) — audited."""
    store = _require_store()
    try:
        store.revoke_scope(ident.tenant, ident.actor, user_id, req.scope.strip())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="utilisateur inconnu") from exc
    return {"status": "revoked"}


@app.post("/api/admin/matters/{matter}/rescope")
def admin_rescope(
    matter: str, req: ScopeIn, ident: Identity = Depends(require_admin)
) -> dict[str, str]:
    """Move a matter's wall to a new scope (admin only) — one audited op with before->after;
    takes effect at the next query (AD-13). 404 unknown matter, 400 a no-op."""
    store = _require_store()
    new_scope = req.scope.strip()
    if not new_scope:
        raise HTTPException(status_code=400, detail="périmètre requis")
    try:
        store.rescope_matter(ident.tenant, ident.actor, matter, new_scope)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "rescoped"}


class AdminFlagIn(BaseModel):
    is_admin: bool


@app.post("/api/admin/users/{user_id}/admin")
def admin_set_admin(
    user_id: str, req: AdminFlagIn, ident: Identity = Depends(require_admin)
) -> dict[str, str]:
    """Grant or revoke the administrative authority for a user (admin only) — audited and
    reversible. The administrative grant is itself granted by this same privileged path (AC2)."""
    store = _require_store()
    try:
        store.set_user_admin(ident.tenant, ident.actor, user_id, req.is_admin)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="utilisateur inconnu") from exc
    return {"status": "updated"}


# ── the configuration surface (AD-25): one audited surface for every config-as-data value ──
class ConfigItemOut(BaseModel):
    key: str
    value: Any
    default: Any
    governs: str


class ConfigSetIn(BaseModel):
    value: Any  # validated against the declared schema in the store, not here


class ConfigChangeOut(BaseModel):
    key: str
    before: Any
    after: Any
    changed: bool


class ConfigProvenanceOut(BaseModel):
    key: str
    value: Any
    audited: bool


@app.get("/api/admin/config", response_model=list[ConfigItemOut])
def admin_get_config(ident: Identity = Depends(require_admin)) -> list[ConfigItemOut]:
    """Every configuration-as-data value for the caller's tenant — current value, default and
    the guarantee each key governs (admin only; tenant from the session, never cross-tenant)."""
    store = _require_store()
    return [
        ConfigItemOut(key=c.key, value=c.value, default=c.default, governs=c.governs)
        for c in store.get_all_config(ident.tenant)
    ]


@app.put("/api/admin/config/{key}", response_model=ConfigChangeOut)
def admin_set_config(
    key: str, req: ConfigSetIn, ident: Identity = Depends(require_admin)
) -> ConfigChangeOut:
    """Set one configuration value for the caller's tenant — validated against the schema and
    audited with before/after (admin only). 422 on an unknown key or a wrong-typed value; a
    re-set to the identical value is accepted as a no-op (`changed=false`)."""
    store = _require_store()
    try:
        change = store.set_config(ident.tenant, ident.actor, key, req.value)
    except ConfigError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ConfigChangeOut(
        key=change.key, before=change.before, after=change.after, changed=change.changed)


@app.get("/api/admin/config/provenance", response_model=list[ConfigProvenanceOut])
def admin_config_provenance(
    ident: Identity = Depends(require_admin)
) -> list[ConfigProvenanceOut]:
    """The provenance of every stored configuration value (admin only): whether it is traceable
    to an audited change through this surface. An `audited=false` row was written by a direct DB
    edit that bypassed the surface (AD-25) — the detectability the guarantee promises."""
    store = _require_store()
    return [
        ConfigProvenanceOut(key=p.key, value=p.value, audited=p.audited)
        for p in store.config_provenance(ident.tenant)
    ]


# ── the content-free projection (AD-26): information ABOUT a tenant's data, never the data ──
class ProjectionOut(BaseModel):
    projector: str
    kinds: list[str]
    values: dict[str, Any]


@app.get("/api/admin/diagnostics", response_model=list[ProjectionOut])
def admin_diagnostics(ident: Identity = Depends(require_admin)) -> list[ProjectionOut]:
    """The content-free projection of the caller's tenant (admin only, tenant from the session):
    counts, an error-class histogram and version identifiers — provably no tenant content
    (AD-26/FR-31). This is the projection registry's first consumer; the full client-pushed
    diagnostic export (packaging, the push act as a named egress) is story 6.2. Every value here
    comes from `project_all` — the endpoint never fabricates a projection (sealed-type check)."""
    store = _require_store()
    snapshot = store.projection_snapshot(ident.tenant)
    return [
        ProjectionOut(projector=p.projector, kinds=list(p.kinds), values=dict(p.values))
        for p in project_all(snapshot)
    ]


# ── backup / restore / disaster recovery status (AD-32/AD-35) ──
class BackupStatusOut(BaseModel):
    last_success_at: str | None
    overdue: bool
    interval_hours: int


class TruncationStatusOut(BaseModel):
    active: bool
    journal_seq: int
    live_seq: int
    detected_at: str | None
    cleared_at: str | None


class FootprintOut(BaseModel):
    piece_count: int
    total_bytes: int
    human: str


class DrStatusOut(BaseModel):
    backup: BackupStatusOut
    truncation: TruncationStatusOut
    design_target_footprint: FootprintOut
    journal_degraded: bool  # the head journal (AD-35) could not be written — a monitored alarm


@app.get("/api/admin/dr", response_model=DrStatusOut)
def admin_dr_status(ident: Identity = Depends(require_admin)) -> DrStatusOut:
    """The tenant's disaster-recovery status (admin only): whether a backup is overdue (AD-32),
    whether a restore-truncation is active and un-acknowledged (AD-35), the stated storage
    footprint at the design target (AD-32), and whether the head journal is degraded (a head write
    failed — a later truncation to that point could go undetected). The worklist/home-screen
    rendering is the front-end."""
    store = _require_store()
    interval = int(store.get_config(ident.tenant, "backup_interval_hours"))
    bs = store.backup_status(ident.tenant, interval)
    ts = store.truncation_status(ident.tenant)
    fp = capacity.design_target_footprint()
    return DrStatusOut(
        backup=BackupStatusOut(
            last_success_at=bs.last_success_at, overdue=bs.overdue,
            interval_hours=bs.interval_hours),
        truncation=TruncationStatusOut(
            active=ts.active, journal_seq=ts.journal_seq, live_seq=ts.live_seq,
            detected_at=ts.detected_at, cleared_at=ts.cleared_at),
        design_target_footprint=FootprintOut(
            piece_count=fp.piece_count, total_bytes=fp.total_bytes, human=fp.human),
        journal_degraded=store.journal_degraded)


class TruncationOverrideIn(BaseModel):
    reason: str


@app.post("/api/admin/dr/truncation/clear")
def admin_clear_truncation(
    req: TruncationOverrideIn, ident: Identity = Depends(require_admin)
) -> dict[str, str]:
    """Acknowledge (override) an active restore-truncation with a reason (admin only, AD-35/AD-25).
    A truncation is never repaired — it is cleared only by this recorded, audited override. 400 if
    the reason is empty or there is no active truncation."""
    store = _require_store()
    try:
        store.clear_truncation(ident.tenant, ident.actor, req.reason)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "cleared"}


def _data_volume_path() -> str:
    """The path whose free space the capacity pre-flight measures: the DATA volume, NOT the API
    host's temp dir (which may be a small tmpfs unrelated to where pieces land). ``APX_DATA_PATH``
    names it explicitly (the deployed image points it at the mounted data volume); else, for a
    SQLite ``DATABASE_URL``, the directory holding the DB file; else ``/`` — a conservative
    whole-root fallback. A remote Postgres exposes no local path to stat, so the operator sets
    ``APX_DATA_PATH`` to the volume the database actually lives on."""
    explicit = os.environ.get("APX_DATA_PATH", "").strip()
    if explicit:
        return explicit
    url = os.environ.get("DATABASE_URL", "").strip()
    prefix = "sqlite:///"
    if url.startswith(prefix):
        db_path = url[len(prefix):]
        if db_path and db_path != ":memory:":
            parent = Path(db_path).resolve().parent
            if parent.is_dir():
                return str(parent)
    return "/"


def _capacity_preflight(projected_pieces: int) -> None:
    """Refuse an import projected not to fit the free space on the DATA volume, at submission, not
    at 70 % (AD-32). Measures ``_data_volume_path`` — where pieces actually land — never the API
    host's temp dir, so the refusal reflects the disk that will fill."""
    free = shutil.disk_usage(_data_volume_path()).free
    verdict = capacity.fits(free, projected_pieces)
    if not verdict.fits:
        raise HTTPException(status_code=507, detail=verdict.reason)  # 507 Insufficient Storage


@app.post("/api/ingest", response_model=IngestResponse)
def ingest(req: IngestRequest, ident: Identity = Depends(current_identity)) -> IngestResponse:
    wall = _held_wall(req.scope, ident)
    custodian = req.custodian.strip()
    if _is_blank(custodian):  # the custodian is mandatory on every ingest path, not just upload
        raise HTTPException(
            status_code=400,
            detail="un détenteur est requis (« détenteur inconnu » si vraiment inconnu)",
        )
    folder = Path(req.folder)
    if not folder.is_dir():
        raise HTTPException(status_code=400, detail=f"not a folder: {req.folder}")
    _capacity_preflight(sum(1 for p in folder.rglob("*") if p.is_file()))  # refuse if it won't fit
    result = ingest_folder(
        folder, matter=req.matter, tenant=ident.tenant,
        extractor=_extractor(), custodian=custodian, expander=_expander(),
    )
    persisted = _persist(
        result, wall, ident.actor,
        matter=req.matter, tenant=ident.tenant,
        case_theory=(req.case_theory or "").strip() or None,
    )
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
    request: Request,
    matter: str = Form(...),
    scope: str = Form(...),
    custodian: str = Form(""),
    case_theory: str | None = Form(None),
    files: list[UploadFile] | None = Form(None),
    ident: Identity = Depends(current_identity),
) -> IngestResponse:
    """The browser path (the onboarding gesture, Story 2.1): a lawyer drops a folder and
    names the matter, its wall and the custodian (mandatory) — the case theory is the one
    optional field. Uploaded files are written to a per-request temp directory,
    reconstructing the submitted folder tree from each file's relative path, then ingested
    through the one path (FR-33). The temp dir is discarded; only the piece text (and
    failures) persist. A folder of zero readable files is a completed 0/0 matter, not an
    error (AC5); an empty custodian (AC3) or scope (AC6) fails the job loudly."""
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="dépôt trop volumineux")
    wall = _held_wall(scope, ident)
    custodian = custodian.strip()
    if _is_blank(custodian):
        raise HTTPException(
            status_code=400,
            detail="un détenteur est requis (« détenteur inconnu » si vraiment inconnu)",
        )
    theory = (case_theory or "").strip() or None
    with tempfile.TemporaryDirectory(prefix="apx-upload-") as tmp:
        root = Path(tmp)
        root_resolved = root.resolve()
        for f in files or []:
            # The SPA sends the folder-relative path as the filename; rebuild the tree.
            rel = Path(f.filename or "unnamed").as_posix().lstrip("/")
            dest = root / rel
            if not dest.resolve().is_relative_to(root_resolved):
                # A crafted "../" filename must never write outside the upload sandbox.
                raise HTTPException(status_code=400, detail="chemin de fichier invalide")
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(await f.read())
        result = ingest_folder(
            root, matter=matter, tenant=ident.tenant,
            extractor=_extractor(), custodian=custodian, expander=_expander(),
        )
    persisted = _persist(
        result, wall, ident.actor,
        matter=matter, tenant=ident.tenant, case_theory=theory,
    )
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
    judge = _judge(store, ident.tenant)  # endpoint/model are the tenant's config-as-data (AD-24)
    try:
        reps = store.representatives(matter, ident.tenant, ident.scopes)
        outcome = triage_pieces(reps, req.question, judge, workers=_judge_workers())
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


# One artifact serves both: the API routes above (/api/*, matched first) and the built
# SPA (everything else). Mounted only when a build is present, so tests and API-only
# runs are unaffected. APX_WEB_DIST overrides the location (the Docker image sets it).
_web_dist = Path(
    os.environ.get("APX_WEB_DIST", str(Path(__file__).resolve().parent.parent / "web" / "dist"))
)
if _web_dist.is_dir():
    app.mount("/", StaticFiles(directory=str(_web_dist), html=True), name="web")
