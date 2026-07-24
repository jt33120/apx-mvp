"""Owned authentication primitives — Argon2id (AD-15), no hosted identity.

The product runs on one machine in a firm, offline (AD-15): auth cannot depend on a cloud
identity service. Passwords are hashed with **Argon2id via `pwdlib[argon2]`** — a memory-hard
KDF, each with its own salt, in a self-describing PHC string (``$argon2id$…``). Legacy scrypt
hashes from before the AD-15 migration still *verify*, and ``verify_and_upgrade`` re-hashes
them to Argon2id on the next successful login (upgrade-on-verify), so nothing locks out;
scrypt is never used to hash a new or changed password. The module imports only ``pwdlib``
and the standard library, so the egress guard has nothing to forbid.

``sign_token``/``verify_token`` remain for now as a stateless-HMAC primitive; user *sessions*
move to opaque server-side rows in this story's later tasks (AD-15 forbids a stateless token
for user sessions), and these are kept only should an internal service-token need arise.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json

from pwdlib import PasswordHash

_hasher = PasswordHash.recommended()  # Argon2id

# Legacy scrypt parameters (pre-AD-15). Kept ONLY to verify existing hashes and upgrade
# them to Argon2id — never to hash a new or changed password.
_SCRYPT_N, _SCRYPT_R, _SCRYPT_P = 2**14, 8, 1
_SCRYPT_MAXMEM = 64 * 1024 * 1024


def hash_password(password: str) -> str:
    """A self-describing Argon2id hash (PHC string, ``$argon2id$…``), with a random
    per-credential salt (pwdlib)."""
    return _hasher.hash(password)


def _verify_scrypt(password: str, stored: str) -> bool:
    """Constant-time check against a LEGACY scrypt hash (``scrypt$N$r$p$salt$hash``)."""
    try:
        algo, n, r, p, salt_hex, hash_hex = stored.split("$")
        if algo != "scrypt":
            return False
        expected = bytes.fromhex(hash_hex)
        dk = hashlib.scrypt(
            password.encode(), salt=bytes.fromhex(salt_hex),
            n=int(n), r=int(r), p=int(p), dklen=len(expected), maxmem=_SCRYPT_MAXMEM,
        )
        return hmac.compare_digest(dk, expected)
    except (ValueError, TypeError):
        return False


def verify_password(password: str, stored: str) -> bool:
    """True iff ``password`` matches ``stored`` — an Argon2id hash (pwdlib) or a legacy
    scrypt hash. Constant-time within each scheme; a malformed hash is a non-match."""
    if stored.startswith("scrypt$"):
        return _verify_scrypt(password, stored)
    try:
        return _hasher.verify(password, stored)
    except Exception:  # noqa: BLE001 — an unknown/garbage hash is a non-match, never a crash
        return False


def verify_and_upgrade(password: str, stored: str) -> tuple[bool, str | None]:
    """Verify, returning ``(ok, new_hash)``. ``new_hash`` is a fresh Argon2id hash when the
    stored hash should be upgraded — a legacy scrypt hash, or Argon2id parameters that have
    since moved — otherwise ``None``. The caller persists ``new_hash`` on a successful
    login (upgrade-on-verify)."""
    if stored.startswith("scrypt$"):
        if _verify_scrypt(password, stored):
            return True, _hasher.hash(password)  # migrate scrypt -> Argon2id
        return False, None
    try:
        return _hasher.verify_and_update(password, stored)
    except Exception:  # noqa: BLE001
        return False, None


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def sign_token(secret: str, claims: dict, *, now: int, ttl_seconds: int = 8 * 3600) -> str:
    """A stateless HMAC-SHA256 token (base64(claims incl. exp) + '.' + sig). Retained for a
    possible internal service token; **not** for user sessions (AD-15 — those are server-side)."""
    body = {**claims, "exp": now + ttl_seconds}
    payload = _b64(json.dumps(body, sort_keys=True, separators=(",", ":")).encode())
    sig = hmac.new(secret.encode(), payload.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


def verify_token(secret: str, token: str, *, now: int) -> dict | None:
    """Return the claims if the signature is valid and the token is unexpired, else None.
    Signature checked in constant time; a tampered or stale token returns None."""
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
