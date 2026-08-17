"""The filesystem retained-original store (story 3.5a; AD-31/AD-40): content-addressed,
tenant-partitioned (the tenant is HASHED into its path segment, so ANY firm slug works and none can
escape the root), encrypted at rest, fail-closed. The blob on disk is ciphertext — the whole point:
a stolen data volume yields nothing without the application key."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from apx.adapters.originals_fs import FilesystemOriginalStore
from apx.core.domain.crypto import Cipher, DecryptionError


def _data(tmp_path):  # noqa: ANN001, ANN202
    """The data volume, in its own subdirectory.

    Story 7.1: APX_INGEST_ROOT is the test's tmp_path, and a root that can reach
    $APX_DATA_PATH/originals or /spool is refused — those hold another matter's
    retained documents and another user's upload. So the data volume sits BESIDE the
    ingestable tree rather than inside it, which is also how a deployment separates them.
    """
    d = tmp_path.parent / f"{tmp_path.name}-data"
    d.mkdir(exist_ok=True)
    return d



def _store(root: Path, key: bytes | None = None) -> FilesystemOriginalStore:
    return FilesystemOriginalStore(root, Cipher(key or os.urandom(32)))


def _ch(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _blob(root: Path, tenant: str, ch: str) -> Path:
    """The blob's on-disk path — the tenant hashed into its directory segment, as the store does."""
    return root / hashlib.sha256(tenant.encode("utf-8")).hexdigest() / ch[:2] / ch


def test_put_then_open_round_trips(tmp_path: Path) -> None:
    s = _store(tmp_path)
    data = b"%PDF-1.7 ... le bail commercial ..."
    s.put("cabinet-a", _ch(data), data)
    assert s.open("cabinet-a", _ch(data)) == data


def test_a_realistic_firm_slug_is_retained(tmp_path: Path) -> None:
    # a real FR/LU tenant id (dots, accents, spaces, '&') must retain — NOT raise (the old
    # [A-Za-z0-9_-] guard broke these; the tenant is now hashed into a safe segment).
    s = _store(tmp_path)
    for tenant in ("cabinet.fr", "étude-müller", "dupont & associés"):
        data = f"acte {tenant}".encode()
        s.put(tenant, _ch(data), data)
        assert s.open(tenant, _ch(data)) == data
        assert _blob(tmp_path, tenant, _ch(data)).is_relative_to(tmp_path)  # never escapes root


def test_blob_is_ciphertext_at_rest_not_the_plaintext(tmp_path: Path) -> None:
    s = _store(tmp_path)
    data = b"CONFIDENTIEL: clause de non-concurrence"
    ch = _ch(data)
    s.put("t", ch, data)
    on_disk = _blob(tmp_path, "t", ch).read_bytes()
    assert data not in on_disk                      # the plaintext never lands on disk
    assert on_disk.startswith(b"apxenc:v1:")        # it is our encrypted token
    # a wrong key cannot read it — encryption at rest, not obfuscation
    with pytest.raises(DecryptionError):
        FilesystemOriginalStore(tmp_path, Cipher(os.urandom(32))).open("t", ch)


def test_content_addressed_dedup_is_idempotent(tmp_path: Path) -> None:
    s = _store(tmp_path)
    data = b"identical bytes"
    ch = _ch(data)
    s.put("t", ch, data)
    blob = _blob(tmp_path, "t", ch)
    first = blob.read_bytes()
    s.put("t", ch, data)                            # a second put of the same content
    assert blob.read_bytes() == first               # not rewritten (same nonce/token kept)
    assert sum(1 for _ in blob.parent.iterdir()) == 1  # exactly one blob, no temp sibling left


def test_two_tenants_with_identical_bytes_get_separate_blobs(tmp_path: Path) -> None:
    s = _store(tmp_path)
    data = b"the same file, two firms"
    ch = _ch(data)
    s.put("cabinet-a", ch, data)
    s.put("cabinet-b", ch, data)
    assert _blob(tmp_path, "cabinet-a", ch).exists()
    assert _blob(tmp_path, "cabinet-b", ch).exists()          # partitioned — distinct dirs
    assert _blob(tmp_path, "cabinet-a", ch) != _blob(tmp_path, "cabinet-b", ch)


def test_a_blob_relocated_to_another_identity_fails_to_decrypt(tmp_path: Path) -> None:
    # the AAD binds a blob to (tenant, content_hash): copying tenant-a's blob under tenant-b's path
    # does NOT let tenant-b read it — one tenant can never address another's original.
    key = os.urandom(32)
    s = _store(tmp_path, key)
    data = b"cabinet-a private"
    ch = _ch(data)
    s.put("cabinet-a", ch, data)
    dst = _blob(tmp_path, "cabinet-b", ch)
    dst.parent.mkdir(parents=True)
    dst.write_bytes(_blob(tmp_path, "cabinet-a", ch).read_bytes())  # relocate the raw blob
    with pytest.raises(DecryptionError):
        s.open("cabinet-b", ch)                     # the AAD no longer matches → fail closed


