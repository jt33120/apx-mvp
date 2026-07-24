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
import random
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import Text, cast, delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from apx.adapters.store_postgres.crypto_types import cipher
from apx.adapters.store_postgres.models import (
    AuditRecord,
    Failure,
    LabelRecord,
    MatterScope,
    Piece,
    RecallReview,
    SessionRecord,
    TenantSetting,
    User,
    UserScope,
)
from apx.core.app.ingest import IngestionResult
from apx.core.domain.auth import hash_password, verify_and_upgrade, verify_password
from apx.core.domain.confidence import prevalence_upper_bound
from apx.core.domain.config import (
    CONFIG_SCHEMA,
    ConfigKey,
    coerce,
    dumps_value,
    loads_value,
    require_key,
)
from apx.core.domain.crypto import DecryptionError
from apx.core.domain.dedup import cluster
from apx.core.domain.inventory import Inventory
from apx.core.domain.search import snippet
from apx.core.domain.triage import TriageOutcome

# A valid hash to verify against when the user is unknown, so authentication takes the
# same time whether or not the email exists (no user-enumeration by timing).
_DUMMY_HASH = hash_password("timing-equalizer")


class ScopeDenied(Exception):
    """A read touched a matter outside the caller's RBAC scope. Fail closed."""


class ScopeConflict(Exception):
    """An ingest would change an existing matter's scope. A matter's wall may only move via
    the audited admin re-scope path (AD-13/FR-49), never silently through a re-ingest."""


class TenantAlreadyProvisioned(Exception):
    """Provisioning was asked to establish a tenant that already has an administrator. Fail
    closed — never silently take over a live firm (AD-25)."""


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
    pieces_written: int
    failures_written: int


@dataclass(frozen=True)
class MatterSummary:
    matter: str
    scope: str
    inventory: Inventory


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


