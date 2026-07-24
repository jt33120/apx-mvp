"""Credential-storage structural properties (story 1.5; AD-15, FR-56). Two static checks:

- **no_reversible_credential_storage:** no model column holds a plaintext/reversible
  credential — passwords live only as a one-way Argon2id hash (`password_hash`). A plaintext
  `password` column is the classic breach; this fails the build on it. (A TOTP `mfa_secret`
  is a *shared* secret by construction, not a reversible password store, so it is permitted.)
- **jwt_decode_pins_algorithms (AD-15):** every `jwt.decode` passes a **literal**
  `algorithms=[...]` list (never inferred from the token header), and `PyJWK`/`PyJWKClient`/
  `jwks` appear in no runtime module. User sessions use no JWT (opaque server-side, AD-15),
  so this passes vacuously today and is ready when internal service tokens land.

Both fail closed on an unparseable file and carry failure fixtures.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path

from sqlalchemy import MetaData

from apx.checks.import_contracts import CheckResult
from apx.checks.payload_schema import _fail_closed, _load_trees
from apx.checks.tenant_isolation import _base_metadata

_APX_ROOT = Path(__file__).resolve().parent.parent

# Column names that would mean a password/credential is stored in the clear.
_PLAINTEXT_CREDENTIAL_NAMES = {
    "password", "passwd", "pwd", "password_plain", "plaintext_password", "secret_plain",
}
_FORBIDDEN_JWT_NAMES = {"PyJWK", "PyJWKClient", "jwks"}


def no_reversible_credential_storage(metadata: MetaData | None = None) -> CheckResult:
    """No model column stores a plaintext/reversible credential (FR-56/AD-15). A password is
    stored only as ``password_hash`` (one-way): any other password-ish column — ``password``,
    ``password_plain``, a reversibly-encrypted ``password_enc`` — fails the build. (Limitation,
    by design: this is a name-and-metadata check; a reversible cipher applied to a credential
    in *store code* is not caught here — the review tracks a store-AST leg as follow-up.)"""
    name, ad = "no reversible credential storage", "AD-15"
    tables = (metadata if metadata is not None else _base_metadata()).tables
    for tname, table in tables.items():
        for col in table.columns:
            low = col.name.lower()
            if "password" in low and low != "password_hash":
                return CheckResult(name, ad, False,
                                   f"{tname}.{col.name} is a non-hash password column — a "
                                   "password is stored only as password_hash (one-way, AD-15)")
            if low in _PLAINTEXT_CREDENTIAL_NAMES:
                return CheckResult(name, ad, False,
                                   f"{tname}.{col.name} looks like a plaintext credential — a "
                                   "password is stored only as a one-way hash (Argon2id, AD-15)")
    return CheckResult(name, ad, True, "credentials are stored only as a one-way hash")


def _is_jwt_decode(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "decode"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "jwt"
    )


def _has_literal_algorithms(call: ast.Call) -> bool:
    for kw in call.keywords:
        if kw.arg == "algorithms" and isinstance(kw.value, ast.List) and kw.value.elts:
            return True
    return False


def jwt_decode_pins_algorithms(roots: Iterable[Path] | None = None) -> CheckResult:
    """Every jwt.decode passes a literal algorithms=[...]; PyJWK/PyJWKClient/jwks are absent
    from runtime (AD-15). Passes vacuously today (no user-session JWT)."""
    name, ad = "jwt.decode pins an explicit algorithm list", "AD-15"
    roots = list(roots) if roots is not None else [_APX_ROOT]
    trees, unparseable = _load_trees(roots)
    if unparseable:
        return _fail_closed(name, ad, unparseable)
    for path, tree in trees:
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id in _FORBIDDEN_JWT_NAMES:
                return CheckResult(name, ad, False,
                                   f"{path.name}: {node.id} is forbidden (AD-15 — no JWK/JWKS)")
            if isinstance(node, ast.Attribute) and node.attr in _FORBIDDEN_JWT_NAMES:
                return CheckResult(name, ad, False,
                                   f"{path.name}: {node.attr} is forbidden (AD-15 — no JWK/JWKS)")
            if _is_jwt_decode(node):
                assert isinstance(node, ast.Call)
                if not _has_literal_algorithms(node):
                    return CheckResult(
                        name, ad, False,
                        f"{path.name}: jwt.decode with no literal algorithms=[...] "
                        "(AD-15 — the algorithm is never inferred from the token)")
    return CheckResult(name, ad, True, "every jwt.decode pins an explicit algorithm list")


def run() -> list[CheckResult]:
    return [no_reversible_credential_storage(), jwt_decode_pins_algorithms()]
