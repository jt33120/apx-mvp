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
import random
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from apx.adapters.store_postgres.models import (
    AuditRecord,
    Failure,
    LabelRecord,
    MatterScope,
    Piece,
    RecallReview,
    User,
    UserScope,
)
from apx.core.app.ingest import IngestionResult
from apx.core.domain.auth import hash_password, verify_password
from apx.core.domain.confidence import prevalence_upper_bound
from apx.core.domain.dedup import cluster
from apx.core.domain.inventory import Inventory
from apx.core.domain.search import snippet
from apx.core.domain.triage import TriageOutcome

# A valid hash to verify against when the user is unknown, so authentication takes the
# same time whether or not the email exists (no user-enumeration by timing).
_DUMMY_HASH = hash_password("timing-equalizer")


class ScopeDenied(Exception):
    """A read touched a matter outside the caller's RBAC scope. Fail closed."""


@dataclass(frozen=True)
class AuthUser:
    id: str
    tenant: str
    email: str
    display_name: str  # the actor recorded on the audit trail


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


def _audit_ts(dt: datetime) -> str:
    """The canonical timestamp string for the chain: UTC, tz-naive, microseconds.
    The chain must recompute to the SAME bytes whichever backend round-trips the
    column — SQLite drops the tzinfo, Postgres timestamptz keeps it — so we
    normalise to a single representation on BOTH the write and the verify side.
    Without this, an untampered chain would fail to verify across backends."""
    if dt.tzinfo is not None:
        dt = dt.astimezone(UTC).replace(tzinfo=None)
    return dt.isoformat(timespec="microseconds")


def _audit_content(seq: int, tenant: str, matter: str | None, actor: str, action: str,
                   detail: str, ts: str) -> str:
    return f"{seq}|{tenant}|{matter or ''}|{actor}|{action}|{detail}|{ts}"


def _audit_chain(prev_chain: str, content: str) -> str:
    return hashlib.sha256(f"{prev_chain}\x00{content}".encode()).hexdigest()


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
                session.merge(MatterScope(matter=matter, tenant=tenant, scope=scope))
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
                        full_text=p.full_text, text_version=p.text_version,
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
                .join(Piece, Piece.id == LabelRecord.piece_id)
                .where(LabelRecord.matter == matter, LabelRecord.tenant == tenant)
                .order_by(Piece.provenance_path)
            ).all()
        pieces = tuple(LabelledPiece(prov, label, rat) for label, rat, prov in rows)
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
                .join(Piece, Piece.id == LabelRecord.piece_id)
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
                .order_by(Piece.matter, Piece.provenance_path)
                .limit(limit)
            ).all()
        hits = tuple(SearchHit(matter, prov, snippet(full, q)) for matter, prov, full in rows)
        return SearchResults(q, total, hits)

    def create_user(self, tenant: str, email: str, password: str, display_name: str,
                    scopes: set[str], *, is_admin: bool = False) -> str:
        """Create an owned user with a scrypt-hashed password and their scope grants.
        The plaintext password is never stored. Returns the new user id."""
        uid = uuid4().hex
        with self._sf() as session, session.begin():
            session.add(User(
                id=uid, tenant=tenant, email=email.strip().lower(),
                password_hash=hash_password(password), display_name=display_name,
                is_admin=is_admin,
            ))
            for scope in scopes:
                session.add(UserScope(user_id=uid, scope=scope))
        return uid

    def authenticate(self, tenant: str, email: str, password: str) -> AuthUser | None:
        """Return the user on a correct password, else None. The password is always
        verified — against a dummy hash when the email is unknown — so timing does not
        reveal whether an account exists."""
        with self._sf() as session:
            u = session.scalar(
                select(User).where(User.tenant == tenant, User.email == email.strip().lower())
            )
            ok = verify_password(password, u.password_hash if u is not None else _DUMMY_HASH)
            if u is None or not ok:
                return None
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

    def grant_scope(self, tenant: str, user_id: str, scope: str) -> None:
        """Grant a wall to a user in this tenant (idempotent). Takes effect on their
        next request (scope is resolved live)."""
        with self._sf() as session, session.begin():
            user = session.scalar(select(User).where(User.id == user_id, User.tenant == tenant))
            if user is None:
                raise ValueError("unknown user")
            session.merge(UserScope(user_id=user_id, scope=scope))

    def revoke_scope(self, tenant: str, user_id: str, scope: str) -> None:
        """Revoke a wall from a user in this tenant (takes effect on their next request)."""
        with self._sf() as session, session.begin():
            user = session.scalar(select(User).where(User.id == user_id, User.tenant == tenant))
            if user is None:
                raise ValueError("unknown user")
            row = session.get(UserScope, {"user_id": user_id, "scope": scope})
            if row is not None:
                session.delete(row)

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
            all_rows = session.execute(
                select(AuditRecord)
                .where(AuditRecord.tenant == tenant)
                .order_by(AuditRecord.seq)
            ).scalars().all()

        verified = True
        prev_chain = ""
        for i, r in enumerate(all_rows):
            content = _audit_content(
                r.seq, tenant, r.matter, r.actor, r.action, r.detail, _audit_ts(r.timestamp)
            )
            if r.seq != i + 1 or _audit_chain(prev_chain, content) != r.chain:
                verified = False
            prev_chain = r.chain

        entries = [
            AuditEntry(r.seq, r.actor, r.action, r.detail, r.chain, r.timestamp.isoformat())
            for r in all_rows
            if r.matter == matter
        ]
        return AuditTrail(entries, verified)
