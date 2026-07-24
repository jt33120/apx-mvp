"""Application-layer encryption at rest (story 1.7, AD-31).

AES-256-GCM behind a tiny, misuse-resistant surface: a 32-byte key, a fresh random
96-bit nonce per value, and an authenticated ciphertext that ``decrypt`` verifies —
tampering, a truncation or the wrong key all fail closed (raise), never return garbage.

The token is ``apxenc:v1:`` + urlsafe-base64(nonce ‖ ciphertext‖tag). The prefix lets a
reader tell ciphertext from plaintext without a key, so a plaintext value that reaches an
encrypted column is a *loud* error (``decrypt`` refuses it) rather than a silent leak —
which is the whole point of this story.

The key is read from the environment (``APX_ENCRYPTION_KEY``), never from source (AD-47);
absence or a malformed value fails closed. ``cryptography`` is a LOCAL crypto library, not
a hosted-provider SDK, so it is untouched by the egress deny-list (AD-45) — the same
standing as ``pwdlib`` in :mod:`apx.core.domain.auth`. Key *rotation* is story 1.8.
"""

from __future__ import annotations

import base64
import hashlib
import os
from collections.abc import Mapping

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_PREFIX = "apxenc:v1:"
_NONCE_BYTES = 12  # 96-bit nonce, the AES-GCM standard
KEY_BYTES = 32     # AES-256
_ENV_KEY = "APX_ENCRYPTION_KEY"          # the PRIMARY key — used to encrypt
_ENV_KEYS_OLD = "APX_ENCRYPTION_KEYS_OLD"  # comma-separated PREVIOUS keys — decrypt-only


class MissingEncryptionKey(RuntimeError):
    """The application encryption key is absent or unusable — start-up must fail closed."""


class DecryptionError(ValueError):
    """A value could not be authenticated and decrypted: tampered, truncated, wrong key, or
    a plaintext value in an encrypted column. Fail closed — never a silent fallback."""


def is_ciphertext(value: str) -> bool:
    """True if ``value`` is one of our tokens (carries the versioned prefix)."""
    return isinstance(value, str) and value.startswith(_PREFIX)


def generate_key() -> str:
    """A fresh urlsafe-base64 AES-256 key, for provisioning and tests. Never committed."""
    return base64.urlsafe_b64encode(os.urandom(KEY_BYTES)).decode("ascii")


def _decode_key(raw: str) -> bytes:
    """Decode a configured key (urlsafe-base64, standard-base64, or hex) to 32 bytes.
    Raises :class:`MissingEncryptionKey` on anything that is not exactly 32 bytes, or on an
    all-zero key (the classic placeholder — a real key is never all zeros)."""
    raw = raw.strip()
    if not raw:
        raise MissingEncryptionKey(f"{_ENV_KEY} is empty")
    for decode in (
        lambda s: base64.urlsafe_b64decode(_pad(s)),
        lambda s: base64.b64decode(_pad(s)),
        bytes.fromhex,
    ):
        try:
            key = decode(raw)
        except (ValueError, TypeError):
            continue
        if len(key) == KEY_BYTES:
            if key == bytes(KEY_BYTES):
                raise MissingEncryptionKey(
                    f"{_ENV_KEY} is all-zero — that is a placeholder, not a real key")
            return key
    raise MissingEncryptionKey(
        f"{_ENV_KEY} must decode (base64 or hex) to exactly {KEY_BYTES} bytes"
    )


def _pad(s: str) -> str:
    """Restore base64 padding a key may have been stored without."""
    return s + "=" * (-len(s) % 4)


def load_key_from_env(env: Mapping[str, str] | None = None) -> bytes:
    """The 32-byte key from ``APX_ENCRYPTION_KEY``. Fails closed (``MissingEncryptionKey``)
    when unset, empty or not decoding to 32 bytes — the start-up gate turns this into a
    refusal to boot (AD-31)."""
    source = os.environ if env is None else env
    raw = source.get(_ENV_KEY)
    if raw is None:
        raise MissingEncryptionKey(f"{_ENV_KEY} is not set")
    return _decode_key(raw)