def _failure_id(matter: str, submitted_path: str) -> str:
    return hashlib.sha256(f"{matter}\x00{submitted_path}".encode()).hexdigest()


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
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._sf = session_factory

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

    def save(self, result: IngestionResult, scope: str, actor: str = "unknown") -> SaveOutcome:
        now = result.pieces[0].ingestion_timestamp if result.pieces else datetime.now(UTC)
        matter = result.pieces[0].matter if result.pieces else (
            result.failures[0].matter if result.failures else None
        )
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
                    session.add(MatterScope(matter=matter, tenant=tenant, scope=scope))
                elif existing.scope != scope:
                    raise ScopeConflict(
                        f"matter {matter!r} already exists under a different scope; "
                        "re-scope via the admin path")
                inv = result.inventory
                detail = (
                    f"submitted={inv.submitted} corpus={inv.in_corpus} "
                    f"failures={inv.failures} exclusions={inv.exclusions}"
                )
                self._append_audit(session, tenant, matter, actor, "ingest", detail, now)
            for p in result.pieces:
                session.merge(
                    Piece(
                        id=p.id, tenant=p.tenant, matter=p.matter, content_hash=p.content_hash,
                        text_key=p.text_key,
                        provenance_path=p.provenance_path, custodian=p.custodian,
                        extraction_method=p.extraction_method,
                        extractor_version=p.extractor_version,
                        schema_version=p.schema_version, ingestion_timestamp=p.ingestion_timestamp,
                        piece_date=None, piece_date_status="undetermined",
                        full_text=p.full_text,
                        text_identity=hashlib.sha256(p.full_text.encode()).hexdigest(),
                        text_version=p.text_version,
                    )
                )
            for f in result.failures:
                session.merge(
                    Failure(
                        id=_failure_id(f.matter, f.submitted_path),
                        tenant=f.tenant, matter=f.matter,
                        filename=f.filename, submitted_path=f.submitted_path,
                        error_class=str(f.error_class), resolution_state="open",
                        detail=f.detail, timestamp=now,
                    )
                )
        return SaveOutcome(len(result.pieces), len(result.failures))

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
            out = []
            for matter, scope in rows:
                in_corpus, failures = self._counts(session, matter, tenant)
                out.append(
                    MatterSummary(
                        matter, scope,
                        Inventory(in_corpus + failures, in_corpus, failures, 0),
                    )
                )
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
            in_corpus, failures = self._counts(session, matter, tenant)
        return Inventory(in_corpus + failures, in_corpus, failures, 0)

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
        """Deterministic exhaustive search over the caller's scope (FR-13): every piece
        whose stored text contains ``query`` (case-insensitive substring), constrained
        to matters the held scopes cover — the Chinese wall pre-filters search too, so
        it cannot leak across the wall. ``total`` is the true match count even when the
        returned ``hits`` are capped at ``limit`` (no silent truncation)."""
        q = query.strip()
        if not scopes or not q:
            return SearchResults(q, 0, ())  # fail closed: no scope or empty query -> nothing
        pattern = f"%{_like_escape(q.lower())}%"
        join_on = (MatterScope.matter == Piece.matter) & (MatterScope.tenant == Piece.tenant)
        conds = [
            Piece.tenant == tenant,
            MatterScope.scope.in_(scopes),
            func.lower(Piece.full_text).like(pattern, escape="\\"),
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
        new_value = spec.coerce(value)    # ConfigError on a wrong-typed value
        for attempt in range(4):
            try:
                with self._sf() as session, session.begin():
                    row = session.get(TenantSetting, {"tenant": tenant, "key": key})
                    before = _config_value(spec, row)
                    if before == new_value:
                        return ConfigChange(key, before, new_value, changed=False)
                    if row is None:
                        session.add(TenantSetting(
                            tenant=tenant, key=key, value=dumps_value(new_value)))
                    else:
                        row.value = dumps_value(new_value)
                    self._append_audit(
                        session, tenant, None, actor, "config_changed",
                        _config_change_detail(key, before, new_value, spec.affects_retrieval),
                        datetime.now(UTC))
                    session.flush()  # surface a (tenant, seq) collision inside the try
                return ConfigChange(key, before, new_value, changed=True)
            except IntegrityError:
                if attempt == 3:
                    raise
        raise RuntimeError("unreachable")  # the loop returns or raises

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
        ``audited`` only when its current value equals the last audited change for its key."""
        with self._sf() as session:
            rows = session.execute(
                select(TenantSetting).where(TenantSetting.tenant == tenant)
            ).scalars().all()
            details = session.execute(
                select(AuditRecord.detail)
                .where(AuditRecord.tenant == tenant, AuditRecord.action == "config_changed")
                .order_by(AuditRecord.seq)
            ).scalars().all()
        audited_after: dict[str, object] = {}
        for detail in details:
            parsed = _parse_config_detail(detail)
            if parsed is not None:
                audited_after[parsed[0]] = parsed[1]  # last write wins (ordered by seq)
        out: list[ConfigProvenance] = []
        for row in rows:
            try:
                value = loads_value(row.value)
            except ValueError:
                value = None
            audited = row.key in audited_after and audited_after[row.key] == value
            out.append(ConfigProvenance(row.key, value, audited))
        return out

    def provision_tenant(
        self, tenant: str, admin_email: str, admin_password: str, admin_name: str,
        scopes: set[str], taxonomy: list[str], *, actor: str = "system:provisioning",
    ) -> str:
        """Provision a tenant through the surface (AD-25): establish its FIRST administrative
        grant (an is_admin user with its scopes) and seed its taxonomy as an audited configuration
        value, in ONE transaction, writing a ``tenant_provisioned`` audit entry. Fails closed with
        ``TenantAlreadyProvisioned`` if the tenant already has an administrator — never a silent
        takeover of a live firm. Returns the new administrator's id."""
        email = admin_email.strip().lower()
        coerced_tax = coerce("taxonomy", list(taxonomy))  # validate before opening the tx
        wall_set = set(scopes)
        uid = uuid4().hex
        now = datetime.now(UTC)
        with self._sf() as session, session.begin():
            existing_admin = session.scalar(
                select(func.count()).select_from(User).where(
                    User.tenant == tenant, User.is_admin.is_(True)))
            if (existing_admin or 0) > 0:
                raise TenantAlreadyProvisioned(
                    f"tenant {tenant!r} already has an administrator")
            session.add(User(
                id=uid, tenant=tenant, email=email, password_hash=hash_password(admin_password),
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
            if coerced_tax:  # seed the taxonomy as an audited value (empty is the default already)
                session.add(TenantSetting(
                    tenant=tenant, key="taxonomy", value=dumps_value(coerced_tax)))
                self._append_audit(
                    session, tenant, None, actor, "config_changed",
                    _config_change_detail("taxonomy", [], coerced_tax, retrieval=False), now)
                session.flush()
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
        gate reads this to decide whether a second factor is demanded."""
        required = bool(self.get_config(tenant, "mfa_required"))
        with self._sf() as session:
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
