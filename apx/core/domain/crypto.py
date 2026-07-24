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
import os
from collections.abc import Mapping

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_PREFIX = "apxenc:v1:"
_NONCE_BYTES = 12  # 96-bit nonce, the AES-GCM standard
KEY_BYTES = 32     # AES-256
_ENV_KEY = "APX_ENCRYPTION_KEY"


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


class Cipher:
    """AES-256-GCM over strings. One instance holds one key; construct from raw bytes, or
    :meth:`from_env` to read the configured key."""

    def __init__(self, key: bytes) -> None:
        if len(key) != KEY_BYTES:
            raise MissingEncryptionKey(f"key must be {KEY_BYTES} bytes, got {len(key)}")
        self._aead = AESGCM(key)

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Cipher:
        return cls(load_key_from_env(env))

    def encrypt(self, plaintext: str, aad: str | None = None) -> str:
        """Encrypt, binding ``aad`` (associated data) into the authentication tag. A value
        encrypted under one ``aad`` will not decrypt under another — so a ciphertext bound to
        one column/table cannot be relocated into another and silently decrypt (the AAD is the
        column identity, so a stolen-disk / DB-write attacker cannot shuffle ciphertexts across
        columns)."""
        nonce = os.urandom(_NONCE_BYTES)
        extra = aad.encode("utf-8") if aad else None
        blob = nonce + self._aead.encrypt(nonce, plaintext.encode("utf-8"), extra)
        return _PREFIX + base64.urlsafe_b64encode(blob).decode("ascii")

    def decrypt(self, token: str, aad: str | None = None) -> str:
        """Decrypt and authenticate. Fails closed (``DecryptionError``) on a wrong key, a
        tamper, a truncation, a plaintext value, OR an ``aad`` that does not match the one the
        value was encrypted under (a relocated ciphertext)."""
        if not is_ciphertext(token):
            # A plaintext value in an encrypted column — surface it, never accept it.
            raise DecryptionError("value is not an apxenc ciphertext token")
        try:
            blob = base64.urlsafe_b64decode(token[len(_PREFIX):])
            nonce, ct = blob[:_NONCE_BYTES], blob[_NONCE_BYTES:]
            extra = aad.encode("utf-8") if aad else None
            return self._aead.decrypt(nonce, ct, extra).decode("utf-8")
        except (InvalidTag, ValueError) as exc:
            raise DecryptionError("ciphertext failed authentication") from exc
