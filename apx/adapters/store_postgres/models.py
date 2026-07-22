"""SQLAlchemy models — a minimal, honest down-payment on the payload schema (story 1.3).

`piece` holds a document's provenance and its full extracted text (the target of
FR-13's exhaustive search, stored once). `failure` enumerates what did not enter
the corpus. No cascade FK (AD-7). Idempotency at the DB level via a unique
(matter, content_hash). The frozen-schema rigor — the one-writer check, the
RBAC-scope-as-a-write-time-check reconciliation — lands in story 1.3; this slice
carries only what "drop a folder, see the inventory" needs.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import CheckConstraint, DateTime, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Piece(Base):
    __tablename__ = "piece"
    __table_args__ = (
        UniqueConstraint("matter", "content_hash", name="uq_piece_matter_content"),
        CheckConstraint(
            "(piece_date IS NOT NULL) = (piece_date_status = 'determined')",
            name="ck_piece_date_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # piece_id(content_hash, matter)
    tenant: Mapped[str] = mapped_column(String, nullable=False)
    matter: Mapped[str] = mapped_column(String, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    provenance_path: Mapped[str] = mapped_column(Text, nullable=False)  # attribute, not identity
    custodian: Mapped[str] = mapped_column(String, nullable=False)
    extraction_method: Mapped[str] = mapped_column(String, nullable=False)
    extractor_version: Mapped[str] = mapped_column(String, nullable=False)
    schema_version: Mapped[str] = mapped_column(String, nullable=False)
    ingestion_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    piece_date: Mapped[date | None] = mapped_column(nullable=True)
    # determined | undetermined
    piece_date_status: Mapped[str] = mapped_column(String, nullable=False)
    full_text: Mapped[str] = mapped_column(Text, nullable=False)  # FR-13's target, stored once
    text_version: Mapped[str] = mapped_column(String, nullable=False)


class Failure(Base):
    __tablename__ = "failure"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant: Mapped[str] = mapped_column(String, nullable=False)
    matter: Mapped[str] = mapped_column(String, nullable=False)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    submitted_path: Mapped[str] = mapped_column(Text, nullable=False)
    error_class: Mapped[str] = mapped_column(String, nullable=False)
    resolution_state: Mapped[str] = mapped_column(String, nullable=False)  # open|resolved
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MatterScope(Base):
    """The authoritative matter -> scope mapping (AD-13). Scope is resolved from
    here at query time and pre-filters every read — it is NEVER denormalised onto
    piece/chunk rows, so a re-scope takes effect at the next query with nothing to
    propagate. One scope per matter here (the Chinese-wall unit); the grant
    mechanics (which users hold which scope) are story 1.6.
    """

    __tablename__ = "matter_scope"

    matter: Mapped[str] = mapped_column(String, primary_key=True)
    tenant: Mapped[str] = mapped_column(String, nullable=False)
    scope: Mapped[str] = mapped_column(String, nullable=False)
