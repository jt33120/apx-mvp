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

from apx.adapters.store_postgres.crypto_types import EncryptedText


class Base(DeclarativeBase):
    pass


class Piece(Base):
    __tablename__ = "piece"
    __table_args__ = (
        # tenant is IN the identity (AD-12): a matter is tenant-local, so the same file
        # under the same matter name in two tenants is two distinct pieces, never a
        # silent collision that lets one firm overwrite the other's row.
        UniqueConstraint("tenant", "matter", "content_hash", name="uq_piece_tenant_matter_content"),
        CheckConstraint(
            "(piece_date IS NOT NULL) = (piece_date_status = 'determined')",
            name="ck_piece_date_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # the tenant-qualified piece_id
    tenant: Mapped[str] = mapped_column(String, nullable=False)
    matter: Mapped[str] = mapped_column(String, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    # the near-duplicate key: sha256 of normalised text; groups exact-modulo-formatting
    # copies so the judgment cascade collapses them before any LLM (recall-first).
    text_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # content-bearing → application-encrypted at rest (AD-31). A path leaks custodian
    # folder structure and client names; custodianship is PII. Neither is a query key.
    provenance_path: Mapped[str] = mapped_column(
        EncryptedText("piece.provenance_path"), nullable=False)  # attribute, not identity
    custodian: Mapped[str] = mapped_column(EncryptedText("piece.custodian"), nullable=False)
    extraction_method: Mapped[str] = mapped_column(String, nullable=False)
    extractor_version: Mapped[str] = mapped_column(String, nullable=False)
    schema_version: Mapped[str] = mapped_column(String, nullable=False)
    ingestion_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    piece_date: Mapped[date | None] = mapped_column(nullable=True)
    # determined | undetermined
    piece_date_status: Mapped[str] = mapped_column(String, nullable=False)
    # AD-31 NAMED EXCEPTION — the deterministic text index. `search` (FR-13) runs an SQL
    # ILIKE over this column, so it CANNOT be application-encrypted (you cannot index
    # ciphertext); it is protected by volume-level encryption and asserted by the start-up
    # gate instead. Left plaintext ON PURPOSE — a structural check (AD-33) forbids encrypting
    # it (it would break exhaustive search) and the seeded-token test excludes it by name.
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
    # content-bearing → application-encrypted (AD-31): filenames/paths/details name the
    # documents that did not enter the corpus. error_class/resolution_state are categorical.
    filename: Mapped[str] = mapped_column(EncryptedText("failure.filename"), nullable=False)
    submitted_path: Mapped[str] = mapped_column(
        EncryptedText("failure.submitted_path"), nullable=False)
    error_class: Mapped[str] = mapped_column(String, nullable=False)
    resolution_state: Mapped[str] = mapped_column(String, nullable=False)  # open|resolved
    detail: Mapped[str | None] = mapped_column(EncryptedText("failure.detail"), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MatterScope(Base):
    """The authoritative matter -> scope mapping (AD-13). Scope is resolved from
    here at query time and pre-filters every read — it is NEVER denormalised onto
    piece/chunk rows, so a re-scope takes effect at the next query with nothing to
    propagate. One scope per matter here (the Chinese-wall unit); the grant
    mechanics (which users hold which scope) are story 1.6.
    """

    __tablename__ = "matter_scope"

    # composite PK (tenant, matter): a matter belongs to exactly one tenant (AD-12;
    # the spine's TENANT-owns-MATTER, AD-43 chains per (tenant, matter)). Two tenants may
    # each hold a matter of the same name — distinct rows, never one overwriting the other.
    tenant: Mapped[str] = mapped_column(String, primary_key=True)
    matter: Mapped[str] = mapped_column(String, primary_key=True)
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
    # actor is a person's display name (PII) and is never a SQL predicate → encrypted (AD-31
    # puts "the audit record" in the encrypted set). action stays plaintext: a categorical
    # verb ("ingest"/"judge"/"login_failed") that may be filtered/counted, not personal data.
    actor: Mapped[str] = mapped_column(EncryptedText("audit_record.actor"), nullable=False)
    action: Mapped[str] = mapped_column(String, nullable=False)
    # the free-text field carries emails, IPs, counts, subjects → application-encrypted (AD-31).
    # Both actor and detail: the chain is computed over the PLAINTEXT values before the columns
    # encrypt them, and read_audit decrypts before recomputing — so tamper-evidence survives
    # (AC3). seq/chain/timestamp stay plaintext: structural metadata and the query surface.
    detail: Mapped[str] = mapped_column(EncryptedText("audit_record.detail"), nullable=False)
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
    # the judge's rationale quotes the evidence → application-encrypted (AD-31)
    rationale: Mapped[str] = mapped_column(
        EncryptedText("piece_label.rationale"), nullable=False)  # why — never empty
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
    # the user's TOTP secret (pyotp), set at enrolment; NULL until enrolled. A shared secret
    # by construction (both sides need it) — not a reversible password store (AD-15).
    # A literal secret at rest → application-encrypted (AD-31); fetched by user id, never
    # queried by value, so encryption is transparent. (email/display_name stay plaintext:
    # email is the login lookup key; both are operator identity, not tenant document content.)
    mfa_secret: Mapped[str | None] = mapped_column(
        EncryptedText("user_account.mfa_secret"), nullable=True)


class UserScope(Base):
    """Which walls a user holds (AD-13). Authoritative: scope is resolved from here at
    query time and the client never supplies it — the request cannot claim a wall.
    """

    __tablename__ = "user_scope"

    user_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    scope: Mapped[str] = mapped_column(String, primary_key=True)


class SessionRecord(Base):
    """An opaque server-side session (AD-15). The cookie carries only this unguessable id;
    authority comes from THIS row — so sign-out, a password change and a scope revocation
    take effect immediately (delete the row / re-resolve live), not "wait for a token to
    expire". There is no stateless self-verifying token for user sessions (AD-15 forbids
    JWT here). No user data is denormalised on the row — the actor, admin flag and scopes
    are resolved live from the user's rows at each request. No cascade FK (AD-7).
    """

    __tablename__ = "session"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # secrets.token_urlsafe(32)
    user_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    tenant: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    absolute_expiry: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TenantConfig(Base):
    """Per-tenant configuration-as-data (AD-24) — never code. Today it carries whether MFA
    (TOTP) is required for the tenant's users (FR-48); the row is the config, so turning MFA
    on for a firm is a data change, not a deploy."""

    __tablename__ = "tenant_config"

    tenant: Mapped[str] = mapped_column(String, primary_key=True)
    mfa_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


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
    # the reviewer's display name (PII), never a SQL predicate → application-encrypted (AD-31)
    reviewer: Mapped[str] = mapped_column(EncryptedText("recall_review.reviewer"), nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
