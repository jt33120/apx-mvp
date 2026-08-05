"""The store — persist an ingestion result, read back the durable inventory, and
enforce the Chinese wall (RBAC scope) as a query PRE-filter (AD-13, AD-14).

Idempotent by construction: a piece is keyed by its deterministic id
(content, matter), a failure by (matter, submitted_path), so re-ingesting the same
folder does not duplicate. Scope is resolved from the authoritative `matter_scope`
table at query time and constrains every read — it is never denormalised onto
piece/chunk rows, so a re-scope takes effect at the next query with nothing to
propagate. The adapter imports app/domain types (adapter -> core is allowed); the
core imports no adapter. The frozen-schema rigor and the single-read-path static
check are stories 1.3 / 3.3; this slice carries the working pre-filter.
"""

from __future__ import annotations

import hashlib
import json
import logging
import random
import secrets
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import Text, cast, delete, event, func, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from apx.adapters.store_postgres.backfill import case_theory_version_id, link_id
from apx.adapters.store_postgres.chunk_writer import UnauthorizedScope
from apx.adapters.store_postgres.crypto_types import cipher
from apx.adapters.store_postgres.deterministic_query import exact_search_stmt
from apx.adapters.store_postgres.models import (
    AuditRecord,
    BackupRecord,
    CaseTheoryVersion,
    Chunk,
    Failure,
    ImportJob,
    ImportUnit,
    LabelRecord,
    LinePlacement,
    MatterScope,
    NoiseExclusion,
    Piece,
    PieceCustodian,
    PieceProvenance,
    RankedEntry,
    RecallReview,
    SessionRecord,
    TaxonomyLabelEntry,
    TenantSetting,
    TruncationMarker,
    User,
    UserScope,
)
from apx.adapters.store_postgres.models import (
    RankingVersion as RankingVersionRow,
)
from apx.adapters.store_postgres.semantic_query import results_from_rows, semantic_search_stmt
from apx.core.app.ingest import IngestedFailure, IngestedPiece, IngestionResult
from apx.core.domain.auth import hash_password, verify_and_upgrade, verify_password
from apx.core.domain.cascade import INTRINSIC_SIGNALS
from apx.core.domain.chunking import (
    PIECE_GONE,
    FailedResolution,
    ResolvedPassage,
    chunking_config,
    resolve_passage,
)
from apx.core.domain.confidence import prevalence_upper_bound
from apx.core.domain.config import (
    CONFIG_SCHEMA,
    ConfigError,
    ConfigKey,
    coerce,
    dumps_value,
    loads_value,
    require_key,
)
from apx.core.domain.crypto import DecryptionError
from apx.core.domain.dedup import cluster
from apx.core.domain.failures import ErrorClass, cardinality_for
from apx.core.domain.head_journal import HeadEntry, HeadJournal, Reconciliation
from apx.core.domain.inventory import Inventory
from apx.core.domain.line import LinePlacementView, RankedBand, recommend_line
from apx.core.domain.line_projection import (
    PROJECTION_METHOD,
    PricedMove,
)
from apx.core.domain.line_projection import (
    price_line_move as project_line_move,
)
from apx.core.domain.normalization import normalize
from apx.core.domain.ranking import (
    RankedOrder,
    RankingIdentity,
    RankingVersion,
)
from apx.core.domain.retrieval import DeterministicResult, SemanticResult
from apx.core.domain.search import snippet
from apx.core.domain.taxonomy_label import (
    LabelEntry,
    LabelSource,
    current_label,
    is_member,
    validate_label,
)
from apx.core.domain.triage import TriageOutcome
from apx.core.domain.triage_sets import Line, Pin, TriageSets, derive_triage_sets
from apx.core.ports.read import ExactSearch, PieceView
from apx.core.projection import Snapshot

_log = logging.getLogger("apx.store")

# A valid hash to verify against when the user is unknown, so authentication takes the
# same time whether or not the email exists (no user-enumeration by timing).
_DUMMY_HASH = hash_password("timing-equalizer")

_APP_VERSION = "0.1.0"           # the application version stamped on a head-journal entry (AD-35)
_HEAD_SCHEMA_VERSION = "slice-a"  # the payload schema version (AD-40) stamped on the head
# The tenant-owned tables a logical backup captures (each has a `tenant` column). `user_scope` is
# keyed by user_id (tenant-bound via the user) and is handled specially in backup/restore.
_BACKUP_TABLES = (
    "matter_scope", "user_account", "session", "tenant_setting",
    "piece", "chunk", "failure", "noise_exclusion", "piece_label", "audit_record", "recall_review",
    "backup_record", "truncation_marker", "taxonomy_label_entry", "line_placement",
)


class ScopeDenied(Exception):
    """A read touched a matter outside the caller's RBAC scope. Fail closed."""


class ScopeConflict(Exception):
    """An ingest would change an existing matter's scope. A matter's wall may only move via
    the audited admin re-scope path (AD-13/FR-49), never silently through a re-ingest."""


class TenantAlreadyProvisioned(Exception):
    """Provisioning was asked to establish a tenant that already has an administrator. Fail
    closed — never silently take over a live firm (AD-25)."""


class StaleRankingInput(Exception):
    """The conditional commit refused a ranking whose recorded identity input changed under it
    (AD-23/AD-37): the *matter*'s latest *case-theory* version at commit time differs from the one
    the ranking recorded. Nothing is written — a ranking is never silently committed over a case
    theory that moved while it was being produced."""


class StaleLabel(Exception):
    """The conditional commit refused a taxonomy-label edit whose observed ``seq`` no longer holds
    (AD-37): the *pièce*'s label moved under the caller between read and write. Nothing is written —
    a label edit never silently overwrites a change the caller did not see (FR-40 / FR-20)."""


class StaleLine(Exception):
    """The serialised line move was refused because the line moved under the caller (FR-19): a
    second user's move against a superseded position is rejected, nothing is written, and the
    CURRENT position (``current_seq`` / ``current_last_retained_piece_id``) is carried so the
    interface can show it. This keeps the audit from ever storing a priced statement never true."""

    def __init__(self, current_seq: int, current_last_retained_piece_id: str | None) -> None:
        self.current_seq = current_seq
        self.current_last_retained_piece_id = current_last_retained_piece_id
        super().__init__(
            f"the line moved under the edit (expected a superseded position; current seq "
            f"{current_seq}, last retained {current_last_retained_piece_id})")


@dataclass(frozen=True)
class ConfigChange:
    """The recorded result of one audited configuration edit (AD-25) — before/after make it
    reversible (set ``before`` back to restore)."""

    key: str
    before: object
    after: object
    changed: bool  # False when the new value equalled the old (a no-op, no audit entry written)


@dataclass(frozen=True)
class ConfigItem:
    key: str
    value: object
    default: object
    governs: str


@dataclass(frozen=True)
class ConfigProvenance:
    """Whether a stored configuration value is traceable to an audited change through the surface
    (AD-25). ``audited`` is False when a value matches neither the last audited change for its key
    nor the schema default — i.e. it was written by a direct DB edit that skipped the surface."""

    key: str
    value: object
    audited: bool


@dataclass(frozen=True)
class TenantBackup:
    """A complete, tenant-boundary logical backup (AD-32). ``tables`` holds each tenant-owned
    table's rows as raw values — content-bearing columns stay CIPHERTEXT (read raw, restored raw),
    so the backup is encrypted at rest without re-encryption. ``head_tail`` copies the tenant's
    head-journal entries onto the backup (AD-35: a copy on every backup target)."""

    tenant: str
    schema_version: str
    tables: dict[str, list[dict]]
    user_scopes: list[dict]
    head_tail: list[dict]
    # the piece SETS (Story 2.5) — keyed by piece_id, not tenant, so gathered/restored specially
    # (like ``user_scopes``); "piece_provenance"/"piece_custodian" → their raw (ciphertext) rows.
    piece_links: dict[str, list[dict]] = field(default_factory=dict)


@dataclass(frozen=True)
class BackupStatus:
    """Whether a tenant has a recent successful backup (AD-32)."""

    tenant: str
    last_success_at: str | None
    overdue: bool
    interval_hours: int


@dataclass(frozen=True)
class TruncationStatus:
    """A detected restore-truncation, or its absence (AD-35). ``active`` is True while un-cleared —
    named on the face of every export until an audited override clears it; never repaired."""

    tenant: str
    active: bool
    journal_seq: int
    live_seq: int
    detected_at: str | None
    cleared_at: str | None


@dataclass(frozen=True)
class AuthUser:
    id: str
    tenant: str
    email: str
    display_name: str  # the actor recorded on the audit trail


@dataclass(frozen=True)
class SessionIdentity:
    """The Principal resolved from an opaque session (AD-15) — everything LIVE from the
    user's rows (never denormalised on the session), so a rename, a scope revocation or an
    admin change takes effect on the next request."""

    user_id: str
    tenant: str
    actor: str  # the user's current display name (the audit actor)
    is_admin: bool
    scopes: set[str]


@dataclass(frozen=True)
class UserInfo:
    id: str
    email: str
    display_name: str
    is_admin: bool
    scopes: tuple[str, ...]


@dataclass(frozen=True)
class SaveOutcome:
    """The result of persisting one ingestion result. Story 2.5 splits the corpus admission
    into `pieces_new` (persisted anew) and `pieces_already_present` (recognised, not
    re-written) — the "recognised-already-present" line FR-4 requires, so a re-import is
    visibly a no-op rather than a silent overwrite (the v1 defect)."""

    pieces_new: int
    pieces_already_present: int
    failures_written: int

    @property
    def pieces_written(self) -> int:
        """Back-compat alias — pieces persisted ANEW this call (== ``pieces_new``)."""
        return self.pieces_new


@dataclass(frozen=True)
class ImportJobView:
    """A detached snapshot of an import_job row — the worker and the status endpoint read this,
    never a live ORM object across sessions (Story 2.2)."""

    id: str
    tenant: str
    matter: str
    scope: str
    actor: str
    custodian: str
    case_theory: str | None
    spool_path: str
    owns_spool: bool
    state: str
    submitted: int | None
    provisional: bool


@dataclass(frozen=True)
class ImportProgress:
    """The processed-against-submitted figure, read ONLY from the application-owned ledger
    (AD-17) — never from Procrastinate's job table."""

    job_id: str
    tenant: str
    matter: str
    state: str
    submitted: int | None
    processed: int
    committed: int
    quarantined: int
    pending: int
    provisional: bool


@dataclass(frozen=True)
class MatterSummary:
    matter: str
    scope: str
    inventory: Inventory


@dataclass(frozen=True)
class RegisterEntry:
    """One failure-register entry (FR-5), decrypted for reading. `retryable` is the retry-action
    affordance: every OPEN entry can be retried; a resolved one cannot (it is history, kept)."""

    id: str
    matter: str | None            # None = undetermined (admin-only visibility, FR-49)
    filename: str
    submitted_path: str
    custodian: str | None         # where known (FR-5)
    error_class: str
    cardinality: str              # one | unknown (AD-38)
    resolution_state: str         # open | resolved (never removed, AD-7)
    timestamp: str
    retryable: bool               # the retry action (FR-5) — true iff open


@dataclass(frozen=True)
class RetryOutcome:
    """The result of an ingestion-retry (AD-37, `open → resolved`, a conditional commit)."""

    entry_id: str
    # resolved | still-failing | precondition-not-met | not-found
    outcome: str
    resolution_state: str | None


@dataclass(frozen=True)
class BulkRetryOutcome:
    """A bulk retry over a filtered set — ONE audit entry, never one per pièce (FR-5)."""

    attempted: int
    resolved: int
    still_failing: int
    skipped: int  # entries no longer open at retry time (never clobbered — the AD-37 defense)
    errored: int = 0  # entries whose re-ingest/commit raised — counted, never aborting the set


@dataclass(frozen=True)
class RegisterExport:
    """The register exported one-pièce-per-line within the caller's RBAC scope (FR-5/FR-49)."""

    lines: tuple[RegisterEntry, ...]
    scope_count: int  # how many held scopes the export covered (for the audit detail)


@dataclass(frozen=True)
class NoiseExclusionEntry:
    """One filesystem-noise exclusion (FR-6), decrypted for reading — the "one click from the list
    of what was excluded" backend. Its own class, distinct from the failure register (Story 2.7)."""

    matter: str
    filename: str
    submitted_path: str
    timestamp: str


@dataclass(frozen=True)
class AuditEntry:
    seq: int
    actor: str
    action: str
    detail: str
    chain: str
    timestamp: str


@dataclass(frozen=True)
class AuditTrail:
    entries: list[AuditEntry]
    verified: bool  # the chain recomputes cleanly (no gap, reorder or truncation)


@dataclass(frozen=True)
class CaseTheoryVersionView:
    """One readable version of a matter's case theory (Story 4.1). ``text`` is None for a
    *withdrawal* version. ``version_id`` is the stable identity a future ranking version names."""

    version_no: int
    version_id: str
    text: str | None
    actor: str
    created_at: datetime


@dataclass(frozen=True)
class CaseTheory:
    """The current state of a matter's case theory (scope-checked). ``present`` = an active
    (non-withdrawn) theory exists; ``withdrawn`` = the latest version is a withdrawal; ``current``
    = the latest version (active OR withdrawal), None when a theory was never set."""

    present: bool
    withdrawn: bool
    current: CaseTheoryVersionView | None


@dataclass(frozen=True)
class RankingVersionView:
    """One readable *ranking version* of a *matter* (Story 4.3, AD-23). ``version_id`` is the
    referenceable identity; ``fingerprint`` decides "the same ranking version"; the counts summarise
    the recorded order without hydrating every row."""

    version_no: int
    version_id: str
    fingerprint: str
    basis: str
    case_theory_version_id: str | None
    stage3_share: float
    ranked_count: int
    unscored_count: int
    created_at: datetime


@dataclass(frozen=True)
class RankedEntryView:
    """One *pièce*'s recorded row in a ranking (AD-23's per-*pièce* output). ``rank`` is None for an
    UNSCORED pièce (out of the order, never ranked last — AD-19)."""

    piece_id: str
    rank: int | None
    outcome: str
    score: float | None
    band: str | None
    label: str | None
    rejection_class: str | None
    failure_reason: str | None
    family_id: str
    is_representative: bool
    supersedes: bool
    confidence: float | None       # Story 4.4 — None == not derived (AD-19)
    confidence_signals: str | None  # the comma-joined observable signals, None when not derived


@dataclass(frozen=True)
class CurrentLabel:
    """A *pièce*'s CURRENT taxonomy label (Story 4.5, FR-40) — a VIEW over the append-only ledger.
    ``label`` is NEVER null: a taxonomy member, or the explicit ``unlabelled`` when the *pièce* has
    no assignment. ``seq``/``source`` are None only for that never-labelled default.
    ``in_current_taxonomy`` is False when the label was valid when set but the taxonomy has since
    changed (FR-40 — such a label is shown as such, never silently remapped or nulled)."""

    piece_id: str
    label: str
    source: str | None
    seq: int | None
    in_current_taxonomy: bool


@dataclass(frozen=True)
class LabelChangeEntry:
    """One entry in a *pièce*'s taxonomy-label change log (Story 4.5, FR-40/FR-20) — append-only, in
    ``seq`` order. An assignment or a reversal is a distinct entry; the history is never rewritten
    (AD-7). ``set_by``/``at`` make each edit attributable and reversible from the log."""

    seq: int
    label: str
    source: str
    set_by: str
    at: datetime


@dataclass(frozen=True)
class LabelCoverage:
    """The SM-19 per-*matter* labelling figures over the *pièces* of the latest *ranking version*:
    ``total`` pièces, how many carry a real (non-``unlabelled``) label, the ``unlabelled`` share,
    and how many carry a label no longer in the taxonomy (``out_of_taxonomy`` — the
    zero-silently-remapped evidence). ``without_label`` is always zero by construction (every pièce
    has exactly one label — a member or ``unlabelled``), so SM-19's first figure is explicit."""

    total: int
    labelled: int
    unlabelled: int
    unlabelled_share: float
    out_of_taxonomy: int
    without_label: int


@dataclass(frozen=True)
class VersionRetentionView:
    """The retained-ranking-versions bound status for a *matter* (Story 4.7, FR-16). ``total`` is
    the number of *ranking versions* held; ``bound`` the configured maximum; ``over_bound`` how many
    exceed the most-recent-``bound`` window. Informational only — 4.7 **retires nothing** (AD-7's
    `retired` transition through the one admin entry point, and the full referenced-by exemption
    — bound/pin/export/audit — are deferred), so nothing is ever deleted from this count."""

    total: int
    bound: int
    over_bound: int


@dataclass(frozen=True)
class DuplicateGroup:
    representative: str        # provenance path of the piece judged for the group
    members: tuple[str, ...]   # provenance paths of every copy, representative included
    size: int


@dataclass(frozen=True)
class DedupSummary:
    submitted: int   # corpus pieces considered
    distinct: int    # what remains to examine (clusters, singletons included)
    duplicates: int  # copies collapsed into a representative (kept, not deleted)
    groups: tuple[DuplicateGroup, ...]  # multi-member groups only


@dataclass(frozen=True)
class LabelledPiece:
    provenance: str
    label: str
    rationale: str


@dataclass(frozen=True)
class LabelSummary:
    relevant: int
    uncertain: int
    discarded: int
    judged: int
    pieces: tuple[LabelledPiece, ...]


@dataclass(frozen=True)
class SearchHit:
    matter: str
    provenance: str
    snippet: str


@dataclass(frozen=True)
class SearchResults:
    query: str
    total: int                       # true count of matching pieces, even when hits is capped
    hits: tuple[SearchHit, ...]


def _like_escape(s: str) -> str:
    """Escape LIKE wildcards so a query is matched literally (escape char: backslash)."""
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@dataclass(frozen=True)
class SampledDiscard:
    piece_id: str
    provenance: str
    excerpt: str


@dataclass(frozen=True)
class RecallSample:
    population: int                       # the whole discard pile
    sample: tuple[SampledDiscard, ...]    # the pieces drawn for review


@dataclass(frozen=True)
class RecallResult:
    population: int
    sample_size: int
    relevant_found: int      # false discards found in the sample
    confidence: float
    count_upper: int         # at most this many of the pile were wrongly discarded
    prevalence_upper: float


def _excerpt(text: str, width: int = 240) -> str:
    flat = " ".join(text.split())
    return flat[:width] + ("…" if len(flat) > width else "")


# Story 3.5b: a coarse media kind for the viewer, DERIVED from the filename extension (no new
# column). The renderer (3.5c) refines this; the viewer (3.5d) branches on it.
_MEDIA_KIND_BY_EXT = {
    ".pdf": "pdf",
    ".msg": "email", ".eml": "email",
    ".xlsx": "spreadsheet", ".xls": "spreadsheet", ".csv": "spreadsheet", ".ods": "spreadsheet",
    ".docx": "document", ".doc": "document", ".rtf": "document", ".txt": "document",
    ".odt": "document",
    ".png": "image", ".jpg": "image", ".jpeg": "image", ".tif": "image", ".tiff": "image",
    ".gif": "image", ".bmp": "image", ".webp": "image",
}


def _media_kind(filename: str) -> str:
    ext = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""
    return _MEDIA_KIND_BY_EXT.get(ext, "other")


def _basename(provenance_path: str) -> str:
    """The representative filename shown in the viewer — the last path segment of the (decrypted)
    provenance path. A container member's provenance is ``outer/inner.ext``; its basename is
    ``inner.ext`` (both '/' and '\\' separators handled)."""
    return provenance_path.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1] or provenance_path


def _failure_id(tenant: str, matter: str | None, submitted_path: str) -> str:
    """A register entry's deterministic id — tenant-qualified (AD-12), exactly as ``piece_id`` is:
    a matter name is tenant-local, so WITHOUT the tenant two firms sharing a matter name and a path
    would collide on one PK and one firm's ingest would `merge`-overwrite the other's entry (a
    Chinese-wall breach, AD-7 'never removed'). ``matter`` is None for an undetermined entry."""
    return hashlib.sha256(f"{tenant}\x00{matter or ''}\x00{submitted_path}".encode()).hexdigest()


