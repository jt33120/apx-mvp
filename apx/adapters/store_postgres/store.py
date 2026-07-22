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

from apx.adapters.store_postgres.models import Failure, MatterScope, Piece
from apx.core.app.ingest import IngestionResult
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


def _failure_id(matter: str, submitted_path: str) -> str:
    return hashlib.sha256(f"{matter}\x00{submitted_path}".encode()).hexdigest()


class SqlStore:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._sf = session_factory

    def save(self, result: IngestionResult, scope: str) -> SaveOutcome:
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
            for p in result.pieces:
                session.merge(
                    Piece(
                        id=p.id, tenant=p.tenant, matter=p.matter, content_hash=p.content_hash,
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