def load_keys_from_env(env: Mapping[str, str] | None = None) -> list[bytes]:
    """The ordered key set — the PRIMARY key first (``APX_ENCRYPTION_KEY``, required), then any
    PREVIOUS keys (``APX_ENCRYPTION_KEYS_OLD``, comma-separated). Encryption always uses the
    primary; decryption tries the primary then each previous — so during a rotation a value
    still under an old key reads until the re-key pass rewrites it. Fails closed if the primary
    is absent/unusable (AD-47/AD-31)."""
    source = os.environ if env is None else env
    keys = [load_key_from_env(source)]  # primary — required
    for piece in source.get(_ENV_KEYS_OLD, "").split(","):
        piece = piece.strip()
        if piece:
            keys.append(_decode_key(piece))
    return keys


def key_fingerprint(key: bytes) -> str:
    """A short, one-way fingerprint of a key — names it in the audit (which key rotated, when)
    without ever holding the key value itself (AD-47: rotation recorded, never the secret)."""
    return hashlib.sha256(key).hexdigest()[:12]


class Cipher:
    """AES-256-GCM over strings. Holds an ordered key set (primary first): ``encrypt`` uses the
    primary; ``decrypt`` tries every key so a value written under a previous key still reads
    during a rotation. Construct from raw key bytes, a list of keys, or :meth:`from_env`."""

    def __init__(self, keys: bytes | list[bytes]) -> None:
        key_list = [keys] if isinstance(keys, (bytes, bytearray)) else list(keys)
        if not key_list:
            raise MissingEncryptionKey("at least one key is required")
        for k in key_list:
            if len(k) != KEY_BYTES:
                raise MissingEncryptionKey(f"key must be {KEY_BYTES} bytes, got {len(k)}")
        self._aeads = [AESGCM(k) for k in key_list]  # primary first

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Cipher:
        return cls(load_keys_from_env(env))

    def encrypt(self, plaintext: str, aad: str | None = None) -> str:
        """Encrypt under the PRIMARY key, binding ``aad`` (associated data) into the auth tag. A
        value encrypted under one ``aad`` will not decrypt under another — so a ciphertext bound
        to one column/table cannot be relocated into another and silently decrypt (the AAD is
        the column identity, so a stolen-disk / DB-write attacker cannot shuffle ciphertexts)."""
        nonce = os.urandom(_NONCE_BYTES)
        extra = aad.encode("utf-8") if aad else None
        blob = nonce + self._aeads[0].encrypt(nonce, plaintext.encode("utf-8"), extra)
        return _PREFIX + base64.urlsafe_b64encode(blob).decode("ascii")

    def decrypt(self, token: str, aad: str | None = None) -> str:
        """Decrypt and authenticate, trying the primary then each previous key. Fails closed
        (``DecryptionError``) when NO key matches — a wrong key, a tamper, a truncation, a
        plaintext value, or an ``aad`` that does not match the one the value was encrypted
        under (a relocated ciphertext)."""
        if not is_ciphertext(token):
            # A plaintext value in an encrypted column — surface it, never accept it.
            raise DecryptionError("value is not an apxenc ciphertext token")
        try:
            blob = base64.urlsafe_b64decode(token[len(_PREFIX):])
        except (ValueError, TypeError) as exc:
            raise DecryptionError("malformed ciphertext token") from exc
        nonce, ct = blob[:_NONCE_BYTES], blob[_NONCE_BYTES:]
        extra = aad.encode("utf-8") if aad else None
        for aead in self._aeads:
            try:
                return aead.decrypt(nonce, ct, extra).decode("utf-8")
            except (InvalidTag, ValueError):
                # InvalidTag: wrong key / tamper — try the next (previous) key during a rotation.
                # ValueError: a truncated blob (a too-short nonce) — a corrupt/tampered value; it
                # will not match any key, so fail closed below rather than escaping as a bare
                # ValueError (which would crash read_audit's graceful-degrade path, FR-24).
                continue
        raise DecryptionError("ciphertext failed authentication (no configured key matched)")
