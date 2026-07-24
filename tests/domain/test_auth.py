"""Owned auth primitives: salted Argon2id hashing (with legacy-scrypt upgrade) and tokens."""

from __future__ import annotations

import hashlib

from apx.core.domain.auth import (
    hash_password,
    sign_token,
    verify_and_upgrade,
    verify_password,
    verify_token,
)


def _legacy_scrypt(password: str, salt: bytes = b"0123456789abcdef") -> str:
    """A pre-AD-15 scrypt hash, to exercise the upgrade-on-verify path."""
    dk = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32,
                        maxmem=64 * 1024 * 1024)
    return f"scrypt$16384$8$1${salt.hex()}${dk.hex()}"


def test_password_round_trip() -> None:
    h = hash_password("s3cret!")
    assert verify_password("s3cret!", h)
    assert not verify_password("wrong", h)


def test_hash_is_salted_and_argon2id() -> None:
    a, b = hash_password("same"), hash_password("same")
    assert a != b and a.startswith("$argon2id$")  # random per-credential salt, Argon2id
    assert verify_password("same", a) and verify_password("same", b)


def test_verify_rejects_garbage() -> None:
    assert not verify_password("x", "not-a-hash")
    assert not verify_password("x", "scrypt$bad")
    assert not verify_password("x", "$argon2id$garbage")


def test_legacy_scrypt_verifies_and_upgrades_to_argon2id() -> None:
    legacy = _legacy_scrypt("s3cret!")
    assert verify_password("s3cret!", legacy)  # a pre-AD-15 hash still logs in
    ok, upgraded = verify_and_upgrade("s3cret!", legacy)
    assert ok and upgraded is not None and upgraded.startswith("$argon2id$")
    assert verify_password("s3cret!", upgraded)  # the upgraded hash works
    # a wrong password neither verifies nor upgrades
    bad_ok, bad_upgraded = verify_and_upgrade("wrong", legacy)
    assert not bad_ok and bad_upgraded is None


def test_argon2id_hash_needs_no_upgrade() -> None:
    ok, upgraded = verify_and_upgrade("s3cret!", hash_password("s3cret!"))
    assert ok and upgraded is None  # already Argon2id at current params


def test_token_sign_and_verify() -> None:
    tok = sign_token("secret", {"user_id": "u1", "tenant": "t"}, now=1000)
    claims = verify_token("secret", tok, now=1000)
    assert claims is not None and claims["user_id"] == "u1" and claims["tenant"] == "t"


def test_token_tamper_and_wrong_key_are_rejected() -> None:
    tok = sign_token("secret", {"user_id": "u1"}, now=1000)
    sig = tok.split(".")[1]
    forged_body = sign_token("secret", {"user_id": "admin"}, now=1000).split(".")[0]
    assert verify_token("secret", f"{forged_body}.{sig}", now=1000) is None  # body swapped
    assert verify_token("wrong-secret", tok, now=1000) is None               # wrong key


def test_token_expiry() -> None:
    tok = sign_token("secret", {"user_id": "u1"}, now=1000, ttl_seconds=100)
    assert verify_token("secret", tok, now=1050) is not None  # within ttl
    assert verify_token("secret", tok, now=1101) is None      # expired
