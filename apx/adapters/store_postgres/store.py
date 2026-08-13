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
import secrets
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import Text, and_, cast, delete, event, func, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from apx.adapters.store_postgres.backfill import case_theory_version_id, link_id
from apx.adapters.store_postgres.chunk_writer import UnauthorizedScope
from apx.adapters.store_postgres.crypto_types import cipher
from apx.adapters.store_postgres.deterministic_query import exact_search_stmt
from apx.adapters.store_postgres.models import (
    ArtefactStamp,
    AuditChainHead,
    AuditRecord,
    BackupRecord,
    CaseTheoryVersion,
    Chunk,
    Failure,
    ImportJob,
    ImportUnit,
    JustificationRejection,
    LabelRecord,
    LinePlacement,
    MatterScope,
    NoiseExclusion,
    Piece,
    PieceCustodian,
    PieceJustification,
    PieceProvenance,
    PinEntry,
    RankedEntry,
    RecallReview,
    SamplingRun,
    SamplingRunItem,
    SamplingVerdict,
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
from apx.core.domain import audit as AUDIT
from apx.core.domain.auth import hash_password, verify_and_upgrade, verify_password
from apx.core.domain.cascade import INTRINSIC_SIGNALS
from apx.core.domain.chunking import (
    PIECE_GONE,
    FailedResolution,
    ResolvedPassage,
    chunking_config,
    resolve_passage,
)
from apx.core.domain.confidence import (
    ESTIMATOR_METHOD,
    PrevalenceBound,
    RecordedBound,
    pieces_upper_bound,
)
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
from apx.core.domain.freshness import (
    KIND_BOUND,
    KIND_LINE,
    KIND_RANKING,
    KIND_SAMPLING_RUN,
    FreshnessStamp,
    compare_stamps,
    config_digest,
    extraction_digest,
    population_digest,
)
from apx.core.domain.head_journal import (
    HeadEntry,
    HeadJournal,
    Reconciliation,
    journal_scope,
    tenant_of,
)
from apx.core.domain.inventory import Inventory
from apx.core.domain.justification import (
    EvidenceExtract,
    JustificationBasis,
    VerifiedJustification,
    rebuild_justification,
    validate_named_evidence,
    verify_justification,
)
from apx.core.domain.line import LinePlacementView, RankedBand, recommend_line
from apx.core.domain.line_projection import (
    PROJECTION_METHOD,
    PricedMove,
)
from apx.core.domain.line_projection import (
    price_line_move as project_line_move,
)
from apx.core.domain.normalization import normalize
from apx.core.domain.pin import (
    PinAction,
    PinLogEntry,
    current_pins,
    validate_pin_reason,
)
from apx.core.domain.ranking import (
    RankedOrder,
    RankingIdentity,
    RankingVersion,
)
from apx.core.domain.retrieval import DeterministicResult, SemanticResult
from apx.core.domain.sampling import (
    NO_CUT_FR,
    NO_POPULATION_FR,
    STATUS_ABANDONED,
    STATUS_COMPLETED,
    STATUS_OPEN,
    DrawnFamily,
    SamplingRunView,
    SamplingUnit,
    Sizing,
    VerdictEntry,
    bound_for_run,
    draw_families,
    group_discarded_families,
    is_census,
    no_population_sizing,
    size_for_target,
)
from apx.core.domain.search import snippet
from apx.core.domain.taxonomy_label import (
    UNLABELLED,
    LabelEntry,
    LabelSource,
    current_label,
    is_member,
    validate_label,
)
from apx.core.domain.triage import TriageOutcome
from apx.core.domain.triage_sets import Line, Pin, PinSide, TriageSets, derive_triage_sets
from apx.core.domain.triage_table import (
    SIDE_DISCARDED,
    SIDE_RETAINED,
    SIDE_UNSCORED,
    SIDE_UNSPLIT,
    ChangeLogEntry,
    LineView,
    TriageRow,
    TriageTable,
    pair_change_log,
)
from apx.core.ports.read import ExactSearch, PieceView
from apx.core.ports.sampling import InvalidatedRun, RunAlreadyClosed
from apx.core.projection import Snapshot

_log = logging.getLogger("apx.store")

# A valid hash to verify against when the user is unknown, so authentication takes the
# same time whether or not the email exists (no user-enumeration by timing).
_DUMMY_HASH = hash_password("timing-equalizer")

#: Provisioning has no human author, so it names the component instead — FR-24: "system-initiated
#: entries name the system component as actor rather than attributing them to a user".
_PROVISIONING = AUDIT.system_actor("provisioning")

_APP_VERSION = "0.1.0"           # the application version stamped on a head-journal entry (AD-35)
_HEAD_SCHEMA_VERSION = "slice-a"  # the payload schema version (AD-40) stamped on the head
# The tenant-owned tables a logical backup captures (each has a `tenant` column). `user_scope` is
# keyed by user_id (tenant-bound via the user) and is handled specially in backup/restore.
_BACKUP_TABLES = (
    "matter_scope", "user_account", "session", "tenant_setting",
    "piece", "chunk", "failure", "noise_exclusion", "piece_label", "audit_record",
    # The chain heads travel WITH the record (Story 5.5, AD-43). Two things break without them:
    # a restored matter chain has no anchor, so its first link is unprovable and the restore-time
    # verification cannot pass; and the sequence authority is gone, so the next act after a restore
    # allocates seq 1 again — colliding with the restored entries, or worse, silently forking the
    # chain. A backup that omits the allocator restores a record it cannot continue.
    "audit_chain_head",
    "recall_review",
    "backup_record", "truncation_marker", "taxonomy_label_entry", "line_placement", "pin_entry",
    "piece_justification", "justification_rejection",
)


def _join_family_sizes(families: Sequence[SamplingUnit]) -> str:
    """The population's family sizes, sorted descending and comma-joined (Story 5.2, OQ-4 input 1).

    Sorted at the freeze so the *pièce* worst case — the sum of the D largest — is a prefix sum of
    what was stored, and so a later reader cannot accidentally take the FIRST D (draw order) for the
    LARGEST D and understate. Counts only: no identity, no content, no PII."""
    return ",".join(str(n) for n in sorted(
        (len(u.member_piece_ids) for u in families), reverse=True))


def _split_family_sizes(raw: str | None) -> tuple[int, ...] | None:
    """The frozen sizes back, or ``None`` for a run that never froze them (a Story-5.1 run).

    ``None`` is *not computable* and is carried as such all the way to the surface; it is never
    softened into an empty tuple, which would read as *a population of no families* and silently
    make the worst case zero — the flattering direction (AD-19)."""
    if raw is None:
        return None
    return tuple(int(part) for part in raw.split(",") if part)


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


class StalePin(Exception):
    """The conditional commit refused a pin edit whose observed ``seq`` no longer holds (AD-37): the
    *pièce*'s pin moved under the caller between read and write. Nothing is written — a pin edit
    never silently overwrites a change the caller did not see (FR-43)."""


class StaleJustification(Exception):
    """The conditional commit refused a justification reject/restore whose observed ``seq`` no
    longer holds (AD-37): the *pièce*'s rejection state moved under the caller between read and
    write.
    Nothing is written — a reversal never silently overwrites a change the caller did not see
    (FR-18)."""


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
    journal_seq: int    # the WORST-hit chain: where its record was
    live_seq: int       # ... and where it ends now
    detected_at: str | None
    cleared_at: str | None
    chains: str = ""        # every truncated chain, "scope:was->now", comma-joined
    entries_lost: int = 0   # the TOTAL across every chain, never one chain's share


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
    chain_scope: str = ""   # the chain this entry is counted on: the matter, or "" (tenant chain)


@dataclass(frozen=True)
class ChainSlice:
    """One chain's contribution to a matter's trail, and what a reader can conclude about it.

    A matter's history spans two chains after Story 5.5: its own, and — for anything written before
    the migration — the *tenant* chain, where the record used to keep everything. The second slice
    is **not verifiable in isolation**: its links run through entries belonging to other matters,
    which the reader is not entitled to see (FR-24 scopes the read). Saying so is the point. One
    boolean over both would assert a property of bytes the reader does not hold."""

    chain_scope: str
    entries: int
    verified: bool
    verifiable_in_isolation: bool
    broken_at: int | None = None


@dataclass(frozen=True)
class AuditTrail:
    entries: list[AuditEntry]
    verified: bool  # every slice recomputes cleanly (no gap, reorder or truncation)
    slices: tuple[ChainSlice, ...] = ()


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
class PinChangeEntry:
    """One entry in a *pièce*'s pin change log (Story 4.11, FR-43/FR-25) — append-only, in ``seq``
    order. A pin (retain/discard) is an *override* with its reason; a ``removed`` action lifts it.
    ``set_by``/``at`` make each act attributable and reversible from the log."""

    seq: int
    action: str
    reason: str
    set_by: str
    at: datetime


@dataclass(frozen=True)
class JustificationRejectionEntry:
    """One entry in a *pièce*'s justification-rejection change log (Story 4.6, FR-18) — append-only,
    in ``seq`` order. ``action`` is ``rejected``/``restored``; ``reason`` is the optional note;
    ``set_by``/``at`` make each act attributable and reversible from the log."""

    seq: int
    action: str
    reason: str | None
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


# The chained content and the chain value live in the Domain (apx.core.domain.audit) as of Story
# 5.5: there is ONE recipe per content version and ONE verifier, and both are reachable from a
# reader that holds an export and no adapter. The adapter-local copies they replaced are gone —
# two implementations of a tamper-evidence rule is one implementation and one liability.


def _snapshot_isolation_sql(dialect: str) -> str | None:
    """The statement that pins a backup's reads to ONE moment, or None where the engine already
    gives that.

    PostgreSQL defaults to READ COMMITTED, where every statement sees a different snapshot — so a
    backup could read ``audit_chain_head`` after a commit that ``audit_record`` was read before,
    capturing an allocator ahead of its own record (review, confirmed). SQLite serialises writers
    against a reader, so it has the property already and rejects the SET."""
    return "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ" if dialect == "postgresql" else None


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
            (journal_scope(obj.tenant, obj.chain_scope), obj.seq, obj.chain)
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
        # Keep the highest seq per CHAIN from this commit — never per tenant: one commit can append
        # to a matter chain and the tenant chain at once (an anchoring), and their sequence numbers
        # belong to different countings. Collapsing them would journal one chain's head under the
        # other's name, and the reconciliation would then compare a seq against an unrelated one.
        for scope, seq, chain in heads:
            if scope not in highest or seq > highest[scope][0]:
                highest[scope] = (seq, chain)
        now = _audit_ts(datetime.now(UTC))
        for scope, (seq, chain) in highest.items():
            try:
                self._journal.record(HeadEntry(
                    scope, seq, chain, now, _APP_VERSION, _HEAD_SCHEMA_VERSION))
            except OSError as exc:
                # Surfaced two ways, never silent (AC5): a WARNING log now, and the sticky
                # `journal_degraded` flag the DR status reads. A head we could not record means a
                # later restore-truncation to this point could go undetected — an operator alarm.
                self.journal_degraded = True
                _log.warning(
                    "head journal write failed for scope %s at seq %s: %s", scope, seq, exc)

    def _lock_chain_head(
        self, session: Session, tenant: str, chain_scope: str
    ) -> AuditChainHead | None:
        """The chain's head row, locked for the rest of this transaction (AD-43), or None when the
        chain has never been written to.

        ``with_for_update`` is the whole point: the number is allocated from a locked row inside
        the acting transaction, so a gap is impossible **by construction** rather than detectable
        after the fact. On SQLite the lock is a no-op (the engine serialises whole writers, so the
        invariant holds anyway); on PostgreSQL it serialises the two writers instead of killing the
        loser on the unique constraint — which AD-22 would turn into a refused legitimate action."""
        return session.execute(
            select(AuditChainHead)
            .where(AuditChainHead.tenant == tenant, AuditChainHead.chain_scope == chain_scope)
            .with_for_update()
        ).scalar_one_or_none()

    def _append_audit(self, session: Session, tenant: str, matter: str | None,
                      actor: str, action: str, detail: str, ts: datetime) -> str:
        """Append one entry inside the caller's transaction (atomic with the act, FR-53), and
        return its chain value.

        The verb must be catalogued and the actor must be somebody (:mod:`apx.core.domain.audit`):
        an uncatalogued verb manufactures an act class no filter, count or export will ever
        surface, and an entry attributed to ``"unknown"`` is worse than no entry at all, because it
        is countable, filterable and looks defensible.

        The chain the entry lands on is the **catalogue's**, never the caller's: a *tenant*-level
        act (a scope grant, a configuration change) goes on the tenant chain even when a *matter*
        is in hand, and a *matter*-level act with no *matter* is refused rather than quietly filed
        under the tenant. The ``matter`` column still records what the act was *about*; the chain
        records where it is *counted*."""
        catalogued = AUDIT.act(action)          # UncataloguedAct on an unknown verb
        AUDIT.check_actor(actor)                # UnknownActor on nobody
        if catalogued.chain == AUDIT.CHAIN_TENANT:
            chain_scope = AUDIT.TENANT_CHAIN
        else:
            if not matter:
                raise ValueError(
                    f"{action!r} is a matter-level act and cannot be recorded without a matter")
            chain_scope = matter

        head = self._lock_chain_head(session, tenant, chain_scope)
        anchor = ""
        if head is not None:
            prev_seq, prev_chain = head.seq, head.chain
        else:
            anchor = self._open_chain(session, tenant, chain_scope, actor, ts)
            # Opening took the TENANT head lock, which serialises openers. Re-read this chain's
            # head under that lock: a concurrent transaction may have created it while we waited,
            # and continuing from it is the difference between a wait and a refused act. Without
            # this re-read the second opener inserts a duplicate head row and dies on the primary
            # key — the "refused legitimate act" the lock exists to eliminate (review, confirmed).
            head = self._lock_chain_head(session, tenant, chain_scope)
            if head is not None:
                prev_seq, prev_chain = head.seq, head.chain
            else:
                prev_seq, prev_chain = 0, anchor

        seq = prev_seq + 1
        content = AUDIT.chained_content(
            version=AUDIT.CONTENT_V2, seq=seq, tenant=tenant, chain_scope=chain_scope,
            matter=matter, actor=actor, action=action, detail=detail, timestamp=_audit_ts(ts),
            app_version=_APP_VERSION, schema_version=_HEAD_SCHEMA_VERSION)
        chain = AUDIT.chain_value(prev_chain, content)
        session.add(
            AuditRecord(
                id=chain, tenant=tenant, chain_scope=chain_scope, seq=seq, matter=matter,
                actor=actor, action=action, detail=detail, chain=chain, timestamp=ts,
                content_version=AUDIT.CONTENT_V2,
                app_version=_APP_VERSION, schema_version=_HEAD_SCHEMA_VERSION,
            )
        )
        if head is not None:
            # The head row is the only mutable thing here, and it is not the record: it is the
            # allocator. The entries themselves are never updated (AC-1, asserted structurally).
            head.seq, head.chain, head.updated_at = seq, chain, ts
        else:
            session.add(AuditChainHead(
                tenant=tenant, chain_scope=chain_scope, seq=seq, chain=chain, anchor=anchor,
                opened_at=ts, updated_at=ts))
        return chain

    def _open_chain(
        self, session: Session, tenant: str, chain_scope: str, actor: str, ts: datetime
    ) -> str:
        """Open a chain and return the value its first entry chains onto (AD-43, D4).

        A *matter* chain is **anchored**: a ``chain_opened`` entry is written on the *tenant* chain
        first, and the *matter* chain's first entry chains onto it. What that buys, precisely: the
        first link of a matter chain has a predecessor like every other link, and the tenant chain
        carries a complete list of every chain ever opened, so an honest reader can tell a matter
        that never wrote from a matter whose chain was removed wholesale.

        **What it does not buy, and this was reviewed:** it is not a defence against an attacker
        with write access to the database. The chain is an unkeyed SHA-256 and the anchor is a
        plaintext column, so anyone who can rewrite the entries can re-chain them from the true
        anchor and leave every internal check satisfied. Two skeptics reproduced exactly that.
        Currency against such an attacker comes from the head journal (AD-35), which lives outside
        the restorable store — not from anything inside it.

        Taking the TENANT head lock here is also what serialises two concurrent openers of the same
        chain (see the re-read in ``_append_audit``).

        The *tenant* chain is the root and anchors onto nothing: it opens at the empty chain value,
        which is also where every pre-5.5 record started."""
        if chain_scope == AUDIT.TENANT_CHAIN:
            return ""
        return self._append_audit(
            session, tenant, None, actor, AUDIT.ACT_CHAIN_OPENED,
            f"chain={chain_scope}", ts)

    def save(
        self,
        result: IngestionResult,
        scope: str,
        actor: str,
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
                self._append_audit(session, tenant, matter, actor, AUDIT.ACT_INGEST, detail, now)
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
            self._append_audit(session, j.tenant, j.matter, j.actor, AUDIT.ACT_INGEST, detail, now)
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
                session, f.tenant, f.matter, actor, AUDIT.ACT_RETRY,
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
            self._append_audit(session, tenant, matter, actor, AUDIT.ACT_BULK_RETRY, detail, now)
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
                session, tenant, None, actor, AUDIT.ACT_EXPORT_REGISTER,
                f"lines={len(entries)} scopes={len(scopes)}", now or datetime.now(UTC))
        return RegisterExport(tuple(entries), len(scopes))

    def audit_bound_export(
        self, *, tenant: str, matter: str, actor: str, detail: str,
        now: datetime | None = None,
    ) -> None:
        """Record the export of a *confidence bound* as an audited egress act (FR-53/FR-58).

        The bound is the sentence a firm says to a judge; taking it out of the system is an act, not
        a read, so it is on the chain with the stamp it was exported under. A **refused** export
        writes nothing — the refusal is not an export."""
        with self._sf() as session, session.begin():
            self._append_audit(
                session, tenant, matter, actor, AUDIT.ACT_EXPORT_BOUND, detail,
                now or datetime.now(UTC))

    def audit_query(
        self, tenant: str, actor: str, *, term: str, engine: str, scopes: set[str],
        denominator: Inventory | None = None, action: str = AUDIT.ACT_SEARCH,
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
            self._append_audit(session, tenant, matter, actor, AUDIT.ACT_OPEN_PIECE,
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
            self._append_audit(session, tenant, matter, actor, AUDIT.ACT_JUDGE, detail, now)

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

    # ── RETIRED (Story 5.1, planning decision A1) ────────────────────────────────────────────
    # ``sample_discards`` and ``record_recall_review`` used to draw from and bound the Story-2.x
    # LABEL PILE (``label_record WHERE label='discard'``). Epic 5's discarded set is the Epic-4
    # DERIVED view, so both acts are superseded by the *sampling run* (``start_sampling_run`` ...
    # ``complete_sampling_run``) below. This is a supersession, not a deletion: every existing
    # ``recall_review`` row stays readable forever with its bound (AD-7), ``read_current_bound``
    # still falls back to them when a matter has no run, and ``no_new_legacy_bound`` asserts no
    # code path can start writing them again.

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
                    scopes: set[str], *, is_admin: bool = False,
                    actor: str = _PROVISIONING) -> str:
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
                session, tenant, None, actor, AUDIT.ACT_CREATE_USER,
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
        """Every live chain head, keyed by journal scope — (last seq, its chain value).

        Keyed per CHAIN, not per tenant (AD-43): a tenant now runs several chains, each with its
        own counting, and a max taken across them would compare one chain's sequence number
        against another's on the next reconciliation. The *tenant* chain keeps the bare tenant as
        its key, which is exactly what every head recorded before Story 5.5 carries — so the
        journal needs no migration and no recorded line is reinterpreted.

        Read from the head rows, which are the sequence authority. A ``MAX(seq)`` over the entries
        would answer the same today and quietly disagree the moment a head row and its entries part
        company — which is the condition a truncation check exists to notice."""
        rows = session.execute(
            select(AuditChainHead.tenant, AuditChainHead.chain_scope,
                   AuditChainHead.seq, AuditChainHead.chain)
        ).all()
        return {
            journal_scope(tenant, scope): (int(seq), chain or "")
            for tenant, scope, seq, chain in rows
        }

    def audit_heads(self) -> dict[str, tuple[int, str]]:
        with self._sf() as session:
            return self._audit_heads(session)

    def record_current_heads(self, journal: HeadJournal | None = None) -> int:
        """Record every live CHAIN head to the journal (called at start-up, after the
        boot reconcile). Returns how many heads were recorded. The journal is append-only and grows
        one line per advance; a long-lived run would want periodic compaction (retain the latest
        head per scope) — deferred, immaterial at the single-firm design target (AD-32)."""
        j = journal or self._journal
        if j is None:
            return 0
        now = _audit_ts(datetime.now(UTC))
        count = 0
        for scope, (seq, chain) in self.audit_heads().items():
            j.record(HeadEntry(scope, seq, chain, now, _APP_VERSION, _HEAD_SCHEMA_VERSION))
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
        ONCE into both views (all-latest, and the per-scope post-clear maxima).

        The reset baseline exists because ``clear_truncation`` writes it — see
        ``_journal_acknowledged_heads``. The ``default=0`` below therefore means what it says: a
        chain that did not exist when the override was signed, not a chain nobody has heard from
        since."""
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
            cleared_at = self._marker_cleared_at(tenant_of(scope))
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
        # ONE marker per tenant describing EVERY chain that fell, not one per chain overwriting the
        # last. A restore rolls the whole database back, so several chains truncate together; the
        # per-chain loop that wrote the marker recorded whichever scope sorted last, understating
        # the loss and naming no matter (review, confirmed by execution: 20 entries lost, 1
        # reported).
        by_tenant: dict[str, list[Reconciliation]] = {}
        for rec in out:
            if rec.truncated:
                by_tenant.setdefault(tenant_of(rec.scope), []).append(rec)
        for tenant, recs in sorted(by_tenant.items()):
            self._record_truncation(tenant, recs)
        return out

    def _marker_cleared_at(self, tenant: str) -> datetime | None:
        """When the tenant's truncation marker was CLEARED by an audited override, or None when
        there is no cleared marker — none at all, or one still active. ``reconcile_heads`` uses it
        to reset the baseline past an acknowledged truncation, so a LATER one is still caught."""
        with self._sf() as session:
            m = session.get(TruncationMarker, tenant)
            return m.cleared_at if m is not None else None

    def _record_truncation(self, tenant: str, recs: list[Reconciliation]) -> None:
        """Upsert ONE active truncation marker describing every chain that fell. The keep-cleared
        decision lives in ``reconcile_heads`` (via the post-override baseline), so this ALWAYS
        records an active marker — a re-detection after an override correctly reactivates it, never
        a silent no-op that would leave a fresh data loss un-flagged.

        ``journal_seq``/``live_seq`` keep their meaning for the WORST-hit chain (the one that lost
        most), because a single pair cannot describe several chains and a reader shown the smallest
        loss is being flattered. ``entries_lost`` is the total and ``chains`` names each one."""
        if not recs:
            return
        worst = max(recs, key=lambda r: r.journal_seq - r.live_seq)
        total = sum(r.journal_seq - r.live_seq for r in recs)
        named = ", ".join(
            f"{r.scope}:{r.journal_seq}->{r.live_seq}" for r in sorted(recs, key=lambda r: r.scope))
        now = datetime.now(UTC)
        with self._sf() as session, session.begin():
            session.merge(TruncationMarker(
                tenant=tenant, detected_at=now, journal_seq=worst.journal_seq,
                live_seq=worst.live_seq, chains=named, entries_lost=total,
                cleared_by=None, reason=None, cleared_at=None))

    def truncation_status(self, tenant: str) -> TruncationStatus:
        """A tenant's truncation status — active while un-cleared (named on every export, AD-35)."""
        with self._sf() as session:
            m = session.get(TruncationMarker, tenant)
        if m is None:
            return TruncationStatus(tenant, False, 0, 0, None, None, "", 0)
        return TruncationStatus(
            tenant, active=m.cleared_at is None, journal_seq=m.journal_seq, live_seq=m.live_seq,
            detected_at=m.detected_at.isoformat(),
            cleared_at=m.cleared_at.isoformat() if m.cleared_at is not None else None,
            chains=m.chains or "", entries_lost=m.entries_lost or 0)

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
                session, tenant, None, actor, AUDIT.ACT_TRUNCATION_OVERRIDE,
                f"journal_seq={m.journal_seq} live_seq={m.live_seq}", now)

        self._audited_tx(_work)
        self._journal_acknowledged_heads(tenant)

    def _journal_acknowledged_heads(self, tenant: str) -> None:
        """Write down, in the journal, the record the override has just accepted.

        An override states one thing: *the record as it now stands is the record*. Until this
        statement was written down, ``reconcile_heads`` had nothing to compare a QUIET chain
        against afterwards — the post-clear baseline of a chain that had not written since the
        override fell back to zero, and nothing is below zero, so that chain could then be emptied
        wholesale, head row and all, and the reconciliation reported no loss at all. The tenant
        chain escaped it only by accident: the override entry is itself written on it, so it always
        had a post-clear head.

        Found by execution rather than by reading, and it is this project's recurring defect once
        more: a comparison whose right-hand side (what the journal holds AFTER the override) was
        not the same thing as its left (what the override actually accepted), failing towards the
        flattering side. Per-matter chains (AD-43) are what opened it — under one chain per tenant,
        the override entry gave every reconciliation a baseline.
        """
        if self._journal is None:
            return
        now = _audit_ts(datetime.now(UTC))
        for scope, (seq, chain) in self.audit_heads().items():
            if tenant_of(scope) != tenant:
                continue
            try:
                self._journal.record(HeadEntry(
                    scope, seq, chain, now, _APP_VERSION, _HEAD_SCHEMA_VERSION))
            except OSError as exc:
                # Same surfacing as any other post-commit head write (AC5): never silent, because
                # an unrecorded acknowledged head is exactly a later truncation nobody will see.
                self.journal_degraded = True
                _log.warning(
                    "head journal write failed for the acknowledged head of scope %s at seq %s: %s",
                    scope, seq, exc)

    # ── logical, tenant-boundary backup + an exercised restore (AD-32) ──

    def backup_tenant(self, tenant: str) -> TenantBackup:
        """A complete, tenant-boundary logical backup (AD-32). Rows are read RAW so content-bearing
        columns stay ciphertext (encrypted at rest); the tenant's head-journal tail is copied on.

        **Read in ONE snapshot.** Under READ COMMITTED each statement sees a different moment, so a
        backup taken during an ingest could capture ``audit_chain_head`` after a commit that
        ``audit_record`` was read before — an allocator ahead of its own record. Restoring that
        hands out numbers past a hole the continuity check reports forever and AD-22 forbids
        repairing. REPEATABLE READ makes the allocator and the entries the same moment. (SQLite
        serialises writers, so it has the property already and rejects the SET; the guard is on the
        dialect.)"""
        with self._sf() as session:
            conn = session.connection()
            snapshot = _snapshot_isolation_sql(conn.dialect.name)
            if snapshot is not None:
                conn.execute(text(snapshot))
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
            # EVERY chain of this tenant, not just the tenant chain (AD-43 + AD-35). A backup that
            # copied only the tenant chain's head would restore into a journal that has never heard
            # of the matter chains — and a later truncation of one of them would be undetectable,
            # which is the single failure AD-35 exists to prevent.
            head_tail = [
                asdict(entry) for scope, entry in sorted(self._journal.all_latest().items())
                if tenant_of(scope) == tenant
            ]
        return TenantBackup(
            tenant, _HEAD_SCHEMA_VERSION, tables, scopes, head_tail, piece_links=piece_links)

    def _chain_verifies(self, session: Session, tenant: str) -> bool:
        """Recompute EVERY chain of a tenant end to end from the rows in ``session`` — the same
        recomputation ``read_audit`` does, through the same verifier — returning False on any gap,
        reorder, tamper, or undecryptable field (fail closed). Used INSIDE ``restore_tenant`` so a
        corrupt or tampered backup is rejected at restore time, not silently accepted and caught
        later on a read. Every chain must hold: a restore whose tenant chain verifies while one
        matter's does not is a rejected restore."""
        entries = self._verifiable_entries(session, tenant)
        anchors = self._chain_anchors(session, tenant)
        # ``verified`` only: every link must hold. A MISSING anchor is not evidence of tampering —
        # a chain rebuilt from a pre-5.5 backup genuinely has none, and refusing the restore on
        # that would make every backup the deployment holds today unrestorable. The loss of the
        # anchor is reported to the reader instead (``verifiable_in_isolation``), which is what it
        # actually is: something they cannot check for themselves, not something that is wrong.
        return all(v.verified for v in AUDIT.verify_chains(entries, anchors))

    def _verifiable_entries(
        self, session: Session, tenant: str, chain_scopes: Sequence[str] | None = None
    ) -> list[AUDIT.VerifiableEntry]:
        """The tenant's entries as the verifier sees them — plaintext where it can be
        authenticated, ``None`` where it cannot.

        The encrypted actor/detail are read as RAW ciphertext (``cast(..., Text)`` uses Text's
        identity result processor, bypassing ``EncryptedText``'s eager decryption), so ONE
        undecryptable row — a tamper, a wrong key, a legacy plaintext value — degrades that chain
        to unverified instead of raising and 500-ing the whole read."""
        stmt = select(
            AuditRecord.seq, AuditRecord.chain_scope, AuditRecord.matter,
            cast(AuditRecord.actor, Text), AuditRecord.action, cast(AuditRecord.detail, Text),
            AuditRecord.chain, AuditRecord.timestamp, AuditRecord.content_version,
            AuditRecord.app_version, AuditRecord.schema_version,
        ).where(AuditRecord.tenant == tenant)
        if chain_scopes is not None:
            stmt = stmt.where(AuditRecord.chain_scope.in_(list(chain_scopes)))
        rows = session.execute(stmt.order_by(AuditRecord.chain_scope, AuditRecord.seq)).all()
        return [
            AUDIT.VerifiableEntry(
                tenant=tenant, chain_scope=scope, seq=seq, matter=matter,
                actor=_safe_decrypt(actor_ct, "audit_record.actor"), action=action,
                detail=_safe_decrypt(detail_ct, "audit_record.detail"),
                timestamp=_audit_ts(ts), chain=chain, content_version=version,
                app_version=app_v, schema_version=schema_v)
            for (seq, scope, matter, actor_ct, action, detail_ct, chain, ts, version,
                 app_v, schema_v) in rows
        ]

    def _chain_anchors(self, session: Session, tenant: str) -> dict[str, str]:
        """Each chain's starting value, from its head row — what makes a matter chain's FIRST link
        provable rather than taken on trust.

        An empty anchor means two different things and they must not be conflated: on the TENANT
        chain it is the root (that chain starts at the empty value, and so did every pre-5.5
        record), while on a MATTER chain it means *unknown* — the head row was rebuilt from the
        entries at restore, and the anchoring value it never carried cannot be invented. An opened
        matter chain always has a real anchor (a sha256 digest, never empty), so the distinction is
        exact. An unknown anchor is OMITTED, which makes ``verify_chains`` report the chain as not
        anchored rather than checking its first link against a value that is not its predecessor."""
        rows = session.execute(
            select(AuditChainHead.chain_scope, AuditChainHead.anchor)
            .where(AuditChainHead.tenant == tenant)
        ).all()
        return {
            scope: anchor for scope, anchor in rows
            if scope == AUDIT.TENANT_CHAIN or anchor
        }

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
            # The allocator is reconciled FIRST: a pre-5.5 backup carries no head rows, and the
            # verification below reads the anchors from them.
            self._reconcile_allocator(session, backup.tenant)
            if not self._chain_verifies(session, backup.tenant):
                raise ValueError(
                    f"restored audit chain for tenant {backup.tenant!r} does not verify — the "
                    "backup is corrupt or was tampered with (AD-35); restore refused")
        self._seed_journal_from_backup(backup, journal)
        return self.reconcile_heads(journal)

    def _reconcile_allocator(self, session: Session, tenant: str) -> None:
        """Make the restored allocator agree with the restored record, or refuse the restore.

        Two failures the review confirmed, both of which end with the tenant unable to write:

        **A backup with no head rows** — every backup taken before Story 5.5, which is every backup
        the live deployment holds today. The entries come back and the allocator does not, so the
        next audited act allocates seq 1, collides with the restored entry 1 on
        ``(tenant, chain_scope, seq)``, and AD-22 turns that into a refused action — permanently,
        for every act. The head is REBUILT from the entries here. That is not a rewrite of the
        record: the allocator is derived from the entries by definition, and rebuilding it asserts
        nothing the entries do not already say.

        **A head that disagrees with its entries** — a head ahead of the record (a tampered backup,
        or the read skew ``backup_tenant`` now prevents) would hand out numbers past a hole that
        the continuity check reports forever and AD-22 forbids repairing. A head BEHIND its entries
        would re-issue numbers already used. Either way the restore is refused rather than
        accepted into a state that cannot be corrected afterwards.
        """
        last: dict[tuple[str, str], tuple[int, str]] = {}
        rows = session.execute(
            select(AuditRecord.chain_scope, AuditRecord.seq, AuditRecord.chain)
            .where(AuditRecord.tenant == tenant)
        ).all()
        for scope, seq, chain in rows:
            key = (tenant, scope)
            if key not in last or seq > last[key][0]:
                last[key] = (int(seq), chain)

        heads = {
            (h.tenant, h.chain_scope): h for h in session.scalars(
                select(AuditChainHead).where(AuditChainHead.tenant == tenant)).all()
        }
        now = datetime.now(UTC)
        for key, (seq, chain) in sorted(last.items()):
            head = heads.get(key)
            if head is None:
                # Rebuilt, not invented: the anchor of a rebuilt matter chain is unknown, so it is
                # left empty and the chain reports itself as NOT verifiable in isolation rather
                # than claiming an anchor nobody recorded.
                session.add(AuditChainHead(
                    tenant=key[0], chain_scope=key[1], seq=seq, chain=chain, anchor="",
                    opened_at=now, updated_at=now))
                _log.warning(
                    "restore: rebuilt the audit allocator for chain %r at seq %s (the backup "
                    "carried no head row — a pre-5.5 backup)", key[1] or "<tenant>", seq)
                continue
            if (head.seq, head.chain) != (seq, chain):
                raise ValueError(
                    f"restored allocator for chain {key[1] or '<tenant>'!r} disagrees with the "
                    f"restored record (head says seq {head.seq}, the entries end at {seq}); "
                    "restore refused rather than accepted into a state AD-22 forbids repairing")
        for key, head in sorted(heads.items()):
            if key not in last and head.seq:
                raise ValueError(
                    f"restored allocator for chain {key[1] or '<tenant>'!r} claims seq {head.seq} "
                    "with no entries behind it; restore refused")

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
                            session, tenant, None, actor, AUDIT.ACT_KEY_ROTATED,
                            f"key={fingerprint}", now)
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
            session, tenant, None, actor, AUDIT.ACT_CONFIG_CHANGED,
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
                    session, tenant, None, actor, AUDIT.ACT_TENANT_PROVISIONED,
                    f"admin={email} scopes={sorted(wall_set)} taxonomy={len(coerced_tax)}", now)
                session.flush()
                self._append_audit(
                    session, tenant, None, actor, AUDIT.ACT_CREATE_USER,
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
                    session, tenant, None, actor, AUDIT.ACT_GRANT_SCOPE,
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
                    session, tenant, None, actor, AUDIT.ACT_REVOKE_SCOPE,
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
                session, tenant, matter, actor, AUDIT.ACT_RESCOPE_MATTER,
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
            action = (AUDIT.ACT_GRANT_ADMIN if is_admin
                      else AUDIT.ACT_REVOKE_ADMIN)
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
            # Two chains carry one matter's history (AD-43): its own, and the tenant chain, which
            # holds both the matterless acts and everything written before Story 5.5 migrated the
            # record. Both are read; each is verified on its own terms.
            all_entries = self._verifiable_entries(session, tenant)
            anchors = self._chain_anchors(session, tenant)
            timestamps = dict(session.execute(
                select(AuditRecord.chain, AuditRecord.timestamp)
                .where(AuditRecord.tenant == tenant)).all())

        verdicts = {v.chain_scope: v for v in AUDIT.verify_chains(all_entries, anchors)}
        mine = [e for e in all_entries if e.chain_scope == matter]
        legacy = [
            e for e in all_entries
            if e.chain_scope == AUDIT.TENANT_CHAIN and e.matter == matter
        ]

        slices: list[ChainSlice] = []
        own = verdicts.get(matter)
        if own is not None:
            slices.append(ChainSlice(
                chain_scope=matter, entries=own.entries, verified=own.verified,
                # The matter's own chain is exactly what FR-53 asks for: a reader holding only
                # these entries and the anchor recomputes every link.
                verifiable_in_isolation=own.anchored, broken_at=own.broken_at))
        # The tenant slice is reported whenever a TENANT CHAIN EXISTS, never only when this reader
        # still holds entries on it. Conditioning it on `legacy` being non-empty made a wholesale
        # removal of a matter's pre-5.5 history invisible: the slice simply disappeared and the
        # trail read clean and shorter (review, confirmed). Its own verdict still covers the whole
        # tenant chain, so a tamper anywhere on it is reported here even when this matter's share
        # of it is now zero.
        tenant_verdict = verdicts.get(AUDIT.TENANT_CHAIN)
        if tenant_verdict is not None or legacy:
            slices.append(ChainSlice(
                chain_scope=AUDIT.TENANT_CHAIN, entries=len(legacy),
                verified=tenant_verdict.verified if tenant_verdict else False,
                # Verified here by recomputing the WHOLE tenant chain, which this reader cannot do
                # from the export: the intervening links belong to matters outside their scope.
                verifiable_in_isolation=False))

        entries = [
            AuditEntry(
                e.seq, e.actor if e.actor is not None else "«illisible»", e.action,
                e.detail if e.detail is not None else "«illisible»", e.chain,
                timestamps[e.chain].isoformat(), e.chain_scope)
            for e in sorted(mine + legacy, key=lambda e: (e.timestamp, e.chain_scope, e.seq))
        ]
        # `verified` requires something to have been verified. all([]) is True, so a matter whose
        # every chain had been removed — head row and all — reported an intact record,
        # indistinguishable from a matter that never acted (review, confirmed). A record with no
        # chain is not a clean record; it is a record with nothing to check.
        verified = bool(slices) and all(s.verified for s in slices)
        return AuditTrail(entries, verified, tuple(slices))

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
            action = (AUDIT.ACT_CASE_THEORY_WRITTEN if normalized is not None
                      else AUDIT.ACT_CASE_THEORY_WITHDRAWN)
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
                session, tenant, matter, actor, AUDIT.ACT_RANKING_RECORDED,
                f"version={version_no} fingerprint={identity.fingerprint[:12]} "
                f"ranked={len(order.rows)} unscored={len(order.unscored_rows)} "
                f"stage3_share={order.stage3_share:.4f}", now)
            # the produced artefact records the state of its inputs, atomically with itself (FR-58)
            self._write_stamp(
                session, tenant=tenant, matter=matter, kind=KIND_RANKING,
                artefact_id=version.version_id, version_no=version_no, now=now)
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
            session, tenant, matter, actor, AUDIT.ACT_PIECE_LABELLED,
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
        # A pin is version-INDEPENDENT (it survives re-ranking, Story 4.11/FR-43), so the passed
        # pins may name a *pièce* unscored or absent in THIS version. Such a pin has no line
        # position to override here, so it is DORMANT for this version's view — it stays in the
        # ledger and
        # applies to any version where the *pièce* is scored. Filter to the ranked set: applying it
        # would make derive_triage_sets fail loudly (it guards a pin naming a pièce not in the
        # order), crashing the WHOLE view over one surviving pin (AD-19 — nothing imputed).
        ranked_set = set(ranked)
        applicable_pins = tuple(p for p in pins if p.piece_id in ranked_set)
        return derive_triage_sets(
            ranked=ranked, unscored=unscored, line=line, pins=applicable_pins,
            version_id=version_id)

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
                session, tenant, matter, actor, AUDIT.ACT_LINE_PLACED,
                f"version={version.version_no} last_retained={line.last_retained_piece_id[:12]} "
                f"basis={basis} seq={seq}", now)
            self._write_stamp(
                session, tenant=tenant, matter=matter, kind=KIND_LINE, artefact_id=entry_id,
                version_no=version.version_no, now=now)
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
                session, tenant, matter, actor, AUDIT.ACT_LINE_MOVED,
                f"version={version.version_no} old={(current_last or 'none')[:12]} "
                f"new={last_retained_piece_id[:12]} method={PROJECTION_METHOD} "
                f"priced={priced_statement}", now)
            self._write_stamp(
                session, tenant=tenant, matter=matter, kind=KIND_LINE, artefact_id=entry_id,
                version_no=version.version_no, now=now)
            box.append(LinePlacementView(
                version_id=version.id, version_no=version.version_no,
                last_retained_piece_id=last_retained_piece_id, basis=basis, seq=seq, at=now))

        self._audited_tx(_work)
        return box[-1]

    # ── Story 4.11: the pin — one pièce across the line (append-only, version-independent) ────────
    def _append_pin_entry(
        self, session: Session, now: datetime, *, tenant: str, matter: str, actor: str,
        piece_id: str, action: PinAction, reason: str, audit_action: str, expected_seq: int | None,
    ) -> int:
        """Validate + append ONE pin ledger entry (and its audit) inside the caller's tx (the caller
        has already scope-checked). Mints the per-*pièce* monotonic ``seq`` (AD-49); a conditional
        commit on ``expected_seq`` fails loudly if it moved (AD-37). Never overwrites — always an
        INSERT (AD-7). The audit entry is marked ``audit_action`` (``pin_override`` /
        ``pin_removed``) carrying the reason verbatim (FR-25). Returns the new ``seq``."""
        current_max = session.scalar(
            select(func.max(PinEntry.seq)).where(
                PinEntry.tenant == tenant, PinEntry.matter == matter,
                PinEntry.piece_id == piece_id)) or 0
        if expected_seq is not None and current_max != expected_seq:
            raise StalePin(
                f"pin moved under the edit (observed seq {expected_seq}, now {current_max})")
        seq = current_max + 1
        entry_id = hashlib.sha256(
            f"{tenant}\x00{matter}\x00{piece_id}\x00{seq}".encode()).hexdigest()
        session.add(PinEntry(
            id=entry_id, tenant=tenant, matter=matter, piece_id=piece_id, seq=seq,
            action=action.value, reason=reason, set_by=actor, at=now))
        self._append_audit(
            session, tenant, matter, actor, audit_action,
            f"piece={piece_id[:12]} action={action.value} seq={seq} reason={reason}", now)
        return seq

    def _current_pin_action(
        self, session: Session, tenant: str, matter: str, piece_id: str
    ) -> PinAction | None:
        """The *pièce*'s CURRENT pin action — the max-``seq`` ledger row, or None when unpinned."""
        row = session.execute(
            select(PinEntry.action).where(
                PinEntry.tenant == tenant, PinEntry.matter == matter, PinEntry.piece_id == piece_id)
            .order_by(PinEntry.seq.desc()).limit(1)).first()
        return PinAction(row[0]) if row is not None else None

    def pin_piece(
        self, *, tenant: str, matter: str, actor: str, piece_id: str, side: PinSide, reason: str,
        scopes: set[str], expected_seq: int | None = None,
    ) -> int:
        """Pin a *pièce* into or out of the *retained set* — the ONE owning use case (AD-37),
        APPEND-ONLY (FR-43). A pin is an *override* of **the line** and **requires a one-line
        reason** (FR-25 — a blank reason raises :class:`MissingPinReason`, nothing written). Appends
        one ledger
        entry with a server monotonic ``seq`` (AD-49) ATOMIC with one ``pin_override`` audit entry
        carrying the reason verbatim (AD-22). CONDITIONAL on ``expected_seq`` (a moved pin raises
        :class:`StalePin`). Scope-checked (``ScopeDenied``). Touches ONLY ``pin_entry`` — never the
        ranked order, never **the line** — so exactly one *pièce* crosses and nothing else moves
        (FR-43, the derivation is Story 4.7). Returns the new ``seq``."""
        validate_pin_reason(reason)
        box: list[int] = []

        def _work(session: Session, now: datetime) -> None:
            if not self._matter_held(session, tenant, matter, scopes):
                raise ScopeDenied(matter)
            box.append(self._append_pin_entry(
                session, now, tenant=tenant, matter=matter, actor=actor, piece_id=piece_id,
                action=PinAction(side.value), reason=reason, audit_action=AUDIT.ACT_PIN_OVERRIDE,
                expected_seq=expected_seq))

        self._audited_tx(_work)
        return box[-1]

    def remove_pin(
        self, *, tenant: str, matter: str, actor: str, piece_id: str, scopes: set[str],
        expected_seq: int | None = None,
    ) -> int:
        """Remove a *pièce*'s pin — a recorded, reversible act (FR-43). Appends a ``removed`` ledger
        entry (append-only, AD-7 — never a delete) ATOMIC with one ``pin_removed`` audit entry. NOT
        an *override* (it lifts a contradiction, it does not make one — no reason required). Raises
        ``ValueError`` when there is no active pin to remove. CONDITIONAL on ``expected_seq``
        (:class:`StalePin`). Scope-checked. Returns the new ``seq``."""
        box: list[int] = []

        def _work(session: Session, now: datetime) -> None:
            if not self._matter_held(session, tenant, matter, scopes):
                raise ScopeDenied(matter)
            current = self._current_pin_action(session, tenant, matter, piece_id)
            if current is None or current is PinAction.REMOVED:
                raise ValueError(f"no active pin to remove for pièce {piece_id}")
            box.append(self._append_pin_entry(
                session, now, tenant=tenant, matter=matter, actor=actor, piece_id=piece_id,
                action=PinAction.REMOVED, reason="", audit_action=AUDIT.ACT_PIN_REMOVED,
                expected_seq=expected_seq))

        self._audited_tx(_work)
        return box[-1]

    def read_current_pins(
        self, *, tenant: str, matter: str, scopes: set[str]
    ) -> tuple[Pin, ...] | None:
        """The in-force pins for a *matter* — a VIEW over the append-only ledger (the latest action
        per *pièce*; ``removed`` lifts it). The input :meth:`read_triage_sets` consumes so the pins
        apply to whatever *ranking version* the sets are derived over (survival is structural,
        FR-43). Scope pre-filtered (None when out of scope or absent — non-disclosing). Not
        audited (a read)."""
        with self._sf() as session:
            if not self._matter_held(session, tenant, matter, scopes):
                return None
            rows = session.execute(
                select(PinEntry.piece_id, PinEntry.seq, PinEntry.action)
                .where(PinEntry.tenant == tenant, PinEntry.matter == matter)).all()
        return current_pins(PinLogEntry(pid, seq, PinAction(action)) for pid, seq, action in rows)

    def read_pin_change_log(
        self, *, tenant: str, matter: str, piece_id: str, scopes: set[str]
    ) -> list[PinChangeEntry] | None:
        """A *pièce*'s full pin change log, ascending by ``seq`` (append-only, FR-43 — every pin and
        removal is a distinct entry, never rewritten). Scope pre-filtered; None when out of scope or
        absent; ``[]`` when the *pièce* has no pin history. Not audited (a read)."""
        with self._sf() as session:
            if not self._matter_held(session, tenant, matter, scopes):
                return None
            rows = session.scalars(
                select(PinEntry)
                .where(PinEntry.tenant == tenant, PinEntry.matter == matter,
                       PinEntry.piece_id == piece_id)
                .order_by(PinEntry.seq.asc())).all()
            return [
                PinChangeEntry(
                    seq=r.seq, action=r.action, reason=r.reason, set_by=r.set_by, at=r.at)
                for r in rows]

    # ── Story 4.6: the per-pièce justification derived from named evidence ────────────────────────
    def _target_version_id(
        self, session: Session, tenant: str, matter: str, version_no: int | None
    ) -> str | None:
        """The ranking-version id to bind a justification to — the latest, or the named
        ``version_no`` (None when the matter has no such ranking version). Mirrors
        :meth:`read_ranked_order`'s target resolution."""
        pinned = [RankingVersionRow.version_no == version_no] if version_no is not None else []
        return session.scalar(
            select(RankingVersionRow.id)
            .where(RankingVersionRow.tenant == tenant, RankingVersionRow.matter == matter, *pinned)
            .order_by(RankingVersionRow.version_no.desc()).limit(1))

    def record_justification(
        self, *, tenant: str, matter: str, actor: str, piece_id: str,
        sentence: str, basis: JustificationBasis, evidence: tuple[EvidenceExtract, ...],
        source_language: str | None = None, scopes: set[str], version_no: int | None = None,
    ) -> None:
        """Record a *pièce*'s justification against a *ranking version* (FR-41/FR-18) — the
        generation write-point (near **the line** / on demand). WRITE-ONCE per (version, *pièce*): a
        second record for the same pair fails loudly (``ValueError``), never a silent overwrite. The
        ``sentence`` is a model summary and the ``evidence`` (chunk id + quoted passage) is the
        checkable control (FR-41); both stored, the quote encrypted. One ``justification_recorded``
        audit entry ATOMIC with the write (AD-22). Scope-checked (``ScopeDenied``). Raises
        ``ValueError`` for an unknown matter / absent ranking version.

        The FR-41 named-evidence invariant is re-run HERE, before anything is written: the read path
        rebuilds a domain :class:`Justification` (whose ``__post_init__`` enforces it), so a row
        accepted without it would be **unreadable forever** — recording is write-once and AD-7
        forbids a delete. Refusing at the write leaves no row and no audit entry."""
        validate_named_evidence(sentence, basis, evidence)
        evidence_json = json.dumps(
            [[e.chunk_id, e.quoted_text] for e in evidence], ensure_ascii=False)
        intrinsic = ",".join(s.value for s in basis.intrinsic_signals)

        def _work(session: Session, now: datetime) -> None:
            if not self._matter_held(session, tenant, matter, scopes):
                raise ScopeDenied(matter)
            version_id = self._target_version_id(session, tenant, matter, version_no)
            if version_id is None:
                raise ValueError("no ranking version to record a justification against")
            entry_id = hashlib.sha256(f"{version_id}\x00{piece_id}".encode()).hexdigest()
            if session.get(PieceJustification, entry_id) is not None:
                raise ValueError(
                    "a justification is already recorded for this pièce in this ranking version")
            session.add(PieceJustification(
                id=entry_id, tenant=tenant, matter=matter, ranking_version_id=version_id,
                piece_id=piece_id, sentence=sentence, basis_kind=basis.kind,
                case_theory_version_id=basis.case_theory_version_id, intrinsic_signals=intrinsic,
                evidence_json=evidence_json, source_language=source_language, at=now))
            self._append_audit(
                session, tenant, matter, actor, AUDIT.ACT_JUSTIFICATION_RECORDED,
                f"piece={piece_id[:12]} basis={basis.named[:40]} extracts={len(evidence)}", now)

        self._audited_tx(_work)

    def read_justification(
        self, *, tenant: str, matter: str, scopes: set[str], piece_id: str,
        version_no: int | None = None, interface_language: str | None = None,
    ) -> VerifiedJustification | None:
        """A *pièce*'s justification AS SHOWN (FR-41/FR-11) — scope pre-filtered (None when out of
        scope or absent, non-disclosing). Rebuilds the domain justification, then **verifies every
        named extract at show time** by exact containment through :meth:`resolve_chunk` (a chunk
        that no longer resolves — gone, text changed, config superseded, out of range, or no longer
        containing — makes that extract UNVERIFIED and the justification ``is_unverified``, never
        ordinary). The current rejection state (the tool's assessment set aside, reversibly) is
        folded in. Carries the DERIVED confidence (Story 4.4). Not audited (a read)."""
        with self._sf() as session:
            if not self._matter_held(session, tenant, matter, scopes):
                return None
            version_id = self._target_version_id(session, tenant, matter, version_no)
            if version_id is None:
                return None
            row = session.scalar(
                select(PieceJustification).where(
                    PieceJustification.ranking_version_id == version_id,
                    PieceJustification.piece_id == piece_id))
            if row is None:
                return None
            entry = session.get(
                RankedEntry, hashlib.sha256(f"{version_id}\x00{piece_id}".encode()).hexdigest())
            confidence = entry.confidence if entry is not None else None
            signals = (
                tuple(entry.confidence_signals.split(","))
                if entry is not None and entry.confidence_signals else ())
            evidence = tuple((cid, quote) for cid, quote in json.loads(row.evidence_json))
            intrinsic = tuple(s for s in row.intrinsic_signals.split(",") if s)
            rejected = self._current_justification_rejection(session, tenant, matter, piece_id) \
                == "rejected"
        justification = rebuild_justification(
            piece_id=piece_id, sentence=row.sentence, basis_kind=row.basis_kind,
            case_theory_version_id=row.case_theory_version_id, intrinsic_signals=intrinsic,
            evidence=evidence, source_language=row.source_language, confidence=confidence,
            confidence_signals=signals)

        def _resolve(chunk_id: str, quoted_text: str) -> ResolvedPassage | FailedResolution:
            # a named extract whose chunk is unknown/gone must be UNVERIFIED, not a raised
            # ScopeDenied: the matter is already in scope here, so a refusal means the chunk is gone
            # (FR-11 — surfaced as unverified, never shown as though it resolved).
            try:
                return self.resolve_chunk(chunk_id, tenant, scopes, expected_text=quoted_text)
            except ScopeDenied:
                return FailedResolution(PIECE_GONE)

        return verify_justification(justification, _resolve, rejected=rejected)

    def _append_justification_rejection(
        self, session: Session, now: datetime, *, tenant: str, matter: str, actor: str,
        piece_id: str, action: str, reason: str | None, audit_action: str, expected_seq: int | None,
    ) -> int:
        """Validate + append ONE justification-rejection ledger entry (and its audit) inside the
        caller's tx. Mints the per-*pièce* monotonic ``seq`` (AD-49); a conditional commit on
        ``expected_seq`` fails loudly (:class:`StaleJustification`) if it moved (AD-37). Never
        overwrites — always an INSERT (AD-7). Returns the new ``seq``."""
        current_max = session.scalar(
            select(func.max(JustificationRejection.seq)).where(
                JustificationRejection.tenant == tenant, JustificationRejection.matter == matter,
                JustificationRejection.piece_id == piece_id)) or 0
        if expected_seq is not None and current_max != expected_seq:
            raise StaleJustification(
                f"rejection moved under the edit (observed seq {expected_seq}, now {current_max})")
        seq = current_max + 1
        entry_id = hashlib.sha256(
            f"{tenant}\x00{matter}\x00{piece_id}\x00{seq}".encode()).hexdigest()
        session.add(JustificationRejection(
            id=entry_id, tenant=tenant, matter=matter, piece_id=piece_id, seq=seq, action=action,
            reason=reason, set_by=actor, at=now))
        self._append_audit(
            session, tenant, matter, actor, audit_action,
            f"piece={piece_id[:12]} action={action} seq={seq} "
            f"reason={reason if reason else ''}", now)
        return seq

    def _current_justification_rejection(
        self, session: Session, tenant: str, matter: str, piece_id: str
    ) -> str | None:
        """The *pièce*'s CURRENT rejection action — the max-``seq`` ledger row, or None when the
        justification has never been rejected/restored."""
        row = session.execute(
            select(JustificationRejection.action).where(
                JustificationRejection.tenant == tenant, JustificationRejection.matter == matter,
                JustificationRejection.piece_id == piece_id)
            .order_by(JustificationRejection.seq.desc()).limit(1)).first()
        return row[0] if row is not None else None

    def reject_justification(
        self, *, tenant: str, matter: str, actor: str, piece_id: str, scopes: set[str],
        reason: str | None = None, expected_seq: int | None = None,
    ) -> int:
        """Reject the tool's assessment for a *pièce* in one action (FR-18) — set it aside,
        reversibly (append-only, AD-7 — never a delete). Recorded in the *audit record*
        (``justification_rejected``). A reason is optional (unlike an FR-25 override). Raises
        ``ValueError`` when it is already rejected. CONDITIONAL on ``expected_seq``
        (:class:`StaleJustification`). Scope-checked. Returns the new ``seq``."""
        box: list[int] = []

        def _work(session: Session, now: datetime) -> None:
            if not self._matter_held(session, tenant, matter, scopes):
                raise ScopeDenied(matter)
            if self._current_justification_rejection(session, tenant, matter, piece_id) \
                    == "rejected":
                raise ValueError(f"the assessment for pièce {piece_id} is already rejected")
            box.append(self._append_justification_rejection(
                session, now, tenant=tenant, matter=matter, actor=actor, piece_id=piece_id,
                action="rejected", reason=reason, audit_action=AUDIT.ACT_JUSTIFICATION_REJECTED,
                expected_seq=expected_seq))

        self._audited_tx(_work)
        return box[-1]

    def restore_justification(
        self, *, tenant: str, matter: str, actor: str, piece_id: str, scopes: set[str],
        reason: str | None = None, expected_seq: int | None = None,
    ) -> int:
        """Re-instate a rejected assessment for a *pièce* (FR-18) — the reversal of a rejection
        (append-only, AD-7 — a NEW ``restored`` entry, never a delete of the rejection). Recorded in
        the *audit record* (``justification_restored``). Raises ``ValueError`` when there is nothing
        to restore (not currently rejected). CONDITIONAL on ``expected_seq``. Scope-checked. Returns
        the new ``seq``."""
        box: list[int] = []

        def _work(session: Session, now: datetime) -> None:
            if not self._matter_held(session, tenant, matter, scopes):
                raise ScopeDenied(matter)
            if self._current_justification_rejection(session, tenant, matter, piece_id) \
                    != "rejected":
                raise ValueError(f"no rejected assessment to restore for pièce {piece_id}")
            box.append(self._append_justification_rejection(
                session, now, tenant=tenant, matter=matter, actor=actor, piece_id=piece_id,
                action="restored", reason=reason, audit_action=AUDIT.ACT_JUSTIFICATION_RESTORED,
                expected_seq=expected_seq))

        self._audited_tx(_work)
        return box[-1]

    def read_justification_rejection_log(
        self, *, tenant: str, matter: str, piece_id: str, scopes: set[str]
    ) -> list[JustificationRejectionEntry] | None:
        """A *pièce*'s full justification-rejection change log, ascending by ``seq`` (append-only,
        FR-18 — every reject and restore is a distinct entry, never rewritten). Scope pre-filtered;
        None when out of scope or absent; ``[]`` when the *pièce* has no rejection history. Not
        audited (a read)."""
        with self._sf() as session:
            if not self._matter_held(session, tenant, matter, scopes):
                return None
            rows = session.scalars(
                select(JustificationRejection)
                .where(JustificationRejection.tenant == tenant,
                       JustificationRejection.matter == matter,
                       JustificationRejection.piece_id == piece_id)
                .order_by(JustificationRejection.seq.asc())).all()
            return [
                JustificationRejectionEntry(
                    seq=r.seq, action=r.action, reason=r.reason, set_by=r.set_by, at=r.at)
                for r in rows]

    # ── Story 4.10: the triage table — ONE coherent read of ONE ranking version (FR-20/AD-23) ────
    def _piece_names(self, session: Session, tenant: str, matter: str) -> dict[str, str]:
        """``piece_id -> provenance path`` for a *matter*. ``matter`` is IN the query (AD-13), so
        this is not a tenant-wide fetch narrowed afterwards."""
        rows = session.execute(
            select(Piece.id, Piece.provenance_path)
            .where(Piece.tenant == tenant, Piece.matter == matter)).all()
        return {pid: name for pid, name in rows}

    def piece_is_in_matter(
        self, *, tenant: str, matter: str, piece_id: str, scopes: set[str]
    ) -> bool:
        """Is this *pièce* actually part of this *matter*, for a caller holding its wall?

        The label ledger is keyed by ``(tenant, matter, piece_id)`` with no foreign key to ``piece``
        (AD-7 forbids the cascade a FK would invite), so nothing at the schema layer stops a write
        naming a *pièce* that does not exist. That is harmless at the internal seam, whose callers
        pass a *pièce* they just read — but Story 4.10 put the act behind an HTTP route, and at a
        trust boundary an unchecked identifier becomes permanent, undeletable rows in an evidential
        ledger that a *bordereau* reader would see. So the boundary checks membership.

        Scope pre-filtered (AD-13); False when out of scope, when the matter is absent, or when the
        *pièce* is not in it — the caller turns all three into the same non-disclosing 404
        (FR-14)."""
        with self._sf() as session:
            if not self._matter_held(session, tenant, matter, scopes):
                return False
            return session.scalar(
                select(func.count()).select_from(Piece)
                .where(Piece.tenant == tenant, Piece.matter == matter,
                       Piece.id == piece_id)) > 0

    def _current_labels(
        self, session: Session, tenant: str, matter: str, taxonomy: list[str]
    ) -> dict[str, CurrentLabel]:
        """Every *pièce*'s CURRENT label for a *matter*, in **one** query — the same max-``seq``
        VIEW as :meth:`read_current_label`, computed for the whole table at once.

        The per-row read would be N+1: one query per *pièce* on a surface built for thousands of
        them (Story 2.13's 5 000-*pièce* run is the standing bound). ``matter`` is in the query
        (AD-13); the pairing and the ``unlabelled`` default stay in the domain (FR-40)."""
        entries = session.execute(
            select(TaxonomyLabelEntry.piece_id, TaxonomyLabelEntry.seq, TaxonomyLabelEntry.label,
                   TaxonomyLabelEntry.source)
            .where(TaxonomyLabelEntry.tenant == tenant,
                   TaxonomyLabelEntry.matter == matter)).all()
        by_piece: dict[str, list[LabelEntry]] = {}
        for pid, seq, label, src in entries:
            by_piece.setdefault(pid, []).append(LabelEntry(pid, seq, label, LabelSource(src)))
        out: dict[str, CurrentLabel] = {}
        for pid, rows in by_piece.items():
            view = current_label(rows)
            out[pid] = CurrentLabel(
                piece_id=pid, label=view.label,
                source=view.source.value if view.source is not None else None, seq=view.seq,
                in_current_taxonomy=is_member(view.label, taxonomy))
        return out

    def read_triage_table(
        self, *, tenant: str, matter: str, scopes: set[str], version_no: int | None = None
    ) -> TriageTable | None:
        """The whole triage surface for ONE *ranking version* (Story 4.10, FR-20).

        Every part is read **against that one version**: the version is resolved first and its
        ``version_no`` is then passed explicitly to the order, the line and the sets, so a
        concurrent re-rank cannot leave the parts describing different versions (AD-23 — no
        unqualified reference). The côté each row carries is **derived** here from *(the order, the
        line, the pins)* and is never stored (AD-39); the label is the max-``seq`` view over the
        append-only ledger and is never null (FR-40); a ``None`` confidence stays ``None`` (AD-19).

        Scope pre-filtered (AD-13). ``None`` when out of scope, absent, or not yet ranked — the
        three are indistinguishable (FR-14). Not audited (a read)."""
        version = self.read_ranking(tenant=tenant, matter=matter, scopes=scopes) \
            if version_no is None else None
        if version_no is None:
            if version is None:
                return None
            version_no = version.version_no
        else:
            versions = self.list_ranking_versions(tenant=tenant, matter=matter, scopes=scopes)
            if versions is None:
                return None
            version = next((v for v in versions if v.version_no == version_no), None)
            if version is None:
                return None
        order = self.read_ranked_order(
            tenant=tenant, matter=matter, scopes=scopes, version_no=version_no)
        if not order:
            return None
        line = self.read_current_line(
            tenant=tenant, matter=matter, scopes=scopes, version_no=version_no)
        pins = self.read_current_pins(tenant=tenant, matter=matter, scopes=scopes) or ()
        sets = self.read_triage_sets(
            tenant=tenant, matter=matter, scopes=scopes,
            line=Line(line.last_retained_piece_id) if line is not None else None,
            pins=pins, version_no=version_no)
        if sets is None:
            return None
        with self._sf() as session:
            names = self._piece_names(session, tenant, matter)
            taxonomy_list = self._current_taxonomy(session, tenant)
            labels = self._current_labels(session, tenant, matter, taxonomy_list)
            # the DOSSIER's pièces — not the ranking's. Pièces ingested after this version ran are
            # counted as unranked, never folded into a set they were never judged for (FR-58).
            corpus_count = session.scalar(
                select(func.count()).select_from(Piece)
                .where(Piece.tenant == tenant, Piece.matter == matter)) or 0
        taxonomy = tuple(taxonomy_list)
        retained, discarded = set(sets.retained), set(sets.discarded)
        pinned_ids = {p.piece_id for p in pins}
        rows: list[TriageRow] = []
        for entry in order:
            if entry.piece_id in retained:
                side = SIDE_RETAINED
            elif entry.piece_id in discarded:
                side = SIDE_DISCARDED
            elif entry.rank is None:
                side = SIDE_UNSCORED
            else:
                # ranked, but no line has been drawn — on neither side of a cut that does not
                # exist. Calling it "écartée" would be the lie FR-16 forbids.
                side = SIDE_UNSPLIT
            current = labels.get(entry.piece_id)
            signals = tuple(
                s for s in (entry.confidence_signals or "").split(",") if s)
            rows.append(TriageRow(
                piece_id=entry.piece_id, name=names.get(entry.piece_id, entry.piece_id),
                rank=entry.rank, side=side, confidence=entry.confidence,
                confidence_signals=signals, band=entry.band,
                label=current.label if current is not None else UNLABELLED,
                label_source=current.source if current is not None else None,
                label_seq=current.seq if current is not None else None,
                in_current_taxonomy=current.in_current_taxonomy if current is not None else True,
                pinned=entry.piece_id in pinned_ids))
        by_id = {r.piece_id: r for r in rows}
        last = by_id.get(line.last_retained_piece_id) if line is not None else None
        return TriageTable(
            matter=matter, version_no=version.version_no, version_id=version.version_id,
            basis=version.basis, case_theory_version_id=version.case_theory_version_id,
            created_at=version.created_at, rows=tuple(rows),
            retained_count=len(sets.retained), discarded_count=len(sets.discarded),
            unscored_count=len(sets.unscored), pins_in_force=sets.pins_in_force,
            line=LineView(
                placed=line is not None,
                last_retained_piece_id=line.last_retained_piece_id if line else None,
                last_retained_rank=last.rank if last else None,
                basis=line.basis if line else None, seq=line.seq if line else None,
                at=line.at if line else None),
            taxonomy=taxonomy,
            corpus_count=corpus_count)

    def read_label_change_log_paired(
        self, *, tenant: str, matter: str, piece_id: str, scopes: set[str]
    ) -> tuple[ChangeLogEntry, ...] | None:
        """One *pièce*'s change log as ``previous → new`` entries (FR-20). The pairing is the pure
        :func:`pair_change_log`; the first entry's previous value is the ``unlabelled`` sentinel —
        never null, because "no label" is a value here, not an absence (FR-40)."""
        entries = self.read_label_change_log(
            tenant=tenant, matter=matter, piece_id=piece_id, scopes=scopes)
        if entries is None:
            return None
        return pair_change_log(
            piece_id,
            tuple((e.seq, e.label, e.source, e.set_by, e.at) for e in entries),
            unlabelled=UNLABELLED)

    def read_matter_change_log(
        self, *, tenant: str, matter: str, scopes: set[str], limit: int = 200
    ) -> tuple[ChangeLogEntry, ...] | None:
        """The *matter*'s whole label change log, **newest first**, bounded by ``limit`` — the
        matter-level panel beside the table (FR-20).

        The pairing is per-*pièce* (a previous value only means something within one *pièce*'s own
        history), so the full ledger for the matter is read, paired per *pièce*, then ordered by
        recency and bounded. ``matter`` is in the query (AD-13). Scope pre-filtered; ``None`` when
        out of scope or absent."""
        with self._sf() as session:
            if not self._matter_held(session, tenant, matter, scopes):
                return None
            rows = session.scalars(
                select(TaxonomyLabelEntry)
                .where(TaxonomyLabelEntry.tenant == tenant, TaxonomyLabelEntry.matter == matter)
                .order_by(TaxonomyLabelEntry.piece_id, TaxonomyLabelEntry.seq.asc())).all()
        by_piece: dict[str, list[tuple[int, str, str, str, datetime]]] = {}
        for r in rows:
            by_piece.setdefault(r.piece_id, []).append((r.seq, r.label, r.source, r.set_by, r.at))
        paired: list[ChangeLogEntry] = []
        for pid, entries in by_piece.items():
            paired.extend(pair_change_log(pid, tuple(entries), unlabelled=UNLABELLED))
        paired.sort(key=lambda e: (e.at, e.seq), reverse=True)
        return tuple(paired[:max(1, limit)])

    # ── Story 4.13: freshness and staleness of derived artefacts (FR-58/AD-23/AD-40) ─────────────

    @staticmethod
    def _pin_ledger_seq(session: Session, tenant: str, matter: str) -> int:
        """The ``pin_ledger_seq`` observable: the SUM over *pièces* of each one's highest
        ``pin_entry.seq``. Every pin act — a pin AND an unpin — appends a row with a strictly
        greater per-*pièce* seq (AD-49), so the sum strictly increases on both. A count of pins in
        force would not move when one is added and another removed in the same read window.

        ONE derivation, shared by the freshness stamp and by the *sampling run*'s freeze (Story
        5.1): a run whose recorded ``pin_ledger_seq`` came from different arithmetic than the
        observable it is later compared against would read valid while its population had moved."""
        pin_max_per_piece = (
            select(func.max(PinEntry.seq).label("s"))
            .where(PinEntry.tenant == tenant, PinEntry.matter == matter)
            .group_by(PinEntry.piece_id).subquery())
        return int(session.scalar(select(func.coalesce(func.sum(pin_max_per_piece.c.s), 0))) or 0)

    @staticmethod
    def _derived_discarded(
        session: Session, tenant: str, matter: str, version_no: int | None
    ) -> tuple[str, tuple[tuple[str, str], ...]] | None:
        """The **derived** discarded set of a *ranking version*, as ``(version_id, ((piece_id,
        family_id), ...))`` in rank order — the ONE population Epic 5 audits (Story 5.1, planning
        decision A1).

        This is ``derive_triage_sets(order, line, pins).discarded`` (AD-39), never
        ``label_record WHERE label='discard'``: the label pile has no *ranking version* and no line,
        so FR-22's freeze cannot be stated over it, and a *pièce* the lawyer pinned back across the
        line would still be in it.

        ``None`` when the *matter* has no such ranking version **or no line is placed** — without a
        cut there is no discarded set, and calling the whole ranked order "écartée" is the lie FR-16
        forbids. Session-scoped and scope-free: every caller has already checked the wall.
        """
        pinned = [RankingVersionRow.version_no == version_no] if version_no is not None else []
        target = session.execute(
            select(RankingVersionRow.id)
            .where(RankingVersionRow.tenant == tenant, RankingVersionRow.matter == matter, *pinned)
            .order_by(RankingVersionRow.version_no.desc()).limit(1)).first()
        if target is None:
            return None
        version_id = target[0]
        rows = session.execute(
            select(RankedEntry.piece_id, RankedEntry.rank, RankedEntry.family_id)
            .where(RankedEntry.ranking_version_id == version_id)
            .order_by(RankedEntry.rank.is_(None), RankedEntry.rank, RankedEntry.piece_id)).all()
        ranked = [pid for pid, rank, _ in rows if rank is not None]
        unscored = [pid for pid, rank, _ in rows if rank is None]
        family_of = {pid: fam for pid, _, fam in rows}
        placement = session.scalars(
            select(LinePlacement)
            .where(LinePlacement.ranking_version_id == version_id)
            .order_by(LinePlacement.seq.desc()).limit(1)).first()
        if placement is None:
            return None
        pin_rows = session.execute(
            select(PinEntry.piece_id, PinEntry.seq, PinEntry.action)
            .where(PinEntry.tenant == tenant, PinEntry.matter == matter)).all()
        pins = current_pins(
            PinLogEntry(pid, seq, PinAction(action)) for pid, seq, action in pin_rows)
        # a version-independent pin may name a pièce this version never scored — dormant here, and
        # applying it would crash the whole derivation (the same rule as read_triage_sets).
        ranked_set = set(ranked)
        sets = derive_triage_sets(
            ranked=ranked, unscored=unscored, line=Line(placement.last_retained_piece_id),
            pins=tuple(p for p in pins if p.piece_id in ranked_set), version_id=version_id)
        return version_id, tuple((pid, family_of[pid]) for pid in sets.discarded)

    def _compute_stamp(
        self, session: Session, tenant: str, matter: str, version_no: int | None
    ) -> FreshnessStamp:
        """The observable state of ALL EIGHT enumerated staleness inputs, read inside the caller's
        session (FR-58/AD-23/AD-40).

        This is the **one** derivation, used both to stamp an artefact at production time and to
        compute the current state at read time — so a stamp can never be produced by different
        arithmetic than the one it is later compared against.

        ``version_no`` selects which *ranking version*'s line the ``line_seq`` observable reads.
        The line is version-bound, so an artefact produced over version 2 must be compared against
        version 2's line; comparing it against the latest version's line would report a phantom
        *line move* every time a re-rank happened. ``ranking_version_no`` is always the *matter*'s
        maximum — that is the observable for the re-rank trigger itself.
        """
        ranking_version_no = session.scalar(
            select(func.max(RankingVersionRow.version_no)).where(
                RankingVersionRow.tenant == tenant, RankingVersionRow.matter == matter)) or 0
        line_seq: int | None = None
        if version_no is not None and version_no > 0:
            line_seq = session.scalar(
                select(func.max(LinePlacement.seq))
                .join(RankingVersionRow, RankingVersionRow.id == LinePlacement.ranking_version_id)
                .where(RankingVersionRow.tenant == tenant, RankingVersionRow.matter == matter,
                       RankingVersionRow.version_no == version_no))
        pin_ledger_seq = self._pin_ledger_seq(session, tenant, matter)
        case_theory_version_no = session.scalar(
            select(func.max(CaseTheoryVersion.version_no)).where(
                CaseTheoryVersion.tenant == tenant, CaseTheoryVersion.matter == matter)) or 0
        # A scope the matter row does not have is not a scope: an absent matter is handled by the
        # callers' scope pre-filter, so this is always the matter's own wall (AD-13).
        scope_identity = session.scalar(
            select(MatterScope.scope).where(
                MatterScope.tenant == tenant, MatterScope.matter == matter)) or ""
        corpus_count = session.scalar(
            select(func.count()).select_from(Piece).where(
                Piece.tenant == tenant, Piece.matter == matter)) or 0
        pairs = session.execute(
            select(Piece.id, Piece.text_identity)
            .where(Piece.tenant == tenant, Piece.matter == matter)
            .order_by(Piece.id)).all()
        derived = self._derived_discarded(session, tenant, matter, version_no)
        discarded = derived[1] if derived is not None else ()
        return FreshnessStamp(
            ranking_version_no=ranking_version_no,
            line_seq=line_seq,
            pin_ledger_seq=pin_ledger_seq,
            case_theory_version_no=case_theory_version_no,
            config_digest=config_digest(self._retrieval_config(session, tenant)),
            scope_identity=scope_identity,
            corpus_count=corpus_count,
            extraction_digest=extraction_digest((pid, ti) for pid, ti in pairs),
            # the DERIVED discarded set of THIS version (decision A1), sorted by pièce id: the
            # digest must be a function of the membership, not of the rank order the derivation
            # emitted, or a re-rank that discarded exactly the same pièces in a different order
            # would report a population change that did not happen.
            discard_population=population_digest(sorted(pid for pid, _ in discarded)),
        )

    @staticmethod
    def _retrieval_config(session: Session, tenant: str) -> dict[str, object]:
        """The effective values of every configuration key declaring ``affects_retrieval`` — the
        ``config_digest`` observable's input (FR-58's *"a configuration change affecting retrieval,
        ranking or the estimator"*).

        Reusing the flag the schema already declares (and which already drives the audited change
        detail, ``_config_change_detail``) means the staleness trigger and the audited reason cannot
        drift apart, and a new ranking-affecting key is covered the moment its author sets the flag
        they already have to set."""
        keys = {k: spec for k, spec in CONFIG_SCHEMA.items() if spec.affects_retrieval}
        stored = {
            r.key: r for r in session.execute(
                select(TenantSetting).where(
                    TenantSetting.tenant == tenant,
                    TenantSetting.key.in_(sorted(keys)))).scalars().all()}
        return {k: _config_value(spec, stored.get(k)) for k, spec in keys.items()}

    def _write_stamp(
        self, session: Session, *, tenant: str, matter: str, kind: str, artefact_id: str,
        version_no: int | None, now: datetime,
    ) -> None:
        """Stamp a produced artefact, INSIDE its producing transaction (AD-22) — never a second
        act a caller could skip, so a produced artefact without a stamp cannot exist (AD-37).

        ``session.flush()`` first so the observables see the rows this very transaction just added:
        the ranking version being minted, the line placement being appended. Without it the stamp
        would record the state *before* the artefact, and the artefact would read stale against
        itself the instant it was produced."""
        session.flush()
        stamp = self._compute_stamp(session, tenant, matter, version_no)
        session.add(ArtefactStamp(
            id=hashlib.sha256(
                f"{tenant}\x00{matter}\x00{kind}\x00{artefact_id}".encode()).hexdigest(),
            tenant=tenant, matter=matter, kind=kind, artefact_id=artefact_id,
            stamp_json=stamp.to_json(), at=now))

    def current_stamp(
        self, *, tenant: str, matter: str, scopes: set[str], version_no: int | None = None
    ) -> FreshnessStamp | None:
        """The current observable state of the eight enumerated inputs (FR-58). Scope pre-filtered
        (AD-13); ``None`` when out of scope or absent (FR-14). Not audited (a read)."""
        with self._sf() as session:
            if not self._matter_held(session, tenant, matter, scopes):
                return None
            return self._compute_stamp(session, tenant, matter, version_no)

    def read_artefact_stamps(
        self, *, tenant: str, matter: str, scopes: set[str]
    ) -> tuple[tuple[str, str, int | None, bool, FreshnessStamp], ...] | None:
        """Every stamped artefact of the *matter* as ``(kind, artefact_id, own version_no,
        superseded, recorded stamp)``, oldest first. ``()`` = read, nothing stamped yet; ``None`` =
        out of scope or absent (FR-14).

        ``superseded`` is True when a NEWER artefact of the same kind exists: a higher ranking
        ``version_no``, a higher placement ``seq`` on the same version (or a placement on a later
        version), a later ``recall_review``. Such an artefact is still readable and its verdict is
        still true of it (AD-7 — nothing is deleted), but the recomputation it would offer has
        already been performed, so it must not generate a *worklist* line.

        **The version_no is the artefact's OWN**, resolved from the artefact itself — the ranking
        version for a ranking, the version its placement cuts for a line — and ``None`` for a bound,
        which is about the *matter*'s current state and has no version of its own. It is NOT
        ``stamp.ranking_version_no``: that observable is the *matter*'s MAXIMUM version, which is a
        different number whenever a line is placed over a version that is not the latest. Comparing
        such a line against the latest version's placement would read it fresh while its own cut had
        moved — the catastrophic direction (AD-23).

        A row whose ``stamp_json`` cannot be decoded **propagates the error** rather than being
        skipped: a stamp that cannot be read is not evidence of freshness, and silently dropping it
        would make an unverifiable artefact disappear from the worklist entirely."""
        with self._sf() as session:
            if not self._matter_held(session, tenant, matter, scopes):
                return None
            rows = session.scalars(
                select(ArtefactStamp)
                .where(ArtefactStamp.tenant == tenant, ArtefactStamp.matter == matter)
                .order_by(ArtefactStamp.at.asc(), ArtefactStamp.id.asc())).all()
            owners = self._artefact_versions(session, tenant, matter, rows)
            live = self._live_artefacts(session, tenant, matter)
            return tuple(
                (r.kind, r.artefact_id, owners.get((r.kind, r.artefact_id)),
                 r.artefact_id != live.get(r.kind),
                 FreshnessStamp.from_json(r.stamp_json))
                for r in rows)

    @staticmethod
    def _live_artefacts(session: Session, tenant: str, matter: str) -> dict[str, str]:
        """The identity of the artefact **in force** for each kind — the latest ranking version, the
        placement in force over it, and the most recent recorded bound. Everything else of that kind
        is superseded.

        The line in force is read over the LATEST ranking version, because that is the one the
        surface renders: a placement over an older version is superseded by the re-rank itself, not
        only by a later placement."""
        live: dict[str, str] = {}
        version = session.scalars(
            select(RankingVersionRow)
            .where(RankingVersionRow.tenant == tenant, RankingVersionRow.matter == matter)
            .order_by(RankingVersionRow.version_no.desc()).limit(1)).first()
        if version is not None:
            live[KIND_RANKING] = version.id
            placement = session.scalars(
                select(LinePlacement)
                .where(LinePlacement.ranking_version_id == version.id)
                .order_by(LinePlacement.seq.desc()).limit(1)).first()
            if placement is not None:
                live[KIND_LINE] = placement.id
        # The sampling run in force is the most recently STARTED one that was not ABANDONED.
        #
        # Started, not completed: an open run started after a completed one supersedes it, and it is
        # the open run the lawyer is working in. Not abandoned: abandoning IS discharging the offer
        # — she looked at the invalidated draw and decided not to have a bound — so an abandoned run
        # must stop generating a worklist line, or the banner demands a re-sample forever and the
        # true alarm is dismissed with it (the Story 4.13 rule, applied to a status instead of a
        # successor). With every run abandoned there is NO live sampling run, and every one of them
        # reads superseded, which is what "no offer" means here.
        run = session.scalars(
            select(SamplingRun)
            .where(SamplingRun.tenant == tenant, SamplingRun.matter == matter,
                   SamplingRun.status != STATUS_ABANDONED)
            .order_by(SamplingRun.started_at.desc(), SamplingRun.id.desc()).limit(1)).first()
        if run is not None:
            live[KIND_SAMPLING_RUN] = run.id
        # A legacy `recall_review` bound is live ONLY while the *matter* has never had a sampling
        # run. Once one exists the label-pile era is over for this dossier, and the legacy bound is
        # superseded by it.
        #
        # This is not tidiness. A legacy bound stamped between 4.13 and 5.1 carries a label-pile
        # digest, so it compares unequal against the derived-view digest FOREVER — and nothing can
        # ever write a `recall_review` row again (``no_new_legacy_bound``). Left live, it would put
        # a permanently stale line on the worklist offering a re-sample that no act in the product
        # can discharge: the banner growing a paragraph nobody can clear, which is exactly the
        # failure Story 4.13 introduced supersession to prevent.
        any_run = session.scalar(
            select(func.count()).select_from(SamplingRun).where(
                SamplingRun.tenant == tenant, SamplingRun.matter == matter)) or 0
        if any_run == 0:
            bound = session.scalars(
                select(RecallReview)
                .where(RecallReview.tenant == tenant, RecallReview.matter == matter)
                .order_by(
                    RecallReview.reviewed_at.desc(), RecallReview.id.desc()).limit(1)).first()
            if bound is not None:
                live[KIND_BOUND] = bound.id
        return live

    @staticmethod
    def _artefact_versions(
        session: Session, tenant: str, matter: str, rows: Sequence[ArtefactStamp]
    ) -> dict[tuple[str, str], int]:
        """Resolve each stamped artefact to the *ranking version* it belongs to, in THREE
        queries — never one per artefact. A legacy ``bound`` is absent from the result: a
        ``recall_review`` was computed over the label pile and has no version of its own.

        A **sampling run** does have one, and it matters: a run drawn over version 2 must be
        assessed against version 2's line and version 2's discarded set. Resolving it to the
        *matter*'s maximum instead would read a run as fresh while its own population had moved —
        the catastrophic direction, and the exact defect Story 4.13's review found on the line."""
        ranking_ids = [r.artefact_id for r in rows if r.kind == KIND_RANKING]
        line_ids = [r.artefact_id for r in rows if r.kind == KIND_LINE]
        run_ids = [r.artefact_id for r in rows if r.kind == KIND_SAMPLING_RUN]
        out: dict[tuple[str, str], int] = {}
        if run_ids:
            for rid, no in session.execute(
                    select(SamplingRun.id, SamplingRun.ranking_version_no).where(
                        SamplingRun.tenant == tenant, SamplingRun.matter == matter,
                        SamplingRun.id.in_(run_ids))).all():
                out[(KIND_SAMPLING_RUN, rid)] = no
        if ranking_ids:
            for vid, no in session.execute(
                    select(RankingVersionRow.id, RankingVersionRow.version_no).where(
                        RankingVersionRow.tenant == tenant, RankingVersionRow.matter == matter,
                        RankingVersionRow.id.in_(ranking_ids))).all():
                out[(KIND_RANKING, vid)] = no
        if line_ids:
            for pid, no in session.execute(
                    select(LinePlacement.id, RankingVersionRow.version_no)
                    .join(RankingVersionRow,
                          RankingVersionRow.id == LinePlacement.ranking_version_id)
                    .where(LinePlacement.tenant == tenant, LinePlacement.matter == matter,
                           LinePlacement.id.in_(line_ids))).all():
                out[(KIND_LINE, pid)] = no
        return out

    def read_current_bound(
        self, *, tenant: str, matter: str, scopes: set[str]
    ) -> RecordedBound | None:
        """The *matter*'s most recent recorded *confidence bound* (FR-58/FR-23). Scope pre-filtered;
        ``None`` when out of scope, absent, or when no bound has been recorded. Not audited.

        A **completed sampling run** is the bound from Story 5.1 onward, and it wins over any legacy
        ``recall_review`` unconditionally — not by date. The two are computed over *different
        populations* (the derived discarded view vs the Story-2.x label pile, decision A1), and
        picking the more recent of two incomparable things is exactly the nearly-right referent this
        build keeps being bitten by. Once a run exists, the label-pile bound is history.

        The bound is stated over the unit the run **drew**: near-duplicate families, not *pièces*
        (FR-38). ``population_pieces`` is carried on the run for the sentence Story 5.4 will write;
        it is deliberately not substituted here, because a bound quoted over a denominator nobody
        sampled is the failure this whole epic exists to prevent."""
        with self._sf() as session:
            if not self._matter_held(session, tenant, matter, scopes):
                return None
            # ORDERED BY RECENCY, and never by how favourable the number is (OQ-4 input 3). Pooling
            # two runs over one population is the textbook multiple-comparisons trap; picking the
            # nicest of them is the one someone will ask for in good faith. Neither happens here,
            # and `estimator-one-run-one-bound` fails the build if this ordering ever mentions
            # prevalence_upper or count_upper.
            run = session.scalars(
                select(SamplingRun)
                .where(SamplingRun.tenant == tenant, SamplingRun.matter == matter,
                       SamplingRun.status == STATUS_COMPLETED)
                .order_by(SamplingRun.completed_at.desc(), SamplingRun.id.desc()).limit(1)).first()
            if run is not None:
                count_upper = run.count_upper or 0
                census = is_census(
                    population=run.population_families, sample_size=run.sample_size)
                return RecordedBound(
                    relevant_pieces=self._census_relevant_pieces(session, run),
                    run_ordinal=self._run_ordinal(session, run),
                    # Story 5.4 — the wall the number was COMPUTED UNDER (FR-23), read off the run's
                    # own frozen column, never off the matter's current wall: an admin re-scope
                    # (Story 1.6) moves the second and not the first, and the difference is exactly
                    # what makes a number a fact about one set of walls rather than about a matter.
                    scope=run.scope,
                    # FR-23's accompanying record — the four things the sentence names OR carries
                    # beside it. The case theory is one join away, on the ranking version the run
                    # froze; a run over the intrinsic path has none, and it stays None (AD-19).
                    ranking_version_no=run.ranking_version_no,
                    last_retained_piece_id=run.last_retained_piece_id,
                    case_theory_version_id=session.scalar(
                        select(RankingVersionRow.case_theory_version_id)
                        .where(RankingVersionRow.id == run.ranking_version_id)),
                    artefact_id=run.id,
                    bound=PrevalenceBound(
                        population=run.population_families, sample_size=run.sample_size,
                        relevant_in_sample=run.relevant_found or 0, confidence=run.confidence,
                        count_upper=count_upper,
                        prevalence_upper=run.prevalence_upper or 0.0),
                    reviewed_at=run.completed_at or run.started_at,
                    unit_fr="familles de quasi-doublons écartées",
                    piece_count=run.population_pieces,
                    method=run.estimator_method,
                    # the WORST CASE in pièces — the D largest frozen families, never
                    # prevalence × pièces. None on a run frozen before the sizes existed, and None
                    # at a CENSUS, where nothing is bounded and a worst case would be a bound
                    # smuggled into the register that states an exact count (OQ-4 input 2).
                    count_upper_pieces=None if census else pieces_upper_bound(
                        count_upper_families=count_upper,
                        family_sizes=_split_family_sizes(run.population_family_sizes)))
            row = session.scalars(
                select(RecallReview)
                .where(RecallReview.tenant == tenant, RecallReview.matter == matter)
                .order_by(RecallReview.reviewed_at.desc(), RecallReview.id.desc()).limit(1)).first()
            if row is None:
                return None
            return RecordedBound(
                artefact_id=row.id,
                bound=PrevalenceBound(
                    population=row.population, sample_size=row.sample_size,
                    relevant_in_sample=row.relevant_found, confidence=row.confidence,
                    count_upper=row.count_upper, prevalence_upper=row.prevalence_upper),
                reviewed_at=row.reviewed_at)

    # ── Story 5.1: the sampling run — a frozen random draw from the DERIVED discarded set ────────

    def _run_population(
        self, session: Session, tenant: str, matter: str, version_no: int | None
    ) -> tuple[str, int, tuple[SamplingUnit, ...], int] | None:
        """``(version_id, version_no, families, piece_count)`` for the *matter*'s discarded set.

        The population and the stamp's ``discard_population`` observable come from the **same**
        derivation (:meth:`_derived_discarded`), so a run can never be drawn over one set and
        invalidated against another. ``None`` when there is no such ranking version, no line, or an
        empty discarded set."""
        derived = self._derived_discarded(session, tenant, matter, version_no)
        if derived is None:
            return None
        version_id, pairs = derived
        if not pairs:
            return None  # nothing discarded — no bound applies, never a flattering 0%
        resolved_no = session.scalar(
            select(RankingVersionRow.version_no).where(RankingVersionRow.id == version_id))
        if resolved_no is None:  # pragma: no cover - the id came from that table one query ago
            return None
        families = self._with_collapsed_twins(
            session, tenant, matter, group_discarded_families(pairs))
        return version_id, resolved_no, families, sum(len(f.member_piece_ids) for f in families)

    @staticmethod
    def _with_collapsed_twins(
        session: Session, tenant: str, matter: str, families: tuple[SamplingUnit, ...]
    ) -> tuple[SamplingUnit, ...]:
        """Give each drawn family the *pièces* the **deduplication** collapsed into it (FR-38,
        Story 5.2).

        This is what makes the family a family. The ranked order holds one entry per near-duplicate
        cluster — ``store.representatives`` groups by ``Piece.text_key`` and the cascade rejects the
        non-representative members at stage 1 (AD-36) — so ``derive_triage_sets`` can only ever hand
        back one *pièce* per family, and without this step ``member_piece_ids`` would be a singleton
        forever, ``population_pieces`` would equal ``population_families``, and the *pièce* worst
        case would be an identity dressed up as a statistic.

        Expanded here rather than inside :meth:`_derived_discarded` on purpose: that derivation also
        feeds the ``discard_population`` freshness observable, which watches what the RANKING
        produced. A new twin arriving does move the run's population — and it is already caught,
        because ``corpus_count`` and ``extraction_digest`` observe every *pièce* in the *matter*.

        The membership referent is ``Piece.text_key`` — the **same** key ``representatives`` grouped
        by. Using a different one would put a *pièce* in a family the ranking never collapsed, which
        is the nearly-right referent this epic exists to keep out of the denominator."""
        proxies = [f.proxy_piece_id for f in families]
        if not proxies:
            return families
        keys = dict(session.execute(
            select(Piece.id, Piece.text_key).where(
                Piece.tenant == tenant, Piece.matter == matter, Piece.id.in_(proxies))).all())
        by_key: dict[str, list[str]] = {}
        if keys:
            for pid, key in session.execute(
                    select(Piece.id, Piece.text_key).where(
                        Piece.tenant == tenant, Piece.matter == matter,
                        Piece.text_key.in_(sorted(set(keys.values()))))).all():
                by_key.setdefault(key, []).append(pid)
        expanded: list[SamplingUnit] = []
        for family in families:
            key = keys.get(family.proxy_piece_id)
            twins = sorted(by_key.get(key, ())) if key is not None else []
            # the proxy FIRST — it is the pièce the lawyer actually reads — then its twins, in
            # identity order. A pièce the ranking already gave this family is never added twice.
            members = tuple(dict.fromkeys(
                (*family.member_piece_ids, *(t for t in twins if t not in family.member_piece_ids))
            ))
            expanded.append(
                SamplingUnit(
                    family_id=family.family_id, proxy_piece_id=family.proxy_piece_id,
                    member_piece_ids=members))
        return tuple(expanded)

    def size_for_target_bound(
        self, *, tenant: str, matter: str, scopes: set[str], target_prevalence: float,
        confidence: float = 0.95, max_size: int | None = None, version_no: int | None = None,
    ) -> Sizing | None:
        """How many families must be drawn to reach ``target_prevalence`` (FR-22). A preview: writes
        nothing, audits nothing. ``None`` when out of scope, absent, not ranked, or no line."""
        with self._sf() as session:
            if not self._matter_held(session, tenant, matter, scopes):
                return None
            derived = self._derived_discarded(session, tenant, matter, version_no)
        if derived is None:
            # no ranking version, or no line placed. NOT the same fact as an empty discarded set:
            # saying "le jeu écarté est vide" here would tell the lawyer the tool looked and found
            # nothing, when the tool never looked.
            return no_population_sizing(
                target_prevalence=target_prevalence, confidence=confidence, reason_fr=NO_CUT_FR)
        families = group_discarded_families(derived[1])
        if not families:
            return no_population_sizing(
                target_prevalence=target_prevalence, confidence=confidence,
                reason_fr=NO_POPULATION_FR)
        return size_for_target(
            population=len(families), target_prevalence=target_prevalence, confidence=confidence,
            max_size=max_size)

    def start_sampling_run(
        self, *, tenant: str, matter: str, actor: str, scopes: set[str],
        sample_size: int | None = None, target_prevalence: float | None = None,
        confidence: float = 0.95, max_size: int | None = None, version_no: int | None = None,
        seed: int | None = None,
    ) -> SamplingRunView | None:
        """Draw, freeze, stamp and audit — ONE transaction (AD-22/AD-37, FR-22).

        The draw is over the near-duplicate **families** of the derived discarded set, uniform and
        without replacement. Everything FR-22 requires frozen is written in the same transaction as
        the draw, so a run whose population is not recorded cannot exist."""
        if (sample_size is None) == (target_prevalence is None):
            raise ValueError("give exactly one of sample_size or target_prevalence")
        box: list[str] = []

        def _work(session: Session, now: datetime) -> None:
            scope = session.scalar(
                select(MatterScope.scope).where(
                    MatterScope.tenant == tenant, MatterScope.matter == matter,
                    MatterScope.scope.in_(sorted(scopes))))
            if scope is None:
                raise ScopeDenied(matter)
            population = self._run_population(session, tenant, matter, version_no)
            if population is None:
                return  # no version / no line / empty discarded set — box stays empty
            version_id, resolved_no, families, piece_count = population
            # FR-58/AD-23: a run over a SUPERSEDED version would become the matter's current bound
            # (read_current_bound takes the latest completed run) while describing a population the
            # re-rank replaced — and it would read FRESH, because every observable it watches is the
            # matter's, not the old version's. The catastrophic direction. Refuse at the draw.
            latest = session.scalar(
                select(func.max(RankingVersionRow.version_no)).where(
                    RankingVersionRow.tenant == tenant, RankingVersionRow.matter == matter))
            if latest is not None and resolved_no != latest:
                raise ValueError(
                    f"le classement v{resolved_no} a été remplacé par la v{latest} : un tirage "
                    "porte sur le classement en vigueur, sinon sa borne décrirait un jeu écarté "
                    "que personne ne regarde plus")
            if sample_size is not None:
                size = max(1, min(sample_size, len(families)))
            else:
                sizing = size_for_target(
                    population=len(families), target_prevalence=float(target_prevalence or 0.0),
                    confidence=confidence, max_size=max_size)
                # an unreachable target still draws — the best achievable IS the offer FR-22 makes,
                # and refusing would leave the lawyer with no sample at all. `is None` and not
                # `or`: a max_size of 0 is a real (if useless) cap, and `or` would read it as
                # "unset" and silently draw a CENSUS — the opposite of what was asked.
                cap = len(families) if max_size is None else max_size
                size = sizing.size if sizing.size is not None else max(
                    1, min(cap, len(families)))
            # the seed is recorded for reproducing a draw in a test; FR-22 is explicit that it is
            # NOT the record — sampling_run_item is.
            draw_seed = seed if seed is not None else secrets.randbelow(2**31)
            drawn = draw_families(families, size, seed=draw_seed)
            pin_ledger_seq = self._pin_ledger_seq(session, tenant, matter)
            run_id = uuid4().hex
            session.add(SamplingRun(
                id=run_id, tenant=tenant, matter=matter,
                ranking_version_id=version_id, ranking_version_no=resolved_no,
                last_retained_piece_id=self._line_identity(session, version_id),
                pin_ledger_seq=pin_ledger_seq, scope=scope, seed=draw_seed,
                confidence=confidence, population_families=len(families),
                population_pieces=piece_count,
                # Story 5.2 / OQ-4 input 1: the size of EVERY family in the population, drawn or
                # not, as it is right now. The *pièce* worst case is the sum of the D largest, so
                # the D largest have to be knowable later without re-deriving a set that may have
                # moved — which for an invalidated run no longer exists at all.
                population_family_sizes=_join_family_sizes(families),
                sample_size=len(drawn),
                is_census=is_census(population=len(families), sample_size=len(drawn)),
                status=STATUS_OPEN, started_by=actor, started_at=now))
            for index, unit in enumerate(drawn):
                session.add(SamplingRunItem(
                    id=uuid4().hex, run_id=run_id, draw_index=index, family_id=unit.family_id,
                    proxy_piece_id=unit.proxy_piece_id,
                    member_piece_ids="\n".join(unit.member_piece_ids)))
            census = is_census(population=len(families), sample_size=len(drawn))
            detail = (
                f"version={resolved_no} families={len(drawn)}/{len(families)} "
                f"pieces={piece_count} census={census}")
            self._append_audit(
                session, tenant, matter, actor, AUDIT.ACT_SAMPLING_RUN_START, detail, now)
            self._write_stamp(
                session, tenant=tenant, matter=matter, kind=KIND_SAMPLING_RUN,
                artefact_id=run_id, version_no=resolved_no, now=now)
            box.append(run_id)

        self._audited_tx(_work)
        if not box:
            return None
        # box[-1] like every other boxed write in this store: _audited_tx RETRIES on an audit-seq
        # collision, so a retried transaction appends a second id and the FIRST one names a
        # transaction that was rolled back.
        return self.read_sampling_run(tenant=tenant, matter=matter, scopes=scopes, run_id=box[-1])

    @staticmethod
    def _line_identity(session: Session, version_id: str) -> str:
        """The identity of the last retained *pièce* over a version — FR-17's position of **the
        line**, never a bare integer. The caller has already established a line exists (the
        population derivation returns None without one)."""
        placement = session.scalars(
            select(LinePlacement)
            .where(LinePlacement.ranking_version_id == version_id)
            .order_by(LinePlacement.seq.desc()).limit(1)).first()
        if placement is None:  # pragma: no cover - guarded by _derived_discarded
            raise ValueError("sampling: no line is placed over this ranking version")
        return placement.last_retained_piece_id

    def _run_changed_inputs(
        self, session: Session, tenant: str, matter: str, run: SamplingRun
    ) -> tuple[bool, tuple[str, ...]]:
        """``(stamped, changed trigger keys)`` for one run — Story 4.13's comparison, read on a run
        that is still in flight. The rule lives in the Domain
        (:func:`~apx.core.domain.freshness.compare_stamps`); the store only supplies observables."""
        row = session.scalars(
            select(ArtefactStamp).where(
                ArtefactStamp.tenant == tenant, ArtefactStamp.matter == matter,
                ArtefactStamp.kind == KIND_SAMPLING_RUN,
                ArtefactStamp.artefact_id == run.id)).first()
        if row is None:
            return False, ()
        recorded = FreshnessStamp.from_json(row.stamp_json)
        current = self._compute_stamp(session, tenant, matter, run.ranking_version_no)
        return True, compare_stamps(recorded, current, kind=KIND_SAMPLING_RUN)

    def _guard_open_run(
        self, session: Session, tenant: str, matter: str, run: SamplingRun
    ) -> None:
        """Refuse to touch a run that is closed or whose frozen population has moved.

        Refusing is the strongest form of FR-22's *"tells the user immediately"*: a verdict recorded
        against a population that no longer exists is worse than no verdict, because it looks like
        evidence. The verdicts already recorded stay readable — nothing is destroyed (AD-7)."""
        if run.status != STATUS_OPEN:
            raise RunAlreadyClosed(run.status)
        stamped, changed = self._run_changed_inputs(session, tenant, matter, run)
        if not stamped or changed:
            raise InvalidatedRun(", ".join(changed) or "unstamped")

    def record_sampling_verdict(
        self, *, tenant: str, matter: str, actor: str, scopes: set[str], run_id: str,
        family_id: str, relevant: bool,
    ) -> SamplingRunView | None:
        """Append one verdict on one drawn family — append-only, attributed, audited (FR-22/FR-24).
        A correction is a NEW row with a greater ``seq``; the earlier one stays readable."""
        found: list[bool] = []

        def _work(session: Session, now: datetime) -> None:
            if not self._matter_held(session, tenant, matter, scopes):
                return
            run = session.scalars(
                select(SamplingRun).where(
                    SamplingRun.id == run_id, SamplingRun.tenant == tenant,
                    SamplingRun.matter == matter)).first()
            if run is None:
                return
            item = session.scalars(
                select(SamplingRunItem).where(
                    SamplingRunItem.run_id == run_id,
                    SamplingRunItem.family_id == family_id)).first()
            if item is None:
                return  # a family this run did not draw — not a verdict, and not disclosed
            self._guard_open_run(session, tenant, matter, run)
            last = session.scalar(
                select(func.max(SamplingVerdict.seq)).where(
                    SamplingVerdict.run_id == run_id,
                    SamplingVerdict.family_id == family_id)) or 0
            session.add(SamplingVerdict(
                id=uuid4().hex, run_id=run_id, family_id=family_id, seq=last + 1,
                relevant=relevant, actor=actor, at=now))
            self._append_audit(
                session, tenant, matter, actor, AUDIT.ACT_SAMPLING_VERDICT,
                f"run={run_id} family={family_id} relevant={relevant} seq={last + 1}", now)
            found.append(True)

        self._audited_tx(_work)
        if not found:
            return None
        return self.read_sampling_run(tenant=tenant, matter=matter, scopes=scopes, run_id=run_id)

    def complete_sampling_run(
        self, *, tenant: str, matter: str, actor: str, scopes: set[str], run_id: str,
    ) -> SamplingRunView | None:
        """Close the run: tally, bound, audit — one transaction (AD-22/FR-53).

        Refuses a run that is not fully judged. An unjudged family is **not** a verdict of "not
        relevant" (AD-19 — nothing imputed), and counting it as one would make every bound look
        better than the evidence supports."""
        found: list[bool] = []

        def _work(session: Session, now: datetime) -> None:
            if not self._matter_held(session, tenant, matter, scopes):
                return
            run = session.scalars(
                select(SamplingRun).where(
                    SamplingRun.id == run_id, SamplingRun.tenant == tenant,
                    SamplingRun.matter == matter)).first()
            if run is None:
                return
            self._guard_open_run(session, tenant, matter, run)
            verdicts = self._current_verdicts(session, run_id)
            drawn = session.scalar(
                select(func.count()).select_from(SamplingRunItem).where(
                    SamplingRunItem.run_id == run_id)) or 0
            if len(verdicts) < drawn:
                raise ValueError(
                    f"the run is not fully judged: {len(verdicts)}/{drawn} families")
            relevant_found = sum(1 for v in verdicts.values() if v.relevant)
            # OQ-4 input 4: the estimator's population and sample are the FROZEN ones, read off the
            # run's own row. Re-deriving the discarded set here would compute a bound over whatever
            # the matter looks like NOW and quote it with the authority of a draw made over what it
            # looked like THEN — and for an invalidated run, over a population that no longer
            # exists. The check `estimator-bound-from-the-freeze` holds this shape.
            bound = bound_for_run(
                population=run.population_families, sample_size=run.sample_size,
                relevant_found=relevant_found, confidence=run.confidence)
            run.status = STATUS_COMPLETED
            run.closed_by = actor
            run.completed_at = now
            run.relevant_found = relevant_found
            run.count_upper = bound.count_upper
            run.prevalence_upper = bound.prevalence_upper
            # FR-23: the method travels with the number, so a later change of method produces a NEW
            # bound instead of silently restating this one.
            run.estimator_method = ESTIMATOR_METHOD
            self._append_audit(
                session, tenant, matter, actor, AUDIT.ACT_SAMPLING_RUN_COMPLETE,
                f"run={run_id} population={run.population_families} sample={run.sample_size} "
                f"relevant={relevant_found} bound={bound.prevalence_upper:.4f}@{run.confidence}",
                now)
            found.append(True)

        self._audited_tx(_work)
        if not found:
            return None
        return self.read_sampling_run(tenant=tenant, matter=matter, scopes=scopes, run_id=run_id)

    def abandon_sampling_run(
        self, *, tenant: str, matter: str, actor: str, scopes: set[str], run_id: str,
    ) -> SamplingRunView | None:
        """Give up an open run, audited. The draw and every verdict stay readable forever (AD-7) —
        an invalidated run is abandoned and redrawn, never silently reused."""
        found: list[bool] = []

        def _work(session: Session, now: datetime) -> None:
            if not self._matter_held(session, tenant, matter, scopes):
                return
            run = session.scalars(
                select(SamplingRun).where(
                    SamplingRun.id == run_id, SamplingRun.tenant == tenant,
                    SamplingRun.matter == matter)).first()
            if run is None:
                return
            if run.status != STATUS_OPEN:
                raise RunAlreadyClosed(run.status)
            run.status = STATUS_ABANDONED
            run.closed_by = actor
            verdicts = self._current_verdicts(session, run_id)
            self._append_audit(
                session, tenant, matter, actor, AUDIT.ACT_SAMPLING_RUN_ABANDON,
                f"run={run_id} verdicts_kept={len(verdicts)}", now)
            found.append(True)

        self._audited_tx(_work)
        if not found:
            return None
        return self.read_sampling_run(tenant=tenant, matter=matter, scopes=scopes, run_id=run_id)

    @staticmethod
    def _current_verdicts(session: Session, run_id: str) -> dict[str, VerdictEntry]:
        """The CURRENT verdict per family — the max-``seq`` row of the append-only ledger. Earlier
        rows stay readable as the record of a mind changed (FR-24)."""
        rows = session.scalars(
            select(SamplingVerdict)
            .where(SamplingVerdict.run_id == run_id)
            .order_by(SamplingVerdict.family_id, SamplingVerdict.seq.asc())).all()
        current: dict[str, VerdictEntry] = {}
        for r in rows:  # ascending seq, so the last write per family wins
            current[r.family_id] = VerdictEntry(
                family_id=r.family_id, relevant=r.relevant, actor=r.actor, at=r.at, seq=r.seq)
        return current

    def _census_relevant_pieces(self, session: Session, run: SamplingRun) -> int | None:
        """How many *pièces* the relevant families hold — **exact**, and only at a census.

        At a census the drawn families ARE the population, so this is a count of what was read, not
        an estimate of what was not. At a sample it would be a fact about the sample masquerading
        as a fact about the population, so it is ``None`` there and the surface falls back to the
        bound register (Story 5.2, OQ-4 input 2)."""
        if not is_census(population=run.population_families, sample_size=run.sample_size):
            return None
        verdicts = self._current_verdicts(session, run.id)
        items = session.scalars(
            select(SamplingRunItem).where(SamplingRunItem.run_id == run.id)).all()
        return sum(
            len(i.member_piece_ids.split("\n"))
            for i in items
            if (v := verdicts.get(i.family_id)) is not None and v.relevant)

    @staticmethod
    def _run_ordinal(session: Session, run: SamplingRun) -> int:
        """How many runs over this run's **frozen population** came first, plus one (OQ-4 input 3).

        Two runs share a population exactly when their populations have the same **membership** —
        which is what ``FreshnessStamp.discard_population`` is: the digest of the derived discarded
        set the run was drawn over, written at the draw by the same derivation that later judges the
        run invalidated. The freeze coordinates are NOT that identity, and the difference is not
        academic: **a pin followed by an un-pin advances the pin ledger twice and leaves the
        discarded set byte-identical**, so keying on ``pin_ledger_seq`` would reset a third draw to
        *"first draw"* — hiding multiplicity, which is the flattering direction.

        FR-22 requires a second run to be *"presented alongside the first rather than replacing
        it"* and any bound to state how many runs it rests on; the sentence travels alone, so the
        ordinal travels inside it.

        **Abandoned runs count.** Abandon-and-redraw is the cheapest route to a favourable number —
        an hour of inconvenient verdicts thrown away, a fresh draw, a nicer sentence — so a count
        that ignored them would be blind to precisely the behaviour it exists to make visible.

        Derived on read, never stored: a stored counter must be incremented by every writer, and a
        writer that forgets leaves a third draw reading as the first (AD-23, AD-39). A run with no
        readable stamp is ordinal 1 and matches nothing: an unverifiable population is not evidence
        of being the same population."""
        stamps = {
            r.artefact_id: FreshnessStamp.from_json(r.stamp_json).discard_population
            for r in session.scalars(
                select(ArtefactStamp).where(
                    ArtefactStamp.tenant == run.tenant, ArtefactStamp.matter == run.matter,
                    ArtefactStamp.kind == KIND_SAMPLING_RUN)).all()}
        mine = stamps.get(run.id)
        if mine is None:
            return 1
        earlier = session.execute(
            select(SamplingRun.id).where(
                SamplingRun.tenant == run.tenant, SamplingRun.matter == run.matter,
                or_(SamplingRun.started_at < run.started_at,
                    and_(SamplingRun.started_at == run.started_at,
                         SamplingRun.id < run.id)))).all()
        return 1 + sum(1 for (rid,) in earlier if stamps.get(rid) == mine)

    def _run_view(self, session: Session, run: SamplingRun) -> SamplingRunView:
        items = session.scalars(
            select(SamplingRunItem)
            .where(SamplingRunItem.run_id == run.id)
            .order_by(SamplingRunItem.draw_index.asc())).all()
        verdicts = self._current_verdicts(session, run.id)
        return SamplingRunView(
            run_id=run.id, matter=run.matter, version_id=run.ranking_version_id,
            version_no=run.ranking_version_no,
            last_retained_piece_id=run.last_retained_piece_id,
            pin_ledger_seq=run.pin_ledger_seq, scope=run.scope, confidence=run.confidence,
            population_families=run.population_families, population_pieces=run.population_pieces,
            sample_size=run.sample_size, seed=run.seed,
            status=run.status, started_by=run.started_by, started_at=run.started_at,
            completed_at=run.completed_at, relevant_found=run.relevant_found,
            count_upper=run.count_upper, prevalence_upper=run.prevalence_upper,
            drawn=tuple(
                DrawnFamily(
                    unit=SamplingUnit(
                        family_id=i.family_id, proxy_piece_id=i.proxy_piece_id,
                        member_piece_ids=tuple(i.member_piece_ids.split("\n"))),
                    draw_index=i.draw_index, verdict=verdicts.get(i.family_id))
                for i in items),
            population_family_sizes=_split_family_sizes(run.population_family_sizes),
            run_ordinal=self._run_ordinal(session, run),
            estimator_method=run.estimator_method)

    def read_sampling_run(
        self, *, tenant: str, matter: str, scopes: set[str], run_id: str | None = None,
    ) -> SamplingRunView | None:
        """One run with its frozen draw and current verdicts — the most recent when ``run_id`` is
        ``None``. Scope pre-filtered (AD-13); ``None`` when out of scope, absent or no run. Not
        audited (a read)."""
        with self._sf() as session:
            if not self._matter_held(session, tenant, matter, scopes):
                return None
            pinned = [SamplingRun.id == run_id] if run_id is not None else []
            run = session.scalars(
                select(SamplingRun)
                .where(SamplingRun.tenant == tenant, SamplingRun.matter == matter, *pinned)
                .order_by(SamplingRun.started_at.desc(), SamplingRun.id.desc()).limit(1)).first()
            if run is None:
                return None
            return self._run_view(session, run)

    def list_sampling_runs(
        self, *, tenant: str, matter: str, scopes: set[str]
    ) -> tuple[SamplingRunView, ...] | None:
        """Every run of the *matter*, newest first. ``()`` = readable with no run yet; ``None`` =
        out of scope or absent — the surface must not render the two the same way."""
        with self._sf() as session:
            if not self._matter_held(session, tenant, matter, scopes):
                return None
            runs = session.scalars(
                select(SamplingRun)
                .where(SamplingRun.tenant == tenant, SamplingRun.matter == matter)
                .order_by(SamplingRun.started_at.desc(), SamplingRun.id.desc())).all()
            return tuple(self._run_view(session, r) for r in runs)

    def read_run_freshness(
        self, *, tenant: str, matter: str, scopes: set[str], run_id: str
    ) -> tuple[bool, tuple[str, ...]] | None:
        """``(stamped, changed trigger keys)`` for one run — the observables FR-22's
        invalidated-in-flight verdict is derived from. The store reports; the Domain decides
        (:func:`~apx.core.domain.sampling.derive_run_state`). ``None`` when out of scope or
        absent."""
        with self._sf() as session:
            if not self._matter_held(session, tenant, matter, scopes):
                return None
            run = session.scalars(
                select(SamplingRun).where(
                    SamplingRun.id == run_id, SamplingRun.tenant == tenant,
                    SamplingRun.matter == matter)).first()
            if run is None:
                return None
            return self._run_changed_inputs(session, tenant, matter, run)
