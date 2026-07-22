"""The store writer — persist an ingestion result and read back the durable inventory.

Idempotent by construction: a piece is keyed by its deterministic id
(content, matter), a failure by (matter, submitted_path), so re-ingesting the same
folder does not duplicate (the v1 defect was ids from a restarting counter). The
writer maps app/domain values onto the SQLAlchemy models; the core never imports
this adapter (adapter → core is the allowed direction). The frozen-schema rigor —
the ONE-writer static check, the RBAC scope write-time reconciliation — lands in
story 1.3; this slice persists what "drop a folder, see the inventory" needs.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from apx.adapters.store_postgres.models import Failure, Piece
from apx.core.app.ingest import IngestionResult
from apx.core.domain.inventory import Inventory


@dataclass(frozen=True)
class SaveOutcome:
    pieces_written: int
    failures_written: int


def _failure_id(matter: str, submitted_path: str) -> str:
    return hashlib.sha256(f"{matter}\x00{submitted_path}".encode()).hexdigest()


class SqlStore:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._sf = session_factory

    def save(self, result: IngestionResult) -> SaveOutcome:
        now = (
            result.pieces[0].ingestion_timestamp
            if result.pieces
            else datetime.now(UTC)
        )
        with self._sf() as session, session.begin():
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

    def inventory(self, matter: str, tenant: str) -> Inventory:
        """The DURABLE inventory: corpus + open failures. Exclusions are a per-run
        detail (not persisted), so submitted here = corpus + failures."""
        with self._sf() as session:
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
        return Inventory(
            submitted=in_corpus + failures, in_corpus=in_corpus, failures=failures, exclusions=0
        )
