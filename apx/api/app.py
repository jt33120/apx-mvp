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

import dataclasses
import html
import os
import shutil
import threading
import time
import unicodedata
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import quote
from uuid import uuid4

import pyotp
from fastapi import Cookie, Depends, FastAPI, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError

from apx.adapters.embedder_bgem3.bgem3 import Bgem3Embedder
from apx.adapters.expansion.archives import SevenZipExpander, ZipExpander
from apx.adapters.expansion.composite import CompositeExpander
from apx.adapters.expansion.mail import EmlExpander, MboxExpander
from apx.adapters.expansion.pdf import PdfPortfolioExpander
from apx.adapters.extraction.composite import CompositeExtractor
from apx.adapters.extraction.files import FileExtractor
from apx.adapters.extraction.msg import MsgExpander, MsgExtractor
from apx.adapters.judge.criteria import CriteriaJudge
from apx.adapters.llm_openai_compat.judge import CascadeJudge, LLMJudge
from apx.adapters.ocr_tesseract.tesseract import TesseractExtractor, WithOcr
from apx.adapters.originals_fs import FilesystemOriginalStore
from apx.adapters.render_html import CompositePieceRenderer, HtmlPieceRenderer, MsgRenderer
from apx.adapters.render_image import Pdf2ImageRasterizer
from apx.adapters.store_postgres.admission import admit
from apx.adapters.store_postgres.engine import make_session_factory
from apx.adapters.store_postgres.queue import enqueue_import
from apx.adapters.store_postgres.store import (
    ScopeConflict,
    ScopeDenied,
    SqlStore,
    StaleLabel,
)
from apx.api.logging import install_secret_redaction
from apx.api.startup import startup_gate
from apx.core.app.ingest import IngestionResult, ingest_folder
from apx.core.app.label import assign_taxonomy_label, revert_taxonomy_label
from apx.core.app.read.deterministic import MovingPopulation, search_exhaustive
from apx.core.app.read.drawer import read_drawer
from apx.core.app.read.freshness import BoundReading, read_bound, read_freshness, read_worklist
from apx.core.app.read.piece import open_piece
from apx.core.app.read.render import render_piece
from apx.core.app.read.sampling import SamplingRunReading, read_sampling_run, read_sampling_runs
from apx.core.app.read.scan import read_scan_page
from apx.core.app.read.semantic import search_semantic
from apx.core.app.read.triage_table import (
    read_matter_change_log,
    read_piece_change_log,
    read_triage_table,
)
from apx.core.app.register_override import (
    override_register_entry as core_override_register_entry,
)
from apx.core.app.sampling import (
    abandon_sampling_run,
    complete_sampling_run,
    record_sampling_verdict,
    size_for_target_bound,
    start_sampling_run,
)
from apx.core.app.triage import triage_pieces
from apx.core.domain import audit as AUDIT
from apx.core.domain import capacity
from apx.core.domain.chunking import resolution_failure_fr
from apx.core.domain.confidence import estimator_is_proven
from apx.core.domain.config import (
    DEFAULT_EXCLUSION_LIST,
    ConfigError,
    ExpansionBounds,
    default_of,
    expansion_bounds,
)
from apx.core.domain.crypto import DecryptionError
from apx.core.domain.freshness import Freshness
from apx.core.domain.head_journal import open_journal
from apx.core.domain.inventory import Inventory
from apx.core.domain.matter_record import Tier
from apx.core.domain.override import MissingOverrideReason, ground_label_fr
from apx.core.domain.sampling import KIND_BOUND, KIND_CENSUS
from apx.core.domain.taxonomy_label import OutOfTaxonomyLabel
from apx.core.domain.triage_table import ChangeLogEntry
from apx.core.ports.embedding import Embedder
from apx.core.ports.extraction import Extractor
from apx.core.ports.judge import Judge
from apx.core.ports.sampling import InvalidatedRun, RunAlreadyClosed
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
# The viewer (Story 3.5d) renders pièces IN THE BROWSER inside the tenant boundary. The additions to
# the base policy are the minimum that lets the offline PDF.js viewer run while the offline/tenant
# guarantee stays intact:
#   - worker-src 'self' blob: — the bundled, same-origin PDF.js worker (never a CDN).
#   - 'wasm-unsafe-eval' in script-src — PDF.js's WASM image decoders (WASM only, NOT JS eval;
#     'unsafe-eval' is still barred).
#   - blob: in img-src — a decrypted pièce from a same-origin in-memory blob (the inline image; the
#     old 'self' data: silently blocked it).
# connect-src stays 'self' — NO external origin is ever added, so no pièce byte leaves the cabinet.
_CSP = (
    "default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob:; connect-src 'self'; font-src 'self'; worker-src 'self' blob:; "
    "base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
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

#: Security events are system-initiated, so they name the component (FR-24) rather than a user —
#: a failed login has no user to attribute it to, and the one it names may be a stranger's guess.
_AUTH_ACTOR = AUDIT.system_actor("auth")


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


def _original_store() -> FilesystemOriginalStore:
    """The retained-original store (Story 3.5a) for the SYNCHRONOUS ingest path — so a pièce
    ingested via POST /api/ingest gets its original kept at rest exactly as the worker's upload path
    does (AC1: every pièce, any format). Built from the data volume + the encryption key (AD-31)."""
    return FilesystemOriginalStore.from_env()


@lru_cache(maxsize=1)
def _piece_renderer() -> CompositePieceRenderer:
    """The server-side renderer chain (Story 3.5c-2/3.5c-3) — stateless, built once. `.docx`/`.xlsx`
    → sanitised HTML in-process (HtmlPieceRenderer); `.msg` → sanitised HTML via the GPL-isolated
    worker (MsgRenderer); any other format falls through to the original. A composition-root
    singleton, like `_embedder`/`_original_store`. All members render inside the tenant boundary."""
    return CompositePieceRenderer([HtmlPieceRenderer(), MsgRenderer()])


@lru_cache(maxsize=1)
def _page_rasterizer() -> Pdf2ImageRasterizer:
    """The scanned-PDF page rasteriser (Story 3.5c-4) — stateless, built once. Rasterises one page
    at a time at the OCR dpi (so the image aligns with the stored word boxes), on the box (poppler),
    inside the tenant boundary. A composition-root singleton, like `_piece_renderer`."""
    return Pdf2ImageRasterizer()


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


class RegisterEntryOut(BaseModel):
    """One failure-register entry (Story 2.6, FR-5). The visual/interaction UX is a later pass;
    this is the data contract the register screen will render."""

    id: str
    matter: str | None
    filename: str
    path: str
    custodian: str | None
    error_class: str
    cardinality: str            # one | unknown (AD-38)
    resolution_state: str       # open | resolved (never removed, AD-7)
    timestamp: str
    retryable: bool             # the retry action affordance (FR-5)


class RegisterOut(BaseModel):
    entries: list[RegisterEntryOut]


class DrawerExtractOut(BaseModel):
    """One retained extract as the drawer shows it (FR-11). An UNRESOLVED extract carries its
    enumerated cause and NO quoted text — the text is precisely what could not be confirmed."""

    chunk_id: str
    verified: bool
    cause: str | None = None
    cause_fr: str | None = None


class ProposedEntryOut(BaseModel):
    """The audit row an action WILL append. No timestamp and no sequence: neither exists yet, and a
    shown value that is not the one that will be written is a lie in the one place that cannot
    afford one."""

    action: str
    action_fr: str
    actor: str
    chain_scope: str
    chain_label_fr: str
    override_ground: str | None = None
    override_ground_fr: str | None = None
    reason_required: bool = False


class DrawerActionOut(BaseModel):
    action: str
    action_fr: str
    reversal_fr: str          # FR-26: every action names its own reversal
    proposed: ProposedEntryOut


class DrawerPendingActionOut(BaseModel):
    label_fr: str
    story: str
    disabled_reason_fr: str


class DrawerOut(BaseModel):
    """The four bands (FR-26). `justification` is null when the tool recorded none for this pièce —
    which the surface states as itself, never as an empty band."""

    piece_id: str
    matter: str
    ranking_version_no: int | None = None
    sentence: str | None = None
    confidence: float | None = None
    confidence_signals: list[str] = []
    source_language: str | None = None
    rejected: bool = False
    is_unverified: bool = False
    unresolved_extracts: int = 0
    extracts: list[DrawerExtractOut] = []
    actions: list[DrawerActionOut] = []
    pending_actions: list[DrawerPendingActionOut] = []


class MatterRecordOut(BaseModel):
    """The *matter* record as a document (FR-26). The tier decided what is here: a numbers-only
    document was BUILT without the client content, not built and then stripped."""

    cover: dict
    denominator: list[dict]
    case_theory: list[dict]
    line_history: list[dict]
    pins: list[dict]
    sampling_runs: list[dict]
    overrides: list[dict]
    overrides_total: int          # over the WHOLE record, never the length of the list above
    modified_values: int
    pending: list[dict]


class RegisterOverrideIn(BaseModel):
    """The one thing an *override* costs (FR-25). No default and no `| None`: a request body that
    omits the field is a 422 at the edge, before the act is even attempted."""

    reason: str


class RegisterOverrideOut(BaseModel):
    entry_id: str
    resolution_state: str


class InventoryOut(BaseModel):
    """The permanent *denominator* (AD-38): the seven disjoint named counts, the words for
    unknown-cardinality containers (never a number folded into a total), and the consistency flag
    (FR-6). ``submitted_pieces == in_corpus + open_register_entries +
    overridden_register_entries`` over known pièces; noise and retired are their own lines, outside
    the identity."""

    submitted_pieces: int
    in_corpus: int
    open_register_entries: int
    # Story 5.6 (FR-25): documents the firm decided to live without — never in the corpus, no
    # longer open. Defaulted so an older client that does not read it still parses the record.
    overridden_register_entries: int = 0
    excluded_as_noise: int
    retired: int
    unknown_cardinality_entries: int
    unknown_cardinality_phrase: str
    consistent: bool


class IngestResponse(BaseModel):
    matter: str
    inventory: InventoryOut
    failure_list: list[FailureOut]
    exclusion_list: list[str]
    persisted: bool  # transparent: whether the result was written to the durable store


class ImportStartedOut(BaseModel):
    """The handle returned the instant an import is enqueued (Story 2.2) — the request does no
    work (AD-6). Poll ``/api/imports/{job_id}`` for progress."""

    job_id: str
    matter: str
    state: str


class ImportProgressOut(BaseModel):
    """The processed-against-submitted figure, read from the application-owned ledger (AD-17)."""

    job_id: str
    matter: str
    state: str
    submitted: int | None
    processed: int
    committed: int
    quarantined: int
    pending: int
    provisional: bool


class AuditEntryOut(BaseModel):
    seq: int
    actor: str
    action: str
    detail: str
    timestamp: str
    # Which chain this entry is counted on — the matter, or "" for the tenant chain (AD-43).
    # Named on the entry rather than inferred, so a reader can tell an act that belongs to no
    # matter from one whose matter went missing (FR-24 as amended).
    chain_scope: str
    chain_label_fr: str
    # FR-25 (Story 5.6): an *override* is countable and filterable SEPARATELY from an ordinary
    # modification, so the entry says which it is and — when it is one — on which of FR-25's three
    # grounds. Derived from the act catalogue at read time, never a stored flag.
    override: bool = False
    override_ground: str | None = None
    override_ground_fr: str | None = None


class ChainSliceOut(BaseModel):
    """What the reader can conclude about one chain of this matter's history."""

    chain_scope: str
    label_fr: str
    entries: int
    verified: bool
    # True only for the matter's OWN chain: a reader holding just these entries and the anchor
    # recomputes every link. The pre-5.5 slice on the tenant chain is verified here by
    # recomputing the whole tenant chain — which the holder of a scoped export cannot do.
    verifiable_in_isolation: bool
    broken_at: int | None = None


class AuditTrailOut(BaseModel):
    entries: list[AuditEntryOut]
    verified: bool
    slices: list[ChainSliceOut] = []
    # Counted over the WHOLE trail, never over the filtered list (FR-25).
    overrides: int = 0
    entries_total: int = 0


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


# ── Story 3.4: the two engines each SERIALISE their truth status (FR-15) — never combined. ──
class SemanticResultOut(BaseModel):
    piece_id: str
    chunk_id: str            # the openable handle (resolved to the passage on demand — Story 3.5)
    similarity: float


class SuggestiveOut(BaseModel):
    """A semantic (SUGGESTIVE) result set, on the wire. It carries its truth status and a wording
    that can never read as completeness; it has NO total/denominator (an exhaustive-only idea)."""

    truth_status: str        # the constant "suggestive" (Story 3.1) — serialised, never dropped
    query: str
    k: int
    similarity_threshold: float
    wording: str             # "top N of the corpus by similarity" — never a completeness total
    results: list[SemanticResultOut]


class DenominatorOut(BaseModel):
    """The AD-38 seven-field scoped denominator, on the wire. ``unknown_cardinality_entries`` is a
    SUBSET of ``open_register_entries``, rendered in words by the surface, never summed."""

    submitted_pieces: int
    in_corpus: int
    open_register_entries: int
    overridden_register_entries: int = 0   # Story 5.6 (FR-25) — decided away, never in the corpus
    excluded_as_noise: int
    retired: int
    unknown_cardinality_entries: int


class RegisterHitOut(BaseModel):
    matter: str
    filename: str
    error_class: str


class DeterministicResultOut(BaseModel):
    matter: str
    piece_id: str
    snippet: str


class ExhaustiveOut(BaseModel):
    """A deterministic (EXHAUSTIVE) result set, on the wire (Story 3.2 / AD-20). It carries its
    truth status, its scoped ``denominator`` (AD-38), the OCR/quality shares and the register
    name-matches (searched separately, AD-21) — the four AD-42 qualifications, as data. No limit."""

    truth_status: str        # the constant "exhaustive" (Story 3.2) — serialised, never dropped
    query: str
    denominator: DenominatorOut
    ocr_share: float
    below_quality_share: float
    register_hits: list[RegisterHitOut]   # separate from `results` (AD-21), never counted within
    normalization: str
    results: list[DeterministicResultOut]



class MatterOut(BaseModel):
    matter: str
    scope: str
    inventory: InventoryOut


def _inventory_out(inv) -> InventoryOut:  # noqa: ANN001
    return InventoryOut(
        submitted_pieces=inv.submitted_pieces, in_corpus=inv.in_corpus,
        open_register_entries=inv.open_register_entries,
        overridden_register_entries=inv.overridden_register_entries,
        excluded_as_noise=inv.excluded_as_noise,
        retired=inv.retired, unknown_cardinality_entries=inv.unknown_cardinality_entries,
        unknown_cardinality_phrase=inv.unknown_cardinality_phrase(),
        consistent=inv.is_consistent(),
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
        # embed-before-admission (Story 2.8): an embedder failure lands the piece in the register,
        # never the corpus, never a chunk — the same seam the async worker uses.
        admit(store, _embedder(), result, scope=scope, actor=actor, matter=matter, tenant=tenant,
              audit=True, case_theory=case_theory)
    except ScopeConflict as exc:
        # a re-ingest may not move a matter's wall — that is the admin re-scope path (409)
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    # Story 4.1: a case theory stated at import is a versioned, audited act (FR-37) — the matter now
    # exists, so record it through the ONE owning use case. Idempotent: a re-ingest with an
    # unchanged theory adds no version; this never triggers a re-rank (ranking is a later act).
    if case_theory is not None:
        store.append_case_theory_version(
            tenant=tenant, matter=matter, actor=actor, text=case_theory)
    return True


_EMBEDDER: Embedder | None = None


def _embedder() -> Embedder:
    """The ONE embedder (AD-11), built once and cached for the process. A test replaces it at the
    port boundary (monkeypatching this function), never a stub in the runtime tree."""
    global _EMBEDDER
    if _EMBEDDER is None:
        _EMBEDDER = Bgem3Embedder()
    return _EMBEDDER


def _extractor() -> Extractor:
    """The text extractor composed at the edge: .msg routes to the out-of-process, GPL-isolated
    MsgExtractor, everything else to FileExtractor. With APX_OCR enabled (the Docker image sets
    it, where Tesseract is installed), scans and images fall back to OCR; the fast born-digital
    path is unchanged and never pays the OCR cost (AD-28)."""
    primary = CompositeExtractor([MsgExtractor(), FileExtractor()])
    if os.environ.get("APX_OCR", "").strip().lower() in ("1", "true", "yes"):
        return WithOcr(primary, TesseractExtractor())
    return primary


def _expander(bounds: ExpansionBounds) -> CompositeExpander:
    """Container expansion composed at the edge (same chain as the worker, Story 2.4): archives
    (.zip/.7z), mailbox (.mbox), email (.eml) + PDF portfolios, and .msg (nested) — each bounded
    by configuration. A container's members are ingested individually; an email's body is a piece
    too. Kept behaviour-identical with the worker's ``_build_expander``."""
    return CompositeExpander([
        ZipExpander(bounds), SevenZipExpander(bounds), MboxExpander(bounds),
        EmlExpander(bounds), PdfPortfolioExpander(bounds), MsgExpander(bounds)])


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
            req.tenant, _AUTH_ACTOR, AUDIT.ACT_LOGIN_FAILED, f"email={req.email} ip={ip}")
        _login_limiter.record_failure(ip)
        if _login_limiter.blocked(ip):
            store.record_auth_event(req.tenant, _AUTH_ACTOR, AUDIT.ACT_LOGIN_LOCKED_OUT, f"ip={ip}")
        raise HTTPException(status_code=401, detail="identifiants invalides")
    # Password ok — demand the second factor when the tenant requires MFA (config-as-data).
    # FAIL CLOSED: an MFA-required tenant whose user is not enrolled cannot log in with a
    # password alone. Enrolment is out-of-band (set_mfa_secret) — [ASSUMPTION] carried.
    requires_mfa, secret = store.mfa_status(user.tenant, user.id)
    if requires_mfa:
        if not secret:  # not enrolled (or an empty secret) — refuse, never downgrade to 1FA
            store.record_auth_event(
                user.tenant, _AUTH_ACTOR, AUDIT.ACT_LOGIN_MFA_UNENROLLED, f"user={user.id} ip={ip}")
            raise HTTPException(
                status_code=403, detail="MFA requis mais non configuré")
        if not req.totp or not pyotp.TOTP(secret).verify(req.totp, valid_window=1):
            store.record_auth_event(
                user.tenant, _AUTH_ACTOR, AUDIT.ACT_LOGIN_MFA_FAILED, f"user={user.id} ip={ip}")
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
    store = _store()
    bounds = (expansion_bounds(lambda k: store.get_config(ident.tenant, k))
              if store is not None else ExpansionBounds.defaults())
    noise_patterns = (store.get_config(ident.tenant, "exclusion_list")  # config-as-data (FR-6)
                      if store is not None else DEFAULT_EXCLUSION_LIST)
    # Retain each pièce's original at rest, exactly as the upload/worker path does (Story 3.5a) —
    # paired with persistence, so a pièce this endpoint stores is also renderable later (AC1).
    original_store = _original_store() if store is not None else None
    result = ingest_folder(
        folder, matter=req.matter, tenant=ident.tenant,
        extractor=_extractor(), custodian=custodian, expander=_expander(bounds), bounds=bounds,
        noise_patterns=noise_patterns, original_store=original_store,
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


@app.post("/api/ingest-upload", response_model=ImportStartedOut, status_code=202)
async def ingest_upload(
    request: Request,
    matter: str = Form(...),
    scope: str = Form(...),
    custodian: str = Form(""),
    case_theory: str | None = Form(None),
    files: list[UploadFile] | None = Form(None),
    ident: Identity = Depends(current_identity),
) -> ImportStartedOut:
    """The onboarding gesture (Story 2.1/2.2): validate and authorise, create the matter
    synchronously (so it is durable at once — a 0-file import is a 0/0 matter, AC5), spool the
    uploaded bytes to a DURABLE staging dir, enqueue a background job, and RETURN IMMEDIATELY
    (AD-6) — the request never does the ingest work. The lawyer keeps working while a worker
    processes the units resumably (FR-2); poll ``/api/imports/{job_id}`` for progress. Preserves
    the Story 2.1 guards: held-only scope (AC6 loud on empty), mandatory custodian (AC3), the
    ``../`` traversal guard, and the 1.6 ScopeConflict wall-change refusal (409)."""
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
    # Reject a crafted "../" filename up front, before any side effect (matter, spool).
    if any(".." in Path(f.filename or "").parts for f in files or []):
        raise HTTPException(status_code=400, detail="chemin de fichier invalide")
    store = _require_store()

    # FR-7: one open import job per matter — a re-submit while one is open returns the existing
    # job, never a second (idempotent submission, AD-6). Only when the caller can SEE the matter
    # (holds its wall); otherwise fall through so `save` fails closed via ScopeConflict (1.6) —
    # never leak an open job's handle across a Chinese wall.
    existing = store.open_import_job(ident.tenant, matter)
    if existing is not None and matter in {
        m.matter for m in store.matters(ident.tenant, ident.scopes)
    }:
        job = store.read_import_job(existing)
        return ImportStartedOut(
            job_id=existing, matter=matter, state=job.state if job else "running")

    # Create the matter now (fail-closed on an empty scope, refuse a wall change — 1.6), before
    # any bytes are spooled; no audit entry here (the worker writes ONE at completion).
    now = datetime.now(UTC)
    try:
        store.save(
            IngestionResult(), wall, ident.actor, matter=matter, tenant=ident.tenant,
            case_theory=theory, audit=False)
    except ScopeConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    # Story 4.1: the case theory stated at upload is versioned + audited NOW (FR-37 "writable at
    # import") — the matter exists (just created above), so version 1 is recorded through the ONE
    # owning use case before the bytes are spooled. Idempotent on a re-upload with the same theory.
    if theory is not None:
        store.append_case_theory_version(
            tenant=ident.tenant, matter=matter, actor=ident.actor, text=theory)

    # Spool the uploaded bytes to a durable staging dir keyed by the job id, so a restartable
    # worker can read them after the request returns (the request's temp dir would not survive).
    job_id = uuid4().hex
    spool = Path(_data_volume_path()) / "spool" / job_id
    spool.mkdir(parents=True, exist_ok=True)
    spool_resolved = spool.resolve()
    for f in files or []:
        rel = Path(f.filename or "unnamed").as_posix().lstrip("/")
        dest = spool / rel
        if not dest.resolve().is_relative_to(spool_resolved):
            shutil.rmtree(spool, ignore_errors=True)
            raise HTTPException(status_code=400, detail="chemin de fichier invalide")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(await f.read())

    try:
        store.create_import_job(
            job_id=job_id, tenant=ident.tenant, matter=matter, scope=wall, actor=ident.actor,
            custodian=custodian, case_theory=theory, spool_path=str(spool), owns_spool=True,
            now=now)
    except IntegrityError as exc:
        # A concurrent submit won the FR-7 race (the DB's one-open-job index) — return the existing
        # job and drop our spool, never a second job (closes the read-then-create TOCTOU).
        shutil.rmtree(spool, ignore_errors=True)
        existing = store.open_import_job(ident.tenant, matter)
        if existing is not None:
            job = store.read_import_job(existing)
            return ImportStartedOut(
                job_id=existing, matter=matter, state=job.state if job else "running")
        raise HTTPException(status_code=409, detail="un import est déjà en cours") from exc
    try:
        await enqueue_import(job_id)
    except Exception as exc:  # noqa: BLE001 — a failed enqueue must not wedge the matter's upload path
        store.delete_import_job(job_id)  # roll back the ledger row so a re-submit is not blocked
        shutil.rmtree(spool, ignore_errors=True)
        raise HTTPException(status_code=503, detail="file d'import indisponible") from exc
    return ImportStartedOut(job_id=job_id, matter=matter, state="enumerating")


@app.get("/api/imports/{job_id}", response_model=ImportProgressOut)
def import_status(job_id: str, ident: Identity = Depends(current_identity)) -> ImportProgressOut:
    """The processed-against-submitted figure the SPA polls (AD-17: read from the ledger, never
    from the queue). Scope-checked: a caller sees only a job for a matter within their wall."""
    store = _require_store()
    progress = store.import_progress(job_id)
    if progress is None or progress.tenant != ident.tenant or progress.matter not in {
        m.matter for m in store.matters(ident.tenant, ident.scopes)
    }:
        raise HTTPException(status_code=404, detail="import introuvable")
    return ImportProgressOut(
        job_id=progress.job_id, matter=progress.matter, state=progress.state,
        submitted=progress.submitted, processed=progress.processed, committed=progress.committed,
        quarantined=progress.quarantined, pending=progress.pending,
        provisional=progress.provisional)


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
    """A **bounded normalised PREVIEW** over the caller's scope (FR-13) — pieces whose stored text
    contains `q` (`fr-fold-v1`), scope-constrained. It is NOT a truth-status-carrying result set and
    it TRUNCATES at `limit` (`total` stays honest): a quick look, never a proof. For the two engines
    that declare their truth status, use `/api/search/suggestive` and `/api/search/exhaustive`."""
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


def _suggestive_payload(store: SqlStore, ident: Identity, q: str, k: int) -> SuggestiveOut:
    """Run the semantic (suggestive) engine and serialise it — the truth status and a wording that
    can never read as completeness. Composes the ONE embedder (AD-11) at the edge, like ingest."""
    rs = search_semantic(
        tenant=ident.tenant, scopes=ident.scopes, query=q, embedder=_embedder(),
        reader=store, k=max(1, min(k, 100)),
        config_get=lambda key: store.get_config(ident.tenant, key))
    return SuggestiveOut(
        truth_status=rs.truth_status.value, query=q, k=rs.k,
        similarity_threshold=rs.similarity_threshold, wording=rs.wording,
        results=[SemanticResultOut(piece_id=r.piece_id, chunk_id=r.chunk_id,
                                   similarity=r.similarity) for r in rs.results])


def _exhaustive_payload(store: SqlStore, ident: Identity, q: str) -> ExhaustiveOut:
    """Run the deterministic (exhaustive) engine and serialise it — the truth status + the scoped
    denominator (AD-38) + the four AD-42 qualifications. Refuses over a moving population (409)."""
    try:
        rs = search_exhaustive(tenant=ident.tenant, scopes=ident.scopes, query=q, reader=store)
    except MovingPopulation as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    d = rs.denominator
    return ExhaustiveOut(
        truth_status=rs.truth_status.value, query=q,
        denominator=DenominatorOut(
            submitted_pieces=d.submitted_pieces, in_corpus=d.in_corpus,
            open_register_entries=d.open_register_entries,
            overridden_register_entries=d.overridden_register_entries,
            excluded_as_noise=d.excluded_as_noise,
            retired=d.retired, unknown_cardinality_entries=d.unknown_cardinality_entries),
        ocr_share=rs.ocr_share, below_quality_share=rs.below_quality_share,
        register_hits=[RegisterHitOut(matter=h.matter, filename=h.filename,
                                      error_class=h.error_class) for h in rs.register_hits],
        normalization=rs.normalization,
        results=[DeterministicResultOut(matter=r.matter, piece_id=r.piece_id, snippet=r.snippet)
                 for r in rs.results])


def _inventory_of(d: DenominatorOut) -> Inventory:
    """The domain denominator behind the wire model — so a query audit records the seven-field
    record (AD-38), never a re-implemented number."""
    return Inventory(
        submitted_pieces=d.submitted_pieces, in_corpus=d.in_corpus,
        open_register_entries=d.open_register_entries,
        overridden_register_entries=d.overridden_register_entries,
        excluded_as_noise=d.excluded_as_noise,
        retired=d.retired, unknown_cardinality_entries=d.unknown_cardinality_entries)


def _exhaustive_header(out: ExhaustiveOut) -> str:
    """The truth-status FACE of an exhaustive export — the scoped denominator + the AD-42
    qualifications + the presence/absence claim, in the lawyer's language. Never a bare
    'introuvable'; never the FR-23 banned phrasing."""
    d = out.denominator
    # DeterministicResult is per-PIÈCE (matter, piece_id, snippet), so a pièce is the unit here.
    claim = (f"{len(out.results)} pièce(s) contenant « {out.query} » — ensemble complet"
             if out.results else f"Aucune occurrence de « {out.query} ».")
    quals = (f"Recherché dans tout l'indexé de ce périmètre "
             f"({d.in_corpus} sur {d.submitted_pieces}). "
             f"Le registre liste {d.open_register_entries} pièce(s) au registre")
    if d.unknown_cardinality_entries:
        quals += f", dont {d.unknown_cardinality_entries} au contenu inconnu"
    quals += f" ; {round(out.ocr_share * 100)} % du corpus recherché provient d'un OCR"
    if out.below_quality_share > 0:
        quals += f", {round(out.below_quality_share * 100)} % sous le seuil de qualité"
    return f"RECHERCHE EXHAUSTIVE — {claim} {quals}."


_SUGGESTIVE_HEADER = ("SUGGESTIONS — liste non exhaustive, classée par proximité ; "
                      "ne constitue pas une preuve d'absence.")

# A court-readable EXPORT is a self-contained, print-ready HTML document — no system needed to read
# it (FR-15). System fonts only (the offline constraint reaches the export too, AD-29).
_EXPORT_CSS = (
    "body{font-family:Georgia,'Times New Roman',serif;color:#0b1f3a;max-width:46rem;"
    "margin:2rem auto;padding:0 1.5rem;line-height:1.5}"
    ".stamp{font-family:system-ui,sans-serif;font-size:.7rem;letter-spacing:.1em;"
    "text-transform:uppercase;font-weight:700;padding:.45rem .9rem;border-radius:6px;"
    "display:inline-block}.exh{color:#2f6f4f;background:#e8f1eb}.sug{color:#5b6678;"
    "background:#efeae0}h1{font-size:1.25rem;margin:.8rem 0 .2rem}.meta{color:#6b7280;"
    "font-size:.85rem}table{border-collapse:collapse;width:100%;font-family:system-ui,"
    "sans-serif;font-size:.9rem;margin-top:.8rem}td,th{border-bottom:1px solid #e6e0d5;"
    "padding:.4rem .5rem;text-align:left;vertical-align:top}.num{font-variant-numeric:"
    "tabular-nums}.disc{margin-top:1rem;padding:.8rem 1rem;border:1px solid #e6e0d5;"
    "border-radius:8px;font-size:.92rem;background:#faf8f3}@media print{body{margin:0}}"
)


def _export_doc(title: str, body: str) -> str:
    return (f"<!doctype html><html lang=\"fr\"><head><meta charset=\"utf-8\">"
            f"<title>{html.escape(title)}</title><style>{_EXPORT_CSS}</style></head>"
            f"<body>{body}</body></html>")


def _exhaustive_export_html(out: ExhaustiveOut) -> str:
    d = out.denominator
    rows = "".join(
        f"<tr><td>{html.escape(r.piece_id)}</td><td>{html.escape(r.matter)}</td>"
        f"<td>{html.escape(r.snippet)}</td></tr>" for r in out.results)
    reg = "".join(
        f"<tr><td>{html.escape(h.filename)}</td><td>{html.escape(h.error_class)}</td></tr>"
        for h in out.register_hits)
    body = (
        f"<span class=\"stamp exh\">= Recherche exhaustive — preuve</span>"
        f"<h1>« {html.escape(out.query)} »</h1>"
        f"<div class=\"disc\">{html.escape(_exhaustive_header(out))}</div>"
        f"<table><thead><tr><th>Pièce</th><th>Dossier</th><th>Passage</th></tr></thead>"
        f"<tbody>{rows or '<tr><td colspan=3>Aucune occurrence.</td></tr>'}</tbody></table>"
        + (f"<h1>Correspondances au registre (hors ensemble recherché)</h1>"
           f"<table><tbody>{reg}</tbody></table>" if reg else "")
        + f"<p class=\"meta\">Périmètre recherché : {d.in_corpus} indexé sur "
          f"{d.submitted_pieces} — normalisation {html.escape(out.normalization)}.</p>")
    return _export_doc(f"Recherche exhaustive — {out.query}", body)


def _suggestive_export_html(out: SuggestiveOut) -> str:
    rows = "".join(
        f"<tr><td>{i + 1}</td><td>{html.escape(r.piece_id)}</td></tr>"
        for i, r in enumerate(out.results))
    body = (
        f"<span class=\"stamp sug\">≈ Suggestions — liste non exhaustive</span>"
        f"<h1>« {html.escape(out.query)} »</h1>"
        f"<div class=\"disc\">{html.escape(_SUGGESTIVE_HEADER)}</div>"
        f"<table><thead><tr><th>Rang</th><th>Pièce</th></tr></thead>"
        f"<tbody>{rows or '<tr><td colspan=2>Aucune suggestion.</td></tr>'}</tbody></table>"
        f"<p class=\"meta\">Les {len(out.results)} pièces les plus proches par similarité.</p>")
    return _export_doc(f"Suggestions — {out.query}", body)


@app.get("/api/search/suggestive", response_model=SuggestiveOut)
def search_suggestive(
    q: str, k: int = 20, ident: Identity = Depends(current_identity)
) -> SuggestiveOut:
    """The semantic SUGGESTIVE engine (FR-12/AD-20): the top-k by similarity, carrying its truth
    status and a wording that can never read as completeness. NOT a proof of absence. Audited."""
    store = _require_store()
    out = _suggestive_payload(store, ident, q, k)
    store.audit_query(ident.tenant, ident.actor, term=q, engine=out.truth_status,
                      scopes=ident.scopes)
    return out


@app.get("/api/search/exhaustive", response_model=ExhaustiveOut)
def search_exhaustive_api(
    q: str, ident: Identity = Depends(current_identity)
) -> ExhaustiveOut:
    """The deterministic EXHAUSTIVE engine (FR-13/AD-20): the complete match set within scope,
    carrying its truth status, the scoped denominator (AD-38) and the AD-42 qualifications. Refuses
    over a moving population (409 — never a partial proof). Audited with its denominator."""
    store = _require_store()
    out = _exhaustive_payload(store, ident, q)
    store.audit_query(ident.tenant, ident.actor, term=q, engine=out.truth_status,
                      scopes=ident.scopes, denominator=_inventory_of(out.denominator))
    return out


@app.get("/api/search/suggestive/export", response_class=HTMLResponse)
def export_suggestive(
    q: str, k: int = 20, ident: Identity = Depends(current_identity)
) -> HTMLResponse:
    """Export a suggestive set as a self-contained, print-ready HTML document — its head carries the
    non-completeness wording, so the distinction survives onto a court-readable page read WITHOUT
    the system (FR-15). One `export-search` audit entry."""
    store = _require_store()
    out = _suggestive_payload(store, ident, q, k)
    store.audit_query(ident.tenant, ident.actor, term=q, engine=out.truth_status,
                      scopes=ident.scopes, action=AUDIT.ACT_EXPORT_SEARCH)
    return HTMLResponse(_suggestive_export_html(out))


@app.get("/api/search/exhaustive/export", response_class=HTMLResponse)
def export_exhaustive(
    q: str, ident: Identity = Depends(current_identity)
) -> HTMLResponse:
    """Export an exhaustive set as a self-contained, print-ready HTML document — its head carries
    the scoped denominator + the four AD-42 qualifications + the presence/absence claim, defensible
    document read WITHOUT the system (FR-15/AD-42). One `export-search` audit entry with the
    denominator."""
    store = _require_store()
    out = _exhaustive_payload(store, ident, q)
    store.audit_query(ident.tenant, ident.actor, term=q, engine=out.truth_status,
                      scopes=ident.scopes, denominator=_inventory_of(out.denominator),
                      action=AUDIT.ACT_EXPORT_SEARCH)
    return HTMLResponse(_exhaustive_export_html(out))


# ── the pièce viewer read path (Story 3.5b) — scope pre-filter · audit-on-open · size bound ──
class PieceMetaOut(BaseModel):
    """The pièce viewer's metadata — enough to render or offer the original, never the content.
    Returned only for an in-scope pièce; out of scope is the SAME 404 as absent (FR-14/FR-44)."""

    piece_id: str
    matter: str
    filename: str
    media_kind: str
    ocr: bool
    byte_size: int | None
    renderable_inline: bool


_PIECE_ABSENT = "pièce introuvable"  # ONE message for out-of-scope AND absent — discloses nothing


def _render_bound() -> int:
    """The inline-render byte bound (config-as-data via env): a pièce larger than this is offered as
    the original / loaded progressively, never rendered inline to exhaustion (Story 3.5b/d)."""
    return _int_env("APX_PIECE_RENDER_MAX_BYTES", 25 * 1024 * 1024)


def _scan_bound() -> int:
    """The scanned-PDF page-render byte bound (config-as-data via env, Story 3.5c-4). Well above the
    inline bound: rasterising reads the whole file to produce ONE page, so a many-page scan renders
    page-by-page while a huge archive is offered as the original. Protects the server's memory."""
    return _int_env("APX_SCAN_RENDER_MAX_BYTES", 128 * 1024 * 1024)


def _scan_pixels_bound() -> int:
    """The per-page PIXEL bound (config-as-data via env, Story 3.5c-4). A tiny PDF can declare a
    giant page whose raster is GBs though its file is under the byte bound (a *pixel bomb*), so a
    page whose ``width × height`` (from the stored OCR layout) exceeds this is offered as the
    original before poppler is invoked. Default 100 Mpx — generous for real scans (A0 @ 200 dpi ≈
    64 Mpx),
    refusing the crafted large-format bombs (60×60 in @ 200 dpi ≈ 144 Mpx)."""
    return _int_env("APX_SCAN_MAX_PIXELS", 100_000_000)


def _content_disposition(name: str) -> str:
    """A safe RFC 6266 ``Content-Disposition`` that PRESERVES a non-ASCII (accented FR/LU) name via
    ``filename*``, with an ASCII fallback for old clients. Both legs are injection-safe: the ASCII
    leg strips control/quote/backslash chars; ``filename*`` percent-encodes everything dangerous (a
    CR/LF becomes %0D%0A — never a literal header break)."""
    printable = "".join(c for c in name if c.isprintable())
    ascii_fallback = printable.replace('"', "").replace("\\", "").encode(
        "ascii", "ignore").decode("ascii").strip() or "piece"
    utf8 = quote(printable, safe="") or "piece"
    return f"attachment; filename=\"{ascii_fallback}\"; filename*=UTF-8''{utf8}"


@app.get("/api/pieces/{piece_id}", response_model=PieceMetaOut)
def get_piece(piece_id: str, ident: Identity = Depends(current_identity)) -> PieceMetaOut:
    """The pièce viewer's metadata IF the caller holds its *matter*'s scope (the read pre-filter,
    AD-13/14). Out of scope OR absent → the SAME 404 (existence not disclosed). A peek — the audited
    read is the /original content access."""
    store = _require_store()
    view = open_piece(tenant=ident.tenant, scopes=ident.scopes, piece_id=piece_id, reader=store)
    if view is None:
        raise HTTPException(status_code=404, detail=_PIECE_ABSENT)
    size = _original_store().size(ident.tenant, view.content_hash)
    return PieceMetaOut(
        piece_id=view.piece_id, matter=view.matter, filename=view.filename,
        media_kind=view.media_kind, ocr=view.ocr, byte_size=size,
        renderable_inline=size is not None and size <= _render_bound())


@app.get("/api/pieces/{piece_id}/original")
def get_piece_original(piece_id: str, ident: Identity = Depends(current_identity)) -> Response:
    """Serve the retained ORIGINAL bytes IF in scope — decrypted within the tenant boundary (3.5a),
    as an ATTACHMENT with octet-stream + nosniff so an uploaded .html/.svg can never execute in the
    app origin (safe inline rendering is the 3.5c/d renderer's job). Opening the content is the
    AUDITED read (FR-45). Out of scope/absent → the same 404; a missing/unreadable blob → an honest
    409, never a 500."""
    store = _require_store()
    view = open_piece(tenant=ident.tenant, scopes=ident.scopes, piece_id=piece_id, reader=store)
    if view is None:
        raise HTTPException(status_code=404, detail=_PIECE_ABSENT)
    try:
        data = _original_store().open(ident.tenant, view.content_hash)
    except (FileNotFoundError, DecryptionError):
        raise HTTPException(
            status_code=409, detail="l'original de cette pièce n'est pas disponible") from None
    store.audit_piece_open(tenant=ident.tenant, matter=view.matter, actor=ident.actor,
                           piece_id=view.piece_id)
    return Response(
        content=data, media_type="application/octet-stream",
        headers={
            "Content-Disposition": _content_disposition(view.filename),
            "X-Content-Type-Options": "nosniff",
        })


class PieceRenderOut(BaseModel):
    """A server-side render of a pièce for the viewer (Story 3.5c-2). ``renderable`` is False when
    the pièce is in scope but the original should be offered instead (over the render bound, an
    unrenderable format, or an unavailable blob) — then ``reason`` carries the honest limit and the
    content fields are null. When True, ``html`` is **sanitised** markup safe for the SPA to embed
    (sandboxed); ``truncated`` says a render bound was hit. Out-of-scope/absent never reaches here —
    it is the same 404 as ``/original`` (existence not disclosed)."""

    piece_id: str
    renderable: bool
    format: str | None = None
    # `title` is UNTRUSTED text metadata (the pièce filename) — NOT sanitised; the SPA renders it as
    # a text node, never innerHTML (same contract as `filename`). Only `html` is embed-safe.
    title: str | None = None
    html: str | None = None      # sanitised markup, safe for the SPA to embed (sandboxed)
    truncated: bool = False
    reason: str | None = None


@app.get("/api/pieces/{piece_id}/render", response_model=PieceRenderOut)
def get_piece_render(
    piece_id: str, response: Response, ident: Identity = Depends(current_identity)
) -> PieceRenderOut:
    """Render an in-scope office/email pièce (`.docx`/`.xlsx` in-process, `.msg` via the isolated
    worker) to **sanitised inline HTML** in the tenant boundary (Story 3.5c-2/3.5c-3). Scope
    pre-filter first (AD-13/14): out-of-scope OR absent → the
    SAME 404 as `/original`. A served render is the AUDITED open (FR-45), one `open-piece` entry —
    reading the rendered content IS opening the pièce. Over the render bound, an unhandled format,
    or a missing/tampered blob → `renderable:false` + the honest reason (the client offers the
    original; the later `/original` fetch is then the audited read — no double audit here). No pièce
    byte leaves for a third-party service; the sanitised HTML rides a JSON envelope, never a live
    top-level HTML document. `Cache-Control: no-store` (AD-29: tenant data is never cached)."""
    store = _require_store()
    outcome = render_piece(
        tenant=ident.tenant, scopes=ident.scopes, piece_id=piece_id, reader=store,
        originals=_original_store(), renderer=_piece_renderer(), max_bytes=_render_bound())
    if outcome is None:
        raise HTTPException(status_code=404, detail=_PIECE_ABSENT)  # discloses nothing
    response.headers["Cache-Control"] = "no-store"
    if outcome.document is None:
        return PieceRenderOut(piece_id=piece_id, renderable=False, reason=outcome.reason)
    store.audit_piece_open(tenant=ident.tenant, matter=outcome.matter, actor=ident.actor,
                           piece_id=outcome.piece_id)
    doc = outcome.document
    return PieceRenderOut(
        piece_id=outcome.piece_id, renderable=True, format=doc.format, title=doc.title,
        html=doc.html, truncated=doc.truncated)


@app.get("/api/pieces/{piece_id}/page/{page}")
def get_piece_page(
    piece_id: str, page: int, ident: Identity = Depends(current_identity)
) -> Response:
    """Rasterise page `page` (0-indexed) of an in-scope scanned PDF to a PNG within the tenant
    boundary (Story 3.5c-4). Scope pre-filter first (AD-13/14): out-of-scope OR absent → 404
    (existence not disclosed). `/page` serves the document's READABLE content, so — like `/original`
    and `/render` — a served page is an AUDITED open (FR-45). It requires a stored OCR layer (a
    scan): a born-digital / no-layout PDF, an out-of-range or pixel-bomb page, over the scan byte
    bound, or a missing/tampered blob → 409 (in-scope but not served here — the client renders the
    original), never a 500 and never an unaudited read. `image/png` + nosniff + no-store (AD-29)."""
    store = _require_store()
    outcome = read_scan_page(
        tenant=ident.tenant, scopes=ident.scopes, piece_id=piece_id, page=page, reader=store,
        originals=_original_store(), rasterizer=_page_rasterizer(), max_bytes=_scan_bound(),
        max_pixels=_scan_pixels_bound())
    if outcome is None:
        raise HTTPException(status_code=404, detail=_PIECE_ABSENT)  # discloses nothing
    if outcome.png is None:
        raise HTTPException(status_code=409, detail=outcome.reason)  # in-scope — offer the original
    store.audit_piece_open(tenant=ident.tenant, matter=outcome.matter, actor=ident.actor,
                           piece_id=outcome.piece_id)  # serving readable content is an audited open
    return Response(
        content=outcome.png, media_type="image/png",
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


@app.get("/api/pieces/{piece_id}/layout")
def get_piece_layout(piece_id: str, ident: Identity = Depends(current_identity)) -> Response:
    """Serve the stored OCR layout (page dims + word boxes + confidence + dpi + page count) for an
    in-scope scanned pièce — the overlay coordinates the viewer draws over the page images (Story
    3.5c-1/c-4). Scope pre-filter first: out-of-scope, absent, OR no layout (a born-digital / no-OCR
    pièce) → the SAME non-disclosing 404; a tampered blob → 409. The stored, authenticated JSON is
    served as-is (no re-serialisation). The layout is overlay METADATA (word coordinates), not the
    readable page content, so it is NOT itself audited — the audited open is the served `/page`
    content (FR-45). `application/json` + nosniff + `Cache-Control: no-store` (AD-29)."""
    view = open_piece(tenant=ident.tenant, scopes=ident.scopes, piece_id=piece_id,
                      reader=_require_store())
    if view is None:
        raise HTTPException(status_code=404, detail=_PIECE_ABSENT)
    try:
        layout = _original_store().open(ident.tenant, view.content_hash, kind="ocr-layout")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=_PIECE_ABSENT) from None  # no OCR layout
    except DecryptionError:
        raise HTTPException(
            status_code=409, detail="la couche OCR de cette pièce n'est pas disponible") from None
    return Response(
        content=layout, media_type="application/json",
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


@app.get("/api/matters/{matter}/audit", response_model=AuditTrailOut)
def read_audit(
    matter: str, overrides_only: bool = False, ident: Identity = Depends(current_identity),
) -> AuditTrailOut:
    """The audit trail for a matter — 403 if its scope is not held.

    A matter's history spans up to two chains (AD-43): its own, and the tenant chain, which holds
    both the matterless acts and everything written before Story 5.5. `slices` reports each one
    separately, because only the matter's own chain is verifiable by a reader holding nothing but
    the export — the other's links run through entries outside their scope. One boolean over both
    would claim a property of bytes the reader does not hold.

    `overrides_only` filters the entries to the *overrides* (FR-25). `overrides` and
    `entries_total` are always counted over the whole trail, so the filtered read reports how much
    of the record it is not showing."""
    store = _require_store()
    try:
        trail = store.read_audit(
            matter, ident.tenant, ident.scopes, overrides_only=overrides_only)
    except ScopeDenied as exc:
        raise HTTPException(status_code=403, detail="outside your scope") from exc
    return AuditTrailOut(
        entries=[
            AuditEntryOut(seq=e.seq, actor=e.actor, action=e.action, detail=e.detail,
                          timestamp=e.timestamp, chain_scope=e.chain_scope,
                          chain_label_fr=AUDIT.chain_label_fr(e.chain_scope),
                          override=e.override, override_ground=e.override_ground,
                          override_ground_fr=(ground_label_fr(e.override_ground)
                                              if e.override_ground else None))
            for e in trail.entries
        ],
        verified=trail.verified,
        overrides=trail.overrides,
        entries_total=trail.entries_total,
        slices=[
            ChainSliceOut(
                chain_scope=sl.chain_scope, label_fr=AUDIT.chain_label_fr(sl.chain_scope),
                entries=sl.entries, verified=sl.verified,
                verifiable_in_isolation=sl.verifiable_in_isolation, broken_at=sl.broken_at)
            for sl in trail.slices
        ],
    )


# ── Story 4.1: the optional case theory — versioned, audited, scope-checked ────────────────────
_MATTER_ABSENT = "dossier introuvable"  # ONE message for out-of-scope AND absent — non-disclosing


class CaseTheoryVersionOut(BaseModel):
    version_no: int
    version_id: str
    text: str | None  # null for a withdrawal version
    withdrawn: bool
    actor: str
    timestamp: datetime


class CaseTheoryOut(BaseModel):
    matter: str
    present: bool     # an active (non-withdrawn) theory exists
    withdrawn: bool   # the latest version is a withdrawal
    current: CaseTheoryVersionOut | None


class CaseTheoryIn(BaseModel):
    text: str  # the lawyer's own words; "" (or whitespace) is a withdrawal (FR-37)


class CaseTheoryHistoryOut(BaseModel):
    matter: str
    versions: list[CaseTheoryVersionOut]


def _version_out(v: object) -> CaseTheoryVersionOut:
    return CaseTheoryVersionOut(
        version_no=v.version_no, version_id=v.version_id, text=v.text,
        withdrawn=v.text is None, actor=v.actor, timestamp=v.created_at)


def _case_theory_out(matter: str, state: object) -> CaseTheoryOut:
    return CaseTheoryOut(
        matter=matter, present=state.present, withdrawn=state.withdrawn,
        current=_version_out(state.current) if state.current is not None else None)


@app.get("/api/matters/{matter}/case-theory", response_model=CaseTheoryOut)
def get_case_theory(matter: str, ident: Identity = Depends(current_identity)) -> CaseTheoryOut:
    """The current case theory for a matter (FR-37) — its text, version and author, or `present`
    false when none is set / it was withdrawn. A matter whose wall the caller does not hold is
    indistinguishable from an absent one: the same non-disclosing 404 (FR-14). Not an audited read
    (the writes below are the audited acts)."""
    store = _require_store()
    state = store.read_case_theory(tenant=ident.tenant, matter=matter, scopes=ident.scopes)
    if state is None:
        raise HTTPException(status_code=404, detail=_MATTER_ABSENT)
    return _case_theory_out(matter, state)


@app.put("/api/matters/{matter}/case-theory", response_model=CaseTheoryOut)
def put_case_theory(
    matter: str, body: CaseTheoryIn, ident: Identity = Depends(current_identity)
) -> CaseTheoryOut:
    """Write or rewrite the case theory (FR-37) — a new version, recorded in the audit record with
    actor and timestamp; an unchanged text is an idempotent no-op. Requires the matter's wall
    (else the same non-disclosing 404). Never triggers a re-rank (ranking is a later, explicit
    act)."""
    store = _require_store()
    if store.read_case_theory(tenant=ident.tenant, matter=matter, scopes=ident.scopes) is None:
        raise HTTPException(status_code=404, detail=_MATTER_ABSENT)  # non-disclosing wall gate
    state = store.append_case_theory_version(
        tenant=ident.tenant, matter=matter, actor=ident.actor, text=body.text)
    return _case_theory_out(matter, state)


@app.delete("/api/matters/{matter}/case-theory", response_model=CaseTheoryOut)
def delete_case_theory(matter: str, ident: Identity = Depends(current_identity)) -> CaseTheoryOut:
    """Withdraw the case theory (FR-37 failure path) — an APPEND-ONLY act: a withdrawal version is
    recorded, prior versions remain readable, nothing is hard-deleted (AD-7). Requires the matter's
    wall."""
    store = _require_store()
    if store.read_case_theory(tenant=ident.tenant, matter=matter, scopes=ident.scopes) is None:
        raise HTTPException(status_code=404, detail=_MATTER_ABSENT)
    state = store.append_case_theory_version(
        tenant=ident.tenant, matter=matter, actor=ident.actor, text=None)
    return _case_theory_out(matter, state)


@app.get("/api/matters/{matter}/case-theory/versions", response_model=CaseTheoryHistoryOut)
def case_theory_history(
    matter: str, ident: Identity = Depends(current_identity)
) -> CaseTheoryHistoryOut:
    """The full readable history of the matter's case theory (FR-37 "retains previous versions
    readably"), ascending by version — requires the matter's wall (else non-disclosing 404)."""
    store = _require_store()
    versions = store.list_case_theory_versions(
        tenant=ident.tenant, matter=matter, scopes=ident.scopes)
    if versions is None:
        raise HTTPException(status_code=404, detail=_MATTER_ABSENT)
    return CaseTheoryHistoryOut(matter=matter, versions=[_version_out(v) for v in versions])


def _register_out(e: object) -> RegisterEntryOut:
    return RegisterEntryOut(
        id=e.id, matter=e.matter, filename=e.filename, path=e.submitted_path,
        custodian=e.custodian, error_class=e.error_class, cardinality=e.cardinality,
        resolution_state=e.resolution_state, timestamp=e.timestamp, retryable=e.retryable)


@app.get("/api/matters/{matter}/register", response_model=RegisterOut)
def read_register(matter: str, ident: Identity = Depends(current_identity)) -> RegisterOut:
    """The failure register for one matter (Story 2.6, FR-5) — 403 outside the scope. Every entry
    whatever its state: open, resolved, and (Story 5.6) overridden — each kept as history, never
    removed (AD-7). The retry/bulk-retry actions and the register screen are the deferred UX pass;
    this is the read contract."""
    store = _require_store()
    try:
        entries = store.register(matter, ident.tenant, ident.scopes)
    except ScopeDenied as exc:
        raise HTTPException(status_code=403, detail="outside your scope") from exc
    return RegisterOut(entries=[_register_out(e) for e in entries])


@app.get("/api/register", response_model=RegisterOut)
def read_register_all(ident: Identity = Depends(current_identity)) -> RegisterOut:
    """The tenant-wide failure register within the caller's RBAC scope (FR-49). Entries whose
    matter could not be determined are included ONLY for the tenant-wide administrator."""
    store = _require_store()
    entries = store.register_all(ident.tenant, ident.scopes, is_admin=ident.is_admin)
    return RegisterOut(entries=[_register_out(e) for e in entries])


@app.get("/api/register/export", response_model=RegisterOut)
def export_register(ident: Identity = Depends(current_identity)) -> RegisterOut:
    """Export the register one-pièce-per-line within the caller's RBAC scope, recorded in the
    audit (FR-5/FR-49). Undetermined-matter entries appear only for the tenant admin."""
    store = _require_store()
    export = store.export_register(
        ident.tenant, ident.scopes, ident.actor, is_admin=ident.is_admin)
    return RegisterOut(entries=[_register_out(e) for e in export.lines])


@app.post("/api/matters/{matter}/record/export", response_model=MatterRecordOut)
def export_matter_record(
    matter: str, tier: str, ident: Identity = Depends(current_identity),
) -> MatterRecordOut:
    """Produce the *matter*'s record as a document — the THIRD named egress path (FR-26 §11).

    ``tier`` is **required and has no default**: this is the one act in the product that can move
    client content out of the firm on purpose, and a boundary that guessed would be guessing about
    that. `numbers-only` carries counts, versions, verdicts, positions and bounds and no client
    content; `full` adds the retained extracts, the override reasons verbatim, the justifications
    and the register's filenames.

    A POST, not a GET, because producing it is an ACT: it is recorded on the *matter*'s own chain
    with the tier, the actor, the scope and the moment. A refusal is not an export and writes
    nothing. 400 on an unknown tier, 403 outside the caller's scope."""
    store = _require_store()
    try:
        chosen = Tier(tier)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"niveau inconnu : {tier!r} — attendu 'numbers-only' ou 'full'") from exc
    try:
        record = store.export_matter_record(
            tenant=ident.tenant, matter=matter, actor=ident.actor, scopes=ident.scopes,
            tier=chosen)
    except ScopeDenied as exc:
        raise HTTPException(status_code=403, detail="outside your scope") from exc
    payload = dataclasses.asdict(record)
    payload["cover"]["degraded"] = record.cover.degraded
    payload["cover"]["degraded_sentence_fr"] = record.cover.degraded_sentence_fr
    return MatterRecordOut(**payload)


@app.get("/api/matters/{matter}/pieces/{piece_id}/drawer", response_model=DrawerOut)
def read_piece_drawer(
    matter: str, piece_id: str, version_no: int | None = None,
    ident: Identity = Depends(current_identity),
) -> DrawerOut:
    """The *audit drawer* for one *pièce* (FR-26) — the four bands, in the contract's order.

    A pure read. The actions it lists are **proposals**: each carries the audit row it would append
    and the sentence naming its own reversal, and committing one is a separate call to the use case
    that owns it. 404 out of scope or absent — the same answer for both (non-disclosing)."""
    store = _require_store()
    drawer = read_drawer(
        store, tenant=ident.tenant, matter=matter, actor=ident.actor, piece_id=piece_id,
        scopes=ident.scopes, version_no=version_no)
    if drawer is None:
        raise HTTPException(status_code=404, detail=_MATTER_ABSENT)
    shown = drawer.justification
    j = shown.justification if shown is not None else None
    return DrawerOut(
        piece_id=drawer.piece_id,
        matter=drawer.matter,
        ranking_version_no=drawer.ranking_version_no,
        sentence=j.sentence if j is not None else None,
        confidence=j.confidence if j is not None else None,
        confidence_signals=[str(sig) for sig in (j.confidence_signals if j else ())],
        source_language=j.source_language if j is not None else None,
        rejected=shown.rejected if shown is not None else False,
        is_unverified=drawer.is_unverified,
        unresolved_extracts=drawer.unresolved_extracts,
        extracts=[
            DrawerExtractOut(
                chunk_id=e.chunk_id, verified=e.verified, cause=e.cause,
                cause_fr=resolution_failure_fr(e.cause))
            for e in (shown.extracts if shown is not None else ())
        ],
        actions=[
            DrawerActionOut(
                action=a.action, action_fr=a.action_fr, reversal_fr=a.reversal_fr,
                proposed=ProposedEntryOut(
                    action=a.proposed.action, action_fr=a.proposed.action_fr,
                    actor=a.proposed.actor, chain_scope=a.proposed.chain_scope,
                    chain_label_fr=a.proposed.chain_label_fr,
                    override_ground=a.proposed.override_ground,
                    override_ground_fr=a.proposed.override_ground_fr,
                    reason_required=a.proposed.reason_required))
            for a in drawer.actions
        ],
        pending_actions=[
            DrawerPendingActionOut(
                label_fr=p.label_fr, story=p.story, disabled_reason_fr=p.disabled_reason_fr)
            for p in drawer.pending_actions
        ],
    )


@app.post("/api/register/{entry_id}/override", response_model=RegisterOverrideOut)
def override_register_entry(
    entry_id: str, req: RegisterOverrideIn, ident: Identity = Depends(current_identity),
) -> RegisterOverrideOut:
    """Close a *failure register* entry by *override* — FR-5's other exit, FR-25's second ground.

    The document never entered the *corpus* and never will (a source that no longer exists, a
    password nobody holds), so a person takes the entry out of `open` and owes one sentence for it,
    stored verbatim in the *audit record*. 400 when the reason is blank or the entry is no longer
    open; 403 outside the caller's scope — an undetermined-matter entry is admin-only (FR-49)."""
    store = _require_store()
    try:
        state = core_override_register_entry(
            store, entry_id=entry_id, tenant=ident.tenant, actor=ident.actor, reason=req.reason,
            scopes=ident.scopes, is_admin=ident.is_admin)
    except MissingOverrideReason as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ScopeDenied as exc:
        raise HTTPException(status_code=403, detail="outside your scope") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RegisterOverrideOut(entry_id=entry_id, resolution_state=state)


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


# ── Story 4.10: the triage table — one read for the surface, and the one act performed on it ──
# The table is a RENDERING of derived views: no route here stores a côté, a rank or a confidence.
# The single write is the taxonomy label, and it goes through the core/app seam (AD-4), which owns
# validation, the monotonic seq, the conditional commit and the atomic audit entry.


class TriageRowOut(BaseModel):
    piece_id: str
    name: str
    rank: int | None
    side: str
    confidence: float | None
    confidence_derived: bool
    confidence_signals: list[str]
    band: str | None
    label: str
    label_source: str | None
    label_seq: int | None
    in_current_taxonomy: bool
    pinned: bool


class LineOut(BaseModel):
    placed: bool
    last_retained_piece_id: str | None = None
    last_retained_rank: int | None = None
    basis: str | None = None
    seq: int | None = None
    at: datetime | None = None


class TriageTableOut(BaseModel):
    matter: str
    version_no: int
    version_id: str
    basis: str
    case_theory_version_id: str | None
    created_at: datetime
    rows: list[TriageRowOut]
    retained_count: int
    discarded_count: int
    unscored_count: int
    unsplit_count: int
    corpus_count: int    # the MATTER's pièces — "pièces au dossier" (FR-58)
    ranked_count: int    # the pièces THIS ranking version holds
    unranked_count: int  # in the dossier, in no set — ingested after the ranking ran (FR-58)
    pins_in_force: int
    line: LineOut
    taxonomy: list[str]


class ChangeLogEntryOut(BaseModel):
    piece_id: str
    seq: int
    previous: str
    label: str
    source: str
    set_by: str
    at: datetime


class ChangeLogOut(BaseModel):
    entries: list[ChangeLogEntryOut]


class LabelIn(BaseModel):
    label: str
    expected_seq: int | None = None


class LabelRevertIn(BaseModel):
    to_seq: int


class LabelWriteOut(BaseModel):
    piece_id: str
    seq: int
    entries: list[ChangeLogEntryOut]


def _change_log_out(entries: tuple[ChangeLogEntry, ...]) -> list[ChangeLogEntryOut]:
    return [
        ChangeLogEntryOut(
            piece_id=e.piece_id, seq=e.seq, previous=e.previous, label=e.label, source=e.source,
            set_by=e.set_by, at=e.at)
        for e in entries]


@app.get("/api/matters/{matter}/triage-table", response_model=TriageTableOut)
def get_triage_table(
    matter: str, version: int | None = None, ident: Identity = Depends(current_identity)
) -> TriageTableOut:
    """The whole triage surface for ONE ranking version (Story 4.10, FR-20) — the latest unless
    `version` pins one (AD-23: every count on screen names its version). Out of scope, absent, or
    not yet ranked are the SAME non-disclosing 404 (FR-14): the client renders "no ranking yet" as
    its own state, never an empty table pretending to be a result."""
    store = _require_store()
    table = read_triage_table(
        tenant=ident.tenant, matter=matter, scopes=ident.scopes, reader=store, version_no=version)
    if table is None:
        raise HTTPException(status_code=404, detail=_MATTER_ABSENT)
    return TriageTableOut(
        matter=table.matter, version_no=table.version_no, version_id=table.version_id,
        basis=table.basis, case_theory_version_id=table.case_theory_version_id,
        created_at=table.created_at,
        rows=[
            TriageRowOut(
                piece_id=r.piece_id, name=r.name, rank=r.rank, side=r.side,
                confidence=r.confidence, confidence_derived=r.confidence_derived,
                confidence_signals=list(r.confidence_signals), band=r.band, label=r.label,
                label_source=r.label_source, label_seq=r.label_seq,
                in_current_taxonomy=r.in_current_taxonomy, pinned=r.pinned)
            for r in table.rows],
        retained_count=table.retained_count, discarded_count=table.discarded_count,
        unscored_count=table.unscored_count, unsplit_count=table.unsplit_count,
        corpus_count=table.corpus_count, ranked_count=table.ranked_count,
        unranked_count=table.unranked_count,
        pins_in_force=table.pins_in_force,
        line=LineOut(
            placed=table.line.placed, last_retained_piece_id=table.line.last_retained_piece_id,
            last_retained_rank=table.line.last_retained_rank, basis=table.line.basis,
            seq=table.line.seq, at=table.line.at),
        taxonomy=list(table.taxonomy))


def _require_piece_in_matter(store: SqlStore, ident: Identity, matter: str,
                             piece_id: str) -> None:
    """A write naming a pièce that is not in the matter is refused with the same non-disclosing 404
    as an absent matter (FR-14). Without this, an arbitrary identifier would become a permanent row
    in an append-only ledger nothing can delete (AD-7) and would surface in the matter's change log
    — an evidential surface — naming a pièce that never existed."""
    if not store.piece_is_in_matter(
            tenant=ident.tenant, matter=matter, piece_id=piece_id, scopes=ident.scopes):
        raise HTTPException(status_code=404, detail=_MATTER_ABSENT)


def _label_write_out(store: SqlStore, ident: Identity, matter: str, piece_id: str,
                     seq: int) -> LabelWriteOut:
    """The written seq plus the row's change log, so the surface can show the entry beside the row
    immediately (FR-20) without a second round trip that could race the write."""
    entries = read_piece_change_log(
        tenant=ident.tenant, matter=matter, piece_id=piece_id, scopes=ident.scopes, reader=store)
    return LabelWriteOut(piece_id=piece_id, seq=seq, entries=_change_log_out(entries or ()))


@app.put("/api/matters/{matter}/pieces/{piece_id}/label", response_model=LabelWriteOut)
def put_piece_label(
    matter: str, piece_id: str, body: LabelIn, ident: Identity = Depends(current_identity)
) -> LabelWriteOut:
    """Set one *pièce*'s taxonomy label (FR-40/FR-20) — the ONE editable cell of the table.

    It changes that cell and nothing else: no rank, no confidence, no côté, no other row (FR-20).
    422 an out-of-taxonomy value (it can never leak), 409 a stale `expected_seq` (someone else
    edited the cell — the client reverts and re-reads rather than silently overwriting), 404 the
    non-disclosing wall gate."""
    store = _require_store()
    _require_piece_in_matter(store, ident, matter, piece_id)
    try:
        seq = assign_taxonomy_label(
            store, tenant=ident.tenant, matter=matter, actor=ident.actor, piece_id=piece_id,
            label=body.label, scopes=ident.scopes, expected_seq=body.expected_seq)
    except OutOfTaxonomyLabel as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except StaleLabel as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ScopeDenied as exc:
        raise HTTPException(status_code=404, detail=_MATTER_ABSENT) from exc
    return _label_write_out(store, ident, matter, piece_id, seq)


@app.post("/api/matters/{matter}/pieces/{piece_id}/label/revert", response_model=LabelWriteOut)
def revert_piece_label(
    matter: str, piece_id: str, body: LabelRevertIn, ident: Identity = Depends(current_identity)
) -> LabelWriteOut:
    """Revert a *pièce*'s label to the value it held at `to_seq` — a **new** change-log entry, never
    an erasure of the one it reverts (AD-7/FR-20). 400 when `to_seq` is not an entry of this pièce,
    422 when the restored value has since left the taxonomy, 404 the non-disclosing wall gate."""
    store = _require_store()
    _require_piece_in_matter(store, ident, matter, piece_id)
    try:
        seq = revert_taxonomy_label(
            store, tenant=ident.tenant, matter=matter, actor=ident.actor, piece_id=piece_id,
            to_seq=body.to_seq, scopes=ident.scopes)
    except OutOfTaxonomyLabel as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ScopeDenied as exc:
        raise HTTPException(status_code=404, detail=_MATTER_ABSENT) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _label_write_out(store, ident, matter, piece_id, seq)


@app.get("/api/matters/{matter}/pieces/{piece_id}/label/log", response_model=ChangeLogOut)
def read_piece_label_log(
    matter: str, piece_id: str, ident: Identity = Depends(current_identity)
) -> ChangeLogOut:
    """One row's change log, ascending: previous value → new value, author, timestamp (FR-20).
    Append-only — there is no route that edits or erases an entry."""
    store = _require_store()
    entries = read_piece_change_log(
        tenant=ident.tenant, matter=matter, piece_id=piece_id, scopes=ident.scopes, reader=store)
    if entries is None:
        raise HTTPException(status_code=404, detail=_MATTER_ABSENT)
    return ChangeLogOut(entries=_change_log_out(entries))


@app.get("/api/matters/{matter}/change-log", response_model=ChangeLogOut)
def read_matter_change_log_api(
    matter: str, limit: int = 200, ident: Identity = Depends(current_identity)
) -> ChangeLogOut:
    """The matter-level change log, newest first (FR-20) — the panel beside the table. `limit` is a
    panel page size, not a truncation of an evidential claim."""
    store = _require_store()
    entries = read_matter_change_log(
        tenant=ident.tenant, matter=matter, scopes=ident.scopes, reader=store,
        limit=max(1, min(limit, 1000)))
    if entries is None:
        raise HTTPException(status_code=404, detail=_MATTER_ABSENT)
    return ChangeLogOut(entries=_change_log_out(entries))


# ── Story 4.13: freshness and staleness of derived artefacts (FR-58/AD-23/AD-40) ───────────────


class FreshnessOut(BaseModel):
    kind: str                 # ranking | line | bound
    artefact_id: str
    fresh: bool
    changed: list[str]        # the trigger keys that moved
    changed_fr: list[str]     # what the surface says
    reason: str
    # a NEWER artefact of this kind exists. The verdict still stands (the artefact is readable and
    # still stale), but the recomputation it would offer has already been performed — so it carries
    # no worklist line, and the surface must not speak of it as the artefact on screen.
    superseded: bool


class WorklistLineOut(BaseModel):
    kind: str
    artefact_id: str
    changed: list[str]
    changed_fr: list[str]
    offer: str
    offer_fr: str


class BoundOut(BaseModel):
    artefact_id: str
    population: int
    sample_size: int
    relevant_found: int
    confidence: float
    # NULL at a census: nothing is bounded when everything was read, and a payload that carried a
    # prevalence there would let any client render the residual-risk figure FR-22 forbids over a
    # fully reviewed population (Story 5.2, OQ-4 input 2). `kind` says which register applies.
    kind: str                        # census | bound
    count_upper: int | None
    prevalence_upper: float | None
    reviewed_at: datetime
    freshness: FreshnessOut | None   # None == the bound recorded no stamp; NOT a claim of freshness
    exportable_as_current: bool
    status_fr: str
    copy_text: str                   # carries its staleness — the surface copies THIS (FR-58)
    # ── Story 5.2 ───────────────────────────────────────────────────────────────────────────────
    unit_fr: str                     # WHAT was counted — a family count is never called "pièces"
    piece_count: int | None          # how many pièces those units hold — never the denominator
    method: str | None               # the statistic by name; None = a bound that recorded none
    count_upper_pieces: int | None   # the WORST CASE in pièces; None = not computable, never 0
    relevant_pieces: int | None      # EXACT, census only
    run_ordinal: int                 # 1 = first draw over this population, abandoned ones counted
    # ── Story 5.4: FR-23's accompanying record, and the unfitness declaration ───────────────────
    # FR-23 requires the sentence to name the matter, the ranking version, the case-theory version,
    # the position of the line and the RBAC scope "or carry them in the accompanying record". This
    # IS that record. `scope` is ALSO inside `copy_text` — a paste carries no payload with it.
    scope: str | None                # the wall the number was COMPUTED UNDER, not the wall now
    ranking_version_no: int | None   # None on a legacy recall_review, which recorded none
    last_retained_piece_id: str | None   # the position of the line, by identity (FR-17)
    case_theory_version_id: str | None   # None on the intrinsic ranking path
    # FR-23's seventh consequence: K approaching N is a finding about the ORDER, not about where it
    # was cut. When present the surface must REMOVE the line-move affordance, not grey it.
    unfit_fr: str | None
    unfit_relevant_share: float | None   # the share observed; None when there is no finding
    unfit_threshold: float | None        # the configured rule that fired


def _freshness_out(assessment: Freshness) -> FreshnessOut:
    return FreshnessOut(
        kind=assessment.kind, artefact_id=assessment.artefact_id,
        fresh=assessment.fresh, changed=list(assessment.changed),
        changed_fr=list(assessment.changed_fr), reason=assessment.reason(),
        superseded=assessment.superseded)


def _bound_out(reading: BoundReading) -> BoundOut:
    b = reading.bound.bound
    return BoundOut(
        artefact_id=reading.bound.artefact_id, population=b.population,
        sample_size=b.sample_size, relevant_found=b.relevant_in_sample,
        confidence=b.confidence, kind=reading.kind,
        # Every register-dependent field is gated on the register, by ALLOW-list.
        #
        # CONFIRMED [HIGH] by two independent lenses: the first version gated `count_upper` and
        # `prevalence_upper` and left `count_upper_pieces` and `relevant_pieces` ungated, so the
        # counts-only register shipped a worst-case pièce PROJECTION — through /bound and through
        # /bound/export — while announcing that it had no bound to state. Gating some of a
        # register's fields is not gating the register; it is the disjointness defect with a
        # shorter list.
        count_upper=b.count_upper if reading.kind == KIND_BOUND else None,
        prevalence_upper=b.prevalence_upper if reading.kind == KIND_BOUND else None,
        count_upper_pieces=(
            reading.bound.count_upper_pieces if reading.kind == KIND_BOUND else None),
        # exact, and only ever at a census
        relevant_pieces=reading.bound.relevant_pieces if reading.kind == KIND_CENSUS else None,
        reviewed_at=reading.bound.reviewed_at,
        freshness=_freshness_out(reading.freshness) if reading.freshness is not None else None,
        exportable_as_current=reading.exportable_as_current,
        status_fr=reading.status_fr, copy_text=reading.copy_text,
        unit_fr=reading.bound.unit_fr, piece_count=reading.bound.piece_count,
        method=reading.bound.method,
        run_ordinal=reading.bound.run_ordinal,
        scope=reading.bound.scope,
        ranking_version_no=reading.bound.ranking_version_no,
        last_retained_piece_id=reading.bound.last_retained_piece_id,
        case_theory_version_id=reading.bound.case_theory_version_id,
        unfit_fr=reading.unfitness_fr,
        unfit_relevant_share=(
            reading.unfitness.share if reading.unfitness_fr is not None else None),
        unfit_threshold=(
            reading.unfitness.threshold if reading.unfitness_fr is not None else None))


@app.get("/api/matters/{matter}/freshness", response_model=list[FreshnessOut])
def get_freshness(
    matter: str, ident: Identity = Depends(current_identity)
) -> list[FreshnessOut]:
    """The verdict on every stamped derived artefact of the matter (FR-58/AD-23).

    Staleness is a COMPARISON of the stamp the artefact was produced under against the current
    observables — never a stored flag, so no writer can leave an artefact falsely fresh by
    forgetting to set one. `[]` means the matter was read and has stamped nothing yet; out of scope
    and absent are the same non-disclosing 404 (FR-14). Reading this resolves nothing."""
    store = _require_store()
    assessments = read_freshness(
        tenant=ident.tenant, matter=matter, scopes=ident.scopes, reader=store)
    if assessments is None:
        raise HTTPException(status_code=404, detail=_MATTER_ABSENT)
    return [_freshness_out(a) for a in assessments]


@app.get("/api/matters/{matter}/worklist", response_model=list[WorklistLineOut])
def get_worklist(
    matter: str, ident: Identity = Depends(current_identity)
) -> list[WorklistLineOut]:
    """The matter's worklist — one line per stale artefact, naming the inputs that moved and
    OFFERING the recomputation (FR-58). Derived from the assessments, stored nowhere.

    Reading it writes nothing and queues nothing: staleness is resolved only by an explicit
    user-initiated act that produces a NEW artefact."""
    store = _require_store()
    lines = read_worklist(
        tenant=ident.tenant, matter=matter, scopes=ident.scopes, reader=store,
        config_get=lambda key: store.get_config(ident.tenant, key))
    if lines is None:
        raise HTTPException(status_code=404, detail=_MATTER_ABSENT)
    return [
        WorklistLineOut(
            kind=line.kind, artefact_id=line.artefact_id, changed=list(line.changed),
            changed_fr=list(line.changed_fr), offer=line.offer, offer_fr=line.offer_fr)
        for line in lines]


@app.get("/api/matters/{matter}/bound", response_model=BoundOut)
def get_bound(matter: str, ident: Identity = Depends(current_identity)) -> BoundOut:
    """The matter's current confidence bound and the verdict on it (FR-58/FR-23).

    404 when out of scope, absent, or when no bound has been recorded — the surface renders "no
    bound yet" as its own state, never as a bound of zero."""
    store = _require_store()
    reading = read_bound(
        tenant=ident.tenant, matter=matter, scopes=ident.scopes, reader=store,
        config_get=lambda key: store.get_config(ident.tenant, key))
    if reading is None:
        raise HTTPException(status_code=404, detail=_MATTER_ABSENT)
    return _bound_out(reading)


@app.get("/api/matters/{matter}/bound/export", response_model=BoundOut)
def export_bound(matter: str, ident: Identity = Depends(current_identity)) -> BoundOut:
    """Export the confidence bound as current — REFUSED with 409 when it is stale or when its
    inputs cannot be verified (FR-58).

    The product blocks rather than warns (PRD §Blocking, not warning): a qualified export of a
    false number is still a false number in a bundle. The refusal names the inputs that moved and
    writes nothing; a successful export is an audited egress act (FR-53)."""
    store = _require_store()
    reading = read_bound(
        tenant=ident.tenant, matter=matter, scopes=ident.scopes, reader=store,
        config_get=lambda key: store.get_config(ident.tenant, key))
    if reading is None:
        raise HTTPException(status_code=404, detail=_MATTER_ABSENT)
    if not reading.exportable_as_current:
        raise HTTPException(status_code=409, detail=reading.status_fr)
    store.audit_bound_export(
        tenant=ident.tenant, matter=matter, actor=ident.actor,
        detail=(f"artefact={reading.bound.artefact_id[:12]} "
                f"bound={reading.bound.bound.prevalence_upper:.4f}"
                f"@{reading.bound.bound.confidence}"))
    return _bound_out(reading)


# ── Story 5.1: the sampling run — a frozen random draw from the DISCARDED SET (FR-22) ──────────
#
# The population is the Epic-4 DERIVED discarded view (order + the line + pins), never the
# Story-2.x label pile: planning decision A1. The two legacy routes that drew from and bounded the
# label pile (`GET /recall/sample`, `POST /recall/review`) are RETIRED here — superseded, not
# deleted: every recorded recall_review row stays readable and `GET /bound` still falls back to
# them when a matter has no run.


class SamplingUnitOut(BaseModel):
    family_id: str
    proxy_piece_id: str          # the pièce the lawyer reads — a verdict on it judges the family
    member_piece_ids: list[str]  # the family's DISCARDED members only (FR-22's identifier list)


class DrawnFamilyOut(BaseModel):
    unit: SamplingUnitOut
    draw_index: int              # position in the DRAW, deliberately not rank order
    relevant: bool | None        # the current verdict; None == not judged yet, never "not relevant"
    verdict_by: str | None
    verdict_at: datetime | None
    verdict_seq: int | None


class SamplingRunOut(BaseModel):
    run_id: str
    # ── the freeze (FR-22) ──────────────────────────────────────────────────────────────────────
    version_id: str
    version_no: int
    last_retained_piece_id: str  # the position of THE LINE, by identity — never a bare integer
    pin_ledger_seq: int
    scope: str
    # ── the draw ────────────────────────────────────────────────────────────────────────────────
    confidence: float
    population_families: int     # the unit the bound is computed over
    population_pieces: int       # how many pièces those families hold — NOT the bound's denominator
    sample_size: int
    is_census: bool
    # ── state (derived, never stored) ───────────────────────────────────────────────────────────
    status: str                  # open | completed | abandoned — what a person did to it
    state: str                   # open | invalidated | completed | abandoned — what it IS
    invalidated_in_flight: bool
    changed: list[str]
    changed_fr: list[str]
    state_fr: str
    # Story 5.4 — the run's own reading, in whichever of the four registers applies, composed by the
    # ONE Domain composer. It REPLACED a census-only string: one arm for one register left the other
    # three to whichever renderer got there first. `None` while the run supports nothing.
    #
    # NOT the copyable constat: only /bound holds FR-58's freshness verdict, and a second copyable
    # string would put one number on a clipboard twice with two different sets of qualifications.
    statement_fr: str | None
    run_qualification_fr: str     # this run's own MEASURED observables, never a freshness verdict
    unfit_fr: str | None          # FR-23: K approaching N — the ORDER carries no signal
    started_by: str
    started_at: datetime
    completed_at: datetime | None
    verdicts_recorded: int
    relevant_found: int | None
    count_upper: int | None
    prevalence_upper: float | None
    # ── Story 5.2: what the run supports, and what it explicitly does not ───────────────────────
    # ``estimate_kind`` is census | bound | no_population, or None while the run supports nothing.
    # The census fields and the bound fields are never both populated: a census states an exact
    # count, a sample states a bound, and the crossover is n == N exactly (OQ-4 input 2).
    estimate_kind: str | None
    estimator_method: str | None      # the statistic, by name — FR-23
    # a WORST CASE in pièces: the sum of the D largest FROZEN families, never prevalence × pièces
    # (OQ-4 input 1). None means NOT COMPUTABLE — a run frozen before the sizes existed, never 0.
    count_upper_pieces: int | None
    relevant_pieces: int | None       # EXACT, census only — every pièce was read
    run_ordinal: int                  # 1 = first draw over this frozen population, incl. abandoned
    repeated_draw_fr: str | None      # the multiplicity fact, stated; None on a first draw
    drawn: list[DrawnFamilyOut]


class SizingOut(BaseModel):
    population: int
    target_prevalence: float
    confidence: float
    size: int | None             # None == unreachable at any size the caller will offer
    is_census: bool
    achievable_prevalence_upper: float
    reason_fr: str
    # CONFIRMED [LOW] by the review: a sizing is a PLAN, but it is a quantitative promise about the
    # bound the run will yield, computed by the same statistic the product may be forbidden to
    # state. Offering "200 familles suffisent pour 5 %" and then refusing to say 5 % is a promise
    # broken after an evening of verdicts. The plan now carries whether the promise can be kept.
    bound_will_be_stated: bool
    caveat_fr: str | None


class StartRunIn(BaseModel):
    sample_size: int | None = None
    target_prevalence: float | None = None
    confidence: float = 0.95
    max_size: int | None = None
    version_no: int | None = None


class VerdictIn(BaseModel):
    family_id: str
    relevant: bool


def _run_out(reading: SamplingRunReading) -> SamplingRunOut:
    run = reading.run
    estimate = reading.estimate
    return SamplingRunOut(
        estimate_kind=estimate.kind if estimate else None,
        estimator_method=run.estimator_method,
        count_upper_pieces=estimate.count_upper_pieces if estimate else None,
        relevant_pieces=estimate.relevant_pieces if estimate else None,
        run_ordinal=run.run_ordinal, repeated_draw_fr=reading.repeated_draw_fr,
        run_id=run.run_id, version_id=run.version_id, version_no=run.version_no,
        last_retained_piece_id=run.last_retained_piece_id, pin_ledger_seq=run.pin_ledger_seq,
        scope=run.scope, confidence=run.confidence,
        population_families=run.population_families, population_pieces=run.population_pieces,
        sample_size=run.sample_size, is_census=run.is_census, status=run.status,
        state=reading.state, invalidated_in_flight=reading.invalidated_in_flight,
        changed=list(reading.changed), changed_fr=list(reading.changed_fr),
        state_fr=reading.state_fr, statement_fr=reading.statement_fr,
        run_qualification_fr=reading.run_qualification_fr, unfit_fr=reading.unfitness_fr,
        started_by=run.started_by, started_at=run.started_at, completed_at=run.completed_at,
        verdicts_recorded=run.verdicts_recorded, relevant_found=run.relevant_found,
        # CONFIRMED [HIGH] by two independent lenses: these came straight off the run ROW, so
        # /sampling/runs shipped a count_upper and a prevalence beside `estimate_kind:
        # "counts_only"` — the register announced that no bound could be defended and the payload
        # carried one anyway. The row is where the numbers were RECORDED; the estimate is what the
        # product is currently entitled to SAY, and only the estimate may reach a surface.
        count_upper=estimate.count_upper_families if estimate else None,
        prevalence_upper=estimate.prevalence_upper if estimate else None,
        drawn=[
            DrawnFamilyOut(
                unit=SamplingUnitOut(
                    family_id=d.unit.family_id, proxy_piece_id=d.unit.proxy_piece_id,
                    member_piece_ids=list(d.unit.member_piece_ids)),
                draw_index=d.draw_index,
                relevant=d.verdict.relevant if d.verdict else None,
                verdict_by=d.verdict.actor if d.verdict else None,
                verdict_at=d.verdict.at if d.verdict else None,
                verdict_seq=d.verdict.seq if d.verdict else None)
            for d in run.drawn])


def _reread_run(matter: str, ident: Identity, run_id: str) -> SamplingRunOut:
    """Re-read a run through the ONE read seam after an act, so the response carries the same
    derived state a GET would (AD-14) — never a second, hand-assembled truth."""
    store = _require_store()
    reading = read_sampling_run(
        tenant=ident.tenant, matter=matter, scopes=ident.scopes, store=store,
        config_get=lambda key: store.get_config(ident.tenant, key), run_id=run_id)
    if reading is None:  # pragma: no cover - the act just succeeded inside the same scope
        raise HTTPException(status_code=404, detail=_MATTER_ABSENT)
    return _run_out(reading)


@app.get("/api/matters/{matter}/sampling/sizing", response_model=SizingOut)
def get_sampling_sizing(
    matter: str, target: float, confidence: float = 0.95, max_size: int | None = None,
    version_no: int | None = None, ident: Identity = Depends(current_identity),
) -> SizingOut:
    """How many near-duplicate FAMILIES must be drawn to reach a target bound (FR-22).

    A preview: writes nothing, audits nothing, starts nothing. Where the target is unreachable the
    answer says so and carries the best achievable — never a refusal and never a silent cap. 404
    when out of scope, absent, not ranked, or with no line placed (indistinguishable, FR-14)."""
    try:
        sizing = size_for_target_bound(
            _require_store(), tenant=ident.tenant, matter=matter, scopes=ident.scopes,
            target_prevalence=target, confidence=confidence, max_size=max_size,
            version_no=version_no)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if sizing is None:
        raise HTTPException(status_code=404, detail=_MATTER_ABSENT)
    return SizingOut(
        population=sizing.population, target_prevalence=sizing.target_prevalence,
        confidence=sizing.confidence, size=sizing.size, is_census=sizing.is_census,
        bound_will_be_stated=estimator_is_proven(),
        caveat_fr=None if estimator_is_proven() else (
            "l'estimateur n'a pas été prouvé par simulation : ce tirage produira des comptes, "
            "pas de borne"),
        achievable_prevalence_upper=sizing.achievable_prevalence_upper,
        reason_fr=sizing.reason_fr)


@app.post("/api/matters/{matter}/sampling/runs", response_model=SamplingRunOut)
def start_run(
    matter: str, req: StartRunIn, ident: Identity = Depends(current_identity)
) -> SamplingRunOut:
    """Start a sampling run over the matter's DERIVED discarded set (FR-22).

    Draws near-duplicate families uniformly WITHOUT replacement, freezes the ranking version, the
    position of the line, the pin ledger, the scope and the explicit identifier list, stamps the run
    and audits it — one transaction. 404 when out of scope, absent, not ranked, no line placed, or
    the discarded set is empty (nothing to audit: no bound applies, never a flattering 0%)."""
    try:
        run = start_sampling_run(
            _require_store(), tenant=ident.tenant, matter=matter, actor=ident.actor,
            scopes=ident.scopes, sample_size=req.sample_size,
            target_prevalence=req.target_prevalence, confidence=req.confidence,
            max_size=req.max_size, version_no=req.version_no)
    except ScopeDenied as exc:
        # 404, NOT 403: every peer sampling route answers an out-of-scope matter with the same
        # non-disclosing 404 as an absent one (FR-14/AD-13). A 403 here would be the one place a
        # caller could learn that another firm's dossier exists by being refused differently.
        raise HTTPException(status_code=404, detail=_MATTER_ABSENT) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if run is None:
        raise HTTPException(status_code=404, detail=_MATTER_ABSENT)
    return _reread_run(matter, ident, run.run_id)


@app.get("/api/matters/{matter}/sampling/runs/current", response_model=SamplingRunOut)
def get_current_run(
    matter: str, run_id: str | None = None, ident: Identity = Depends(current_identity)
) -> SamplingRunOut:
    """The matter's current run (or a named one) with the verdict on its frozen population.

    `invalidated_in_flight` is FR-22's failure path and is DERIVED — the comparison of the run's
    freshness stamp against the current observables (Story 4.13), never a stored flag a writer could
    forget to set. 404 when out of scope, absent, or no run exists."""
    store = _require_store()
    reading = read_sampling_run(
        tenant=ident.tenant, matter=matter, scopes=ident.scopes, store=store,
        config_get=lambda key: store.get_config(ident.tenant, key), run_id=run_id)
    if reading is None:
        raise HTTPException(status_code=404, detail=_MATTER_ABSENT)
    return _run_out(reading)


@app.get("/api/matters/{matter}/sampling/runs", response_model=list[SamplingRunOut])
def list_runs(
    matter: str, ident: Identity = Depends(current_identity)
) -> list[SamplingRunOut]:
    """Every sampling run of the matter, newest first — including abandoned and invalidated ones
    with their verdicts (AD-7: an hour of verdicts is never destroyed). `[]` means the matter was
    read and has no run yet; 404 means it was not read."""
    store = _require_store()
    runs = read_sampling_runs(
        tenant=ident.tenant, matter=matter, scopes=ident.scopes, store=store,
        config_get=lambda key: store.get_config(ident.tenant, key))
    if runs is None:
        raise HTTPException(status_code=404, detail=_MATTER_ABSENT)
    return [_run_out(reading) for reading in runs]


@app.post("/api/matters/{matter}/sampling/runs/{run_id}/verdicts", response_model=SamplingRunOut)
def record_verdict(
    matter: str, run_id: str, req: VerdictIn, ident: Identity = Depends(current_identity)
) -> SamplingRunOut:
    """Record one verdict on one drawn family — append-only, attributed, audited (FR-22/FR-24).

    409 when the run's frozen population has MOVED: refusing is the strongest form of FR-22's "tells
    the user immediately", because a verdict against a population that no longer exists is worse
    than no verdict — it looks like evidence. 409 too when the run is already closed. 404 when out
    of scope, absent, or the family was not drawn by this run."""
    try:
        run = record_sampling_verdict(
            _require_store(), tenant=ident.tenant, matter=matter, actor=ident.actor,
            scopes=ident.scopes, run_id=run_id, family_id=req.family_id, relevant=req.relevant)
    except InvalidatedRun as exc:
        raise HTTPException(
            status_code=409,
            detail=f"tirage invalidé ; abandonnez-le et retirez ({exc})") from exc
    except RunAlreadyClosed as exc:
        raise HTTPException(status_code=409, detail=f"tirage déjà clos ({exc})") from exc
    if run is None:
        raise HTTPException(status_code=404, detail=_MATTER_ABSENT)
    return _reread_run(matter, ident, run_id)


@app.post("/api/matters/{matter}/sampling/runs/{run_id}/complete", response_model=SamplingRunOut)
def complete_run(
    matter: str, run_id: str, ident: Identity = Depends(current_identity)
) -> SamplingRunOut:
    """Close a fully-judged run: tally, bound over the unit DRAWN (families), audit — atomically.

    400 when the run is not fully judged: an unjudged family is not a verdict of "not relevant"
    (AD-19), and counting it as one would make the bound look better than the evidence supports.
    409 when the population moved. 404 when out of scope or absent."""
    try:
        run = complete_sampling_run(
            _require_store(), tenant=ident.tenant, matter=matter, actor=ident.actor,
            scopes=ident.scopes, run_id=run_id)
    except InvalidatedRun as exc:
        raise HTTPException(
            status_code=409,
            detail=f"tirage invalidé ; abandonnez-le et retirez ({exc})") from exc
    except RunAlreadyClosed as exc:
        raise HTTPException(status_code=409, detail=f"tirage déjà clos ({exc})") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if run is None:
        raise HTTPException(status_code=404, detail=_MATTER_ABSENT)
    return _reread_run(matter, ident, run_id)


@app.post("/api/matters/{matter}/sampling/runs/{run_id}/abandon", response_model=SamplingRunOut)
def abandon_run(
    matter: str, run_id: str, ident: Identity = Depends(current_identity)
) -> SamplingRunOut:
    """Give up an open run, audited. Its draw and every verdict stay readable forever (AD-7) — an
    invalidated run is abandoned and redrawn, never silently reused. 409 when already closed; 404
    when out of scope or absent."""
    try:
        run = abandon_sampling_run(
            _require_store(), tenant=ident.tenant, matter=matter, actor=ident.actor,
            scopes=ident.scopes, run_id=run_id)
    except RunAlreadyClosed as exc:
        raise HTTPException(status_code=409, detail=f"tirage déjà clos ({exc})") from exc
    if run is None:
        raise HTTPException(status_code=404, detail=_MATTER_ABSENT)
    return _reread_run(matter, ident, run_id)


# One artifact serves both: the API routes above (/api/*, matched first) and the built
# SPA (everything else). Mounted only when a build is present, so tests and API-only
# runs are unaffected. APX_WEB_DIST overrides the location (the Docker image sets it).
_web_dist = Path(
    os.environ.get("APX_WEB_DIST", str(Path(__file__).resolve().parent.parent / "web" / "dist"))
)
if _web_dist.is_dir():
    app.mount("/", StaticFiles(directory=str(_web_dist), html=True), name="web")
