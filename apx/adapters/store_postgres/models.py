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
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from apx.adapters.store_postgres.crypto_types import EncryptedText
from apx.adapters.store_postgres.vector_types import Halfvec
from apx.core.domain.normalization import normalize

EMBEDDING_DIM = 1024  # the halfvec width (AD-11); must match the Embedder port's `dimensions`


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
    # This scalar is the FIRST-SEEN *representative* provenance (a piece may carry several,
    # AD-8): the full set lives in `piece_provenance`, unioned across imports (Story 2.5).
    provenance_path: Mapped[str] = mapped_column(
        EncryptedText("piece.provenance_path"), nullable=False)  # attribute, not identity
    # NO `custodian` column (AD-9): custodianship is a SET on the pièce (`piece_custodian`,
    # the CUSTODIAN_LINK), unioned — never replaced or collapsed — by every import job
    # admitting the same content, and resolved by join at read time. Enforced structurally
    # (`no_custodian_or_scope_column_on_piece`). Removed from `piece` in Story 2.5.
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
    # The deterministic engine's searchable surface (Story 3.2, AD-21): the ONE `normalize()`
    # (fr-fold-v1) rule applied to the full text at write time, so the corpus is folded the SAME way
    # the query is — the query and the index share one implementation, so a normalisation divergence
    # cannot cause a false absence. A plain LIKE over this column needs no `unaccent`. Derived from
    # `full_text`, kept in sync by the ``_normalise_full_text`` event; the same AD-31 exemption as
    # `full_text` applies (a searchable index cannot be application-encrypted).
    full_text_normalized: Mapped[str] = mapped_column(Text, nullable=False)
    # AD-10: the full text is a first-class artefact with its OWN identity and version,
    # separate from the raw-content identity (content_hash) — two scans of one page can
    # share a text_identity though their content_hash differs. `text_version` records
    # how it was produced; `text_identity` records what it IS (a hash of the text).
    text_identity: Mapped[str] = mapped_column(String(64), nullable=False)
    text_version: Mapped[str] = mapped_column(String, nullable=False)


@event.listens_for(Piece, "before_insert")
@event.listens_for(Piece, "before_update")
def _normalise_full_text(_mapper: object, _conn: object, target: Piece) -> None:
    """Keep ``full_text_normalized`` = ``normalize(full_text)`` on every write, so the search index
    is folded by the SAME rule as the query (Story 3.2, AD-21) — no caller can forget it."""
    target.full_text_normalized = normalize(target.full_text)


class PieceProvenance(Base):
    """The provenance SET of a *pièce* (AD-8: "one *pièce* may carry several" provenance
    paths). One row per (piece, distinct path), **unioned — never replaced — by every import
    job** admitting the same content (Story 2.5). The path is PII → application-encrypted
    (AD-31). AES-GCM is randomised so the ciphertext cannot be a SQL key; the set-membership
    key is the deterministic ``id`` = sha256(piece_id \x00 path) instead — the same pattern
    the *failure* table uses (``_failure_id``) — so a repeated path is one row and a
    concurrent double-insert collides on the PK (absorbed, never a duplicate). No cascade FK
    (AD-7): a *pièce* is retired, never hard-deleted out from under its provenance."""

    __tablename__ = "piece_provenance"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # sha256(piece_id \0 path)
    # no ON DELETE anywhere (AD-7) — RESTRICT by default, a retired state never a cascade
    piece_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("piece.id"), nullable=False, index=True)
    provenance_path: Mapped[str] = mapped_column(
        EncryptedText("piece_provenance.provenance_path"), nullable=False)


class PieceCustodian(Base):
    """The CUSTODIAN_LINK (AD-9): custodianship is a SET on the *pièce*, **unioned — never
    replaced or collapsed — by every import job** admitting the same content, resolved by
    join at read time. Who held a document is frequently the fact in issue in *ordonnance
    145 CPC* work, so deduplication may never collapse two custodians into one (FR-4). One
    row per (piece, distinct custodian); the custodian is PII → application-encrypted
    (AD-31), with the deterministic ``id`` = sha256(piece_id \x00 custodian) as the
    set-membership key (see :class:`PieceProvenance`). No cascade FK (AD-7)."""

    __tablename__ = "piece_custodian"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # sha256(piece_id \0 custodian)
    piece_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("piece.id"), nullable=False, index=True)
    custodian: Mapped[str] = mapped_column(
        EncryptedText("piece_custodian.custodian"), nullable=False)