def test_aad_is_injective_even_for_a_colon_bearing_tenant(tmp_path: Path) -> None:
    # the AAD puts the fixed-length content_hash first, so no two distinct (tenant, ch) identities
    # share an AAD — even a tenant containing ':' (which the old guard forbade). A blob for one
    # identity never decrypts under another.
    s = _store(tmp_path)
    data = b"payload"
    ch = _ch(data)
    s.put("a:b", ch, data)
    assert s.open("a:b", ch) == data
    # relocate the "a:b" blob to a different tenant "a" → must not decrypt (distinct AAD)
    dst = _blob(tmp_path, "a", ch)
    dst.parent.mkdir(parents=True)
    dst.write_bytes(_blob(tmp_path, "a:b", ch).read_bytes())
    with pytest.raises(DecryptionError):
        s.open("a", ch)


def test_guard_rejects_a_non_hex_hash_and_empty_tenant_but_a_slashy_tenant_is_safe(
        tmp_path: Path) -> None:
    s = _store(tmp_path)
    with pytest.raises(ValueError):
        s.put("t", "../../etc/passwd", b"x")        # not a sha256 hex digest → rejected
    with pytest.raises(ValueError):
        s.put("", _ch(b"x"), b"x")                  # an empty tenant is a bug → rejected
    # a slashy/dotted tenant is now SAFE — it hashes to a segment that stays inside root
    s.put("../evil", _ch(b"x"), b"x")
    assert _blob(tmp_path, "../evil", _ch(b"x")).is_relative_to(tmp_path)


def test_open_fails_closed_on_a_missing_or_tampered_blob(tmp_path: Path) -> None:
    s = _store(tmp_path)
    data = b"payload"
    ch = _ch(data)
    with pytest.raises(FileNotFoundError):
        s.open("t", ch)                             # absent → fail closed
    s.put("t", ch, data)
    blob = _blob(tmp_path, "t", ch)
    raw = bytearray(blob.read_bytes())
    raw[-1] ^= 0x01                                 # flip a tag byte
    blob.write_bytes(bytes(raw))
    with pytest.raises(DecryptionError):
        s.open("t", ch)                             # tampered → fail closed


def test_empty_file_round_trips(tmp_path: Path) -> None:
    s = _store(tmp_path)
    ch = _ch(b"")
    s.put("t", ch, b"")
    assert s.open("t", ch) == b""                   # a 0-byte original is still retained, encrypted
    assert _blob(tmp_path, "t", ch).read_bytes().startswith(b"apxenc:v1:")


def test_a_kind_blob_round_trips_and_is_a_distinct_artifact(tmp_path: Path) -> None:
    # Story 3.5c-1: a second KIND (the OCR layout) shares the content_hash but is a distinct blob.
    s = _store(tmp_path)
    data, layout = b"%PDF scanned original", b'{"dpi":200,"pages":[]}'
    ch = _ch(data)
    s.put("t", ch, data)                                  # the original
    s.put("t", ch, layout, kind="ocr-layout")             # its OCR layout
    assert s.open("t", ch) == data
    assert s.open("t", ch, kind="ocr-layout") == layout
    assert _blob(tmp_path, "t", ch).exists()                                   # the original blob
    assert _blob(tmp_path, "t", ch).with_name(f"{ch}.ocr-layout").exists()     # the layout blob


def test_a_kind_blob_cannot_be_read_as_another_kind(tmp_path: Path) -> None:
    # the AAD binds the KIND: relocating the layout bytes onto the original path fails closed, so an
    # ocr-layout can never be served as the original (or vice versa).
    s = _store(tmp_path)
    ch = _ch(b"x")
    s.put("t", ch, b"the layout bytes", kind="ocr-layout")
    with pytest.raises(FileNotFoundError):
        s.open("t", ch)                                   # no original blob exists at that path
    orig = _blob(tmp_path, "t", ch)
    orig.write_bytes(orig.with_name(f"{ch}.ocr-layout").read_bytes())  # relocate the layout blob
    with pytest.raises(DecryptionError):
        s.open("t", ch)                                   # wrong-kind AAD → fail closed


def test_from_env_builds_from_data_path_and_key(tmp_path: Path) -> None:
    from apx.core.domain.crypto import generate_key
    env = {"APX_DATA_PATH": str(_data(tmp_path)), "APX_ENCRYPTION_KEY": generate_key()}
    s = FilesystemOriginalStore.from_env(env)
    data = b"env-built"
    ch = _ch(data)
    s.put("t", ch, data)
    # root is $APX_DATA_PATH/originals
    assert _blob(_data(tmp_path) / "originals", "t", ch).exists()
    assert s.open("t", ch) == data