def _unit_id(job_id: str, provenance: str) -> str:
    """A deterministic import-unit id, so enumeration and resume are idempotent (Story 2.2)."""
    return hashlib.sha256(f"{job_id}\x00{provenance}".encode()).hexdigest()


def _noise_id(tenant: str, matter: str, submitted_path: str) -> str:
    """A noise-exclusion row's deterministic id — tenant+matter-qualified, exactly like
    ``_failure_id``: re-importing the same file is idempotent (insert-if-absent, so it never
    double-counts, Story 2.5), and two matters/firms never collide on one PK (Story 2.7)."""
    return hashlib.sha256(f"{tenant}\x00{matter}\x00{submitted_path}".encode()).hexdigest()


def _config_value(spec: ConfigKey, row: TenantSetting | None) -> object:
    """A setting row's value coerced to the key's declared type, or the schema default when the
    row is absent or its stored value is unreadable (fail safe to the default — a value that
    never came through the audited surface is caught by ``config_provenance``, not here)."""
    if row is None:
        return spec.default
    try:
        return spec.coerce(loads_value(row.value))
    except ValueError:
        return spec.default


def _config_change_detail(key: str, before: object, after: object, retrieval: bool) -> str:
    """The audit detail for one config change — a JSON object (not a fragile ``k=v`` line, since
    ``before``/``after`` are arbitrary JSON values that could contain any delimiter). Carries the
    retrieval-staleness flag (AD-23) when set. ``config_provenance`` parses it back structurally."""
    payload: dict[str, object] = {"key": key, "before": before, "after": after}
    if retrieval:
        payload["retrieval"] = True
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _parse_config_detail(detail: str) -> tuple[str, object] | None:
    """Recover (key, after-value) from a ``config_changed`` audit detail, or None if it is not a
    parseable config change (only ``config_changed`` details are ever passed here)."""
    try:
        obj = json.loads(detail)
    except ValueError:
        return None
    if not isinstance(obj, dict) or "key" not in obj or "after" not in obj:
        return None
    return obj["key"], obj["after"]


def _audit_ts(dt: datetime) -> str:
    """The canonical timestamp string for the chain: UTC, tz-naive, microseconds.
    The chain must recompute to the SAME bytes whichever backend round-trips the
    column — SQLite drops the tzinfo, Postgres timestamptz keeps it — so we
    normalise to a single representation on BOTH the write and the verify side.
    Without this, an untampered chain would fail to verify across backends."""
    if dt.tzinfo is not None:
        dt = dt.astimezone(UTC).replace(tzinfo=None)
    return dt.isoformat(timespec="microseconds")


def _as_utc(dt: datetime) -> datetime:
    """An aware-UTC datetime for comparison. A read-back value is tz-naive on SQLite (it
    drops the tzinfo) and aware on Postgres; treat a naive value as UTC so aware/naive
    comparisons never explode."""
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def _audit_content(seq: int, tenant: str, matter: str | None, actor: str, action: str,
                   detail: str, ts: str) -> str:
    return f"{seq}|{tenant}|{matter or ''}|{actor}|{action}|{detail}|{ts}"


def _audit_chain(prev_chain: str, content: str) -> str:
    return hashlib.sha256(f"{prev_chain}\x00{content}".encode()).hexdigest()


def _safe_decrypt(ciphertext: str | None, context: str) -> str | None:
    """Decrypt a raw-read encrypted column, or ``None`` if it cannot be authenticated — a
    tamper, the wrong key, or a legacy plaintext value. Lets the audit read degrade ONE bad row
    to verified=False instead of 500-ing the whole tenant trail (FR-24 tamper-evidence)."""
    if ciphertext is None:
        return None
    try:
        return cipher().decrypt(ciphertext, aad=context)
    except DecryptionError:
        return None


