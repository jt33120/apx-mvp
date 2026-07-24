"""Owned authentication primitives — Argon2id (AD-15), no hosted identity.

The product runs on one machine in a firm, offline (AD-15): auth cannot depend on a cloud
identity service. Passwords are hashed with **Argon2id via `pwdlib[argon2]`** — a memory-hard
KDF, each with its own salt, in a self-describing PHC string (``$argon2id$…``). Legacy scrypt
hashes from before the AD-15 migration still *verify*, and ``verify_and_upgrade`` re-hashes
them to Argon2id on the next successful login (upgrade-on-verify), so nothing locks out;
scrypt is never used to hash a new or changed password. The module imports only ``pwdlib``
and the standard library, so the egress guard has nothing to forbid. User *sessions* are
opaque server-side rows (AD-15 forbids a stateless token for user sessions) — there is no
stateless-token primitive here to be misused for one.
"""

from __future__ import annotations

import hashlib
import hmac

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
