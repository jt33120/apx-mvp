"""Encrypt-at-rest backfill (story 1.7, AD-31).

Re-encrypt any content-bearing column value still stored in the clear — a store provisioned
before 1.7 turned these columns into ``EncryptedText``. Idempotent (an already-encrypted value
is skipped), and key-free when there is nothing to do: the cipher is loaded ONLY when a
plaintext value is found, so a fresh/already-encrypted store needs no ``APX_ENCRYPTION_KEY``.

Shared by the ``0013_encrypt_backfill`` data migration (run in the deploy's ``alembic upgrade``)
and testable directly against a connection. Without it, enabling encryption on an existing store
would make every historical row fail closed on read (the type refuses a non-ciphertext value).
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from sqlalchemy import Connection, text

from apx.core.domain.crypto import Cipher, DecryptionError, is_ciphertext

# (table, primary key, encrypted column, AAD context) — this MUST list EVERY ``EncryptedText``
# column in the models: rekey_all() and encrypt_backfill() iterate ONLY this list, so a column
# omitted here is silently skipped by a key rotation and then fails closed on read under the retired
# key (permanent PII loss). The completeness is asserted against the live model metadata by
# ``test_rekey_covers_every_encrypted_column`` — a drift fails the build. The primary key is a
# column name, or a TUPLE of names for a composite PK (e.g. ``matter_scope``). Story 2.5 moved
# custodian off ``piece`` into the ``piece_custodian`` SET, added the ``piece_provenance`` SET (both
# covered below), and swept in the eight PII columns a prior rotation had missed.
ENCRYPTED_COLUMNS = [
    ("piece", "id", "provenance_path", "piece.provenance_path"),
    ("piece_provenance", "id", "provenance_path", "piece_provenance.provenance_path"),
    ("piece_custodian", "id", "custodian", "piece_custodian.custodian"),
    ("failure", "id", "filename", "failure.filename"),
    ("failure", "id", "submitted_path", "failure.submitted_path"),
    ("failure", "id", "custodian", "failure.custodian"),
    ("failure", "id", "detail", "failure.detail"),
    ("noise_exclusion", "id", "submitted_path", "noise_exclusion.submitted_path"),
    ("noise_exclusion", "id", "filename", "noise_exclusion.filename"),
    ("audit_record", "id", "actor", "audit_record.actor"),
    ("audit_record", "id", "detail", "audit_record.detail"),
    ("piece_label", "piece_id", "rationale", "piece_label.rationale"),
    ("user_account", "id", "mfa_secret", "user_account.mfa_secret"),
    ("recall_review", "id", "reviewer", "recall_review.reviewer"),
    ("matter_scope", ("tenant", "matter"), "case_theory", "matter_scope.case_theory"),
    # Story 4.1: the versioned case theory — text (legal strategy) + actor (display name) encrypted.
    ("case_theory_version", "id", "text", "case_theory_version.text"),
    ("case_theory_version", "id", "actor", "case_theory_version.actor"),
    ("import_job", "id", "actor", "import_job.actor"),
    ("import_job", "id", "custodian", "import_job.custodian"),
    ("import_job", "id", "case_theory", "import_job.case_theory"),
    ("import_unit", "id", "provenance_path", "import_unit.provenance_path"),
    ("backup_record", "id", "detail", "backup_record.detail"),
    ("truncation_marker", "tenant", "cleared_by", "truncation_marker.cleared_by"),
    ("truncation_marker", "tenant", "reason", "truncation_marker.reason"),
    # Story 4.5: the per-pièce taxonomy-label ledger — the actor who set a label (PII) is encrypted;
    # single-PK (`id`), so key rotation addresses it directly (unlike composite-PK tenant_setting).
    ("taxonomy_label_entry", "id", "set_by", "taxonomy_label_entry.set_by"),
    # Story 4.8: the line-placement ledger — the actor who placed the line (PII) is encrypted;
    # single-PK (`id`), so key rotation addresses it directly.
    ("line_placement", "id", "placed_by", "line_placement.placed_by"),
]


def link_id(piece_id: str, value: str) -> str:
    """The deterministic set-membership key for a `piece_provenance` / `piece_custodian` row:
    sha256(piece_id \x00 plaintext value) — the same shape as the store's `_failure_id`. The
    same (piece, value) is one row, and a concurrent double-insert collides on this PK (absorbed,
    never a duplicate). The store computes the SAME id at write time, so this and runtime agree."""
    return hashlib.sha256(f"{piece_id}\x00{value}".encode()).hexdigest()


def case_theory_version_id(tenant: str, matter: str, version_no: int, text: str | None) -> str:
    """The deterministic identity of one case theory version (Story 4.1, FR-37):
    ``sha256(tenant \x00 matter \x00 version_no \x00 text)``. ``version_no`` makes two identical
    texts distinct; a withdrawal (``text`` None) hashes the empty string. This is the referent a
    future *ranking version* names (AD-23); the store computes the SAME id at write time, so this
    backfill and the runtime agree."""
    return hashlib.sha256(
        f"{tenant}\x00{matter}\x00{version_no}\x00{text or ''}".encode()).hexdigest()


def _pk_cols(pk: str | tuple[str, ...]) -> tuple[str, ...]:
    """Normalise a PK spec to a tuple of column names (a bare string is a one-column PK)."""
    return (pk,) if isinstance(pk, str) else tuple(pk)


def _update_value(conn: Connection, table: str, pks: tuple[str, ...], col: str,
                  value: str, row: dict) -> None:
    """UPDATE one row's encrypted column, keyed by its (possibly composite) primary key. The
    value bind is ``__v`` so it never collides with a PK column name."""
    where = " AND ".join(f"{p} = :{p}" for p in pks)
    params = {p: row[p] for p in pks}
    params["__v"] = value
    conn.execute(
        text(f"UPDATE {table} SET {col} = :__v WHERE {where}"), params)  # noqa: S608


def encrypt_backfill(conn: Connection) -> int:
    """Encrypt every plaintext value in the AD-31 encrypted columns. Returns the number of
    values encrypted. Idempotent; loads the cipher only when there is plaintext to encrypt."""
    cipher = None
    encrypted = 0
    for table, pk, col, context in ENCRYPTED_COLUMNS:
        pks = _pk_cols(pk)
        sel = ", ".join((*pks, col))
        rows = conn.execute(
            text(f"SELECT {sel} FROM {table} WHERE {col} IS NOT NULL")  # noqa: S608
        ).mappings().all()
        plaintext = [r for r in rows if not is_ciphertext(r[col])]
        if not plaintext:
            continue
        if cipher is None:
            from apx.adapters.store_postgres.crypto_types import cipher as _cipher
            cipher = _cipher()  # raises MissingEncryptionKey if absent — fail closed
        for r in plaintext:
            _update_value(conn, table, pks, col, cipher.encrypt(r[col], aad=context), r)
            encrypted += 1
    return encrypted


def rekey_all(conn: Connection, cipher: Cipher | None = None) -> int:
    """Re-encrypt EVERY application-encrypted value under the current PRIMARY key (story 1.8,
    AD-47). For key rotation: after adding the new key as primary and the old as previous
    (``APX_ENCRYPTION_KEYS_OLD``), this decrypts each value with whichever key matches and
    re-encrypts it under the primary — so the previous key can then be retired. A plaintext
    legacy value is encrypted too (rekey subsumes backfill). Touches NO searchable surface (the
    vector column and text index are never application-encrypted), so a rotation needs no
    re-index. Returns the number of values rewritten. ``cipher`` defaults to the env cipher (the
    multi-key set: decrypt tries all keys, encrypt uses the primary)."""
    if cipher is None:
        from apx.adapters.store_postgres.crypto_types import cipher as _cipher
        cipher = _cipher()
    rekeyed = 0
    for table, pk, col, context in ENCRYPTED_COLUMNS:
        pks = _pk_cols(pk)
        sel = ", ".join((*pks, col))
        rows = conn.execute(
            text(f"SELECT {sel} FROM {table} WHERE {col} IS NOT NULL")  # noqa: S608
        ).mappings().all()
        for r in rows:
            value = r[col]
            try:
                plain = cipher.decrypt(value, aad=context) if is_ciphertext(value) else value
            except DecryptionError as exc:
                # name the poison row so an operator can find it, instead of an opaque
                # "no key matched" that blocks the whole (atomic) rotation.
                key = {p: r[p] for p in pks}
                raise DecryptionError(f"cannot decrypt {table}.{col} pk={key!r}: {exc}") from exc
            _update_value(conn, table, pks, col, cipher.encrypt(plain, aad=context), r)
            rekeyed += 1
    return rekeyed


# ── Story 2.5: move the piece's scalar custodian + provenance into the SET tables ──────────────
# The value is re-encrypted under the NEW column's AAD (an EncryptedText AAD binds a ciphertext to
# its column, so a verbatim copy would fail closed on read). Key-free on an EMPTY piece table (a
# fresh DB / the CI upgrade→downgrade→upgrade cycle, which runs without APX_ENCRYPTION_KEY): the
# cipher is loaded ONLY when a ciphertext value is present. Idempotent: an already-present link id
# is skipped, so a re-run is a no-op.

_LINK_SPECS = (
    ("custodian", "piece.custodian", "piece_custodian", "custodian",
     "piece_custodian.custodian"),
    ("provenance_path", "piece.provenance_path", "piece_provenance", "provenance_path",
     "piece_provenance.provenance_path"),
)


def migrate_piece_scalars_to_links(conn: Connection) -> int:
    """Backfill each `piece` row's scalar ``custodian`` and ``provenance_path`` into the
    ``piece_custodian`` / ``piece_provenance`` SET tables (Story 2.5). Returns the rows written.
    Runs BEFORE the ``piece.custodian`` column is dropped."""
    rows = conn.execute(text("SELECT id, custodian, provenance_path FROM piece")).all()
    if not rows:
        return 0
    cipher = _cipher_if(any(is_ciphertext(r.custodian) or is_ciphertext(r.provenance_path)
                            for r in rows))
    written = 0
    for row in rows:
        for src_col, old_ctx, table, dst_col, new_ctx in _LINK_SPECS:
            raw = getattr(row, src_col)
            plain = cipher.decrypt(raw, aad=old_ctx) if (cipher and is_ciphertext(raw)) else raw
            lid = link_id(row.id, plain)
            if conn.execute(
                text(f"SELECT 1 FROM {table} WHERE id = :i"), {"i": lid}  # noqa: S608
            ).first():
                continue  # idempotent — a re-run does not duplicate
            stored = cipher.encrypt(plain, aad=new_ctx) if cipher else plain
            conn.execute(
                text(f"INSERT INTO {table} (id, piece_id, {dst_col}) "  # noqa: S608
                     "VALUES (:i, :p, :v)"),
                {"i": lid, "p": row.id, "v": stored})
            written += 1
    return written


def revert_piece_links_to_scalar(conn: Connection) -> int:
    """Re-populate the (re-added, nullable) ``piece.custodian`` scalar from a representative
    ``piece_custodian`` row per piece, for a downgrade (Story 2.5). Returns the rows written. The
    smallest link id is the deterministic representative. Key-free on an empty store."""
    links = conn.execute(
        text("SELECT piece_id, id, custodian FROM piece_custodian ORDER BY piece_id, id")).all()
    if not links:
        return 0
    cipher = _cipher_if(any(is_ciphertext(r.custodian) for r in links))
    reps: dict[str, str] = {}
    for row in links:  # first (smallest id) per piece wins — ordered above
        if row.piece_id not in reps:
            plain = cipher.decrypt(row.custodian, aad="piece_custodian.custodian") \
                if (cipher and is_ciphertext(row.custodian)) else row.custodian
            reps[row.piece_id] = plain
    written = 0
    for piece_id, plain in reps.items():
        stored = cipher.encrypt(plain, aad="piece.custodian") if cipher else plain
        conn.execute(
            text("UPDATE piece SET custodian = :v WHERE id = :k"), {"v": stored, "k": piece_id})
        written += 1
    return written


def backfill_case_theory_versions(conn: Connection) -> int:
    """Seed ``case_theory_version`` version 1 from each ``matter_scope`` row's current
    ``case_theory`` (Story 4.1, migration ``0023``). The text is re-encrypted under the version
    column's AAD (an ``EncryptedText`` AAD binds a ciphertext to its column, so a verbatim copy
    would fail closed on read). Key-free on an EMPTY store (a fresh DB / the CI
    upgrade→downgrade→upgrade cycle, which runs without ``APX_ENCRYPTION_KEY``): the cipher is
    loaded ONLY when a ciphertext value is present. Idempotent: a matter that already carries a
    version is skipped, so a re-run is a no-op. The backfilled version is authored by
    ``system:backfill`` at migration time — the original authoring timestamp is not recoverable
    from a single column. Returns the rows written."""
    rows = conn.execute(text(
        "SELECT tenant, matter, case_theory FROM matter_scope WHERE case_theory IS NOT NULL")).all()
    if not rows:
        return 0
    cipher = _cipher_if(any(is_ciphertext(r.case_theory) for r in rows))
    now = datetime.now(UTC)
    written = 0
    for row in rows:
        if conn.execute(
            text("SELECT 1 FROM case_theory_version WHERE tenant = :t AND matter = :m"),
            {"t": row.tenant, "m": row.matter},
        ).first():
            continue  # idempotent — a matter already versioned is left untouched
        plain = cipher.decrypt(row.case_theory, aad="matter_scope.case_theory") \
            if (cipher and is_ciphertext(row.case_theory)) else row.case_theory
        vid = case_theory_version_id(row.tenant, row.matter, 1, plain)
        stored_text = cipher.encrypt(plain, aad="case_theory_version.text") if cipher else plain
        stored_actor = cipher.encrypt("system:backfill", aad="case_theory_version.actor") \
            if cipher else "system:backfill"
        conn.execute(
            text("INSERT INTO case_theory_version "
                 "(id, tenant, matter, version_no, text, actor, created_at) "
                 "VALUES (:id, :t, :m, 1, :txt, :actor, :ts)"),
            {"id": vid, "t": row.tenant, "m": row.matter, "txt": stored_text,
             "actor": stored_actor, "ts": now})
        written += 1
    return written


def backfill_failure_cardinality(conn: Connection) -> int:
    """Set each existing failure-register row's `cardinality` (Story 2.6, AD-38): `unknown` for a
    `container-unopenable` entry (it stands for an unknown number of pièces), else `one`. Idempotent
    and key-free (only NULL rows are touched). Returns the number of rows actually SET. Run once,
    after the column is added."""
    unknown = conn.execute(text(
        "UPDATE failure SET cardinality = 'unknown' "
        "WHERE error_class = 'container-unopenable' AND cardinality IS NULL")).rowcount or 0
    one = conn.execute(text(
        "UPDATE failure SET cardinality = 'one' WHERE cardinality IS NULL")).rowcount or 0
    return unknown + one


def backfill_submitted_pieces(conn: Connection) -> int:
    """Freeze each existing matter's ``submitted_pieces`` watermark from its current known
    population (Story 2.7, AD-38): ``in_corpus + open_register_entries``. A safe post-hoc initial
    value — on a healthy store the watermark equals this sum, and thereafter it is only raised by
    ingestion (never recomputed at read time). Run ONCE, after the column is added. Returns the
    number of matter rows set."""
    return conn.execute(text(
        "UPDATE matter_scope SET submitted_pieces = ("
        "  (SELECT count(*) FROM piece"
        "     WHERE piece.tenant = matter_scope.tenant AND piece.matter = matter_scope.matter)"
        "  + (SELECT count(*) FROM failure"
        "       WHERE failure.tenant = matter_scope.tenant"
        "         AND failure.matter = matter_scope.matter"
        "         AND failure.resolution_state = 'open'))")).rowcount or 0


def _cipher_if(needed: bool) -> Cipher | None:
    """The env cipher when a ciphertext value must be de/re-crypted, else None (so an empty or
    all-plaintext store needs no ``APX_ENCRYPTION_KEY``)."""
    if not needed:
        return None
    from apx.adapters.store_postgres.crypto_types import cipher as _cipher
    return _cipher()