class SqlStore:
    def __init__(
        self, session_factory: sessionmaker[Session], head_journal: HeadJournal | None = None
    ) -> None:
        self._sf = session_factory
        self._journal = head_journal
        self.journal_degraded = False  # set if a post-commit head write failed (surfaced, AC5)
        if head_journal is not None and not getattr(session_factory, "_apx_head_listener", False):
            # Record each new chain head to the journal AS IT ADVANCES (AD-35 "on every append").
            # Capture the pending heads during flush; write them AFTER commit — a file append is
            # not transactional, so journaling after commit avoids a journal entry ahead of a
            # rolled-back write (which would false-positive a truncation). A post-commit write
            # failure is surfaced as degraded, never silent (AC5). The sentinel makes registration
            # idempotent: re-wrapping ONE session factory (a cleared _store() cache) never
            # double-writes each head.
            session_factory._apx_head_listener = True
            event.listen(session_factory, "before_flush", self._capture_heads)
            event.listen(session_factory, "after_commit", self._write_heads)

    def _capture_heads(self, session: Session, _ctx: object, _instances: object) -> None:
        pending = [
            (obj.tenant, obj.seq, obj.chain)
            for obj in session.new if isinstance(obj, AuditRecord)
        ]
        if pending:
            prior = session.info.get("_apx_heads", [])
            session.info["_apx_heads"] = prior + pending

    def _write_heads(self, session: Session) -> None:
        heads = session.info.pop("_apx_heads", None)
        if not heads or self._journal is None:
            return
        highest: dict[str, tuple[int, str]] = {}
        for tenant, seq, chain in heads:  # keep the highest seq per tenant from this commit
            if tenant not in highest or seq > highest[tenant][0]:
                highest[tenant] = (seq, chain)
        now = _audit_ts(datetime.now(UTC))
        for tenant, (seq, chain) in highest.items():
            try:
                self._journal.record(HeadEntry(
                    tenant, seq, chain, now, _APP_VERSION, _HEAD_SCHEMA_VERSION))
            except OSError as exc:
                # Surfaced two ways, never silent (AC5): a WARNING log now, and the sticky
                # `journal_degraded` flag the DR status reads. A head we could not record means a
                # later restore-truncation to this point could go undetected — an operator alarm.
                self.journal_degraded = True
                _log.warning(
                    "head journal write failed for tenant %s at seq %s: %s", tenant, seq, exc)

    def _append_audit(self, session: Session, tenant: str, matter: str | None,
                      actor: str, action: str, detail: str, ts: datetime) -> None:
        """Append one entry inside the caller's transaction (atomic with the act,
        FR-53). Monotonic per-tenant seq; chained over the previous entry."""
        last = session.execute(
            select(AuditRecord.seq, AuditRecord.chain)
            .where(AuditRecord.tenant == tenant)
            .order_by(AuditRecord.seq.desc())
            .limit(1)
        ).first()
        prev_seq, prev_chain = (last[0], last[1]) if last else (0, "")
        seq = prev_seq + 1
        content = _audit_content(seq, tenant, matter, actor, action, detail, _audit_ts(ts))
        chain = _audit_chain(prev_chain, content)
        session.add(
            AuditRecord(
                id=chain, tenant=tenant, seq=seq, matter=matter, actor=actor,
                action=action, detail=detail, chain=chain, timestamp=ts,
            )
        )

    def save(
        self,
        result: IngestionResult,
        scope: str,
        actor: str = "unknown",
        *,
        matter: str | None = None,
        tenant: str | None = None,
        case_theory: str | None = None,
        audit: bool = True,
    ) -> SaveOutcome:
        # Fail closed: a null/empty/whitespace scope is never permissive (AD-12). The guard
        # lives here at the persist boundary, so no caller — API, CLI or test — can write a
        # piece under no wall, even one that bypasses the API's _held_wall (Story 2.1 AC6).
        if not scope or not scope.strip():
            raise UnauthorizedScope("an empty RBAC scope is never authorised (fail closed)")
        # A skipped case theory never persists as "" — the persist boundary owns this rule
        # symmetrically with the scope guard, so no caller can wipe a theory to an empty string.
        case_theory = (case_theory or "").strip() or None
        now = result.pieces[0].ingestion_timestamp if result.pieces else datetime.now(UTC)
        # matter/tenant come from the caller when given — so a folder of zero readable files
        # still creates a durable matter and its audit entry (Story 2.1 AC5) — and are derived
        # from the result otherwise (the pre-2.1 behaviour, unchanged for existing callers).
        if matter is None:
            matter = result.pieces[0].matter if result.pieces else (
                result.failures[0].matter if result.failures else None
            )
        if tenant is None:
            tenant = result.pieces[0].tenant if result.pieces else (
                result.failures[0].tenant if result.failures else None
            )
        with self._sf() as session, session.begin():
            if matter is not None and tenant is not None:
                # A matter's wall may only move via the audited admin re-scope path — never
                # silently through a re-ingest (the 1.6 review High). Create on first ingest;
                # refuse an ingest that would change an existing matter's scope.
                existing = session.get(MatterScope, {"tenant": tenant, "matter": matter})
                if existing is None:
                    session.add(MatterScope(
                        matter=matter, tenant=tenant, scope=scope, case_theory=case_theory))
                elif existing.scope != scope:
                    raise ScopeConflict(
                        f"matter {matter!r} already exists under a different scope; "
                        "re-scope via the admin path")
                elif case_theory is not None:
                    # A restated case theory updates in place; a skipped one (None) never wipes
                    # an existing one (FR-37: statable at import or later). Versioning is Epic 4.
                    existing.case_theory = case_theory
            pieces_new = 0
            pieces_already_present = 0
            seen: set[str] = set()
            for p in result.pieces:
                # Insert-if-absent — NEVER overwrite (AC2 "readable and unmodified"); the v1
                # defect was `merge`, which overwrote provenance/custodian/timestamp on re-import.
                if self._insert_piece_if_absent(session, p, seen):
                    pieces_new += 1
                else:
                    pieces_already_present += 1
                # Union the provenance path and the custodian into the pièce's SETS on EVERY
                # import — new or already-present — never replaced or collapsed (AD-8/AD-9). So a
                # second import under a different custodian keeps both; two folders keep both paths.
                self._insert_link_if_absent(
                    session, PieceProvenance, p.id, "provenance_path", p.provenance_path)
                self._insert_link_if_absent(
                    session, PieceCustodian, p.id, "custodian", p.custodian)
            for f in result.failures:
                self._write_failure(session, f, now)
            if matter is not None and tenant is not None:
                for prov in result.exclusions:
                    # Filesystem noise (FR-6): a durable, countable, listable line —
                    # insert-if-absent by (tenant, matter, path) so a re-import never double-counts
                    # (Story 2.5). Not a pièce, not a register entry; the path is client data
                    # (AD-41), encrypted at rest.
                    nid = _noise_id(tenant, matter, prov)
                    if session.get(NoiseExclusion, nid) is None:
                        session.add(NoiseExclusion(
                            id=nid, tenant=tenant, matter=matter, submitted_path=prov,
                            filename=prov.replace("\\", "/").rsplit("/", 1)[-1], timestamp=now))
                # Story 2.7: raise the durable submitted_pieces watermark from the new known
                # population (counted after this result's pieces + failures are flushed).
                self._raise_submitted_watermark(session, matter, tenant)
            if matter is not None and tenant is not None and audit:
                # One `ingest` audit entry per call, appended AFTER the loop so it carries the
                # recognised-already-present count as its own field (AC2) — a re-import no-op is
                # then distinguishable from a real ingest on the trail, not silently identical. The
                # resumable worker (Story 2.2) commits units with audit=False and writes ONE
                # job-level entry at completion (its already-present breakdown is the completion
                # summary's job, Story 2.10), so a 100 000-unit import is one audit row, not 100k.
                inv = result.inventory
                detail = (
                    f"submitted_pieces={inv.submitted_pieces} in_corpus={inv.in_corpus} "
                    f"already_present={pieces_already_present} "
                    f"open_register={inv.open_register_entries} noise={inv.excluded_as_noise}"
                )
                self._append_audit(session, tenant, matter, actor, "ingest", detail, now)
        return SaveOutcome(pieces_new, pieces_already_present, len(result.failures))

    def _insert_piece_if_absent(
        self, session: Session, p: IngestedPiece, seen: set[str]
    ) -> bool:
        """Insert the pièce row IF it is absent; NEVER overwrite an existing one (AC2 — a prior
        pièce stays readable and unmodified). Returns True when newly inserted, False when already
        present (this same result, the DB, or a worker that won a concurrent race). Conflict-safe
        (AC5): a PK/unique collision is absorbed via a SAVEPOINT so exactly one copy survives and
        the job does not fail. The `custodian` is NOT a column here (AD-9) — it is unioned into the
        set separately; `provenance_path` is the first-seen representative, never re-stamped."""
        if p.id in seen or session.get(Piece, p.id) is not None:
            seen.add(p.id)
            return False
        row = Piece(
            id=p.id, tenant=p.tenant, matter=p.matter, content_hash=p.content_hash,
            text_key=p.text_key, provenance_path=p.provenance_path,
            extraction_method=p.extraction_method, extractor_version=p.extractor_version,
            schema_version=p.schema_version, ingestion_timestamp=p.ingestion_timestamp,
            piece_date=None, piece_date_status="undetermined", full_text=p.full_text,
            text_identity=hashlib.sha256(p.full_text.encode()).hexdigest(),
            text_version=p.text_version)
        try:
            with session.begin_nested():  # SAVEPOINT: a concurrent insert of the same id rolls
                session.add(row)          # back to here, not the whole import (AC5)
                session.flush()
        except IntegrityError:
            # ONLY a concurrent insert of the SAME id is "already present" — the row is there now.
            # Any OTHER integrity failure (a malformed pièce: NOT NULL / CHECK) is a genuine fault,
            # never a duplicate: re-raise so it fails the unit loudly rather than vanishing, wrongly
            # counted as already-present. The outer transaction rolls back, so no orphan link row
            # survives either. `seen` is advanced only on a genuine outcome (found / inserted /
            # confirmed-present), so a re-raised malformed pièce never masks a valid same-id twin.
            if session.get(Piece, p.id) is None:
                raise
            seen.add(p.id)
            return False
        seen.add(p.id)
        return True

    def _insert_link_if_absent(
        self, session: Session, model: type, piece_id: str, col: str, value: str
    ) -> None:
        """Union one value into a pièce's provenance/custodian SET (AD-8/AD-9) — insert-if-absent
        keyed by the deterministic ``link_id`` so a repeat is one row and a concurrent double-insert
        is absorbed (SAVEPOINT). Never replaces or collapses an existing member."""
        lid = link_id(piece_id, value)
        if session.get(model, lid) is not None:
            return
        try:
            with session.begin_nested():
                session.add(model(id=lid, piece_id=piece_id, **{col: value}))
                session.flush()
        except IntegrityError:
            # Absorb ONLY a genuine concurrent duplicate (the member is present now); re-raise any
            # other integrity failure (e.g. a NOT NULL from a blank value) so it is never a silent
            # drop that leaves a pièce with an empty set.
            if session.get(model, lid) is None:
                raise

    def provenances(self, piece_id: str) -> set[str]:
        """Every recorded provenance path of a pièce — the set, decrypted (AD-8: a pièce may
        carry several; path is an attribute, not identity)."""
        with self._sf() as session:
            return set(session.scalars(
                select(PieceProvenance.provenance_path).where(
                    PieceProvenance.piece_id == piece_id)))

    def custodians(self, piece_id: str) -> set[str]:
        """Every custodian who held a pièce — the CUSTODIAN_LINK set (AD-9), unioned across
        imports and never collapsed, so who held a document survives deduplication (FR-4)."""
        with self._sf() as session:
            return set(session.scalars(
                select(PieceCustodian.custodian).where(PieceCustodian.piece_id == piece_id)))

    # ── Story 2.2: the application-owned import-job ledger (AD-17) ──────────────────────────
    # The SOLE authority for a job's state and the processed-against-submitted figure. Every
    # method opens its own transaction; the attempt counter and the quarantine transition are
    # deliberately independent commits (the two load-bearing AD-17 mechanics).

    def open_import_job(self, tenant: str, matter: str) -> str | None:
        """The id of an open (not-done) import job for this matter, if any — FR-7's one-open-job
        rule, so a re-submit returns the existing job rather than starting a second."""
        with self._sf() as session:
            return session.scalar(
                select(ImportJob.id).where(
                    ImportJob.tenant == tenant, ImportJob.matter == matter,
                    ImportJob.state != "done"))

    def create_import_job(
        self, *, job_id: str, tenant: str, matter: str, scope: str, actor: str,
        custodian: str, case_theory: str | None, spool_path: str, owns_spool: bool = True,
        now: datetime,
    ) -> None:
        """Create the job ledger row (state=enumerating, submitted provisional). Idempotent by id.
        ``owns_spool`` = the worker deletes ``spool_path`` on completion (an uploaded spool), vs.
        a server-local source folder it must not touch."""
        with self._sf() as session, session.begin():
            if session.get(ImportJob, job_id) is None:
                session.add(ImportJob(
                    id=job_id, tenant=tenant, matter=matter, scope=scope, actor=actor,
                    custodian=custodian, case_theory=case_theory, spool_path=spool_path,
                    owns_spool=owns_spool, state="enumerating", submitted=None, provisional=True,
                    created_at=now, updated_at=now))

    def delete_import_job(self, job_id: str) -> None:
        """Remove a job and its units (no audit) — rolls back a job whose enqueue failed, so the
        matter's upload path is not wedged by a stuck `enumerating` row (review Med-6)."""
        with self._sf() as session, session.begin():
            session.execute(delete(ImportUnit).where(ImportUnit.job_id == job_id))
            j = session.get(ImportJob, job_id)
            if j is not None:
                session.delete(j)

    def read_import_job(self, job_id: str) -> ImportJobView | None:
        with self._sf() as session:
            j = session.get(ImportJob, job_id)
            if j is None:
                return None
            return ImportJobView(
                j.id, j.tenant, j.matter, j.scope, j.actor, j.custodian, j.case_theory,
                j.spool_path, j.owns_spool, j.state, j.submitted, j.provisional)

    def record_enumeration(self, job_id: str, provenances: list[str], now: datetime) -> None:
        """Freeze the submitted set and record every unit (idempotent — resume-safe): units go in
        pending, the job goes running with submitted frozen and provisional cleared (AD-17)."""
        with self._sf() as session, session.begin():
            j = session.get(ImportJob, job_id)
            if j is None:
                return
            existing = set(session.scalars(
                select(ImportUnit.id).where(ImportUnit.job_id == job_id)))
            for prov in provenances:
                uid = _unit_id(job_id, prov)
                if uid not in existing:
                    session.add(ImportUnit(
                        id=uid, job_id=job_id, provenance_path=prov, state="pending", attempts=0))
            if j.submitted is None:   # freeze write-once (AD-17) — never re-derive on a resume
                j.submitted = len(provenances)
                j.provisional = False
            if j.state == "enumerating":
                j.state = "running"
            j.updated_at = now

    def pending_units(self, job_id: str) -> list[tuple[str, str]]:
        """(unit_id, provenance) for units not yet processed — the resume work list."""
        with self._sf() as session:
            rows = session.execute(
                select(ImportUnit.id, ImportUnit.provenance_path).where(
                    ImportUnit.job_id == job_id, ImportUnit.state == "pending")).all()
        return [(r[0], r[1]) for r in rows]

    def bump_import_attempt(self, unit_id: str) -> int:
        """Increment a unit's attempt counter in its OWN transaction, committed BEFORE the unit's
        work begins, so an OS-level kill still advances it and resume never loops onto the poison
        forever (AD-17). Returns the new count."""
        with self._sf() as session, session.begin():
            u = session.get(ImportUnit, unit_id)
            if u is None:
                return 0
            u.attempts += 1
            return u.attempts

    def mark_unit_committed(self, unit_id: str) -> None:
        with self._sf() as session, session.begin():
            u = session.get(ImportUnit, unit_id)
            if u is not None and u.state == "pending":
                u.state = "committed"

    def quarantine_unit(
        self, *, unit_id: str, provenance: str, matter: str, tenant: str, now: datetime,
        custodian: str | None = None,
    ) -> None:
        """Quarantine a poison unit in a transaction INDEPENDENT of the failing unit's (AD-17):
        flip the unit AND write its `quarantined` failure-register entry together here, so an
        exception handler running inside the failing unit's transaction cannot roll it back and
        retry the poison forever. The entry carries the job's `custodian` (where known) and
        cardinality `one` (a quarantined unit is one pièce), like every register entry (FR-5)."""
        with self._sf() as session, session.begin():
            u = session.get(ImportUnit, unit_id)
            if u is not None:
                u.state = "quarantined"
            session.merge(Failure(
                id=_failure_id(tenant, matter, provenance), tenant=tenant, matter=matter,
                filename=provenance.rsplit("/", 1)[-1], submitted_path=provenance,
                custodian=custodian, error_class=str(ErrorClass.QUARANTINED),
                cardinality=cardinality_for(ErrorClass.QUARANTINED), resolution_state="open",
                detail="repeatedly killed the worker; quarantined after the configured attempts",
                timestamp=now))
            # Story 2.7: a quarantined unit is a newly-submitted pièce that failed — raise the
            # watermark so the inventory invariant holds at completion (open grew by one).
            self._raise_submitted_watermark(session, matter, tenant)

    def finish_import(self, job_id: str, now: datetime) -> None:
        """Mark the job done and write ONE job-level `ingest` audit entry (AD-6 — one entry per
        job, not per unit). Idempotent (a re-run after completion writes nothing)."""
        with self._sf() as session, session.begin():
            j = session.get(ImportJob, job_id)
            if j is None or j.state == "done":
                return
            committed = session.scalar(select(func.count()).select_from(ImportUnit).where(
                ImportUnit.job_id == job_id, ImportUnit.state == "committed")) or 0
            quarantined = session.scalar(select(func.count()).select_from(ImportUnit).where(
                ImportUnit.job_id == job_id, ImportUnit.state == "quarantined")) or 0
            detail = (f"submitted={j.submitted or 0} committed={committed} "
                      f"quarantined={quarantined}")
            # Story 2.7 (SM-3): the inventory guarantee MUST hold at completion — a violation is a
            # release blocker, raised loudly (and rolls back this tx), never a job silently marked
            # done over a lost pièce. submitted_pieces == in_corpus + open_register_entries.
            self._durable_inventory(session, j.matter, j.tenant).require_consistent()
            self._append_audit(session, j.tenant, j.matter, j.actor, "ingest", detail, now)
            j.state = "done"
            j.updated_at = now

    def import_progress(self, job_id: str) -> ImportProgress | None:
        """The processed-against-submitted figure, read ONLY from the ledger (AD-17 — never from
        Procrastinate's job table)."""
        with self._sf() as session:
            j = session.get(ImportJob, job_id)
            if j is None:
                return None

            def _count(state: str) -> int:
                return session.scalar(select(func.count()).select_from(ImportUnit).where(
                    ImportUnit.job_id == job_id, ImportUnit.state == state)) or 0

            committed, quarantined, pending = _count("committed"), _count("quarantined"), _count(
                "pending")
            return ImportProgress(
                job_id, j.tenant, j.matter, j.state, j.submitted, committed + quarantined,
                committed, quarantined, pending, j.provisional)

    def existing_piece_ids(self, tenant: str, matter: str, ids: list[str]) -> set[str]:
        """Which of ``ids`` are ALREADY corpus pièces for this matter (Story 2.8). A pièce already
        in the corpus has met the embed-precondition, so re-ingestion must NOT re-embed it — a
        re-embed failure on an already-admitted pièce would double-count it (in_corpus AND a new
        register entry, masked by the 2.7 watermark). Empty ``ids`` → empty set (no query)."""
        if not ids:
            return set()
        with self._sf() as session:
            rows = session.scalars(select(Piece.id).where(
                Piece.tenant == tenant, Piece.matter == matter, Piece.id.in_(ids))).all()
        return set(rows)

    def _counts(self, session: Session, matter: str, tenant: str) -> tuple[int, int]:
        in_corpus = session.scalar(
            select(func.count()).select_from(Piece).where(
                Piece.matter == matter, Piece.tenant == tenant
            )
        ) or 0
        failures = session.scalar(
            select(func.count()).select_from(Failure).where(
                Failure.matter == matter, Failure.tenant == tenant,
                Failure.resolution_state == "open",
            )
        ) or 0
        return in_corpus, failures

    def _raise_submitted_watermark(self, session: Session, matter: str, tenant: str) -> None:
        """Raise the durable ``submitted_pieces`` high-water mark to the current known population on
        a SUBMISSION (AD-38 / AD-17). Monotonic — ``max(...)`` so it never shrinks below a submitted
        pièce; a genuinely new pièce/failure raises it, an idempotent re-import leaves it untouched.
        It is never recomputed as the sum at READ time — that independence is what lets it catch a
        pièce lost outside the normal flow. Called by ``save`` and ``quarantine_unit`` (the
        submission paths). A RESOLVE uses ``_settle_submitted_after_retry`` instead, because a
        resolution to a content-DUPLICATE legitimately LOWERS the distinct count (a failed duplicate
        was never a distinct pièce), which a monotonic max would wrongly flag as a lost pièce."""
        in_corpus, open_failures = self._counts(session, matter, tenant)
        ms = session.get(MatterScope, {"tenant": tenant, "matter": matter})
        if ms is not None:
            ms.submitted_pieces = max(ms.submitted_pieces, in_corpus + open_failures)

    def _settle_submitted_after_retry(self, session: Session, matter: str, tenant: str) -> None:
        """Settle ``submitted_pieces`` to the reconciled known population after a RETRY (AD-38). A
        retry resolves an entry to a NEW pièce (in_corpus +1 / open -1, net zero), to a content-
        DUPLICATE already in the corpus (in_corpus flat / open -1 — the failed entry was never a
        distinct pièce, so the distinct count legitimately drops by one), or records fresh member
        failures (open +N). In every case ``in_corpus + open_register_entries`` is the new true
        distinct-submitted count, so we SET it (not ``max``) — otherwise a dedup-collapse leaves the
        frozen watermark ABOVE the live sum and falsely trips SM-3 (the retry would crash and the
        entry could never resolve; a bulk retry would persist a wedged matter). A pièce lost outside
        the normal flow is still caught: a raw deletion runs no retry, so the next
        read / ``finish_import`` sees the stale high mark and raises."""
        in_corpus, open_failures = self._counts(session, matter, tenant)
        ms = session.get(MatterScope, {"tenant": tenant, "matter": matter})
        if ms is not None:
            ms.submitted_pieces = in_corpus + open_failures

    def _durable_inventory(self, session: Session, matter: str, tenant: str) -> Inventory:
        """The six-field *denominator* (AD-38) from the durable ledger. ``submitted_pieces`` is the
        FROZEN high-water mark (read, never recomputed as the sum — Story 2.7); ``in_corpus`` and
        ``open_register_entries`` are counted live (their identity is the SM-3 check);
        ``excluded_as_noise`` and ``unknown_cardinality_entries`` are counted durably (Story 2.7
        Task 3/4); ``retired`` is reserved (0 — no retirement transition exists yet, AD-7)."""
        in_corpus, open_failures = self._counts(session, matter, tenant)
        submitted = session.scalar(
            select(MatterScope.submitted_pieces).where(
                MatterScope.matter == matter, MatterScope.tenant == tenant
            )
        ) or 0
        unknown = session.scalar(
            select(func.count()).select_from(Failure).where(
                Failure.matter == matter, Failure.tenant == tenant,
                Failure.resolution_state == "open", Failure.cardinality == "unknown",
            )
        ) or 0
        excluded = session.scalar(
            select(func.count()).select_from(NoiseExclusion).where(
                NoiseExclusion.matter == matter, NoiseExclusion.tenant == tenant
            )
        ) or 0
        return Inventory(
            submitted_pieces=submitted, in_corpus=in_corpus, open_register_entries=open_failures,
            excluded_as_noise=excluded, unknown_cardinality_entries=unknown,
        )

    def matters(self, tenant: str, scopes: set[str]) -> list[MatterSummary]:
        """Every matter the caller may see — pre-filtered by scope IN the query."""
        if not scopes:
            return []  # fail closed: no scope, no matters
        with self._sf() as session:
            rows = session.execute(
                select(MatterScope.matter, MatterScope.scope).where(
                    MatterScope.tenant == tenant, MatterScope.scope.in_(scopes)
                )
            ).all()
            out = [
                MatterSummary(matter, scope, self._durable_inventory(session, matter, tenant))
                for matter, scope in rows
            ]
        return sorted(out, key=lambda m: m.matter)

    def inventory(self, matter: str, tenant: str, scopes: set[str]) -> Inventory:
        """The durable inventory for one matter — refused if its scope is not held."""
        with self._sf() as session:
            scope = session.scalar(
                select(MatterScope.scope).where(
                    MatterScope.matter == matter, MatterScope.tenant == tenant
                )
            )
            if scope is None or scope not in scopes:
                raise ScopeDenied(matter)  # fail closed, and never disclose existence
            return self._durable_inventory(session, matter, tenant)

    # ── Story 2.6: the failure register (FR-5; AD-37 conditional commits, AD-7 never removed) ──

    def _register_entry(self, f: Failure) -> RegisterEntry:
        return RegisterEntry(
            id=f.id, matter=f.matter, filename=f.filename, submitted_path=f.submitted_path,
            custodian=f.custodian, error_class=f.error_class, cardinality=f.cardinality,
            resolution_state=f.resolution_state, timestamp=_as_utc(f.timestamp).isoformat(),
            retryable=f.resolution_state == "open")

    def register(self, matter: str, tenant: str, scopes: set[str]) -> list[RegisterEntry]:
        """The durable failure register for one matter — scope-checked; OPEN and RESOLVED entries
        (a resolved entry is kept as history, never removed — AD-7), deterministically ordered."""
        with self._sf() as session:
            scope = session.scalar(select(MatterScope.scope).where(
                MatterScope.matter == matter, MatterScope.tenant == tenant))
            if scope is None or scope not in scopes:
                raise ScopeDenied(matter)
            rows = session.scalars(select(Failure).where(
                Failure.tenant == tenant, Failure.matter == matter)).all()
            entries = [self._register_entry(f) for f in rows]
        return sorted(entries, key=lambda e: (e.resolution_state, e.submitted_path, e.id))

    def search_semantic(
        self, *, tenant: str, scopes: set[str], query_vector: list[float], k: int,
        min_similarity: float,
    ) -> list[SemanticResult]:
        """The scoped semantic nearest-neighbour search (Story 3.1, the ``SemanticReader`` port). Up
        to ``k`` chunks ranked by descending cosine similarity, scope joined from ``matter_scope``
        as a query PRE-filter (AD-13). An empty scope reads nothing and runs no query (fail-closed,
        AD-12). The ``<=>`` cosine operator is PostgreSQL-native (halfvec)."""
        if not scopes:
            return []
        stmt = semantic_search_stmt(
            tenant=tenant, scopes=scopes, query_vector=query_vector, k=k,
            min_similarity=min_similarity,
        )
        with self._sf() as session:
            rows = session.execute(stmt).all()
        return results_from_rows(rows)

    def resolve_chunk(
        self, chunk_id: str, tenant: str, scopes: set[str], *, expected_text: str | None = None,
    ) -> ResolvedPassage | FailedResolution:
        """Resolve a stored chunk to its exact source passage (Story 2.9, FR-11) — scope-checked.
        Re-chunks the pièce's stored full text under the tenant's current chunking configuration and
        takes the chunk's ``position`` (provenance by resolution, AD-9/AD-10). Returns a
        ``FailedResolution`` — never a passage — for a gone pièce, text changed under re-extraction,
        a superseded config, a lost position, or (with ``expected_text``) a stored extract no longer
        contained. Fail-closed on scope: an out-of-scope or unknown chunk is refused and its
        existence never disclosed."""
        cfg = chunking_config(lambda k: self.get_config(tenant, k))  # resolved before the session
        with self._sf() as session:
            ch = session.get(Chunk, chunk_id)
            if ch is None or ch.tenant != tenant:
                raise ScopeDenied(chunk_id)  # never disclose whether the chunk exists
            scope = session.scalar(select(MatterScope.scope).where(
                MatterScope.matter == ch.matter, MatterScope.tenant == tenant))
            if scope is None or scope not in scopes:
                # echo ONLY the caller-supplied chunk_id — never the derived matter — so this branch
                # is indistinguishable from the unknown-chunk branch above: neither the chunk's
                # existence nor its matter leaks across the Chinese wall (AD-13; review MED-2).
                raise ScopeDenied(chunk_id)
            piece = session.get(Piece, ch.piece_id)
            if piece is None:  # no hard delete (AD-7), but the resolver stays honest if it dangles
                return FailedResolution(PIECE_GONE)
            return resolve_passage(
                full_text=piece.full_text, piece_text_version=piece.text_version,
                piece_text_identity=piece.text_identity,
                chunk_full_text_version=ch.full_text_version, chunk_position=ch.position,
                chunk_config_version=ch.chunking_config_version, config=cfg,
                expected_text=expected_text)

    def noise_exclusions(
        self, matter: str, tenant: str, scopes: set[str]
    ) -> list[NoiseExclusionEntry]:
        """The durable filesystem-noise list for one matter — scope-checked, decrypted, ordered
        (FR-6, the "one click from the list of what was excluded" backend). The screen is a UX-pass
        concern; this is the tested contract behind the ``excluded_as_noise`` denominator line."""
        with self._sf() as session:
            scope = session.scalar(select(MatterScope.scope).where(
                MatterScope.matter == matter, MatterScope.tenant == tenant))
            if scope is None or scope not in scopes:
                raise ScopeDenied(matter)  # fail closed, and never disclose existence
            rows = session.scalars(select(NoiseExclusion).where(
                NoiseExclusion.tenant == tenant, NoiseExclusion.matter == matter)).all()
            entries = [
                NoiseExclusionEntry(
                    matter=n.matter, filename=n.filename, submitted_path=n.submitted_path,
                    timestamp=_as_utc(n.timestamp).isoformat())
                for n in rows
            ]
        return sorted(entries, key=lambda e: e.submitted_path)

    def register_all(
        self, tenant: str, scopes: set[str], *, is_admin: bool
    ) -> list[RegisterEntry]:
        """The tenant-wide register: entries whose matter's scope is held, PLUS — only for the
        tenant-wide admin — the undetermined-matter entries (``matter IS NULL``). A non-admin never
        sees an undetermined entry (AD-12/FR-49, fail closed).

        Scope is a query PRE-FILTER (AD-13/AD-14): a ``Failure`` is visible iff its matter's scope
        is held (a ``matter_scope`` sub-query) OR — admin only — it has no matter. No out-of-scope
        row is ever fetched; there is no Python post-filter over a tenant-wide fetch (Story 3.3)."""
        if not scopes and not is_admin:
            return []  # fail closed (AD-12): no scope and not admin → an empty register
        held_matters = select(MatterScope.matter).where(
            MatterScope.tenant == tenant, MatterScope.scope.in_(sorted(scopes)))
        with self._sf() as session:
            rows = session.scalars(
                select(Failure).where(
                    Failure.tenant == tenant,
                    or_(Failure.matter.in_(held_matters), Failure.matter.is_(None))
                    if is_admin
                    else Failure.matter.in_(held_matters),
                )
            ).all()
            out = [self._register_entry(f) for f in rows]
        return sorted(
            out, key=lambda e: (e.matter or "", e.resolution_state, e.submitted_path, e.id))

    def _authorise_entry(
        self, session: Session, f: Failure, tenant: str, scopes: set[str], is_admin: bool
    ) -> None:
        """Fail closed unless the caller may act on this entry: it must be the caller's TENANT
        (AD-12, scope is never applied without a tenant); then a determined entry needs its matter's
        scope held, while an undetermined (matter IS NULL) entry is admin-only (FR-49)."""
        if f.tenant != tenant:
            raise ScopeDenied(f.matter or "undetermined")  # cross-tenant — never disclose
        if f.matter is None:
            if not is_admin:
                raise ScopeDenied("undetermined")
            return
        scope = session.scalar(select(MatterScope.scope).where(
            MatterScope.matter == f.matter, MatterScope.tenant == f.tenant))
        if scope is None or scope not in scopes:
            raise ScopeDenied(f.matter)

    def _write_failure(
        self, session: Session, f: IngestedFailure, now: datetime, *, if_absent: bool = False
    ) -> None:
        """Persist one register entry (`open`) — the single failure-write, shared by ``save`` and
        the retry reconcile. ``if_absent`` inserts only when the id is new, so a container member
        recovered alongside failures never clobbers — nor re-opens — an existing entry (AD-7)."""
        fid = _failure_id(f.tenant, f.matter, f.submitted_path)
        if if_absent and session.get(Failure, fid) is not None:
            return
        session.merge(Failure(
            id=fid, tenant=f.tenant, matter=f.matter, filename=f.filename,
            submitted_path=f.submitted_path, custodian=f.custodian,
            error_class=str(f.error_class), cardinality=cardinality_for(f.error_class),
            resolution_state="open", detail=f.detail, timestamp=now))

    def _reconcile_retry(
        self, session: Session, f: Failure, result: IngestionResult, now: datetime
    ) -> str:
        """Reconcile an observed-OPEN entry against a freshly-run ingestion result, in the caller's
        transaction. Persist every recovered pièce that belongs to THIS entry (same tenant+matter;
        a foreign-matter pièce is ignored, never resolving this entry nor landing unscoped). Record
        every OTHER (container-member) failure as its own entry — never dropped (FR-5). The entry
        RESOLVES iff its own path succeeded — a pièce recovered and NO fresh failure for that path
        (AD-7 keeps the row); a fresh failure for its own path refreshes it and keeps it OPEN. No
        audit here — the caller writes one. Returns 'resolved' | 'still-failing'."""
        own_pieces = [p for p in result.pieces if p.tenant == f.tenant and p.matter == f.matter]
        own_failure = next(
            (nf for nf in result.failures if nf.submitted_path == f.submitted_path), None)
        for nf in result.failures:  # member failures — recorded, never dropped, never clobbering
            if nf.submitted_path != f.submitted_path:
                self._write_failure(session, nf, now, if_absent=True)
        seen: set[str] = set()
        for p in own_pieces:  # recovered content is persisted whether or not the unit itself failed
            self._insert_piece_if_absent(session, p, seen)
            self._insert_link_if_absent(
                session, PieceProvenance, p.id, "provenance_path", p.provenance_path)
            self._insert_link_if_absent(session, PieceCustodian, p.id, "custodian", p.custodian)
        if own_failure is not None:  # the unit's OWN path still fails — refresh, keep open
            f.error_class = str(own_failure.error_class)
            f.cardinality = cardinality_for(own_failure.error_class)
            f.detail = own_failure.detail
            return "still-failing"
        if own_pieces:
            f.resolution_state = "resolved"
            return "resolved"
        return "still-failing"  # nothing recovered for this unit, no fresh own-path failure

    def retry_failure(
        self, entry_id: str, reingest: Callable[[], IngestionResult], tenant: str,
        scopes: set[str], actor: str, *, is_admin: bool = False, now: datetime | None = None,
    ) -> RetryOutcome:
        """AD-37's ingestion-retry (`open → resolved`), a CONDITIONAL COMMIT. Phase 1: confirm the
        entry is the caller's tenant, is open, and the caller may act on it (fail closed). Phase 2
        (no tx held): re-run ingestion via `reingest`. Phase 3 (one tx): RE-OBSERVE open under a ROW
        LOCK (`with_for_update`, so a concurrent override committing between the read and the write
        cannot be lost on Postgres — the AD-37 override-race defense), RE-AUTHORISE (scope may have
        moved), reconcile, and write ONE `retry` audit entry. Never clobbers what moved."""
        now = now or datetime.now(UTC)
        with self._sf() as session:  # phase 1 — cheap precondition + authorisation read
            f0 = session.get(Failure, entry_id)
            if f0 is None:
                return RetryOutcome(entry_id, "not-found", None)
            self._authorise_entry(session, f0, tenant, scopes, is_admin)
            if f0.resolution_state != "open":
                return RetryOutcome(entry_id, "precondition-not-met", f0.resolution_state)
        result = reingest()  # phase 2 — slow extraction, no transaction held
        with self._sf() as session, session.begin():  # phase 3 — the conditional commit
            f = session.get(Failure, entry_id, with_for_update=True)  # row-locked re-observe
            if f is None:
                return RetryOutcome(entry_id, "not-found", None)
            self._authorise_entry(session, f, tenant, scopes, is_admin)  # re-authorise; scope moves
            if f.resolution_state != "open":  # moved during reingest — never clobber (AD-37)
                return RetryOutcome(entry_id, "precondition-not-met", f.resolution_state)
            outcome = self._reconcile_retry(session, f, result, now)
            if f.matter is not None:  # an undetermined-matter entry has no matter denominator
                # Story 2.7 (SM-3): a retry can resolve an entry (possibly collapsing a duplicate)
                # and/or record fresh member failures — SETTLE submitted_pieces to the reconciled
                # population, then assert the inventory guarantee holds (fail loud).
                self._settle_submitted_after_retry(session, f.matter, f.tenant)
                self._durable_inventory(session, f.matter, f.tenant).require_consistent()
            state = f.resolution_state
            self._append_audit(
                session, f.tenant, f.matter, actor, "retry",
                f"entry={entry_id} outcome={outcome}", now)
        return RetryOutcome(entry_id, outcome, state)

    def bulk_retry(
        self, tenant: str, scopes: set[str], *,
        reingest_for: Callable[[RegisterEntry], Callable[[], IngestionResult]],
        error_class: str | None = None, matter: str | None = None, custodian: str | None = None,
        actor: str, is_admin: bool = False, now: datetime | None = None,
    ) -> BulkRetryOutcome:
        """Retry every OPEN entry matching the filter (by class / matter / custodian), each a
        conditional commit under a row lock; write EXACTLY ONE `bulk-retry` audit entry naming the
        filter and the counts — never one per pièce (AD-6/FR-5). An entry no longer open at retry
        time is skipped, never clobbered (the AD-37 override-race defense); a per-entry re-ingest or
        commit error is COUNTED (`errored`) and the batch continues, so one poison unit never aborts
        the set nor loses the single audit entry. Candidates come from the scope/admin-filtered
        register read, so a wall the caller lacks is never touched."""
        now = now or datetime.now(UTC)
        candidates = [
            e for e in self.register_all(tenant, scopes, is_admin=is_admin)
            if e.resolution_state == "open"
            and (error_class is None or e.error_class == error_class)
            and (matter is None or e.matter == matter)
            and (custodian is None or e.custodian == custodian)
        ]
        resolved = still = skipped = errored = 0
        for entry in candidates:
            try:
                result = reingest_for(entry)()  # slow, no transaction held
                with self._sf() as session, session.begin():
                    f = session.get(Failure, entry.id, with_for_update=True)
                    if f is None or f.resolution_state != "open":
                        skipped += 1
                        continue
                    outcome = self._reconcile_retry(session, f, result, now)
                    if f.matter is not None:
                        # Story 2.7 (SM-3): settle submitted_pieces to the reconciled population (a
                        # resolve may collapse a duplicate) and assert the guarantee holds — parity
                        # with retry_failure, so a bulk retry can never persist a wedged matter.
                        self._settle_submitted_after_retry(session, f.matter, f.tenant)
                        self._durable_inventory(session, f.matter, f.tenant).require_consistent()
                    resolved += outcome == "resolved"
                    still += outcome == "still-failing"
            except Exception:  # noqa: BLE001 — a poison unit is counted, never aborts the whole set
                errored += 1
        with self._sf() as session, session.begin():  # ONE audit entry for the set, ALWAYS written
            detail = (f"filter=class:{error_class or '*'},matter:{matter or '*'},"
                      f"custodian:{'set' if custodian else '*'} attempted={len(candidates)} "
                      f"resolved={resolved} still_open={still} skipped={skipped} errored={errored}")
            self._append_audit(session, tenant, matter, actor, "bulk-retry", detail, now)
        return BulkRetryOutcome(len(candidates), resolved, still, skipped, errored)

    def export_register(
        self, tenant: str, scopes: set[str], actor: str, *, is_admin: bool,
        now: datetime | None = None,
    ) -> RegisterExport:
        """Export the register one-pièce-per-line within the caller's RBAC scope (undetermined
        entries only for the admin), recorded with ONE `export-register` audit entry (FR-49)."""
        entries = self.register_all(tenant, scopes, is_admin=is_admin)
        with self._sf() as session, session.begin():
            self._append_audit(
                session, tenant, None, actor, "export-register",
                f"lines={len(entries)} scopes={len(scopes)}", now or datetime.now(UTC))
        return RegisterExport(tuple(entries), len(scopes))

    def audit_query(
        self, tenant: str, actor: str, *, term: str, engine: str, scopes: set[str],
        denominator: Inventory | None = None, action: str = "search",
        now: datetime | None = None,
    ) -> None:
        """Record a search as an audited READ (AD-14/FR-15): ONE entry naming the term, the engine
        (its *truth status*), the scope, and — for an exhaustive query — the denominator at that
        moment. A corpus search is scope-wide, so it audits on the tenant chain (``matter=None``),
        like a scope grant. ``action`` is ``search`` for a run, ``export-search`` for an export."""
        denom = (f" denominator={denominator.in_corpus}/{denominator.submitted_pieces}"
                 if denominator is not None else "")
        detail = f"engine={engine} scopes={len(scopes)} term={term!r}{denom}"
        with self._sf() as session, session.begin():
            self._append_audit(session, tenant, None, actor, action, detail,
                               now or datetime.now(UTC))

    def read_piece(
        self, *, tenant: str, scopes: set[str], piece_id: str
    ) -> PieceView | None:
        """Story 3.5b — the pièce viewer's metadata for ONE pièce, IF its *matter*'s scope is held.
        Scope is a query PRE-FILTER (AD-13/AD-14): the pièce is fetched only when its matter is in
        the held set — never fetched-then-post-filtered. Out of scope (or absent) → ``None``, so a
        caller cannot tell an out-of-scope pièce from an absent one (FR-14/FR-44). No admin
        bypass (a Piece read takes no ``is_admin`` — Story 3.3 gate); empty scope → ``None``
        (fail-closed, AD-12)."""
        if not scopes:
            return None
        held_matters = select(MatterScope.matter).where(
            MatterScope.tenant == tenant, MatterScope.scope.in_(sorted(scopes)))
        with self._sf() as session:
            piece = session.scalars(
                select(Piece).where(
                    Piece.id == piece_id,
                    Piece.tenant == tenant,
                    Piece.matter.in_(held_matters),
                )
            ).one_or_none()
            if piece is None:
                return None
            filename = _basename(piece.provenance_path)  # EncryptedText decrypts on access
            return PieceView(
                piece_id=piece.id, matter=piece.matter, content_hash=piece.content_hash,
                filename=filename, media_kind=_media_kind(filename),
                ocr=piece.extraction_method == "tesseract",
            )

    def audit_piece_open(
        self, *, tenant: str, matter: str, actor: str, piece_id: str, now: datetime | None = None
    ) -> None:
        """Record opening a pièce's CONTENT as an audited act (FR-45) — the fact distinguishing a
        *validation act* performed AFTER reading from one performed from the list. ONE entry on the
        (tenant, matter) chain (AD-43), like a query audit (Story 3.4). The edge calls this only
        after a successful in-scope read, so a denied/out-of-scope attempt writes no disclosing
        entry."""
        with self._sf() as session, session.begin():
            self._append_audit(session, tenant, matter, actor, "open-piece",
                               f"piece={piece_id}", now or datetime.now(UTC))

    def deduplicate(self, matter: str, tenant: str, scopes: set[str]) -> DedupSummary:
        """The deterministic tier of the judgment cascade for a matter — scope-checked.
        Groups the corpus by the near-duplicate key so copies (same text modulo
        formatting) collapse to one representative; the LLM band only ever faces the
        distinct set. A pure read — it computes clusters and mutates nothing, so it is
        not itself an audited act (the reversible label written later is)."""
        with self._sf() as session:
            scope = session.scalar(
                select(MatterScope.scope).where(
                    MatterScope.matter == matter, MatterScope.tenant == tenant
                )
            )
            if scope is None or scope not in scopes:
                raise ScopeDenied(matter)  # fail closed, existence not disclosed
            rows = session.execute(
                select(Piece.id, Piece.text_key, Piece.provenance_path).where(
                    Piece.matter == matter, Piece.tenant == tenant
                )
            ).all()
        prov = {pid: path for pid, _key, path in rows}
        report = cluster([(pid, key) for pid, key, _path in rows])
        groups = tuple(
            DuplicateGroup(
                representative=prov[c.representative],
                members=tuple(prov[m] for m in c.members),
                size=c.size,
            )
            for c in report.clusters
        )
        return DedupSummary(report.submitted, report.distinct, report.duplicates, groups)

    def representatives(self, matter: str, tenant: str, scopes: set[str]) -> list[tuple[str, str]]:
        """The distinct pieces to judge — one representative per near-duplicate cluster,
        with its text (a representative's verdict stands for its whole cluster).
        Scope-checked; deterministic (the smallest piece_id per key)."""
        with self._sf() as session:
            scope = session.scalar(
                select(MatterScope.scope).where(
                    MatterScope.matter == matter, MatterScope.tenant == tenant
                )
            )
            if scope is None or scope not in scopes:
                raise ScopeDenied(matter)
            rows = session.execute(
                select(Piece.id, Piece.text_key, Piece.full_text).where(
                    Piece.matter == matter, Piece.tenant == tenant
                )
            ).all()
        text = {pid: full for pid, _key, full in rows}
        groups: dict[str, list[str]] = {}
        for pid, key, _full in rows:
            groups.setdefault(key, []).append(pid)
        reps = sorted(min(pids) for pids in groups.values())
        return [(rid, text[rid]) for rid in reps]

    def save_labels(self, matter: str, tenant: str, scopes: set[str],
                    outcome: TriageOutcome, judge: str, actor: str) -> None:
        """Persist the triage verdicts — reversible (overwrite the current label) and
        atomic with ONE audit entry recording the act (FR-53). Scope-checked."""
        now = datetime.now(UTC)
        with self._sf() as session, session.begin():
            scope = session.scalar(
                select(MatterScope.scope).where(
                    MatterScope.matter == matter, MatterScope.tenant == tenant
                )
            )
            if scope is None or scope not in scopes:
                raise ScopeDenied(matter)
            for x in outcome.labels:
                session.merge(
                    LabelRecord(
                        piece_id=x.piece_id, tenant=tenant, matter=matter,
                        label=x.label.value, rationale=x.rationale, judge=judge, judged_at=now,
                    )
                )
            detail = (
                f"relevant={outcome.relevant} uncertain={outcome.uncertain} "
                f"discard={outcome.discarded} judge={judge}"
            )
            self._append_audit(session, tenant, matter, actor, "judge", detail, now)

    def labels(self, matter: str, tenant: str, scopes: set[str]) -> LabelSummary:
        """The current triage labels for a matter — scope-checked. Counts plus each
        labelled piece by its provenance path and rationale (a discard is shown, with
        its reason — never silent)."""
        with self._sf() as session:
            scope = session.scalar(
                select(MatterScope.scope).where(
                    MatterScope.matter == matter, MatterScope.tenant == tenant
                )
            )
            if scope is None or scope not in scopes:
                raise ScopeDenied(matter)
            rows = session.execute(
                select(LabelRecord.label, LabelRecord.rationale, Piece.provenance_path)
                .join(Piece, (Piece.id == LabelRecord.piece_id) & (Piece.tenant == tenant))
                .where(LabelRecord.matter == matter, LabelRecord.tenant == tenant)
                .order_by(Piece.id)  # provenance_path is ciphertext at rest (AD-31); sort below
            ).all()
        # present by provenance path, sorted AFTER the column decrypts (encrypted at rest)
        pieces = tuple(
            LabelledPiece(prov, label, rat)
            for label, rat, prov in sorted(rows, key=lambda r: r[2])
        )
        relevant = sum(1 for p in pieces if p.label == "relevant")
        uncertain = sum(1 for p in pieces if p.label == "uncertain")
        discarded = sum(1 for p in pieces if p.label == "discard")
        return LabelSummary(relevant, uncertain, discarded, len(pieces), pieces)

    def sample_discards(self, matter: str, tenant: str, scopes: set[str], n: int,
                        *, seed: int | None = None) -> RecallSample:
        """Draw a random sample of the matter's discard pile for review — scope-checked.
        A review's bound is only sound if the sample is random w.r.t. relevance, so this
        samples uniformly (seedable, for reproducible tests)."""
        with self._sf() as session:
            scope = session.scalar(
                select(MatterScope.scope).where(
                    MatterScope.matter == matter, MatterScope.tenant == tenant
                )
            )
            if scope is None or scope not in scopes:
                raise ScopeDenied(matter)
            rows = session.execute(
                select(LabelRecord.piece_id, Piece.provenance_path, Piece.full_text)
                .join(Piece, (Piece.id == LabelRecord.piece_id) & (Piece.tenant == tenant))
                .where(
                    LabelRecord.matter == matter, LabelRecord.tenant == tenant,
                    LabelRecord.label == "discard",
                )
            ).all()
        chosen = random.Random(seed).sample(rows, min(n, len(rows))) if rows else []
        sample = tuple(SampledDiscard(pid, prov, _excerpt(full)) for pid, prov, full in chosen)
        return RecallSample(population=len(rows), sample=sample)

    def record_recall_review(self, matter: str, tenant: str, scopes: set[str],
                             verdicts: dict[str, bool], actor: str,
                             *, confidence: float = 0.95) -> RecallResult:
        """Record a recall check: from the reviewed sample of the discard pile, compute
        the finite-population upper confidence bound on wrongly-discarded pieces, persist
        it, and append the act to the audit trail (atomic). ``verdicts`` maps a sampled
        piece_id to whether it was actually relevant (a false discard). Scope-checked;
        rejects any reviewed piece that is not currently discarded."""
        now = datetime.now(UTC)
        with self._sf() as session, session.begin():
            scope = session.scalar(
                select(MatterScope.scope).where(
                    MatterScope.matter == matter, MatterScope.tenant == tenant
                )
            )
            if scope is None or scope not in scopes:
                raise ScopeDenied(matter)
            discard_ids = {
                pid for (pid,) in session.execute(
                    select(LabelRecord.piece_id).where(
                        LabelRecord.matter == matter, LabelRecord.tenant == tenant,
                        LabelRecord.label == "discard",
                    )
                ).all()
            }
            unknown = set(verdicts) - discard_ids
            if unknown:
                raise ValueError(f"reviewed pieces are not discarded: {sorted(unknown)}")
            population = len(discard_ids)
            sample_size = len(verdicts)
            relevant_found = sum(1 for v in verdicts.values() if v)
            bound = prevalence_upper_bound(
                population, sample_size, relevant_found, confidence=confidence
            )
            session.add(RecallReview(
                id=uuid4().hex, tenant=tenant, matter=matter, population=population,
                sample_size=sample_size, relevant_found=relevant_found, confidence=confidence,
                count_upper=bound.count_upper, prevalence_upper=bound.prevalence_upper,
                reviewer=actor, reviewed_at=now,
            ))
            detail = (
                f"population={population} sample={sample_size} relevant={relevant_found} "
                f"bound={bound.prevalence_upper:.4f}@{confidence}"
            )
            self._append_audit(session, tenant, matter, actor, "recall-review", detail, now)
        return RecallResult(
            population, sample_size, relevant_found, confidence,
            bound.count_upper, bound.prevalence_upper,
        )

    def search(
        self, tenant: str, scopes: set[str], query: str, *, limit: int = 100
    ) -> SearchResults:
        """A **bounded normalised preview** over the caller's scope (FR-13): pieces whose stored
        text contains ``query`` under the ``fr-fold-v1`` rule (so ``etat`` finds ``État``), scope
        pre-filtered so it cannot leak across the wall. ``total`` is the true match count even when
        ``hits`` are capped at ``limit``. This is NOT the exhaustive engine — it carries no
        *truth status* and it truncates; the AD-20 exhaustive set (complete, EXHAUSTIVE, with its
        denominator, no limit) is ``search_exhaustive`` / ``exact_search``. A future surface points
        here for a quick preview and there for a defensible absence claim."""
        q = query.strip()
        nq = normalize(q)
        if not scopes or not nq:
            return SearchResults(q, 0, ())  # fail closed: no scope or empty query -> nothing
        pattern = f"%{_like_escape(nq)}%"
        join_on = (MatterScope.matter == Piece.matter) & (MatterScope.tenant == Piece.tenant)
        conds = [
            Piece.tenant == tenant,
            MatterScope.scope.in_(scopes),
            Piece.full_text_normalized.like(pattern, escape="\\"),
        ]
        with self._sf() as session:
            total = session.scalar(
                select(func.count()).select_from(Piece).join(MatterScope, join_on).where(*conds)
            ) or 0
            rows = session.execute(
                select(Piece.matter, Piece.provenance_path, Piece.full_text)
                .join(MatterScope, join_on)
                .where(*conds)
                # provenance_path is ciphertext at rest (AD-31) — order the capped subset by
                # the plaintext PK for determinism, then present by (matter, provenance) below.
                .order_by(Piece.matter, Piece.id)
                .limit(limit)
            ).all()
        rows = sorted(rows, key=lambda r: (r[0], r[1]))  # present by (matter, provenance)
        hits = tuple(SearchHit(matter, prov, snippet(full, q)) for matter, prov, full in rows)
        return SearchResults(q, total, hits)

    def _scoped_inventory(self, session: Session, tenant: str, scopes: set[str]) -> Inventory:
        """The scoped *denominator* (AD-38) computed DIRECTLY over the in-scope *matters* in one
        snapshot — never by summing per-matter records (unknown-cardinality / noise / retired are
        never a ``+`` operand, AD-38). ``submitted_pieces`` is the SQL sum of the frozen high-water
        marks; the rest are live counts, mirroring ``_durable_inventory``'s definitions."""
        in_scope = select(MatterScope.matter).where(
            MatterScope.tenant == tenant, MatterScope.scope.in_(sorted(scopes))).scalar_subquery()

        def _count(model: type, *extra: object) -> int:
            return session.scalar(select(func.count()).select_from(model).where(
                model.tenant == tenant, model.matter.in_(in_scope), *extra)) or 0

        submitted = session.scalar(select(func.coalesce(func.sum(MatterScope.submitted_pieces), 0))
                                   .where(MatterScope.tenant == tenant,
                                          MatterScope.scope.in_(sorted(scopes)))) or 0
        return Inventory(
            submitted_pieces=int(submitted),
            in_corpus=_count(Piece),
            open_register_entries=_count(Failure, Failure.resolution_state == "open"),
            excluded_as_noise=_count(NoiseExclusion),
            unknown_cardinality_entries=_count(
                Failure, Failure.resolution_state == "open", Failure.cardinality == "unknown"),
        )

    def open_import_jobs(self, *, tenant: str, scopes: set[str]) -> list[str]:
        """Open (not-done) import jobs over the in-scope *matters* — the exhaustive engine refuses
        over a moving population (AD-20, Story 3.2). Empty scope → ``[]`` (fail-closed)."""
        if not scopes:
            return []
        with self._sf() as session:
            matters = list(session.scalars(select(MatterScope.matter).where(
                MatterScope.tenant == tenant, MatterScope.scope.in_(sorted(scopes)))).all())
        return [job for m in matters if (job := self.open_import_job(tenant, m))]

    def exact_search(
        self, *, tenant: str, scopes: set[str], normalized_query: str
    ) -> ExactSearch:
        """The scoped deterministic exact search (Story 3.2, the ``ExactSearchReader`` port): the
        COMPLETE normalised match over ``full_text_normalized`` (no ``LIMIT`` — AD-20), with the
        *scoped denominator* aggregated across in-scope *matters* and the OCR-derived share of the
        searched set, in one snapshot. Scope is a query PRE-filter (AD-13); an empty scope OR a
        query that normalises to empty reads nothing (fail-closed, AD-12 — a blank query never
        matches the whole corpus).

        Deferred, carried honestly — not fabricated: ``below_quality_share`` needs an
        extraction-layer OCR-quality signal that does not yet exist; the register **name-match**
        (``register_hits``) is deferred on scope — its counts are already in the denominator, and a
        decrypt-and-match over the encrypted filenames is feasible in-app but out of scope here.
        """
        if not scopes or not normalized_query:
            return ExactSearch(results=[], register_hits=[],
                               denominator=Inventory(0, 0, 0),
                               ocr_share=0.0, below_quality_share=0.0)
        stmt = exact_search_stmt(tenant=tenant, scopes=scopes, normalized_query=normalized_query)
        with self._sf() as session:
            rows = session.execute(stmt).all()
            denom = self._scoped_inventory(session, tenant, scopes)
            ocr_share = self._scoped_ocr_share(session, tenant, scopes, denom.in_corpus)
        results = [
            DeterministicResult(matter=m, piece_id=pid, snippet=snippet(full, normalized_query))
            for m, pid, full in rows
        ]
        return ExactSearch(results=results, register_hits=[], denominator=denom,
                           ocr_share=ocr_share, below_quality_share=0.0)

    def _scoped_ocr_share(
        self, session: Session, tenant: str, scopes: set[str], in_corpus: int
    ) -> float:
        """The OCR-derived share of the searched set (AD-42): the fraction of in-scope, in-corpus
        *pièces* whose text came from OCR (``extraction_method == "tesseract"``), so an unreadable
        scan is *"in the corpus but its text may not be"*. 0.0 when the corpus is empty."""
        if in_corpus <= 0:
            return 0.0
        in_scope = select(MatterScope.matter).where(
            MatterScope.tenant == tenant, MatterScope.scope.in_(sorted(scopes))).scalar_subquery()
        ocr = session.scalar(select(func.count()).select_from(Piece).where(
            Piece.tenant == tenant, Piece.matter.in_(in_scope),
            Piece.extraction_method == "tesseract")) or 0
        return ocr / in_corpus

    def create_user(self, tenant: str, email: str, password: str, display_name: str,
                    scopes: set[str], *, is_admin: bool = False, actor: str = "system") -> str:
        """Create an owned user with an Argon2id-hashed password and their scope grants, on the
        authority of `actor` — an **audited** privileged act (it grants scopes and, possibly,
        the administrative authority, so it may not skip the record). The plaintext password is
        never stored. Returns the new user id."""
        uid = uuid4().hex
        now = datetime.now(UTC)
        with self._sf() as session, session.begin():
            session.add(User(
                id=uid, tenant=tenant, email=email.strip().lower(),
                password_hash=hash_password(password), display_name=display_name,
                is_admin=is_admin,
            ))
            for scope in scopes:
                session.add(UserScope(user_id=uid, scope=scope))
            self._append_audit(
                session, tenant, None, actor, "create_user",
                f"subject={uid} email={email.strip().lower()} scopes={sorted(scopes)} "
                f"admin={is_admin}", now)
        return uid

    def authenticate(self, tenant: str, email: str, password: str) -> AuthUser | None:
        """Return the user on a correct password, else None. The password is always
        verified — against a dummy hash when the email is unknown — so timing does not
        reveal whether an account exists."""
        with self._sf() as session, session.begin():
            u = session.scalar(
                select(User).where(User.tenant == tenant, User.email == email.strip().lower())
            )
            ok, upgraded = verify_and_upgrade(
                password, u.password_hash if u is not None else _DUMMY_HASH
            )
            if u is None or not ok:
                return None
            if upgraded is not None:
                u.password_hash = upgraded  # upgrade-on-verify: legacy scrypt -> Argon2id
            return AuthUser(u.id, u.tenant, u.email, u.display_name)

    def scopes_for(self, user_id: str) -> set[str]:
        """The walls a user holds — resolved live (never denormalised), so a re-grant
        takes effect on the next request (AD-13)."""
        with self._sf() as session:
            return {
                scope for (scope,) in session.execute(
                    select(UserScope.scope).where(UserScope.user_id == user_id)
                ).all()
            }

    def identity(self, user_id: str) -> tuple[bool, set[str]]:
        """A user's admin flag and held scopes in one live read (for the request path)."""
        with self._sf() as session:
            is_admin = bool(session.scalar(select(User.is_admin).where(User.id == user_id)))
            scopes = {
                scope for (scope,) in session.execute(
                    select(UserScope.scope).where(UserScope.user_id == user_id)
                ).all()
            }
        return is_admin, scopes

    # ── opaque server-side sessions (AD-15) — the one Principal-resolution interface ──

    def create_session(
        self, user_id: str, tenant: str, *, absolute_ttl: timedelta, now: datetime | None = None
    ) -> str:
        """Open a session and return its opaque, unguessable id (the cookie value). The id
        is never a signed claim blob — authority is the row (AD-15)."""
        now = now or datetime.now(UTC)
        sid = secrets.token_urlsafe(32)
        with self._sf() as session, session.begin():
            session.add(SessionRecord(
                id=sid, user_id=user_id, tenant=tenant,
                created_at=now, last_seen_at=now, absolute_expiry=now + absolute_ttl,
            ))
        return sid

    def resolve_session(
        self, session_id: str, *, idle_ttl: timedelta, now: datetime | None = None
    ) -> SessionIdentity | None:
        """Resolve an opaque session to a live Principal, or None if absent/expired. Slides
        the idle window (touches last_seen_at) and reaps an expired row. The actor, admin
        flag and scopes are resolved LIVE from the user's rows — a revoked scope is gone
        here on the next request (AD-13/FR-49)."""
        now = now or datetime.now(UTC)
        with self._sf() as session, session.begin():
            row = session.get(SessionRecord, session_id)
            if row is None:
                return None
            if now >= _as_utc(row.absolute_expiry) or (now - _as_utc(row.last_seen_at)) > idle_ttl:
                session.delete(row)  # expired (absolute or idle) — reap and refuse
                return None
            user = session.get(User, row.user_id)
            if user is None:
                session.delete(row)  # the user is gone — the session cannot stand
                return None
            row.last_seen_at = now  # slide the idle window
            scopes = {
                s for (s,) in session.execute(
                    select(UserScope.scope).where(UserScope.user_id == row.user_id)
                ).all()
            }
            return SessionIdentity(
                row.user_id, user.tenant, user.display_name, bool(user.is_admin), scopes
            )

    def delete_session(self, session_id: str) -> None:
        """Sign-out: the id is not reusable afterwards."""
        with self._sf() as session, session.begin():
            row = session.get(SessionRecord, session_id)
            if row is not None:
                session.delete(row)

    def delete_user_sessions(self, user_id: str) -> None:
        """Invalidate every live session for a user (on a password change)."""
        with self._sf() as session, session.begin():
            session.execute(delete(SessionRecord).where(SessionRecord.user_id == user_id))

    def record_auth_event(self, tenant: str, actor: str, action: str, detail: str) -> None:
        """Append a tenant-level audit entry for an auth event — a failed login, a lockout:
        a matterless act on the per-tenant chain (AD-43/AD-22). A failure is durably recorded
        (FR-48), not only throttled in memory.

        Recorded only for a tenant that EXISTS (has users), so an unauthenticated login-spray
        with arbitrary tenant names cannot seed audit chains for non-existent firms. Retries
        on a concurrent (tenant, seq) collision so a burst of failed logins does not surface
        as a 500. (AD-44 note: high-volume auth events on the serialized chain head can still
        contend; a dedicated non-chained auth-events log is the AD-44-aligned future — a
        separate story, tracked in the 1.5 review.)"""
        now = datetime.now(UTC)
        for attempt in range(4):
            try:
                with self._sf() as session, session.begin():
                    exists = session.scalar(
                        select(func.count()).select_from(User).where(User.tenant == tenant)
                    )
                    if not exists:
                        return  # unknown tenant — never pollute the audit with a spray target
                    self._append_audit(session, tenant, None, actor, action, detail, now)
                    session.flush()  # surface a (tenant, seq) collision here, inside the try
                return
            except IntegrityError:
                if attempt == 3:
                    raise
                continue

    def _tenants(self, session: Session) -> list[str]:
        """Every tenant that has DATA — the union across the tenant-bearing tables, not just
        `user_account`. A tenant can hold ingested pieces before any user is enrolled (or after
        all are removed), and a maintenance act (a key rotation) must account for its data too."""
        found: set[str] = set()
        for col in (User.tenant, MatterScope.tenant, Piece.tenant, Failure.tenant,
                    AuditRecord.tenant, LabelRecord.tenant, RecallReview.tenant):
            found.update(session.execute(select(col).distinct()).scalars().all())
        return sorted(found)

    def tenants(self) -> list[str]:
        """Every data-bearing tenant (see :meth:`_tenants`)."""
        with self._sf() as session:
            return self._tenants(session)

    def projection_snapshot(self, tenant: str) -> Snapshot:
        """The content-free facts the projection primitive (AD-26) emits: counts, an error-class
        histogram (enumerated classes → counts) and distinct version identifiers — NO names, paths,
        content or query text. The seeded-token test seeds content into this tenant's data and
        asserts none of it survives this gather-plus-project path (FR-31)."""
        with self._sf() as session:
            piece_count = session.scalar(
                select(func.count()).select_from(Piece).where(Piece.tenant == tenant)) or 0
            failure_count = session.scalar(
                select(func.count()).select_from(Failure).where(Failure.tenant == tenant)) or 0
            matter_count = session.scalar(
                select(func.count()).select_from(MatterScope).where(
                    MatterScope.tenant == tenant)) or 0
            histogram = {
                cls: n for cls, n in session.execute(
                    select(Failure.error_class, func.count())
                    .where(Failure.tenant == tenant)
                    .group_by(Failure.error_class)
                ).all()
            }
            schema_versions = tuple(sorted(
                v for (v,) in session.execute(
                    select(Piece.schema_version).where(Piece.tenant == tenant).distinct()).all()))
            extractor_versions = tuple(sorted(
                v for (v,) in session.execute(
                    select(Piece.extractor_version).where(Piece.tenant == tenant).distinct()).all()
            ))
        return Snapshot(
            piece_count=piece_count, failure_count=failure_count, matter_count=matter_count,
            error_class_histogram=histogram, schema_versions=schema_versions,
            extractor_versions=extractor_versions)

    # ── the chain head, recorded outside the restorable store, and reconciled (AD-35) ──

    def _audit_heads(self, session: Session) -> dict[str, tuple[int, str]]:
        """Each tenant's live chain head — (max seq, its chain value)."""
        maxes = session.execute(
            select(AuditRecord.tenant, func.max(AuditRecord.seq)).group_by(AuditRecord.tenant)
        ).all()
        heads: dict[str, tuple[int, str]] = {}
        for tenant, max_seq in maxes:
            chain = session.scalar(
                select(AuditRecord.chain).where(
                    AuditRecord.tenant == tenant, AuditRecord.seq == max_seq))
            heads[tenant] = (int(max_seq), chain or "")
        return heads

    def audit_heads(self) -> dict[str, tuple[int, str]]:
        with self._sf() as session:
            return self._audit_heads(session)

    def record_current_heads(self, journal: HeadJournal | None = None) -> int:
        """Record every tenant's current live head to the journal (called at start-up, after the
        boot reconcile). Returns how many heads were recorded. The journal is append-only and grows
        one line per advance; a long-lived run would want periodic compaction (retain the latest
        head per scope) — deferred, immaterial at the single-firm design target (AD-32)."""
        j = journal or self._journal
        if j is None:
            return 0
        now = _audit_ts(datetime.now(UTC))
        count = 0
        for tenant, (seq, chain) in self.audit_heads().items():
            j.record(HeadEntry(tenant, seq, chain, now, _APP_VERSION, _HEAD_SCHEMA_VERSION))
            count += 1
        return count

    def reconcile_heads(self, journal: HeadJournal | None = None) -> list[Reconciliation]:
        """Reconcile every scope's live head against the journal (AD-35). A live head BEHIND the
        expected head is a truncation — the record now ends earlier than it did — recorded as a
        persistent marker (named on exports, cleared only by an audited override). Called on
        start-up and after a restore.

        An already-acknowledged truncation is not re-flagged, but a NEW truncation after an override
        IS. Once a truncation is cleared, the baseline resets to the heads recorded AFTER the
        override (``post_clear_max``) — NOT the stale pre-truncation head the append-only journal
        still carries — so a second restore that falls below that reset baseline is a fresh
        truncation, not silently swallowed as 'the same acknowledged one'. The journal is parsed
        ONCE into both views (all-latest, and the per-scope post-clear maxima)."""
        j = journal or self._journal
        if j is None:
            return []
        entries = j.entries()
        journal_max: dict[str, int] = {}
        for e in entries:
            if e.scope not in journal_max or e.seq > journal_max[e.scope]:
                journal_max[e.scope] = e.seq
        heads = self.audit_heads()
        out: list[Reconciliation] = []
        for scope in sorted(set(heads) | set(journal_max)):
            live_seq = heads.get(scope, (0, ""))[0]
            cleared_at = self._marker_cleared_at(scope)
            if cleared_at is not None:
                # A cleared marker: the baseline is the heads recorded AFTER the override, so a live
                # head below THAT is a new truncation — not below the stale pre-truncation head the
                # append-only journal still carries (which the override already accounted for).
                floor = _audit_ts(_as_utc(cleared_at))
                reference = max(
                    (e.seq for e in entries if e.scope == scope and e.recorded_at > floor),
                    default=0)
            else:  # no marker, or one still active — the plain 'live behind the journal' test
                reference = journal_max.get(scope, 0)
            rec = Reconciliation(scope, live_seq, reference, truncated=live_seq < reference)
            out.append(rec)
            if rec.truncated:
                self._record_truncation(scope, rec)
        return out

    def _marker_cleared_at(self, tenant: str) -> datetime | None:
        """When the tenant's truncation marker was CLEARED by an audited override, or None when
        there is no cleared marker — none at all, or one still active. ``reconcile_heads`` uses it
        to reset the baseline past an acknowledged truncation, so a LATER one is still caught."""
        with self._sf() as session:
            m = session.get(TruncationMarker, tenant)
            return m.cleared_at if m is not None else None

    def _record_truncation(self, tenant: str, rec: Reconciliation) -> None:
        """Upsert an ACTIVE truncation marker for the latest detection. The keep-cleared decision
        lives in ``reconcile_heads`` (via the post-override baseline), so this ALWAYS records an
        active marker — a re-detection after an override correctly reactivates it, never a silent
        no-op that would leave a fresh data loss un-flagged."""
        now = datetime.now(UTC)
        with self._sf() as session, session.begin():
            session.merge(TruncationMarker(
                tenant=tenant, detected_at=now, journal_seq=rec.journal_seq,
                live_seq=rec.live_seq, cleared_by=None, reason=None, cleared_at=None))

    def truncation_status(self, tenant: str) -> TruncationStatus:
        """A tenant's truncation status — active while un-cleared (named on every export, AD-35)."""
        with self._sf() as session:
            m = session.get(TruncationMarker, tenant)
        if m is None:
            return TruncationStatus(tenant, False, 0, 0, None, None)
        return TruncationStatus(
            tenant, active=m.cleared_at is None, journal_seq=m.journal_seq, live_seq=m.live_seq,
            detected_at=m.detected_at.isoformat(),
            cleared_at=m.cleared_at.isoformat() if m.cleared_at is not None else None)

    def clear_truncation(self, tenant: str, actor: str, reason: str) -> None:
        """Clear an active truncation by an audited OVERRIDE with a reason (AD-35/AD-25) — the only
        way it clears; it is never repaired. Refuses an empty reason and a no-op (none active)."""
        if not reason.strip():
            raise ValueError("a reason is required to override a truncation")

        def _work(session: Session, now: datetime) -> None:
            m = session.get(TruncationMarker, tenant)
            if m is None or m.cleared_at is not None:
                raise ValueError("no active truncation to clear")
            m.cleared_by, m.reason, m.cleared_at = actor, reason, now
            self._append_audit(
                session, tenant, None, actor, "truncation_override",
                f"journal_seq={m.journal_seq} live_seq={m.live_seq}", now)

        self._audited_tx(_work)

    # ── logical, tenant-boundary backup + an exercised restore (AD-32) ──

    def backup_tenant(self, tenant: str) -> TenantBackup:
        """A complete, tenant-boundary logical backup (AD-32). Rows are read RAW so content-bearing
        columns stay ciphertext (encrypted at rest); the tenant's head-journal tail is copied on."""
        with self._sf() as session:
            conn = session.connection()
            tables: dict[str, list[dict]] = {}
            for tbl in _BACKUP_TABLES:
                rows = conn.execute(
                    text(f"SELECT * FROM {tbl} WHERE tenant = :t"), {"t": tenant}  # noqa: S608
                ).mappings().all()
                tables[tbl] = [dict(r) for r in rows]
            uids = [
                uid for (uid,) in conn.execute(
                    text("SELECT id FROM user_account WHERE tenant = :t"), {"t": tenant}).all()
            ]
            scopes = [
                {"user_id": r.user_id, "scope": r.scope}
                for r in session.execute(
                    select(UserScope).where(UserScope.user_id.in_(uids))).scalars().all()
            ] if uids else []
            # the piece SETS (Story 2.5) — keyed by piece_id, so captured via the tenant's pieces
            # (like user_scope via the tenant's users), RAW so ciphertext is preserved.
            piece_links: dict[str, list[dict]] = {}
            for tbl in ("piece_provenance", "piece_custodian"):
                rows = conn.execute(
                    text(f"SELECT * FROM {tbl} WHERE piece_id IN "  # noqa: S608
                         "(SELECT id FROM piece WHERE tenant = :t)"), {"t": tenant}
                ).mappings().all()
                piece_links[tbl] = [dict(r) for r in rows]
        head_tail: list[dict] = []
        if self._journal is not None:
            latest = self._journal.latest(tenant)
            if latest is not None:
                head_tail = [asdict(latest)]
        return TenantBackup(
            tenant, _HEAD_SCHEMA_VERSION, tables, scopes, head_tail, piece_links=piece_links)

    def _chain_verifies(self, session: Session, tenant: str) -> bool:
        """Recompute a tenant's audit chain end to end from the rows in ``session`` — the same
        recomputation ``read_audit`` does — returning False on any gap, reorder, tamper, or
        undecryptable field (fail closed). Used INSIDE ``restore_tenant`` so a corrupt or tampered
        backup is rejected at restore time, not silently accepted and caught later on a read."""
        rows = session.execute(
            select(
                AuditRecord.seq, AuditRecord.tenant, AuditRecord.matter,
                cast(AuditRecord.actor, Text), AuditRecord.action,
                cast(AuditRecord.detail, Text), AuditRecord.chain, AuditRecord.timestamp,
            ).where(AuditRecord.tenant == tenant).order_by(AuditRecord.seq)
        ).all()
        prev_chain = ""
        for i, (seq, r_tenant, matter, actor_ct, action, detail_ct, chain, ts) in enumerate(rows):
            actor = _safe_decrypt(actor_ct, "audit_record.actor")
            detail = _safe_decrypt(detail_ct, "audit_record.detail")
            if actor is None or detail is None:
                return False  # an unreadable field cannot be authenticated
            content = _audit_content(seq, r_tenant, matter, actor, action, detail, _audit_ts(ts))
            if seq != i + 1 or _audit_chain(prev_chain, content) != chain:
                return False
            prev_chain = chain
        return True

    def restore_tenant(
        self, backup: TenantBackup, journal: HeadJournal | None = None
    ) -> list[Reconciliation]:
        """Restore a tenant into an EMPTY store (AD-32) — refuses to overwrite an existing tenant.
        Rows go back RAW (ciphertext preserved byte-for-byte). The restored audit chain is
        re-verified INSIDE the transaction, so a corrupt or tampered backup rolls back (rejected at
        restore, not caught later on a read). After commit the backup's copied head tail is seeded
        into the journal (true DR: the journal volume may have died with the primary), then the head
        is reconciled — a restore that moved the head backwards is a truncation."""
        with self._sf() as session, session.begin():
            conn = session.connection()
            for tbl in _BACKUP_TABLES:
                if conn.execute(
                    text(f"SELECT 1 FROM {tbl} WHERE tenant = :t LIMIT 1"),  # noqa: S608
                    {"t": backup.tenant},
                ).first():
                    raise ValueError(
                        f"tenant {backup.tenant!r} already has {tbl} rows — restore is into an "
                        "empty store (AD-32)")
            for tbl in _BACKUP_TABLES:
                for row in backup.tables.get(tbl, []):
                    cols = list(row.keys())
                    collist = ", ".join(cols)
                    binds = ", ".join(f":{c}" for c in cols)
                    conn.execute(
                        text(f"INSERT INTO {tbl} ({collist}) VALUES ({binds})"), row)  # noqa: S608
            for sc in backup.user_scopes:
                conn.execute(
                    text("INSERT INTO user_scope (user_id, scope) VALUES (:user_id, :scope)"), sc)
            for tbl in ("piece_provenance", "piece_custodian"):  # the piece SETS (Story 2.5)
                for row in backup.piece_links.get(tbl, []):
                    cols = list(row.keys())
                    collist = ", ".join(cols)
                    binds = ", ".join(f":{c}" for c in cols)
                    conn.execute(
                        text(f"INSERT INTO {tbl} ({collist}) VALUES ({binds})"), row)  # noqa: S608
            if not self._chain_verifies(session, backup.tenant):
                raise ValueError(
                    f"restored audit chain for tenant {backup.tenant!r} does not verify — the "
                    "backup is corrupt or was tampered with (AD-35); restore refused")
        self._seed_journal_from_backup(backup, journal)
        return self.reconcile_heads(journal)

    def _seed_journal_from_backup(
        self, backup: TenantBackup, journal: HeadJournal | None
    ) -> None:
        """Seed the live journal with the head tail copied onto the backup (AD-35: a copy on every
        backup target). In a true disaster the journal volume is lost WITH the primary; the backup's
        own head tail is then the only surviving outside record, and reconcile needs it to detect a
        truncation at all. Append-only and best-effort: a malformed tail is skipped, a write failure
        is surfaced as degraded — neither fails the restore itself."""
        j = journal or self._journal
        if j is None:
            return
        for h in backup.head_tail:
            try:
                j.record(HeadEntry(**h))
            except TypeError:
                continue  # a malformed head-tail entry is skipped, never fatal to the restore
            except OSError as exc:
                self.journal_degraded = True
                _log.warning(
                    "could not seed head tail on restore of %s: %s", backup.tenant, exc)

    # ── backup status: overdue is answerable (AD-32) ──

    def record_backup(
        self, tenant: str, outcome: str, *, byte_size: int = 0, detail: str | None = None
    ) -> None:
        """Record a backup run's outcome (success|failure) — so "no backup within the interval" is
        answerable and the worklist can render it (AD-32). ``outcome`` is a closed categorical: a
        typo must fail loudly, not poison ``backup_status`` (which counts only 'success')."""
        if outcome not in ("success", "failure"):
            raise ValueError(f"outcome must be 'success' or 'failure', not {outcome!r}")
        with self._sf() as session, session.begin():
            session.add(BackupRecord(
                id=uuid4().hex, tenant=tenant, outcome=outcome, detail=detail,
                byte_size=byte_size, created_at=datetime.now(UTC)))

    def backup_status(self, tenant: str, interval_hours: int) -> BackupStatus:
        """Whether the tenant has a successful backup within the configured interval (AD-32)."""
        with self._sf() as session:
            last = session.scalar(
                select(func.max(BackupRecord.created_at)).where(
                    BackupRecord.tenant == tenant, BackupRecord.outcome == "success"))
        if last is None:
            return BackupStatus(tenant, None, overdue=True, interval_hours=interval_hours)
        last_utc = _as_utc(last)
        overdue = (datetime.now(UTC) - last_utc) > timedelta(hours=interval_hours)
        return BackupStatus(tenant, last_utc.isoformat(), overdue, interval_hours)

    def rekey_and_record(self, fingerprint: str, actor: str = "system:maintenance") -> int:
        """Rotate the key in place (AD-47): re-encrypt every application-encrypted value under
        the PRIMARY key AND record the rotation on every data-bearing tenant's chain — ALL in one
        transaction, so a crash cannot leave data rotated but the audit partial. `fingerprint`
        names WHICH key (a one-way hash), never the key. Returns the number of values rewritten."""
        from apx.adapters.store_postgres.backfill import rekey_all

        now = datetime.now(UTC)
        for attempt in range(4):
            try:
                with self._sf() as session, session.begin():
                    count = rekey_all(session.connection())
                    for tenant in self._tenants(session):
                        self._append_audit(
                            session, tenant, None, actor, "key_rotated", f"key={fingerprint}", now)
                    session.flush()  # surface a (tenant, seq) collision inside the try
                return count
            except IntegrityError:
                if attempt == 3:
                    raise
                continue
        raise RuntimeError("unreachable")  # the loop returns or raises

    # ── configuration-as-data: one audited surface for every per-tenant value (AD-24/AD-25) ──

    def set_config(self, tenant: str, actor: str, key: str, value: object) -> ConfigChange:
        """The one write path for a configuration-as-data value (AD-25). Validates ``value``
        against the declared schema (an unknown key or a wrong-typed value raises ``ConfigError``
        — never a silent default), records an audit entry carrying actor/key/before/after
        atomically with the write (so the change is reversible — set ``before`` back to restore),
        and is a no-op that writes NO audit entry when the value is unchanged. A change to a
        retrieval-affecting key is flagged on the entry as the AD-23 staleness hook."""
        spec = require_key(key)          # ConfigError on an unknown key
        new_value = spec.coerce(value)    # ConfigError on a wrong-typed / out-of-range value
        for attempt in range(4):
            try:
                with self._sf() as session, session.begin():
                    row = session.get(TenantSetting, {"tenant": tenant, "key": key})
                    before = _config_value(spec, row)
                    if before == new_value:
                        return ConfigChange(key, before, new_value, changed=False)
                    self._refuse_immutable_chunking_change(session, tenant, key)
                    self._apply_config_change(session, tenant, actor, spec, before, new_value)
                    session.flush()  # surface a (tenant, seq) collision inside the try
                return ConfigChange(key, before, new_value, changed=True)
            except IntegrityError:
                if attempt == 3:
                    raise
        raise RuntimeError("unreachable")  # the loop returns or raises

    def _refuse_immutable_chunking_change(self, session: Session, tenant: str, key: str) -> None:
        """AD-40: chunking config is immutable once a *corpus* exists. Changing it would strand
        every existing chunk as a superseded generation (they resolve ``config-superseded`` and the
        old params are unrecoverable, only the hash is stored), so it is refused, not silent.
        Allowed before the first chunk, or via an audited re-chunk (a later story). Review MED-1."""
        if key != "chunking_target_chars":
            return
        has_corpus = session.scalar(
            select(Chunk.chunk_id).where(Chunk.tenant == tenant).limit(1))
        if has_corpus is not None:
            raise ConfigError(
                "chunking_target_chars is immutable once a corpus exists (AD-40): the change would "
                "supersede every existing chunk. Re-chunk through an audited migration.")

    def _apply_config_change(self, session: Session, tenant: str, actor: str, spec: ConfigKey,
                             before: object, after: object) -> None:
        """Write (or update) one setting row and append its ``config_changed`` audit entry — the
        single place the row + audit shape live, shared by ``set_config`` and ``provision_tenant``
        so the two never drift. Runs inside the caller's transaction."""
        row = session.get(TenantSetting, {"tenant": tenant, "key": spec.name})
        if row is None:
            session.add(TenantSetting(tenant=tenant, key=spec.name, value=dumps_value(after)))
        else:
            row.value = dumps_value(after)
        self._append_audit(
            session, tenant, None, actor, "config_changed",
            _config_change_detail(spec.name, before, after, spec.affects_retrieval),
            datetime.now(UTC))

    def get_config(self, tenant: str, key: str) -> object:
        """One configuration value — the tenant's stored value, or the schema default when it
        was never set. Raises ``ConfigError`` on an unknown key."""
        spec = require_key(key)
        with self._sf() as session:
            row = session.get(TenantSetting, {"tenant": tenant, "key": key})
        return _config_value(spec, row)

    def get_all_config(self, tenant: str) -> list[ConfigItem]:
        """Every configuration-as-data value for the tenant — the schema, each key carrying its
        current value (stored or default) and its default. This is the read half of the one
        surface (AD-25)."""
        with self._sf() as session:
            stored = {
                r.key: r for r in session.execute(
                    select(TenantSetting).where(TenantSetting.tenant == tenant)
                ).scalars().all()
            }
        return [
            ConfigItem(key, _config_value(spec, stored.get(key)), spec.default, spec.governs)
            for key, spec in CONFIG_SCHEMA.items()
        ]

    def config_provenance(self, tenant: str) -> list[ConfigProvenance]:
        """Reconcile every stored setting row against the tenant's audited config changes, so a
        value written by a direct DB edit (bypassing the surface) is detectable (AD-25). A row is
        ``audited`` only when its current value equals the last audited change for its key; a key
        whose last audited change set a non-default value but which now has NO row was reverted by
        a direct DELETE and is reported ``audited=False`` (its effective value is the default).
        Reads the audit detail as RAW ciphertext + ``_safe_decrypt`` (like ``read_audit``), so one
        undecryptable row — after a key rotation, say — degrades instead of 500-ing the surface."""
        with self._sf() as session:
            rows = session.execute(
                select(TenantSetting).where(TenantSetting.tenant == tenant)
            ).scalars().all()
            detail_cts = session.execute(
                select(cast(AuditRecord.detail, Text))
                .where(AuditRecord.tenant == tenant, AuditRecord.action == "config_changed")
                .order_by(AuditRecord.seq)
            ).scalars().all()
        audited_after: dict[str, object] = {}
        for detail_ct in detail_cts:
            detail = _safe_decrypt(detail_ct, "audit_record.detail")
            if detail is None:
                continue  # undecryptable → contributes no audited value (no 500)
            parsed = _parse_config_detail(detail)
            if parsed is not None:
                audited_after[parsed[0]] = parsed[1]  # last write wins (ordered by seq)
        out: list[ConfigProvenance] = []
        row_keys: set[str] = set()
        for row in rows:
            row_keys.add(row.key)
            try:
                value = loads_value(row.value)
            except ValueError:
                value = None
            audited = row.key in audited_after and audited_after[row.key] == value
            out.append(ConfigProvenance(row.key, value, audited))
        # a key last audited to a NON-default value but with no row now = a direct DELETE that
        # reverted it off the record (e.g. silently turning MFA back off) — surface it.
        for key, after in audited_after.items():
            spec = CONFIG_SCHEMA.get(key)
            if key not in row_keys and spec is not None and after != spec.default:
                out.append(ConfigProvenance(key, spec.default, audited=False))
        return out

    def provision_tenant(
        self, tenant: str, admin_email: str, admin_password: str, admin_name: str,
        scopes: set[str], taxonomy: list[str], *, actor: str = "system:provisioning",
    ) -> str:
        """Provision a tenant through the surface (AD-25): establish its FIRST administrative
        grant (an is_admin user with its scopes) and seed its taxonomy as an audited configuration
        value, in ONE transaction, writing a ``tenant_provisioned`` audit entry. Fails closed with
        ``TenantAlreadyProvisioned`` if the tenant already has an administrator OR the admin email
        is already taken — never a silent takeover of a live firm, and never a raw IntegrityError
        (a concurrent bootstrap loser is translated too). Returns the new administrator's id."""
        email = admin_email.strip().lower()
        coerced_tax = coerce("taxonomy", list(taxonomy))  # validate before opening the tx
        wall_set = set(scopes)
        uid = uuid4().hex
        now = datetime.now(UTC)
        try:
            with self._sf() as session, session.begin():
                # fail closed on an existing admin OR an existing user with this email (a
                # non-admin user already holding the email would otherwise IntegrityError on insert)
                clash = session.scalar(
                    select(func.count()).select_from(User).where(
                        User.tenant == tenant,
                        or_(User.is_admin.is_(True), User.email == email)))
                if (clash or 0) > 0:
                    raise TenantAlreadyProvisioned(
                        f"tenant {tenant!r} already has an administrator or a user {email!r}")
                session.add(User(
                    id=uid, tenant=tenant, email=email,
                    password_hash=hash_password(admin_password),
                    display_name=admin_name, is_admin=True))
                for scope in sorted(wall_set):
                    session.add(UserScope(user_id=uid, scope=scope))
                self._append_audit(
                    session, tenant, None, actor, "tenant_provisioned",
                    f"admin={email} scopes={sorted(wall_set)} taxonomy={len(coerced_tax)}", now)
                session.flush()
                self._append_audit(
                    session, tenant, None, actor, "create_user",
                    f"subject={uid} email={email} scopes={sorted(wall_set)} admin=True", now)
                session.flush()
                if coerced_tax:  # seed the taxonomy as an audited value (empty is the default)
                    self._apply_config_change(
                        session, tenant, actor, require_key("taxonomy"), [], coerced_tax)
                    session.flush()
        except IntegrityError as exc:  # a concurrent bootstrap that slipped past the guard
            raise TenantAlreadyProvisioned(
                f"tenant {tenant!r} was provisioned concurrently") from exc
        return uid

    # ── MFA reads/writes route through the config surface (one audited path, AD-25) ──

    def set_mfa_required(self, tenant: str, required: bool, actor: str = "system:config") -> None:
        """Turn MFA (TOTP) on or off for a tenant — through the audited config surface (AD-25)."""
        self.set_config(tenant, actor, "mfa_required", required)

    def set_mfa_secret(self, user_id: str, secret: str) -> None:
        """Enrol a user's TOTP secret (minimal enrolment; the secret is a shared secret,
        not a reversible password store — AD-15)."""
        with self._sf() as session, session.begin():
            user = session.get(User, user_id)
            if user is None:
                raise ValueError("unknown user")
            user.mfa_secret = secret

    def mfa_status(self, tenant: str, user_id: str) -> tuple[bool, str | None]:
        """(whether the tenant requires MFA, the user's TOTP secret or None) — the login
        gate reads this to decide whether a second factor is demanded. One session (the login
        hot path): the mfa_required config row and the user's secret in a single round trip."""
        with self._sf() as session:
            cfg = session.get(TenantSetting, {"tenant": tenant, "key": "mfa_required"})
            required = bool(_config_value(require_key("mfa_required"), cfg))
            secret = session.scalar(select(User.mfa_secret).where(User.id == user_id))
        return required, secret

    def verify_user_password(self, user_id: str, password: str) -> bool:
        """Check a password for a known user id (used to confirm a self-service change)."""
        with self._sf() as session:
            user = session.get(User, user_id)
            return user is not None and verify_password(password, user.password_hash)

    def set_password(self, user_id: str, new_password: str) -> None:
        """Replace a user's password with a fresh Argon2id hash (plaintext never stored)."""
        with self._sf() as session, session.begin():
            user = session.get(User, user_id)
            if user is None:
                raise ValueError("unknown user")
            user.password_hash = hash_password(new_password)

    def list_users(self, tenant: str) -> list[UserInfo]:
        """Every user in the tenant with their scopes — the cockpit roster."""
        with self._sf() as session:
            users = session.execute(
                select(User).where(User.tenant == tenant).order_by(User.email)
            ).scalars().all()
            out = [
                UserInfo(
                    u.id, u.email, u.display_name, u.is_admin,
                    tuple(sorted(
                        scope for (scope,) in session.execute(
                            select(UserScope.scope).where(UserScope.user_id == u.id)
                        ).all()
                    )),
                )
                for u in users
            ]
        return out

    def _audited_tx(self, work: Callable[[Session, datetime], None]) -> None:
        """Run a scope-mutation-plus-audit as one transaction, retrying on a concurrent
        (tenant, seq) audit collision — the same hazard record_auth_event handles. `work`
        raises a domain ValueError for a bad request (propagated, never retried)."""
        now = datetime.now(UTC)
        for attempt in range(4):
            try:
                with self._sf() as session, session.begin():
                    work(session, now)
                return
            except IntegrityError:
                if attempt == 3:
                    raise

    def grant_scope(self, tenant: str, actor: str, user_id: str, scope: str) -> None:
        """Grant a wall to a user on the authority of `actor` (an administrator) — audited and
        reversible (FR-49). Idempotent: re-granting a held scope is a no-op that writes no
        phantom audit entry. Takes effect on the user's next request (scope resolved live)."""
        if not scope.strip():
            raise ValueError("scope is required")

        def _work(session: Session, now: datetime) -> None:
            user = session.scalar(select(User).where(User.id == user_id, User.tenant == tenant))
            if user is None:
                raise ValueError("unknown user")
            if session.get(UserScope, {"user_id": user_id, "scope": scope}) is None:
                session.add(UserScope(user_id=user_id, scope=scope))
                self._append_audit(
                    session, tenant, None, actor, "grant_scope",
                    f"subject={user_id} scope={scope}", now)

        self._audited_tx(_work)

    def revoke_scope(self, tenant: str, actor: str, user_id: str, scope: str) -> None:
        """Revoke a wall from a user on the authority of `actor` — audited and reversible
        (FR-49). Revoking a scope the user does not hold is a no-op that writes no phantom
        audit entry. Takes effect on the user's next request."""
        def _work(session: Session, now: datetime) -> None:
            user = session.scalar(select(User).where(User.id == user_id, User.tenant == tenant))
            if user is None:
                raise ValueError("unknown user")
            row = session.get(UserScope, {"user_id": user_id, "scope": scope})
            if row is not None:
                session.delete(row)
                self._append_audit(
                    session, tenant, None, actor, "revoke_scope",
                    f"subject={user_id} scope={scope}", now)

        self._audited_tx(_work)

    def rescope_matter(self, tenant: str, actor: str, matter: str, new_scope: str) -> None:
        """Move a matter's wall — update the ONE authoritative matter_scope row and record one
        audit entry with before->after. Because scope is resolved live at query time (AD-13),
        this takes effect at the next query with nothing to propagate and no re-index. Rejects a
        no-op (same scope), an unknown matter, and an empty scope — never a silent write (FR-49)."""
        if not new_scope.strip():
            raise ValueError("scope is required")

        def _work(session: Session, now: datetime) -> None:
            row = session.get(MatterScope, {"tenant": tenant, "matter": matter})
            if row is None:
                raise ValueError("unknown matter")
            if row.scope == new_scope:
                raise ValueError("matter is already in that scope")  # no silent no-op
            before = row.scope
            row.scope = new_scope
            self._append_audit(
                session, tenant, matter, actor, "rescope_matter",
                f"subject={matter} scope={before}->{new_scope}", now)

        self._audited_tx(_work)

    def set_user_admin(self, tenant: str, actor: str, subject_user: str, is_admin: bool) -> None:
        """Grant or revoke the administrative authority for a user — an audited, admin-only,
        reversible act (AC2). Refuses to revoke the LAST administrator of a tenant (no lockout).
        A no-op (already at the target flag) writes no phantom entry. The first admin is the
        provisioned one; holding it does not widen a data read (AD-12)."""
        def _work(session: Session, now: datetime) -> None:
            user = session.scalar(
                select(User).where(User.id == subject_user, User.tenant == tenant))
            if user is None:
                raise ValueError("unknown user")
            if user.is_admin == is_admin:
                return  # no change — no phantom audit entry
            if not is_admin:
                admins = session.scalar(
                    select(func.count()).select_from(User).where(
                        User.tenant == tenant, User.is_admin.is_(True)))
                if (admins or 0) <= 1:
                    raise ValueError("cannot revoke the last administrator")
            user.is_admin = is_admin
            action = "grant_admin" if is_admin else "revoke_admin"
            self._append_audit(session, tenant, None, actor, action, f"subject={subject_user}", now)

        self._audited_tx(_work)

    def read_audit(self, matter: str, tenant: str, scopes: set[str]) -> AuditTrail:
        """The audit trail for a matter — scope-checked. The chain is per-tenant
        (a single authority, FR-24), so verification recomputes the WHOLE tenant
        chain end to end; a gap, reorder or truncation anywhere flips `verified`.
        The returned entries are this matter's slice (FR-53)."""
        with self._sf() as session:
            scope = session.scalar(
                select(MatterScope.scope).where(
                    MatterScope.matter == matter, MatterScope.tenant == tenant
                )
            )
            if scope is None or scope not in scopes:
                raise ScopeDenied(matter)
            # Read the encrypted actor/detail as RAW ciphertext — cast(..., Text) uses Text's
            # (identity) result processor, bypassing EncryptedText's eager decryption — so ONE
            # undecryptable row (a tamper, a wrong key, a legacy plaintext value) degrades the
            # trail to verified=False instead of raising and 500-ing the whole tenant read.
            # Every other column keeps its native ORM type (timestamp stays a datetime).
            rows = session.execute(
                select(
                    AuditRecord.seq, AuditRecord.matter,
                    cast(AuditRecord.actor, Text), AuditRecord.action,
                    cast(AuditRecord.detail, Text), AuditRecord.chain, AuditRecord.timestamp,
                )
                .where(AuditRecord.tenant == tenant)
                .order_by(AuditRecord.seq)
            ).all()

        verified = True
        prev_chain = ""
        entries: list[AuditEntry] = []
        for i, (seq, r_matter, actor_ct, action, detail_ct, chain, ts) in enumerate(rows):
            actor = _safe_decrypt(actor_ct, "audit_record.actor")
            detail = _safe_decrypt(detail_ct, "audit_record.detail")
            if actor is None or detail is None:
                verified = False  # an unreadable field cannot be authenticated
            content = _audit_content(
                seq, tenant, r_matter, actor or "", action, detail or "", _audit_ts(ts)
            )
            if seq != i + 1 or _audit_chain(prev_chain, content) != chain:
                verified = False
            prev_chain = chain
            if r_matter == matter:
                entries.append(AuditEntry(
                    seq, actor if actor is not None else "«illisible»", action,
                    detail if detail is not None else "«illisible»", chain, ts.isoformat()))
        return AuditTrail(entries, verified)

    # ── Story 4.1: the optional case theory — versioned, audited, referenceable ────────────────
    def _version_view(self, row: CaseTheoryVersion) -> CaseTheoryVersionView:
        return CaseTheoryVersionView(
            version_no=row.version_no, version_id=row.id, text=row.text,
            actor=row.actor, created_at=row.created_at)

    def _case_theory_state(self, latest: CaseTheoryVersion | None) -> CaseTheory:
        """The current state derived from the latest version row: none set → absent; a NULL-text
        latest → withdrawn; else present."""
        if latest is None:
            return CaseTheory(present=False, withdrawn=False, current=None)
        view = self._version_view(latest)
        if latest.text is None:  # a withdrawal version
            return CaseTheory(present=False, withdrawn=True, current=view)
        return CaseTheory(present=True, withdrawn=False, current=view)

    def append_case_theory_version(
        self, *, tenant: str, matter: str, actor: str, text: str | None
    ) -> CaseTheory:
        """The ONE owning use case (AD-37) for a case theory version — APPEND-ONLY (FR-37).
        Normalises ``text`` ("" → None, a *withdrawal*); a NO-OP that writes neither a version nor
        an audit entry when the text equals the current active/withdrawn state (as ``set_config``).
        Otherwise appends ``version_no = prev + 1``, updates the denormalised
        ``matter_scope.case_theory`` cache, and writes ONE audit entry
        (``case_theory_written`` / ``case_theory_withdrawn``) ATOMIC with the version (AD-22 — both
        commit or neither). The ``(tenant, matter, version_no)`` unique constraint makes a
        concurrent double-write fail loudly and retry, never silently overwrite (AD-37 conditional
        commit). Raises ``ValueError`` for an unknown matter. This method NEVER triggers any
        recompute — its only effects are the version row, the cache update and the one audit entry
        (the "re-rank is never automatic" guarantee; ranking does not exist yet)."""
        normalized = (text or "").strip() or None
        box: list[CaseTheory] = []

        def _work(session: Session, now: datetime) -> None:
            ms = session.get(MatterScope, {"tenant": tenant, "matter": matter})
            if ms is None:
                raise ValueError("unknown matter")
            latest = session.scalar(
                select(CaseTheoryVersion)
                .where(CaseTheoryVersion.tenant == tenant, CaseTheoryVersion.matter == matter)
                .order_by(CaseTheoryVersion.version_no.desc())
                .limit(1))
            effective = latest.text if latest is not None else None
            if effective == normalized:
                box.append(self._case_theory_state(latest))  # no change — no version, no audit
                return
            version_no = (latest.version_no if latest is not None else 0) + 1
            row = CaseTheoryVersion(
                id=case_theory_version_id(tenant, matter, version_no, normalized),
                tenant=tenant, matter=matter, version_no=version_no,
                text=normalized, actor=actor, created_at=now)
            session.add(row)
            ms.case_theory = normalized  # the denormalised current-value cache tracks the latest
            action = "case_theory_written" if normalized is not None else "case_theory_withdrawn"
            self._append_audit(session, tenant, matter, actor, action, f"version={version_no}", now)
            box.append(self._case_theory_state(row))

        self._audited_tx(_work)
        return box[-1]

    def read_case_theory(
        self, *, tenant: str, matter: str, scopes: set[str]
    ) -> CaseTheory | None:
        """The current state of a matter's case theory — scope pre-filtered (AD-13). Returns None
        when the matter is out of scope OR absent (indistinguishable — non-disclosing, FR-14);
        a ``CaseTheory`` (possibly ``present=False``) when the matter's wall is held. Not audited
        (a read; the writes are the audited acts, FR-37)."""
        with self._sf() as session:
            held = session.scalar(
                select(MatterScope.matter).where(
                    MatterScope.tenant == tenant, MatterScope.matter == matter,
                    MatterScope.scope.in_(sorted(scopes))))
            if held is None:
                return None
            latest = session.scalar(
                select(CaseTheoryVersion)
                .where(CaseTheoryVersion.tenant == tenant, CaseTheoryVersion.matter == matter)
                .order_by(CaseTheoryVersion.version_no.desc())
                .limit(1))
            return self._case_theory_state(latest)

    def list_case_theory_versions(
        self, *, tenant: str, matter: str, scopes: set[str]
    ) -> list[CaseTheoryVersionView] | None:
        """The full readable history of a matter's case theory, ascending by ``version_no`` (FR-37
        "retains previous versions readably") — scope pre-filtered the same way as
        :meth:`read_case_theory`. Returns None when the matter is out of scope or absent."""
        with self._sf() as session:
            held = session.scalar(
                select(MatterScope.matter).where(
                    MatterScope.tenant == tenant, MatterScope.matter == matter,
                    MatterScope.scope.in_(sorted(scopes))))
            if held is None:
                return None
            rows = session.scalars(
                select(CaseTheoryVersion)
                .where(CaseTheoryVersion.tenant == tenant, CaseTheoryVersion.matter == matter)
                .order_by(CaseTheoryVersion.version_no.asc())).all()
            return [self._version_view(r) for r in rows]

    # ── Story 4.3: the ranked order + the reproducible ranking version ─────────────────────────
    def _operative_case_theory_version_id(
        self, session: Session, tenant: str, matter: str
    ) -> str | None:
        """The id of the matter's OPERATIVE case-theory version — the conditional-commit input
        (AD-23/AD-37). None when none was ever set OR the latest version is a *withdrawal* (text
        NULL), MIRRORING ``_case_theory_state`` (a withdrawn theory is absent, present=False). This
        matters: an intrinsic ranking records ``case_theory_version_id=None``, so comparing against
        the raw latest-row id would treat a *withdrawn* matter (latest row present but NULL-text) as
        forever stale and permanently refuse every ranking on it. The ``text IS NULL`` check is a DB
        predicate — the ciphertext is never decrypted here."""
        row = session.execute(
            select(CaseTheoryVersion.id, CaseTheoryVersion.text.is_(None))
            .where(CaseTheoryVersion.tenant == tenant, CaseTheoryVersion.matter == matter)
            .order_by(CaseTheoryVersion.version_no.desc())
            .limit(1)).first()
        if row is None or row[1]:  # no version, or the latest is a withdrawal → operative is absent
            return None
        return row[0]

    def record_ranking(
        self, *, tenant: str, matter: str, actor: str, identity: RankingIdentity, order: RankedOrder
    ) -> RankingVersion:
        """The ONE owning use case (AD-37) for a *ranking version* — APPEND-ONLY (FR-39). Mints the
        per-matter monotonic ``version_no`` and the referenceable ``version_id`` (AD-23), persists
        the
        version + one :class:`~apx.adapters.store_postgres.models.RankedEntry` per pièce (the ranked
        order plus the unscored tail — the whole population, AD-36), and writes ONE
        ``ranking_recorded``
        audit entry ATOMIC with the write (AD-22). The commit is CONDITIONAL (AD-23/AD-37): it
        re-reads
        the matter's latest case-theory version inside the transaction and raises
        :class:`StaleRankingInput` (nothing written) if it differs from the recorded
        ``case_theory_version_id``. The ``(tenant, matter, version_no)`` unique constraint makes a
        concurrent double-write fail loudly and retry, never overwrite. Raises ``ValueError`` for an
        unknown matter. Returns the minted domain :class:`RankingVersion`."""
        box: list[RankingVersion] = []

        def _work(session: Session, now: datetime) -> None:
            ms = session.get(MatterScope, {"tenant": tenant, "matter": matter})
            if ms is None:
                raise ValueError("unknown matter")
            # conditional commit — a case theory that moved under the ranking invalidates it
            # (AD-23). Compared against the OPERATIVE id (None for a withdrawn/absent theory), so a
            # withdrawn matter's intrinsic ranking (recorded None) still commits.
            current_ct = self._operative_case_theory_version_id(session, tenant, matter)
            if current_ct != identity.case_theory_version_id:
                raise StaleRankingInput(
                    f"case theory changed under the ranking (recorded "
                    f"{identity.case_theory_version_id}, now {current_ct})")
            prev = session.scalar(
                select(func.max(RankingVersionRow.version_no))
                .where(RankingVersionRow.tenant == tenant, RankingVersionRow.matter == matter))
            version_no = (prev or 0) + 1
            version = RankingVersion.build(
                tenant=tenant, matter=matter, version_no=version_no, identity=identity)
            session.add(RankingVersionRow(
                id=version.version_id, tenant=tenant, matter=matter, version_no=version_no,
                fingerprint=identity.fingerprint, basis=identity.basis,
                identity_json=identity.canonical_json(),
                case_theory_version_id=identity.case_theory_version_id,
                stage3_share=order.stage3_share, created_at=now))
            for row in order.all_rows:
                session.add(RankedEntry(
                    id=hashlib.sha256(
                        f"{version.version_id}\x00{row.piece_id}".encode()).hexdigest(),
                    ranking_version_id=version.version_id, tenant=tenant, matter=matter,
                    piece_id=row.piece_id, rank=row.rank, outcome=row.outcome.value,
                    score=row.score, band=row.band.value if row.band is not None else None,
                    label=row.label,
                    rejection_class=(
                        row.rejection_class.value if row.rejection_class is not None else None),
                    failure_reason=row.failure_reason, family_id=row.family_id,
                    is_representative=row.is_representative, supersedes=row.supersedes,
                    confidence=row.confidence,  # Story 4.4 — None == not derived (AD-19)
                    confidence_signals=(
                        ",".join(s.value for s in row.confidence_signals)
                        if row.confidence_signals else None)))
            self._append_audit(
                session, tenant, matter, actor, "ranking_recorded",
                f"version={version_no} fingerprint={identity.fingerprint[:12]} "
                f"ranked={len(order.rows)} unscored={len(order.unscored_rows)} "
                f"stage3_share={order.stage3_share:.4f}", now)
            box.append(version)

        self._audited_tx(_work)
        return box[-1]

    def _ranking_version_view(
        self, session: Session, row: RankingVersionRow
    ) -> RankingVersionView:
        ranked = session.scalar(
            select(func.count()).select_from(RankedEntry).where(
                RankedEntry.ranking_version_id == row.id, RankedEntry.rank.isnot(None))) or 0
        unscored = session.scalar(
            select(func.count()).select_from(RankedEntry).where(
                RankedEntry.ranking_version_id == row.id, RankedEntry.rank.is_(None))) or 0
        return RankingVersionView(
            version_no=row.version_no, version_id=row.id, fingerprint=row.fingerprint,
            basis=row.basis, case_theory_version_id=row.case_theory_version_id,
            stage3_share=row.stage3_share, ranked_count=ranked, unscored_count=unscored,
            created_at=row.created_at)

    def _matter_held(self, session: Session, tenant: str, matter: str, scopes: set[str]) -> bool:
        """Whether the matter's wall is within ``scopes`` (AD-13). A False is indistinguishable from
        an absent matter to the caller (non-disclosing, FR-14)."""
        return session.scalar(
            select(MatterScope.matter).where(
                MatterScope.tenant == tenant, MatterScope.matter == matter,
                MatterScope.scope.in_(sorted(scopes)))) is not None

    def read_ranking(
        self, *, tenant: str, matter: str, scopes: set[str]
    ) -> RankingVersionView | None:
        """The matter's latest ranking version — scope pre-filtered (AD-13). Returns None when the
        matter is out of scope OR absent OR has no ranking yet (indistinguishable — non-disclosing,
        FR-14). Not audited (a read)."""
        with self._sf() as session:
            if not self._matter_held(session, tenant, matter, scopes):
                return None
            row = session.scalar(
                select(RankingVersionRow)
                .where(RankingVersionRow.tenant == tenant, RankingVersionRow.matter == matter)
                .order_by(RankingVersionRow.version_no.desc()).limit(1))
            return self._ranking_version_view(session, row) if row is not None else None

    def list_ranking_versions(
        self, *, tenant: str, matter: str, scopes: set[str]
    ) -> list[RankingVersionView] | None:
        """The matter's full ranking-version history, ascending by ``version_no`` (AD-23 — every
        version is retained and referenceable). Scope pre-filtered; None when out of scope or
        absent."""
        with self._sf() as session:
            if not self._matter_held(session, tenant, matter, scopes):
                return None
            rows = session.scalars(
                select(RankingVersionRow)
                .where(RankingVersionRow.tenant == tenant, RankingVersionRow.matter == matter)
                .order_by(RankingVersionRow.version_no.asc())).all()
            return [self._ranking_version_view(session, r) for r in rows]

    def read_ranked_order(
        self, *, tenant: str, matter: str, scopes: set[str], version_no: int | None = None
    ) -> list[RankedEntryView] | None:
        """The ordered rows of a ranking version (the latest when ``version_no`` is None) — scope
        pre-filtered. Ordered BY the integer ``rank`` (collation-independent, AC-3); the UNSCORED
        rows (rank NULL) come as a named tail ordered by ``piece_id``, never interleaved into the
        order (AD-19). Returns None when the matter is out of scope or absent; ``[]`` when the
        matter
        is held but has no such ranking version."""
        with self._sf() as session:
            if not self._matter_held(session, tenant, matter, scopes):
                return None
            pinned = (
                [RankingVersionRow.version_no == version_no] if version_no is not None else [])
            target = session.scalar(
                select(RankingVersionRow.id)
                .where(
                    RankingVersionRow.tenant == tenant, RankingVersionRow.matter == matter, *pinned)
                .order_by(RankingVersionRow.version_no.desc()).limit(1))
            if target is None:
                return []  # held, but no such ranking version — distinguishable from out-of-scope
            rows = session.scalars(
                select(RankedEntry)
                .where(RankedEntry.ranking_version_id == target)
                # ranked rows first (rank not NULL) in rank order, then the unscored tail by
                # piece_id
                # — never SQL collation, portable NULL placement (AC-3/AD-19).
                .order_by(RankedEntry.rank.is_(None), RankedEntry.rank, RankedEntry.piece_id)).all()
            return [
                RankedEntryView(
                    piece_id=r.piece_id, rank=r.rank, outcome=r.outcome, score=r.score,
                    band=r.band, label=r.label, rejection_class=r.rejection_class,
                    failure_reason=r.failure_reason, family_id=r.family_id,
                    is_representative=r.is_representative, supersedes=r.supersedes,
                    confidence=r.confidence, confidence_signals=r.confidence_signals)
                for r in rows]

    # ── Story 4.5: per-pièce taxonomy labelling — the append-only, version-independent ledger ────
    def _current_taxonomy(self, session: Session, tenant: str) -> list[str]:
        """The tenant's configured taxonomy list (config-as-data), read INSIDE the caller's tx so a
        label is validated against the taxonomy current at write time (AD-24/AD-25)."""
        spec = require_key("taxonomy")
        row = session.get(TenantSetting, {"tenant": tenant, "key": "taxonomy"})
        return list(loads_value(row.value)) if row is not None else list(spec.default)

    def _append_label_entry(
        self, session: Session, now: datetime, *, tenant: str, matter: str, actor: str,
        piece_id: str, label: str, source: LabelSource, expected_seq: int | None, note: str,
    ) -> int:
        """Validate + append ONE label ledger entry (and its audit) inside the caller's tx (the
        caller has already scope-checked). Validates ``label`` against the CURRENT taxonomy ∪
        {unlabelled} — an out-of-taxonomy label can never leak (FR-40). Mints the per-pièce
        monotonic ``seq`` (AD-49); a conditional commit on ``expected_seq`` fails loudly if it moved
        (AD-37). Never overwrites — this is always an INSERT (AD-7). Returns the new ``seq``."""
        validate_label(label, self._current_taxonomy(session, tenant))
        current_max = session.scalar(
            select(func.max(TaxonomyLabelEntry.seq)).where(
                TaxonomyLabelEntry.tenant == tenant, TaxonomyLabelEntry.matter == matter,
                TaxonomyLabelEntry.piece_id == piece_id)) or 0
        if expected_seq is not None and current_max != expected_seq:
            raise StaleLabel(
                f"label moved under the edit (observed seq {expected_seq}, now {current_max})")
        seq = current_max + 1
        entry_id = hashlib.sha256(
            f"{tenant}\x00{matter}\x00{piece_id}\x00{seq}".encode()).hexdigest()
        session.add(TaxonomyLabelEntry(
            id=entry_id, tenant=tenant, matter=matter, piece_id=piece_id, seq=seq,
            label=label, source=source.value, set_by=actor, at=now))
        self._append_audit(
            session, tenant, matter, actor, "piece_labelled",
            f"piece={piece_id[:12]} label={label} source={source.value} seq={seq} {note}", now)
        return seq

    def assign_label(
        self, *, tenant: str, matter: str, actor: str, piece_id: str, label: str,
        scopes: set[str], expected_seq: int | None = None,
    ) -> int:
        """Assign a *pièce*'s taxonomy label — the ONE owning use case (AD-37), APPEND-ONLY (FR-40).
        Validates against the tenant's current taxonomy ∪ {unlabelled} (out-of-taxonomy can never
        leak); appends one ledger entry with a server monotonic ``seq`` (AD-49) ATOMIC with
        one ``piece_labelled`` audit entry (AD-22); NEVER overwrites — a change is a new entry
        (AD-7). CONDITIONAL on ``expected_seq`` when supplied: a label that moved raises
        :class:`StaleLabel` (nothing written). Scope-checked (``ScopeDenied``, non-disclosing).
        Returns the new ``seq``. Touches ONLY the label ledger — never the ranked order, so a label
        never moves a *pièce* or the line (FR-43)."""
        box: list[int] = []

        def _work(session: Session, now: datetime) -> None:
            if not self._matter_held(session, tenant, matter, scopes):
                raise ScopeDenied(matter)
            box.append(self._append_label_entry(
                session, now, tenant=tenant, matter=matter, actor=actor, piece_id=piece_id,
                label=label, source=LabelSource.HUMAN, expected_seq=expected_seq, note="assigned"))

        self._audited_tx(_work)
        return box[-1]

    def revert_label(
        self, *, tenant: str, matter: str, actor: str, piece_id: str, to_seq: int,
        scopes: set[str],
    ) -> int:
        """Revert a *pièce*'s taxonomy label to the value it held at ``to_seq`` — reversible from
        the change log (FR-40/FR-20). A reversal is a NEW human-set entry restoring a prior value,
        never a destructive undo (AD-7). The restored value is re-validated against the CURRENT
        taxonomy, so a reversion cannot re-introduce a category the taxonomy no longer contains
        (revert to ``unlabelled`` is always possible). Scope-checked. Returns the new ``seq``.
        Raises ``ValueError`` if ``to_seq`` is not an entry of this *pièce*."""
        box: list[int] = []

        def _work(session: Session, now: datetime) -> None:
            if not self._matter_held(session, tenant, matter, scopes):
                raise ScopeDenied(matter)
            prior = session.scalar(
                select(TaxonomyLabelEntry.label).where(
                    TaxonomyLabelEntry.tenant == tenant, TaxonomyLabelEntry.matter == matter,
                    TaxonomyLabelEntry.piece_id == piece_id, TaxonomyLabelEntry.seq == to_seq))
            if prior is None:
                raise ValueError(f"no label entry at seq {to_seq} for this pièce")
            box.append(self._append_label_entry(
                session, now, tenant=tenant, matter=matter, actor=actor, piece_id=piece_id,
                label=prior, source=LabelSource.HUMAN, expected_seq=None,
                note=f"reverted to seq {to_seq}"))

        self._audited_tx(_work)
        return box[-1]

    def read_current_label(
        self, *, tenant: str, matter: str, piece_id: str, scopes: set[str]
    ) -> CurrentLabel | None:
        """A *pièce*'s CURRENT taxonomy label — a VIEW over the append-only ledger (the max-``seq``
        entry, or ``unlabelled`` when none — never null, FR-40). ``in_current_taxonomy`` is False
        for a label the taxonomy no longer contains (shown as such, never remapped). Scope
        pre-filtered (None when out of scope or absent — non-disclosing). Not audited (a read)."""
        with self._sf() as session:
            if not self._matter_held(session, tenant, matter, scopes):
                return None
            rows = session.execute(
                select(TaxonomyLabelEntry.piece_id, TaxonomyLabelEntry.seq,
                       TaxonomyLabelEntry.label, TaxonomyLabelEntry.source)
                .where(TaxonomyLabelEntry.tenant == tenant, TaxonomyLabelEntry.matter == matter,
                       TaxonomyLabelEntry.piece_id == piece_id)).all()
            taxonomy = self._current_taxonomy(session, tenant)
        view = current_label(
            LabelEntry(pid, seq, label, LabelSource(src)) for pid, seq, label, src in rows)
        return CurrentLabel(
            piece_id=piece_id, label=view.label,
            source=view.source.value if view.source is not None else None, seq=view.seq,
            in_current_taxonomy=is_member(view.label, taxonomy))

    def read_label_change_log(
        self, *, tenant: str, matter: str, piece_id: str, scopes: set[str]
    ) -> list[LabelChangeEntry] | None:
        """A *pièce*'s full taxonomy-label change log, ascending by ``seq`` (append-only, FR-40/
        FR-20 — every assignment and reversal is a distinct entry, never rewritten). Scope
        pre-filtered; None when out of scope or absent; ``[]`` when no assignment exists."""
        with self._sf() as session:
            if not self._matter_held(session, tenant, matter, scopes):
                return None
            rows = session.scalars(
                select(TaxonomyLabelEntry)
                .where(TaxonomyLabelEntry.tenant == tenant, TaxonomyLabelEntry.matter == matter,
                       TaxonomyLabelEntry.piece_id == piece_id)
                .order_by(TaxonomyLabelEntry.seq.asc())).all()
            return [
                LabelChangeEntry(
                    seq=r.seq, label=r.label, source=r.source, set_by=r.set_by, at=r.at)
                for r in rows]

    def read_label_coverage(
        self, *, tenant: str, matter: str, scopes: set[str]
    ) -> LabelCoverage | None:
        """The SM-19 labelling figures over the *pièces* of the matter's LATEST *ranking version*
        (FR-40): every pièce carries exactly one label (``without_label`` is zero by construction),
        the ``unlabelled`` share, and the count carrying a label no longer in the taxonomy
        (``out_of_taxonomy`` — the zero-silently-remapped evidence). Scope pre-filtered; None when
        out of scope or absent; zeroed when the matter has no ranking yet. Not audited (a read)."""
        with self._sf() as session:
            if not self._matter_held(session, tenant, matter, scopes):
                return None
            target = session.scalar(
                select(RankingVersionRow.id)
                .where(RankingVersionRow.tenant == tenant, RankingVersionRow.matter == matter)
                .order_by(RankingVersionRow.version_no.desc()).limit(1))
            if target is None:
                return LabelCoverage(0, 0, 0, 0.0, 0, 0)
            piece_ids = list(session.scalars(
                select(RankedEntry.piece_id).where(RankedEntry.ranking_version_id == target)).all())
            entries = session.execute(
                select(TaxonomyLabelEntry.piece_id, TaxonomyLabelEntry.seq,
                       TaxonomyLabelEntry.label, TaxonomyLabelEntry.source)
                .where(TaxonomyLabelEntry.tenant == tenant,
                       TaxonomyLabelEntry.matter == matter)).all()
            taxonomy = self._current_taxonomy(session, tenant)
        by_piece: dict[str, list[LabelEntry]] = {}
        for pid, seq, label, src in entries:
            by_piece.setdefault(pid, []).append(LabelEntry(pid, seq, label, LabelSource(src)))
        labelled = unlabelled = out_of_taxonomy = 0
        for pid in piece_ids:
            view = current_label(by_piece.get(pid, ()))
            if view.is_unlabelled:
                unlabelled += 1
            else:
                labelled += 1
                if not is_member(view.label, taxonomy):
                    out_of_taxonomy += 1
        total = len(piece_ids)
        return LabelCoverage(
            total=total, labelled=labelled, unlabelled=unlabelled,
            unlabelled_share=(unlabelled / total) if total else 0.0,
            out_of_taxonomy=out_of_taxonomy, without_label=0)

    # ── Story 4.7: the retained/discarded sets are VIEWS derived from the order + line + pins ─────
    def read_triage_sets(
        self, *, tenant: str, matter: str, scopes: set[str], line: Line | None = None,
        pins: tuple[Pin, ...] = (), version_no: int | None = None,
    ) -> TriageSets | None:
        """The *retained*/*discarded*/*unscored* sets for a *ranking version*, DERIVED at read time
        from the persisted order + the given line cut + pins (FR-16/AD-39) — **never a stored
        membership**. The view names its ``version_id`` (AD-23 — no unqualified reference). ``line``
        and ``pins`` are INPUTS (their owning use cases are Story 4.8/4.11); ``line=None`` means no
        split yet. Scope pre-filtered (AD-13); returns None when out of scope, absent, or with no
        such ranking version (non-disclosing). Not audited (a read)."""
        with self._sf() as session:
            if not self._matter_held(session, tenant, matter, scopes):
                return None
            pinned = (
                [RankingVersionRow.version_no == version_no] if version_no is not None else [])
            target = session.execute(
                select(RankingVersionRow.id, RankingVersionRow.version_no)
                .where(
                    RankingVersionRow.tenant == tenant, RankingVersionRow.matter == matter, *pinned)
                .order_by(RankingVersionRow.version_no.desc()).limit(1)).first()
            if target is None:
                return None  # held, but no such ranking version — nothing to derive a view over
            version_id = target[0]
            rows = session.execute(
                select(RankedEntry.piece_id, RankedEntry.rank)
                .where(RankedEntry.ranking_version_id == version_id)
                .order_by(RankedEntry.rank.is_(None), RankedEntry.rank, RankedEntry.piece_id)).all()
        ranked = [pid for pid, rank in rows if rank is not None]
        unscored = [pid for pid, rank in rows if rank is None]
        return derive_triage_sets(
            ranked=ranked, unscored=unscored, line=line, pins=pins, version_id=version_id)

    def read_version_retention(
        self, *, tenant: str, matter: str, scopes: set[str]
    ) -> VersionRetentionView | None:
        """The retained-ranking-versions bound status for a *matter* (FR-16) — the count of held
        versions against the configured ``retained_ranking_versions_max``. Scope pre-filtered; None
        when out of scope or absent. **Retires nothing** (AD-7): the report is informational; the
        retirement transition and the referenced-by exemption are deferred. Not audited (a read)."""
        spec = require_key("retained_ranking_versions_max")
        with self._sf() as session:
            if not self._matter_held(session, tenant, matter, scopes):
                return None
            total = session.scalar(
                select(func.count()).select_from(RankingVersionRow).where(
                    RankingVersionRow.tenant == tenant, RankingVersionRow.matter == matter)) or 0
            row = session.get(
                TenantSetting, {"tenant": tenant, "key": "retained_ranking_versions_max"})
        bound = int(loads_value(row.value)) if row is not None else int(spec.default)
        return VersionRetentionView(total=total, bound=bound, over_bound=max(0, total - bound))

    # ── Story 4.8: the tool draws the line and commits — the append-only version-bound placement ──
    def _line_retain_bands(self, session: Session, tenant: str) -> frozenset[str]:
        """The tenant's configured line-retain bands (config-as-data), read INSIDE the caller's tx
        so the cut is placed against the policy current at write time (AD-24/AD-25)."""
        spec = require_key("line_retain_bands")
        row = session.get(TenantSetting, {"tenant": tenant, "key": "line_retain_bands"})
        return frozenset(loads_value(row.value) if row is not None else spec.default)

    @staticmethod
    def _line_basis(version: RankingVersionRow) -> str:
        """The line's stated basis (FR-17), **inherited** from the *ranking version* it cuts — never
        invented. ``case-theory:<version_id>`` where the ranking was computed under a case theory,
        else ``intrinsic:<the named intrinsic signals>`` (FR-38's enumerated signals)."""
        if version.basis == "case-theory" and version.case_theory_version_id is not None:
            return f"case-theory:{version.case_theory_version_id}"
        return "intrinsic:" + ",".join(s.value for s in INTRINSIC_SIGNALS)

    def place_line(
        self, *, tenant: str, matter: str, actor: str, scopes: set[str],
        version_no: int | None = None,
    ) -> LinePlacementView | None:
        """Draw and commit **the line** over a *ranking version* — the ONE owning use case (AD-37).
        The system recommends the cut recall-first (``recommend_line`` over the version's ranked
        bands, using the tenant's ``line_retain_bands``); when a cut exists it appends one
        ``LinePlacement`` row (server monotonic ``seq``, AD-49) ATOMIC with one ``line_placed``
        audit entry (AD-22), CONDITIONAL on the ``seq`` (a concurrent double-write collides on the
        unique constraint and fails loudly, AD-37). The line is stored by the identity of the **last
        retained *pièce*** (never a bare integer, FR-17), with basis + author + timestamp. Touches
        ONLY ``line_placement`` — never ``ranked_entry`` — so placing the line cannot reorder the
        order (FR-17). Scope-checked (``ScopeDenied``, non-disclosing). Returns the placement view,
        or ``None`` when the tool commits to no line (no *pièce* in a retain-band — never
        fabricated, AD-19) or the matter has no such ranking version."""
        box: list[LinePlacementView | None] = []

        def _work(session: Session, now: datetime) -> None:
            if not self._matter_held(session, tenant, matter, scopes):
                raise ScopeDenied(matter)
            pinned = (
                [RankingVersionRow.version_no == version_no] if version_no is not None else [])
            version = session.scalars(
                select(RankingVersionRow)
                .where(
                    RankingVersionRow.tenant == tenant, RankingVersionRow.matter == matter, *pinned)
                .order_by(RankingVersionRow.version_no.desc()).limit(1)).first()
            if version is None:
                box.append(None)  # held, but no such ranking version — nothing to place a line over
                return
            rows = session.execute(
                select(RankedEntry.piece_id, RankedEntry.band)
                .where(RankedEntry.ranking_version_id == version.id,
                       RankedEntry.rank.isnot(None))
                .order_by(RankedEntry.rank)).all()
            order = [RankedBand(piece_id=pid, band=band) for pid, band in rows]
            line = recommend_line(
                order, retain_bands=self._line_retain_bands(session, tenant))
            if line is None:
                box.append(None)  # no pièce in a retain-band — the tool commits to no line (AD-19)
                return
            basis = self._line_basis(version)
            current_max = session.scalar(
                select(func.max(LinePlacement.seq)).where(
                    LinePlacement.ranking_version_id == version.id)) or 0
            seq = current_max + 1
            entry_id = hashlib.sha256(f"{version.id}\x00{seq}".encode()).hexdigest()
            session.add(LinePlacement(
                id=entry_id, tenant=tenant, matter=matter, ranking_version_id=version.id, seq=seq,
                last_retained_piece_id=line.last_retained_piece_id, basis=basis, placed_by=actor,
                at=now))
            self._append_audit(
                session, tenant, matter, actor, "line_placed",
                f"version={version.version_no} last_retained={line.last_retained_piece_id[:12]} "
                f"basis={basis} seq={seq}", now)
            box.append(LinePlacementView(
                version_id=version.id, version_no=version.version_no,
                last_retained_piece_id=line.last_retained_piece_id, basis=basis, seq=seq, at=now))

        self._audited_tx(_work)
        return box[-1]

    def read_current_line(
        self, *, tenant: str, matter: str, scopes: set[str], version_no: int | None = None,
    ) -> LinePlacementView | None:
        """The CURRENT line over a *ranking version* — a VIEW (the max-``seq`` ``LinePlacement``
        row), naming its ``version_id`` (AD-23). Scope pre-filtered (AD-13); returns None when out
        of scope, absent, with no such ranking version, or no line placed yet (non-disclosing).
        Not audited (a read)."""
        with self._sf() as session:
            if not self._matter_held(session, tenant, matter, scopes):
                return None
            pinned = (
                [RankingVersionRow.version_no == version_no] if version_no is not None else [])
            version = session.execute(
                select(RankingVersionRow.id, RankingVersionRow.version_no)
                .where(
                    RankingVersionRow.tenant == tenant, RankingVersionRow.matter == matter, *pinned)
                .order_by(RankingVersionRow.version_no.desc()).limit(1)).first()
            if version is None:
                return None
            row = session.scalars(
                select(LinePlacement)
                .where(LinePlacement.ranking_version_id == version[0])
                .order_by(LinePlacement.seq.desc()).limit(1)).first()
            if row is None:
                return None  # held ranking version, but no line placed yet
            return LinePlacementView(
                version_id=version[0], version_no=version[1],
                last_retained_piece_id=row.last_retained_piece_id, basis=row.basis, seq=row.seq,
                at=row.at)

    # ── Story 4.9: moving the line is priced — the ranking projection + the serialised move ──────
    def price_line_move(
        self, *, tenant: str, matter: str, scopes: set[str],
        candidate_last_retained_piece_id: str, version_no: int | None = None,
    ) -> PricedMove | None:
        """Price moving **the line** to a candidate position (FR-19) — Δ *pièces*-to-read and the
        change in the estimated prevalence of relevant material in the resulting discarded set, a
        **projection from the ranking** (never a sampling bound; §0.2). Compares against the CURRENT
        line (the ledger's current placement, else the system recommendation). Scope pre-filtered
        (AD-13); returns None when out of scope, absent, or with no such ranking version
        (non-disclosing). **Not audited** (a preview). Retain-everything → the discarded set is
        empty, no bound applies (never 0%); no projectable *pièce* → the prevalence unavailable."""
        with self._sf() as session:
            if not self._matter_held(session, tenant, matter, scopes):
                return None
            pinned = (
                [RankingVersionRow.version_no == version_no] if version_no is not None else [])
            version = session.scalar(
                select(RankingVersionRow.id)
                .where(
                    RankingVersionRow.tenant == tenant, RankingVersionRow.matter == matter, *pinned)
                .order_by(RankingVersionRow.version_no.desc()).limit(1))
            if version is None:
                return None
            rows = session.execute(
                select(RankedEntry.piece_id, RankedEntry.band, RankedEntry.confidence)
                .where(RankedEntry.ranking_version_id == version, RankedEntry.rank.isnot(None))
                .order_by(RankedEntry.rank)).all()
            placed = session.scalar(
                select(LinePlacement.last_retained_piece_id)
                .where(LinePlacement.ranking_version_id == version)
                .order_by(LinePlacement.seq.desc()).limit(1))
            retain_bands = self._line_retain_bands(session, tenant)
        order = [(pid, band, conf) for pid, band, conf in rows]
        if placed is not None:
            current_line: Line | None = Line(last_retained_piece_id=placed)
        else:  # no line placed yet — the system recommendation is the implicit current position
            current_line = recommend_line(
                [RankedBand(piece_id=pid, band=band) for pid, band, _ in rows],
                retain_bands=retain_bands)
        candidate_line = Line(last_retained_piece_id=candidate_last_retained_piece_id)
        return project_line_move(order, current_line, candidate_line)

    def move_line(
        self, *, tenant: str, matter: str, actor: str, scopes: set[str],
        last_retained_piece_id: str, expected_seq: int, priced_statement: str,
        version_no: int | None = None,
    ) -> LinePlacementView:
        """Commit a human move of **the line** to a chosen *pièce* (FR-19) — appends a
        ``LinePlacement`` (append-only, AD-7), **CONDITIONAL on ``expected_seq``**: a move against a
        superseded position raises :class:`StaleLine` with the current position and writes nothing
        (the serialised-move rule — the line is a single per-*matter* parameter, not a cell). The
        write is atomic with one ``line_moved`` audit entry recording old position, new position,
        author, ranking version, the projection method and the **priced statement that was shown**
        (FR-19). Touches only ``line_placement`` — never the order. Scope-checked (``ScopeDenied``).
        Raises ``ValueError`` when the chosen *pièce* is not in the version's ranked order."""
        box: list[LinePlacementView] = []

        def _work(session: Session, now: datetime) -> None:
            if not self._matter_held(session, tenant, matter, scopes):
                raise ScopeDenied(matter)
            pinned = (
                [RankingVersionRow.version_no == version_no] if version_no is not None else [])
            version = session.scalars(
                select(RankingVersionRow)
                .where(
                    RankingVersionRow.tenant == tenant, RankingVersionRow.matter == matter, *pinned)
                .order_by(RankingVersionRow.version_no.desc()).limit(1)).first()
            if version is None:
                raise ValueError("no ranking version to move the line over")
            ranked_ids = set(session.scalars(
                select(RankedEntry.piece_id).where(
                    RankedEntry.ranking_version_id == version.id,
                    RankedEntry.rank.isnot(None))).all())
            if last_retained_piece_id not in ranked_ids:
                raise ValueError(
                    f"the line names a pièce not in the ranked order: {last_retained_piece_id}")
            current = session.execute(
                select(LinePlacement.seq, LinePlacement.last_retained_piece_id)
                .where(LinePlacement.ranking_version_id == version.id)
                .order_by(LinePlacement.seq.desc()).limit(1)).first()
            current_seq = current[0] if current is not None else 0
            current_last = current[1] if current is not None else None
            if expected_seq != current_seq:  # the line moved under the caller (AD-37) — refuse
                raise StaleLine(current_seq, current_last)
            basis = self._line_basis(version)
            seq = current_seq + 1
            entry_id = hashlib.sha256(f"{version.id}\x00{seq}".encode()).hexdigest()
            session.add(LinePlacement(
                id=entry_id, tenant=tenant, matter=matter, ranking_version_id=version.id, seq=seq,
                last_retained_piece_id=last_retained_piece_id, basis=basis, placed_by=actor,
                at=now))
            self._append_audit(
                session, tenant, matter, actor, "line_moved",
                f"version={version.version_no} old={(current_last or 'none')[:12]} "
                f"new={last_retained_piece_id[:12]} method={PROJECTION_METHOD} "
                f"priced={priced_statement}", now)
            box.append(LinePlacementView(
                version_id=version.id, version_no=version.version_no,
                last_retained_piece_id=last_retained_piece_id, basis=basis, seq=seq, at=now))

        self._audited_tx(_work)
        return box[-1]
