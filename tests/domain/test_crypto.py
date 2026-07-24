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
    key_fingerprint,
    load_key_from_env,
    load_keys_from_env,
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


def test_associated_data_binds_the_ciphertext_to_its_context() -> None:
    # a value encrypted under one AAD (its column identity) will not decrypt under another — so a
    # ciphertext cannot be relocated from one column/table into another and silently decrypt.
    c = Cipher(_key())
    token = c.encrypt("secret", aad="piece.provenance_path")
    assert c.decrypt(token, aad="piece.provenance_path") == "secret"  # right context
    with pytest.raises(DecryptionError):
        c.decrypt(token, aad="piece.custodian")  # relocated to another column
    with pytest.raises(DecryptionError):
        c.decrypt(token)  # no context at all


def test_an_all_zero_key_is_rejected() -> None:
    import base64
    with pytest.raises(MissingEncryptionKey):
        load_key_from_env({"APX_ENCRYPTION_KEY": base64.urlsafe_b64encode(bytes(32)).decode()})


# ── key rotation (story 1.8, AD-47): a multi-key cipher — encrypt with the primary, decrypt
# with primary-or-previous, so a value under an old key still reads during the transition ──


def test_a_previous_key_still_decrypts_during_rotation() -> None:
    old, new = _key(), _key()
    old_token = Cipher(old).encrypt("secret professionnel", aad="c")
    rotating = Cipher([new, old])  # new is primary, old is the previous key
    assert rotating.decrypt(old_token, aad="c") == "secret professionnel"  # old still reads
    new_token = rotating.encrypt("secret professionnel", aad="c")
    assert Cipher(new).decrypt(new_token, aad="c") == "secret professionnel"  # new writes primary
    with pytest.raises(DecryptionError):
        Cipher(new).decrypt(old_token, aad="c")  # the new key ALONE cannot read the old value


def test_encrypt_uses_the_primary_key() -> None:
    primary, previous = _key(), _key()
    token = Cipher([primary, previous]).encrypt("x", aad="c")
    assert Cipher(primary).decrypt(token, aad="c") == "x"  # readable by the primary alone


def test_load_keys_from_env_orders_primary_then_previous() -> None:
    primary, old1, old2 = generate_key(), generate_key(), generate_key()
    keys = load_keys_from_env(
        {"APX_ENCRYPTION_KEY": primary, "APX_ENCRYPTION_KEYS_OLD": f"{old1}, {old2}"}
    )
    assert len(keys) == 3
    assert keys[0] == base64.urlsafe_b64decode(primary)  # primary first — the one that encrypts


def test_load_keys_from_env_needs_only_the_primary() -> None:
    keys = load_keys_from_env({"APX_ENCRYPTION_KEY": generate_key()})  # no previous keys
    assert len(keys) == 1


def test_key_fingerprint_names_the_key_without_revealing_it() -> None:
    key = _key()
    fp = key_fingerprint(key)
    assert len(fp) == 12 and fp == key_fingerprint(key)      # stable
    assert fp != key_fingerprint(_key())                     # distinguishes keys
    assert key.hex() != fp and fp in key_fingerprint(key)    # one-way, not the key itself


def test_a_truncated_ciphertext_fails_closed_not_with_a_bare_valueerror() -> None:
    # a blob too short to hold a nonce makes AESGCM raise ValueError, not InvalidTag; decrypt
    # must map it to DecryptionError (the multi-key loop must catch BOTH) — else read_audit's
    # graceful-degrade path (which catches only DecryptionError) crashes the whole trail (FR-24).
    truncated = "apxenc:v1:" + base64.urlsafe_b64encode(b"AAAA").decode()
    with pytest.raises(DecryptionError):
        Cipher(_key()).decrypt(truncated, aad="c")


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
