"""The on-disk shape of a *tenant* backup — one sealed directory (Story 7.2, AD-32).

AD-32's Rule names what a complete backup carries, and it opens with the word this format exists
for: *"a complete restorable backup of a tenant — **originals**, extracted text, index, audit
record, failure register, configuration — … **encrypted**, inside the tenant boundary"*. The format
this replaces was a single plaintext JSON file holding the database rows and nothing else.

Two things were wrong with it and they are different mistakes.

**The originals were not in it.** They live on the filesystem under ``OriginalStore``, the *pièce*
viewer renders them, and no code path copied them. A restored *matter* returned *pièces* whose
source document was gone — including through FR-13's exhaustive search, which is the surface that
exists to prove nothing was lost.

**It was not encrypted.** Content-bearing columns are ciphertext inside the payload, so most of it
was sealed by accident of AD-31. But ``chunk.full_text`` is the one column AD-31 deliberately leaves
in the clear — *you cannot index ciphertext* — and its stated protection is the encrypted
**volume**. A backup file is the one artefact designed to leave that volume, and it carried the
whole searchable corpus in plaintext to wherever the operator put it.

So: a directory, and nothing in it is in the clear.

    <bundle>/tables.json.sealed     the rows, AES-256-GCM under the application key
    <bundle>/originals/<hash>       each retained blob, byte-for-byte as it sits on disk

The blobs are copied **already sealed** and are never decrypted: taking a backup needs no encryption
key, never holds a firm's corpus in memory in the clear, and cannot corrupt a blob by re-encrypting
it. Their AAD binds ``(tenant, content_hash, kind)``, so a blob restored under an identity that is
not its own fails authentication rather than being served as that document.

What a bundle still discloses without the key: how many originals a *tenant* has, and each one's
content hash (its file name). That is inherent to one-file-per-blob and is stated rather than left
to be discovered.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from apx.adapters.store_postgres.store import TenantBackup
from apx.core.domain.crypto import Cipher
from apx.core.ports.originals import OriginalStore

#: Bumped from the implicit `1` (the plaintext single file) — a v1 file is not readable here, and
#: is refused by name rather than misread, because it is incomplete by construction: twelve tables
#: and every original are missing from it.
BUNDLE_FORMAT = "apx-backup/2"

TABLES_FILE = "tables.json.sealed"
ORIGINALS_DIR = "originals"

#: The sealed payload's associated data. It does NOT name the *tenant*: the tenant is *inside* the
#: payload and ``restore_tenant`` reads it from there, so binding it here would only force the
#: bundle's directory name to be load-bearing — and a directory name is the one part of a backup an
#: operator renames.
_TABLES_AAD = f"apx-backup:{BUNDLE_FORMAT}:tables"


class BundleFormatError(ValueError):
    """A directory that is not a bundle of this format — named, never guessed at."""


@dataclass(frozen=True)
class Bundle:
    """A bundle's sealed half: the rows, and the inventory of blobs that belong with them.

    The inventory is INSIDE the sealed payload rather than read off the directory, and that is a
    property and not a convenience. A restore that enumerated ``originals/`` would put back whatever
    was in it — so a blob dropped into a bundle after it was written would be restored under the
    firm's own *tenant*, unauthenticated and unmentioned by anything the key protects. It also makes
    a truncated bundle detectable: a blob named here and absent from the directory is a missing
    document with a name, instead of a count that came out lower than nobody was checking.
    """

    backup: TenantBackup
    #: ``(content_hash, kind)`` for every retained blob, as sealed at backup time
    originals: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class RestoreCoverage:
    """What a restore put back. Deliberately NOT a :class:`BundleCoverage`: that one carries a
    ``byte_size``, and a restore has none — reusing it would put a zero under a name that means
    *how big the bundle is*, which is a number that reads as a fact."""

    originals: int
    #: retained *pièces* whose document was already missing when the backup was taken
    orphaned_pieces: int


@dataclass(frozen=True)
class BundleCoverage:
    """What a backup actually captured. Recorded with the outcome (AD-32) so *"the backup
    succeeded"* stops being compatible with *"nine tables were not in it"*."""

    tables: int
    rows: int
    originals: int
    byte_size: int
    #: retained *pièces* whose original was NOT on the volume to be copied. Not a bug in the
    #: backup — a hole in the installation that the backup is the first thing to notice.
    orphaned_pieces: int = 0

    @property
    def is_complete(self) -> bool:
        return self.orphaned_pieces == 0

    def sentence_fr(self) -> str:
        base = (f"{self.tables} tables, {self.rows} lignes, {self.originals} originaux, "
                f"{self.byte_size} octets")
        if self.orphaned_pieces:
            base += (f" — INCOMPLET : {self.orphaned_pieces} pièce(s) conservée(s) sans document "
                     "d'origine sur le volume")
        return base


def _json_default(o: object) -> object:
    """Row values JSON cannot hold. A ``DATE``/``TIMESTAMP`` column comes back from Postgres as a
    ``date``/``datetime`` object (SQLite hands back a string, which needs no help) — so a DETERMINED
    ``piece_date`` (a pure ``date``, AD-40) MUST be handled or the backup crashes. ``datetime`` is
    tested FIRST because it is a subclass of ``date`` (else a timestamp would be narrowed to a bare
    date). ``bytes`` (a binary column, e.g. an embedding) is base64'd; ``Decimal`` is stringified
    losslessly (a float would round)."""
    if isinstance(o, datetime):
        return {"$dt": o.isoformat()}
    if isinstance(o, date):
        return {"$d": o.isoformat()}
    if isinstance(o, bytes):
        return {"$b64": base64.b64encode(o).decode("ascii")}
    if isinstance(o, Decimal):
        return str(o)
    raise TypeError(f"not serialisable: {type(o).__name__}")


