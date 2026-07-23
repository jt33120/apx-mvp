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

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
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
    # the near-duplicate key: sha256 of normalised text; groups exact-modulo-formatting
    # copies so the judgment cascade collapses them before any LLM (recall-first).
    text_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
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
    # AD-10: the full text is a first-class artefact with its OWN identity and version,
    # separate from the raw-content identity (content_hash) — two scans of one page can
    # share a text_identity though their content_hash differs. `text_version` records
    # how it was produced; `text_identity` records what it IS (a hash of the text).
    text_identity: Mapped[str] = mapped_column(String(64), nullable=False)
    text_version: Mapped[str] = mapped_column(String, nullable=False)


class Chunk(Base):
    """A chunk of a *pièce*'s full text — the unit the semantic engine indexes. Its
    columns are EXACTLY the enumerated payload-schema set (AD-9); any other column fails
    the build (Task 5 asserts it). Absent by design: **no** ``rbac_scope``/``scope``
    column — scope is a write-time check resolved from ``matter_scope`` at query time
    (AD-13/AD-40) — and **no** ``custodian`` column — custodianship lives on the *pièce*
    (today a legacy scalar column; AD-9's ``CUSTODIAN_LINK`` set is a later story). The
    embedding trio (the ``halfvec`` vector and its
    ``model_id``/``model_version``) is added by the embedder story (2.8); 1.3 freezes the
    non-embedding provenance. No cascade FK (AD-7): a *pièce* is retired, never
    hard-deleted out from under its chunks.
    """

    __tablename__ = "chunk"
    __table_args__ = (
        # The natural key BEHIND the deterministic chunk_id — it must match chunk_id's
        # preimage exactly, full_text_version included (AD-40), so a re-extraction is a
        # NEW chunk (new id, new row) rather than a collision that overwrites evidence.
        UniqueConstraint(
            "piece_id", "full_text_version", "position", "chunking_config_version",
            name="uq_chunk_piece_ftv_position_cfg",
        ),
    )

    # chunk_id(piece_id, full_text_version, position, chunking_config_version) — AD-40,
    # deterministic, never a counter; the extractor version is inside it via full_text_version
    chunk_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    # no ON DELETE anywhere on this FK — a retired state, never a cascade (AD-7)
    piece_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("piece.id"), nullable=False, index=True
    )
    tenant: Mapped[str] = mapped_column(String, nullable=False)
    matter: Mapped[str] = mapped_column(String, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)  # source position in the piece
    # the version of the piece's full text this chunk was derived from (AD-10/AD-23)
    full_text_version: Mapped[str] = mapped_column(String, nullable=False)
    chunking_config_version: Mapped[str] = mapped_column(String, nullable=False)
    schema_version: Mapped[str] = mapped_column(String, nullable=False)
    # the reserved external-authority reference (AD-9) — nullable, unused until a court
    # or bâtonnier reference is attached; present so its later use is not a migration.
    external_ref: Mapped[str | None] = mapped_column(String, nullable=True)


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


class AuditRecord(Base):
    """Append-only, tamper-evident trail (FR-24, FR-53). Each entry carries a
    monotonic per-tenant sequence and a chain value over the previous entry, so a
    gap, a reordering or a truncation is detectable by a reader holding only the
    export. No user-facing action edits or removes an entry; a correction is a new
    entry. The validation act (FR-45) and the full recorded surface are later
    stories; this slice records ingestion under an actor.
    """

    __tablename__ = "audit_record"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant: Mapped[str] = mapped_column(String, nullable=False)
    seq: Mapped[int] = mapped_column(nullable=False)          # monotonic per tenant
    matter: Mapped[str | None] = mapped_column(String, nullable=True)
    actor: Mapped[str] = mapped_column(String, nullable=False)
    action: Mapped[str] = mapped_column(String, nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False)
    chain: Mapped[str] = mapped_column(String(64), nullable=False)  # sha256(prev.chain + content)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (UniqueConstraint("tenant", "seq", name="uq_audit_tenant_seq"),)


class LabelRecord(Base):
    """A piece's CURRENT triage label (FR-…, the judgment cascade). Reversible
    labelling, never deletion: one row per piece, overwritten on a re-judge; the
    history of the act lives on the append-only audit trail, not here. No cascade FK
    (AD-7). The judge that produced it is recorded for transparency (FR-33).
    """

    __tablename__ = "piece_label"

    piece_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant: Mapped[str] = mapped_column(String, nullable=False)
    matter: Mapped[str] = mapped_column(String, nullable=False, index=True)
    label: Mapped[str] = mapped_column(String, nullable=False)  # relevant | uncertain | discard
    rationale: Mapped[str] = mapped_column(Text, nullable=False)  # why — never empty
    judge: Mapped[str] = mapped_column(String, nullable=False)  # which judge decided (transparency)
    judged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class User(Base):
    """An owned user (AD-15) — no hosted identity. The password is a scrypt hash
    (apx.core.domain.auth); the plaintext is never stored. `user` is reserved in
    Postgres, hence `user_account`.
    """

    __tablename__ = "user_account"
    __table_args__ = (UniqueConstraint("tenant", "email", name="uq_user_tenant_email"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    tenant: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)  # cockpit access


class UserScope(Base):
    """Which walls a user holds (AD-13). Authoritative: scope is resolved from here at
    query time and the client never supplies it — the request cannot claim a wall.
    """

    __tablename__ = "user_scope"

    user_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    scope: Mapped[str] = mapped_column(String, primary_key=True)


class RecallReview(Base):
    """A recorded recall check on a matter's discard pile (the FR-… guarantee). A
    sample of the discards was reviewed; this stores the finite-population upper
    confidence bound computed from it — evidence that discarding at scale did not
    silently lose the decisive piece. The act is also on the audit trail.
    """

    __tablename__ = "recall_review"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    tenant: Mapped[str] = mapped_column(String, nullable=False)
    matter: Mapped[str] = mapped_column(String, nullable=False, index=True)
    population: Mapped[int] = mapped_column(nullable=False)       # discards at review time
    sample_size: Mapped[int] = mapped_column(nullable=False)      # how many were reviewed
    relevant_found: Mapped[int] = mapped_column(nullable=False)   # false discards in the sample
    confidence: Mapped[float] = mapped_column(nullable=False)
    count_upper: Mapped[int] = mapped_column(nullable=False)      # <= this many wrongly discarded
    prevalence_upper: Mapped[float] = mapped_column(nullable=False)
    reviewer: Mapped[str] = mapped_column(String, nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
