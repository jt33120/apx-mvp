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
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from apx.adapters.store_postgres.models import AuditRecord, Failure, MatterScope, Piece
from apx.core.app.ingest import IngestionResult
from apx.core.domain.dedup import cluster
from apx.core.domain.inventory import Inventory


class ScopeDenied(Exception):
    """A read touched a matter outside the caller's RBAC scope. Fail closed."""


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
