"""Owned authentication primitives — no hosted identity, no third-party library.

The product runs on one machine in a firm, offline (AD-15): auth cannot depend on a
cloud identity service, and the security core stays vendor-free. Passwords are hashed
with scrypt (a memory-hard KDF from the standard library — no dependency), each with
its own random salt; sessions are stateless signed tokens (HMAC-SHA256 over a
locally-held secret). Both are pure functions here — the clock and the secret are
passed in, so they test without I/O — and the whole module imports only the standard
library, so the egress guard has nothing to forbid.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os

# Interactive scrypt parameters (~16 MiB); tune up as hardware allows.
_N, _R, _P = 2**14, 8, 1
_MAXMEM = 64 * 1024 * 1024


def hash_password(password: str, *, salt: bytes | None = None) -> str:
    """A self-describing scrypt hash: ``scrypt$N$r$p$salt_hex$hash_hex``. A random
    per-password salt unless one is given (given only for tests)."""
    salt = os.urandom(16) if salt is None else salt
    dk = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=32, maxmem=_MAXMEM)
    return f"scrypt${_N}${_R}${_P}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Constant-time check of ``password`` against a stored scrypt hash."""
    try:
        algo, n, r, p, salt_hex, hash_hex = stored.split("$")
        if algo != "scrypt":
            return False
        expected = bytes.fromhex(hash_hex)
        dk = hashlib.scrypt(
            password.encode(), salt=bytes.fromhex(salt_hex),
            n=int(n), r=int(r), p=int(p), dklen=len(expected), maxmem=_MAXMEM,
        )
        return hmac.compare_digest(dk, expected)
    except (ValueError, TypeError):
        return False


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def sign_token(secret: str, claims: dict, *, now: int, ttl_seconds: int = 8 * 3600) -> str:
    """A stateless session token: base64(claims incl. exp) + '.' + HMAC-SHA256. The
    clock (``now``, epoch seconds) is passed in so signing is a pure function."""
    body = {**claims, "exp": now + ttl_seconds}
    payload = _b64(json.dumps(body, sort_keys=True, separators=(",", ":")).encode())
    sig = hmac.new(secret.encode(), payload.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


def verify_token(secret: str, token: str, *, now: int) -> dict | None:
    """Return the claims if the signature is valid and the token is unexpired, else
    None. Signature checked in constant time; a tampered or stale token returns None."""
    try:
        payload, sig = token.split(".")
        expected = hmac.new(secret.encode(), payload.encode("ascii"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        claims = json.loads(_unb64(payload))
        if int(claims.get("exp", 0)) < now:
            return None
        return claims
    except (ValueError, TypeError):
        return None
