"""Owned auth primitives: salted scrypt hashing and signed session tokens."""

from __future__ import annotations

from apx.core.domain.auth import hash_password, sign_token, verify_password, verify_token


def test_password_round_trip() -> None:
    h = hash_password("s3cret!")
    assert verify_password("s3cret!", h)
    assert not verify_password("wrong", h)


def test_hash_is_salted_and_self_describing() -> None:
    a, b = hash_password("same"), hash_password("same")
    assert a != b and a.startswith("scrypt$")  # random per-password salt
    assert verify_password("same", a) and verify_password("same", b)


def test_verify_rejects_garbage() -> None:
    assert not verify_password("x", "not-a-hash")
    assert not verify_password("x", "scrypt$bad")


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