class Chunk(Base):
    """A chunk of a *pièce*'s full text — the unit the semantic engine indexes. Its
    columns are EXACTLY the enumerated payload-schema set (AD-9); any other column fails
    the build (``chunk_columns_enumerated`` asserts it). Absent by design: **no**
    ``rbac_scope``/``scope`` column — scope is a write-time check resolved from
    ``matter_scope`` at query time (AD-13/AD-40) — and **no** ``custodian`` column —
    custodianship is a SET on the *pièce* (:class:`PieceCustodian`, the CUSTODIAN_LINK;
    Story 2.5). The embedding trio (the ``halfvec`` vector and its
    ``model_id``/``model_version``) is present as of the embedder story (2.8), so a
    mixed-provenance *corpus* is detectable rather than suspected (AD-11); 1.3 froze the
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
    # ── the embedding trio (AD-11, story 2.8) — the embedder's identity + its output ──
    # model_id/model_version make a mixed-provenance corpus DETECTABLE (AD-11); the vector is
    # 1024-dim halfvec on PG (volume-encrypted, AD-31 — never app-encrypted, a randomised column
    # could not be HNSW-indexed). All NOT NULL: a chunk exists only once it has been embedded.
    model_id: Mapped[str] = mapped_column(String, nullable=False)
    model_version: Mapped[str] = mapped_column(String, nullable=False)
    vector: Mapped[list[float]] = mapped_column(Halfvec(EMBEDDING_DIM), nullable=False)


class Failure(Base):
    """The failure register (FR-5): every pièce submitted but not in the corpus, enumerated,
    attributed and actionable. Resolved by STATE CHANGE, never removed (AD-7): a resolved entry
    stays so "what was and was not reviewed" remains answerable. `resolution_state` transitions are
    conditional commits owned by the store's register use cases (AD-37) — asserted by the
    `register_state_written_once` structural property. `matter` is nullable: an entry that could
    not be attributed to a matter (undetermined) is visible only to the tenant-wide admin (FR-49);
    a NULL matter has no `matter_scope` row, so the scope pre-filter excludes it from every ordinary
    read by construction."""

    __tablename__ = "failure"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant: Mapped[str] = mapped_column(String, nullable=False)
    # nullable = the matter could not be determined (undetermined) — admin-only visibility (FR-49)
    matter: Mapped[str | None] = mapped_column(String, nullable=True)
    # content-bearing → application-encrypted (AD-31): filenames/paths/details/custodian name the
    # documents that did not enter the corpus. error_class/resolution_state/cardinality are
    # categorical (query keys), left plaintext.
    filename: Mapped[str] = mapped_column(EncryptedText("failure.filename"), nullable=False)
    submitted_path: Mapped[str] = mapped_column(
        EncryptedText("failure.submitted_path"), nullable=False)
    # the custodian who held the pièce, WHERE KNOWN (FR-5) — PII, nullable
    custodian: Mapped[str | None] = mapped_column(
        EncryptedText("failure.custodian"), nullable=True)
    error_class: Mapped[str] = mapped_column(String, nullable=False)
    # AD-38: `one` for an ordinary pièce; `unknown` for a `container-unopenable` entry (it stands
    # for an unknown number of pièces and is never summed into a total).
    cardinality: Mapped[str] = mapped_column(String, nullable=False, default="one")
    resolution_state: Mapped[str] = mapped_column(String, nullable=False)  # open|resolved
    detail: Mapped[str | None] = mapped_column(EncryptedText("failure.detail"), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class NoiseExclusion(Base):
    """Filesystem noise (FR-6, Story 2.7): a file excluded at enumeration as declared noise
    (`.DS_Store`, lock files, resource forks). It is NOT a *pièce* and NOT a *failure register*
    entry — its own durable, countable, listable class, so `excluded_as_noise` is a permanent
    *denominator* line and the excluded set is one click away (neither silently dropped nor
    dominating the register). Keyed idempotently by (tenant, matter, submitted_path) so re-importing
    the same folder never double-counts (Story 2.5 idempotency). Its path is client data — the path
    is frequently the privileged fact (AD-41) — so path and filename are encrypted at rest
    (AD-31/AD-28). No cascade FK (AD-7)."""

    __tablename__ = "noise_exclusion"

    # sha256(tenant \0 matter \0 submitted_path) — the set key (a ciphertext column can't be a PK).
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant: Mapped[str] = mapped_column(String, nullable=False)
    matter: Mapped[str] = mapped_column(String, nullable=False)  # always known (the ingest matter)
    submitted_path: Mapped[str] = mapped_column(
        EncryptedText("noise_exclusion.submitted_path"), nullable=False)
    filename: Mapped[str] = mapped_column(
        EncryptedText("noise_exclusion.filename"), nullable=False)
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
    # Story 2.7: the durable, monotonic `submitted_pieces` high-water mark — the *denominator*'s
    # frozen count of the known pièce population (AD-38 / the AD-17 application-owned ledger). It is
    # NOT recomputed as `in_corpus + open_register_entries` (that tautology can never catch a
    # miscount, defeating SM-3); it is raised to `max(stored, in_corpus + open)` at each ingest and
    # retry so it never shrinks. A later loss of a corpus pièce or a register entry then makes it
    # EXCEED the live sum and fails the invariant — the machine form of "nothing silently lost".
    submitted_pieces: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0")
    # The optional case theory (FR-37): free text, in the lawyer's own language, stated at
    # import or later. Confidential legal strategy, not a query key → encrypted at rest
    # (AD-31), nullable when skipped. A single current value here; the versioned/audited/
    # re-rankable model is Epic 4 (story 4.1), which supersedes this column.
    case_theory: Mapped[str | None] = mapped_column(
        EncryptedText("matter_scope.case_theory"), nullable=True
    )


class CaseTheoryVersion(Base):
    """One version of a *matter*'s optional case theory (FR-37, Story 4.1) — the versioned,
    audited, referenceable model that SUPERSEDES the single ``matter_scope.case_theory`` column
    (now a denormalised current-value cache). APPEND-ONLY: a rewrite is a NEW row; a *withdrawal*
    (FR-37's "delete") is a new row with ``text = NULL``; a prior version is NEVER updated or
    deleted (AD-7 — asserted by the ``case_theory_version_is_append_only`` structural check). The
    version + its audit entry are written by exactly one owning use case (AD-37).

    ``version_no`` is a per-matter monotonic counter — the ordering AD-49 wants for the history
    (the audit ``seq`` carries the record's monotonic order). ``id`` is the deterministic
    ``sha256(tenant \\x00 matter \\x00 version_no \\x00 text)`` — a stable, collision-free identity
    a future *ranking version* names (AD-23). ``text`` (the legal strategy) and ``actor`` (a
    person's display name) are confidential → application-encrypted at rest (AD-31). No cascade FK
    (AD-7): a *matter* is retired, never hard-deleted out from under its case-theory history."""

    __tablename__ = "case_theory_version"
    __table_args__ = (
        # a per-matter monotonic version_no; a concurrent double-write collides here and fails
        # loudly (AD-37 conditional commit), never a silent overwrite. Also indexes (tenant,matter).
        UniqueConstraint("tenant", "matter", "version_no", name="uq_case_theory_version"),
        # the matter identity is composite (tenant, matter) (AD-12); no ondelete (AD-7 RESTRICT).
        ForeignKeyConstraint(
            ["tenant", "matter"], ["matter_scope.tenant", "matter_scope.matter"]),
    )

    # sha256(tenant \0 matter \0 version_no \0 text) — the referent a ranking version names (AD-23)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant: Mapped[str] = mapped_column(String, nullable=False)
    matter: Mapped[str] = mapped_column(String, nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)  # per-matter, 1-based
    # NULL text == a withdrawal version (the append-only "delete", FR-37). Confidential → encrypted.
    text: Mapped[str | None] = mapped_column(
        EncryptedText("case_theory_version.text"), nullable=True)
    actor: Mapped[str] = mapped_column(EncryptedText("case_theory_version.actor"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ImportJob(Base):
    """The application-owned import-job ledger (AD-17): the SOLE authority for a job's state
    and for the *processed-against-submitted* progress figure. Procrastinate's queue holds no
    state any read path consults — a structural property (no module outside
    ``adapters/store_postgres/queue`` may query a queue table). One open job per *matter* (FR-7).
    `submitted` is NULL while enumeration is provisional and frozen at its completion (AD-17)."""

    __tablename__ = "import_job"
    # FR-7: at most ONE open (not-done) import job per matter, enforced atomically by the DB so a
    # concurrent double-submit cannot create two (the API's read-then-create is a TOCTOU alone).
    __table_args__ = (
        Index(
            "uq_import_job_open", "tenant", "matter", unique=True,
            sqlite_where=text("state != 'done'"), postgresql_where=text("state != 'done'")),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant: Mapped[str] = mapped_column(String, nullable=False)
    matter: Mapped[str] = mapped_column(String, nullable=False)
    scope: Mapped[str] = mapped_column(String, nullable=False)  # the wall to persist under (AD-13)
    # actor/custodian/case_theory are confidential (a person's display name, the custodian, the
    # legal strategy) → encrypted at rest (AD-31), as on audit_record/piece/matter_scope.
    actor: Mapped[str] = mapped_column(EncryptedText("import_job.actor"), nullable=False)
    custodian: Mapped[str] = mapped_column(EncryptedText("import_job.custodian"), nullable=False)
    case_theory: Mapped[str | None] = mapped_column(
        EncryptedText("import_job.case_theory"), nullable=True
    )
    spool_path: Mapped[str] = mapped_column(String, nullable=False)  # durable staging dir (opaque)
    owns_spool: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    state: Mapped[str] = mapped_column(String, nullable=False)  # enumerating|running|done
    submitted: Mapped[int | None] = mapped_column(Integer, nullable=True)  # frozen unit count
    provisional: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ImportUnit(Base):
    """One unit of work — a submitted file — against the import-job ledger (AD-17). Keyed by
    ``(job, provenance)`` so enumeration and resume are idempotent; ``attempts`` is the resume
    authority, advanced in its own transaction committed BEFORE the unit's work begins so an
    OS-level kill still advances it. No cascade FK (AD-7)."""

    __tablename__ = "import_unit"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # sha256(job_id \0 provenance)
    job_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("import_job.id"), nullable=False, index=True
    )
    provenance_path: Mapped[str] = mapped_column(
        EncryptedText("import_unit.provenance_path"), nullable=False  # a path leaks folder/client
    )
    state: Mapped[str] = mapped_column(String, nullable=False)  # pending|committed|quarantined
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


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


class TenantSetting(Base):
    """Per-tenant configuration-as-data (AD-24) — never code, never a per-deployment env var.
    One row per (tenant, key); ``value`` holds the JSON-encoded configuration value. The set of
    permitted keys, their types and their defaults are declared in ``apx.core.domain.config``;
    this table only stores the *non-default* values a tenant has set. Written exclusively through
    the audited surface (AD-25) — ``store.set_config`` validates against the schema and records
    before/after — so a value here without a matching audited change is a direct edit and is
    detectable (``store.config_provenance``). Replaces the earlier single ``mfa_required`` column:
    MFA is now the ``mfa_required`` key, so there is one surface for every configuration value."""

    __tablename__ = "tenant_setting"

    tenant: Mapped[str] = mapped_column(String, primary_key=True)
    key: Mapped[str] = mapped_column(String, primary_key=True)
    # JSON-encoded value (apx.core.domain.config declares each key's type + default)
    value: Mapped[str] = mapped_column(Text, nullable=False)


class BackupRecord(Base):
    """A recorded backup run per tenant (story 1.11, AD-32): outcome + when + size, so "no
    successful backup within the interval" is answerable and the worklist can render it."""

    __tablename__ = "backup_record"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    tenant: Mapped[str] = mapped_column(String, nullable=False, index=True)
    outcome: Mapped[str] = mapped_column(String, nullable=False)   # success | failure (categorical)
    # a failure diagnostic may name a path → content-bearing, application-encrypted (AD-31)
    detail: Mapped[str | None] = mapped_column(EncryptedText("backup_record.detail"), nullable=True)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TruncationMarker(Base):
    """A detected restore-truncation (story 1.11, AD-35): the live chain head fell BEHIND the head
    journal — the record now ends earlier than it did. Persistent and **never repaired**; cleared
    only by an audited override with a reason. One row per tenant (the latest detection)."""

    __tablename__ = "truncation_marker"

    tenant: Mapped[str] = mapped_column(String, primary_key=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    journal_seq: Mapped[int] = mapped_column(Integer, nullable=False)   # where the record was
    live_seq: Mapped[int] = mapped_column(Integer, nullable=False)      # where it ends now
    # the override actor (PII) and reason → application-encrypted (AD-31); NULL until cleared
    cleared_by: Mapped[str | None] = mapped_column(
        EncryptedText("truncation_marker.cleared_by"), nullable=True)
    reason: Mapped[str | None] = mapped_column(
        EncryptedText("truncation_marker.reason"), nullable=True)
    cleared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


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


class RankingVersion(Base):
    """One *ranking version* of a *matter* (FR-39, Story 4.3) — the complete immutable identity of
    what produced one ranked order (AD-23). APPEND-ONLY and NEVER mutated after creation (AD-37 —
    the
    ranking use case owns its creation; asserted by ``ranking_version_is_append_only``). The version
    + its ranked rows + one audit entry are written atomically by exactly one owning use case
    (AD-22).

    ``version_no`` is a per-*matter* monotonic counter (AD-49's ordering; the audit ``seq`` carries
    the record's monotonic order). ``id`` (= ``version_id``) is the referenceable
    ``sha256(tenant \\x00 matter \\x00 version_no \\x00 fingerprint)`` (AD-23 — referenceable +
    immutable). ``identity_json`` is the canonical AD-23 identity — **plaintext**: it is structural
    version metadata readable in the interface and the content-free projection (NFR-56), carrying no
    PII or content (like ``schema_version``). ``case_theory_version_id`` names the referenced 4.1
    version so the conditional commit (AD-23/AD-37) can verify it is unchanged at write time. No
    cascade FK (AD-7): a *matter* is retired, never hard-deleted out from under its rankings."""

    __tablename__ = "ranking_version"
    __table_args__ = (
        # a per-matter monotonic version_no; a concurrent double-write collides here and fails
        # loudly (AD-37 conditional commit), never a silent overwrite. Also indexes (tenant,matter).
        UniqueConstraint("tenant", "matter", "version_no", name="uq_ranking_version"),
        # the matter identity is composite (tenant, matter) (AD-12); no ondelete (AD-7 RESTRICT).
        ForeignKeyConstraint(
            ["tenant", "matter"], ["matter_scope.tenant", "matter_scope.matter"]),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # = version_id (AD-23)
    tenant: Mapped[str] = mapped_column(String, nullable=False)
    matter: Mapped[str] = mapped_column(String, nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)  # per-matter, 1-based
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)  # "same version" identity
    basis: Mapped[str] = mapped_column(String, nullable=False)  # case-theory | intrinsic
    # the complete AD-23 identity, canonical JSON — plaintext structural metadata (NFR-56), no PII.
    identity_json: Mapped[str] = mapped_column(Text, nullable=False)
    # the referenced case-theory version (NULL on the intrinsic path) — the conditional-commit
    # input.
    case_theory_version_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    stage3_share: Mapped[float] = mapped_column(Float, nullable=False)  # SM-18, recorded on the run
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RankedEntry(Base):
    """One *pièce*'s recorded row in a *ranking version* (AD-23's per-*pièce* output, Story 4.3).
    APPEND-ONLY with its version (asserted by ``ranking_version_is_append_only``); no cascade FK
    (AD-7). ``rank`` is 1-based for a pièce IN the order (judged or rejected) and **NULL for an
    UNSCORED pièce** — out of the order, never ranked last, never dropped (AD-19). It carries its
    ``score`` OR its ``rejection_class`` (AD-36), its near-duplicate ``family_id`` and
    ``is_representative`` (the estimator needs the family), and its ``supersedes`` state.

    **All columns plaintext** — none is content or PII: ``band``/``label``/``outcome``/
    ``rejection_class`` are categorical, ``score`` a float, ``family_id`` a text_key hash,
    ``failure_reason`` an already-redacted diagnostic. Like ``LabelRecord`` (which encrypts only its
    rationale). **No ``retained``/``discarded`` column** — those sets are views, never a membership
    (AD-39, asserted by ``no_retained_or_discarded_set_column``)."""

    __tablename__ = "ranked_entry"
    __table_args__ = (
        UniqueConstraint("ranking_version_id", "piece_id", name="uq_ranked_entry"),
        Index("ix_ranked_entry_version_rank", "ranking_version_id", "rank"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # sha256(version_id \0 piece_id)
    ranking_version_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("ranking_version.id"), nullable=False, index=True)  # no ondelete
    tenant: Mapped[str] = mapped_column(String, nullable=False)
    matter: Mapped[str] = mapped_column(String, nullable=False)
    piece_id: Mapped[str] = mapped_column(String(64), nullable=False)
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)  # NULL = unscored (AD-19)
    outcome: Mapped[str] = mapped_column(String, nullable=False)  # judged | rejected | unscored
    score: Mapped[float | None] = mapped_column(Float, nullable=True)  # never imputed (AD-19)
    band: Mapped[str | None] = mapped_column(String, nullable=True)
    label: Mapped[str | None] = mapped_column(String, nullable=True)
    rejection_class: Mapped[str | None] = mapped_column(String, nullable=True)  # AD-36
    failure_reason: Mapped[str | None] = mapped_column(String, nullable=True)  # redacted (AD-19)
    family_id: Mapped[str] = mapped_column(String(64), nullable=False)  # the near-duplicate key
    is_representative: Mapped[bool] = mapped_column(Boolean, nullable=False)
    supersedes: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