def _revive(d: dict) -> object:
    if len(d) == 1:
        if "$dt" in d:
            return datetime.fromisoformat(d["$dt"])
        if "$d" in d:
            return date.fromisoformat(d["$d"])
        if "$b64" in d:
            return base64.b64decode(d["$b64"])
    return d


def _blob_name(content_hash: str, kind: str) -> str:
    return content_hash if kind == "original" else f"{content_hash}.{kind}"


def write_bundle(
    out_dir: Path, backup: TenantBackup, originals: OriginalStore, cipher: Cipher
) -> BundleCoverage:
    """Write ``backup`` and the *tenant*'s retained originals to a fresh bundle directory.

    Refuses an existing directory. A backup that could land inside another backup would produce one
    directory holding two *tenants*' blobs under a single sealed payload naming one of them — and
    the extra blobs would restore silently, since the blob face is content-addressed and does not
    ask which backup a file came from.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=False)
    blob_dir = out / ORIGINALS_DIR
    blob_dir.mkdir()

    # The blobs go first: the inventory is sealed WITH the rows, so it has to be the inventory of
    # what was actually written, not of what was intended.
    size = 0
    inventory: list[tuple[str, str]] = []
    for content_hash, kind in originals.sealed_blobs(backup.tenant):
        raw = originals.read_sealed(backup.tenant, content_hash, kind)
        (blob_dir / _blob_name(content_hash, kind)).write_bytes(raw)
        inventory.append((content_hash, kind))
        size += len(raw)

    payload = {
        "format": BUNDLE_FORMAT,
        "tenant": backup.tenant,
        "schema_version": backup.schema_version,
        "tables": backup.tables,
        "head_tail": backup.head_tail,
        "originals": [list(item) for item in inventory],
    }
    sealed = cipher.encrypt_bytes(
        json.dumps(payload, default=_json_default, ensure_ascii=False).encode("utf-8"),
        aad=_TABLES_AAD)
    (out / TABLES_FILE).write_bytes(sealed)
    retained = {
        row["content_hash"] for row in backup.tables.get("piece", []) if row.get("content_hash")}
    return BundleCoverage(
        tables=len(backup.tables),
        rows=sum(len(rows) for rows in backup.tables.values()),
        originals=len(inventory),
        byte_size=size + len(sealed),
        orphaned_pieces=len(retained - {h for h, _ in inventory}))


def read_bundle(in_dir: Path, cipher: Cipher) -> Bundle:
    """The rows back out of a bundle. Raises :class:`BundleFormatError` for anything that is not one
    of these — including the legacy plaintext file, which is refused rather than read, because it
    cannot produce a complete restore and a partial restore reporting success is the failure this
    story exists to remove."""
    path = Path(in_dir)
    if path.is_file():
        raise BundleFormatError(
            f"{path} is a file, not a bundle directory — a pre-7.2 backup is a plaintext JSON dump "
            "of 20 of 35 tables with no originals in it, and restoring it would report success "
            "over a tenant missing every ranking, sampling run and validation act (AD-32)")
    sealed_path = path / TABLES_FILE
    if not sealed_path.is_file():
        raise BundleFormatError(f"{path} holds no {TABLES_FILE} — not an {BUNDLE_FORMAT} bundle")
    payload = json.loads(
        cipher.decrypt_bytes(sealed_path.read_bytes(), aad=_TABLES_AAD).decode("utf-8"),
        object_hook=_revive)
    if payload.get("format") != BUNDLE_FORMAT:
        raise BundleFormatError(
            f"bundle format {payload.get('format')!r}, expected {BUNDLE_FORMAT!r}")
    return Bundle(
        TenantBackup(
            payload["tenant"], payload["schema_version"], payload["tables"], payload["head_tail"]),
        tuple((h, k) for h, k in payload.get("originals", ())))


def restore_originals(in_dir: Path, bundle: Bundle, originals: OriginalStore) -> RestoreCoverage:
    """Put back every blob the **sealed inventory** names, and say what the record is short of.

    Two different completeness questions, asked in two different places because they fail
    differently and only one of them can be a refusal.

    *Is the bundle intact?* Every ``(content_hash, kind)`` the sealed payload names must be in
    ``originals/``. A blob lost in transit **refuses the restore** — it is a named missing document
    rather than a count that came out lower than nobody was checking.

    *Was the installation whole when the backup was taken?* Every ``content_hash`` in the restored
    ``piece`` rows should have arrived. A shortfall here is **reported, never refused**: the hole
    predates the disaster, ``write_bundle`` already recorded the backup as incomplete on the day it
    happened, and refusing the restore would leave a firm holding the only copy of its *matter* and
    no way to open it. It is named on the way in instead, so the *pièce* the viewer cannot render is
    known before somebody looks for it.
    """
    blob_dir = Path(in_dir) / ORIGINALS_DIR
    tenant = bundle.backup.tenant
    restored: set[str] = set()
    absent: list[str] = []
    for content_hash, kind in bundle.originals:
        blob = blob_dir / _blob_name(content_hash, kind)
        if not blob.is_file():
            absent.append(blob.name)
            continue
        originals.put_sealed(tenant, content_hash, kind, blob.read_bytes())
        restored.add(content_hash)
    if absent:
        raise BundleFormatError(
            f"{len(absent)} blob(s) the sealed inventory names are not in {ORIGINALS_DIR}/ "
            f"(first: {absent[0]}) — the bundle is truncated (AD-32)")
    retained = {
        row["content_hash"] for row in bundle.backup.tables.get("piece", [])
        if row.get("content_hash")}
    return RestoreCoverage(
        originals=len(bundle.originals), orphaned_pieces=len(retained - restored))
