"""A filesystem retained-original store on the tenant data volume (Story 3.5a; AD-31/AD-40).

The ``OriginalStore`` for the on-prem deployment: each pièce's original bytes live at
``{root}/{tenant}/{ch[:2]}/{ch}``, **application-encrypted** (AES-256-GCM via the shared
:class:`Cipher`) before they touch disk, content-addressed by ``content_hash`` (dedup within a
tenant), and partitioned by ``tenant`` (one tenant can never address another's original — the AAD
binds a blob to its exact identity, so a relocated blob fails authentication).

The original is *content* and is not searchable, so the AD-31 named exception for the ``full_text``
search index does not apply: the default — application-encryption — does, on the (also
volume-encrypted) data volume. The write is atomic (temp file + ``os.replace``) so a crash never
leaves a half-written blob a reader could mistake for whole.
"""

from __future__ import annotations

import contextlib
import hashlib
import os
import re
import tempfile
from collections.abc import Mapping
from pathlib import Path

from apx.core.domain.crypto import Cipher

_HEX64 = re.compile(r"[0-9a-f]{64}")            # a sha256 content_hash (AD-40) — the ONLY blob name
_SAFE_KIND = re.compile(r"[a-z][a-z0-9-]*")     # an artifact kind: original | ocr-layout | …


def _aad(tenant: str, content_hash: str, kind: str) -> str:
    """The associated data binding a blob to its exact identity — a blob file moved under another
    tenant/hash/kind fails authentication on read, so a disk-level attacker cannot re-address it nor
    swap one artifact KIND for another (an ``ocr-layout`` can never be read as an ``original``). The
    fixed-position ``kind`` and fixed-length ``content_hash`` keep this INJECTIVE for ANY tenant
    string (no reliance on a tenant charset — two distinct identities never share an AAD)."""
    return f"apx-original:v1:{kind}:{content_hash}:{tenant}"


class FilesystemOriginalStore:
    """Content-addressed, tenant-partitioned, encrypted-at-rest original store on ``root``."""

    def __init__(self, root: Path, cipher: Cipher) -> None:
        self._root = Path(root)
        self._cipher = cipher

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> FilesystemOriginalStore:
        """Build from the environment: ``root`` = ``$APX_DATA_PATH/originals`` — the durable,
        volume-encrypted tenant data volume, which **production MUST set** (AC1 durability + AD-31).
        If ``APX_DATA_PATH`` is unset it falls back to the host temp dir — a non-durable last resort
        for local/dev only (NOT the API's ``_data_volume_path`` resolution). The cipher comes from
        ``$APX_ENCRYPTION_KEY`` (fail-closed if unusable — AD-31)."""
        source = os.environ if env is None else env
        base = (source.get("APX_DATA_PATH", "") or "").strip() or tempfile.gettempdir()
        return cls(Path(base) / "originals", Cipher.from_env(source))

    def _blob_path(self, tenant: str, content_hash: str, kind: str) -> Path:
        """The blob path. ``content_hash`` is validated as a sha256 hex digest and ``kind`` as a
        plain token (the traversal guard on the file name); the ``tenant`` is HASHED into its
        directory segment, so ANY tenant string — a real firm slug like ``cabinet.fr`` or
        ``étude-müller`` — yields a safe segment that cannot escape ``root`` (the raw tenant still
        binds the AAD, so isolation is not weakened). The ``original`` kind is the bare hash; a
        derived kind (``ocr-layout``) is a ``.kind`` sibling."""
        if not _HEX64.fullmatch(content_hash):
            raise ValueError("content_hash must be a sha256 hex digest")
        if not tenant:
            raise ValueError("tenant must be non-empty")
        if not _SAFE_KIND.fullmatch(kind):
            raise ValueError("kind must be a plain token")
        tenant_dir = hashlib.sha256(tenant.encode("utf-8")).hexdigest()
        base = self._root / tenant_dir / content_hash[:2] / content_hash
        return base if kind == "original" else base.with_name(f"{content_hash}.{kind}")

    def put(self, tenant: str, content_hash: str, data: bytes, kind: str = "original") -> None:
        path = self._blob_path(tenant, content_hash, kind)
        if path.exists():
            return  # content-addressed: identical bytes are stored once (idempotent)
        path.parent.mkdir(parents=True, exist_ok=True)
        token = self._cipher.encrypt_bytes(data, aad=_aad(tenant, content_hash, kind))
        # Atomic publish: write a temp sibling, fsync, then rename onto the final name — a crash
        # mid-write leaves a stray temp file, never a half-written blob read as whole.
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-", suffix=".blob")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(token)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)
        except BaseException:
            with contextlib.suppress(OSError):
                os.unlink(tmp)  # a failed cleanup must not mask the real error
            raise
        # fsync the directory so the rename ITSELF is durable — a power-loss right after os.replace
        # must not lose the blob while the DB pièce persists (best-effort: some FS/platforms refuse
        # a directory fsync, which is not a write failure).
        with contextlib.suppress(OSError):
            dir_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)

    def open(self, tenant: str, content_hash: str, kind: str = "original") -> bytes:
        """The decrypted bytes for ``kind``. Fail-closed: a missing blob raises
        ``FileNotFoundError`` and a tampered/relocated/wrong-kind blob raises ``DecryptionError``
        (the AAD/tag never authenticates)."""
        token = self._blob_path(tenant, content_hash, kind).read_bytes()
        return self._cipher.decrypt_bytes(token, aad=_aad(tenant, content_hash, kind))

    def size(self, tenant: str, content_hash: str, kind: str = "original") -> int | None:
        """The retained blob's PLAINTEXT byte size, or ``None`` if absent (Story 3.5b — the viewer's
        render-bound decision). Derived from the on-disk token size minus the fixed cipher overhead
        (prefix + nonce + GCM tag; the AAD is authenticated, not stored) — no decryption, so it is
        cheap even for a large blob."""
        path = self._blob_path(tenant, content_hash, kind)
        if not path.exists():
            return None
        overhead = len(self._cipher.encrypt_bytes(b""))  # constant: prefix + nonce + tag
        return max(0, path.stat().st_size - overhead)
