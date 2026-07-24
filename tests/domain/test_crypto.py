"""The application-layer cipher (story 1.7, AD-31): AES-256-GCM round-trips, and fails
CLOSED on tampering, the wrong key, a truncation, or a plaintext value — never a silent
fallback. Key loading from the environment fails closed on absence or a malformed value.
"""

from __future__ import annotations

import base64

import pytest

from apx.core.domain.crypto import (
    KEY_BYTES,
    Cipher,
    DecryptionError,
    MissingEncryptionKey,
    generate_key,
    is_ciphertext,
    load_key_from_env,
)


def _key() -> bytes:
    return base64.urlsafe_b64decode(generate_key())


def test_round_trip_recovers_the_plaintext() -> None:
    c = Cipher(_key())
    for text in ("", "le contrat", "accents: é à ç — ✓", "x" * 10_000):
        token = c.encrypt(text)
        assert is_ciphertext(token) and token.startswith("apxenc:v1:")
        assert c.decrypt(token) == text


def test_ciphertext_is_randomised_per_write() -> None:
    # a fresh nonce each time — the same plaintext never yields the same token (so it cannot
    # be matched/grouped in SQL, which is why encrypted columns hold content, never keys).
    c = Cipher(_key())
    assert c.encrypt("same") != c.encrypt("same")


def test_tampering_fails_closed() -> None:
    c = Cipher(_key())
    token = c.encrypt("secret professionnel")
    # flip a byte in the base64 body — authentication must reject it, not return garbage
    body = bytearray(token.encode())
    body[-2] ^= 0x01
    with pytest.raises(DecryptionError):
        c.decrypt(body.decode())


def test_the_wrong_key_fails_closed() -> None:
    token = Cipher(_key()).encrypt("cross-firm")
    with pytest.raises(DecryptionError):
        Cipher(_key()).decrypt(token)  # a different key


def test_a_plaintext_value_in_an_encrypted_column_is_a_loud_error() -> None:
    # the whole point: a value that never went through encrypt() is refused on read, so a
    # plaintext leak into an encrypted column surfaces instead of being silently accepted.
    with pytest.raises(DecryptionError):
        Cipher(_key()).decrypt("le contrat")  # no apxenc prefix
    assert not is_ciphertext("le contrat")


def test_a_short_key_is_refused() -> None:
    with pytest.raises(MissingEncryptionKey):
        Cipher(b"tooshort")


def test_load_key_from_env_reads_a_32_byte_key() -> None:
    key = generate_key()
    assert len(load_key_from_env({"APX_ENCRYPTION_KEY": key})) == KEY_BYTES
    # hex-encoded is accepted too
    hex_key = base64.urlsafe_b64decode(key).hex()
    assert len(load_key_from_env({"APX_ENCRYPTION_KEY": hex_key})) == KEY_BYTES


def test_load_key_from_env_fails_closed_on_absence_or_garbage() -> None:
    with pytest.raises(MissingEncryptionKey):
        load_key_from_env({})  # unset
    with pytest.raises(MissingEncryptionKey):
        load_key_from_env({"APX_ENCRYPTION_KEY": ""})  # empty
    with pytest.raises(MissingEncryptionKey):
        load_key_from_env({"APX_ENCRYPTION_KEY": "not-a-32-byte-key"})  # wrong length
