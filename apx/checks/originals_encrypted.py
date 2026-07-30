"""Retained-original encryption-at-rest structural property (Story 3.5a; AD-31, AD-33).

The pièce viewer keeps every pièce's ORIGINAL bytes at rest so it can render them. Those blobs are
content — not the searchable ``full_text`` index — so the AD-31 default applies: they are
**application-encrypted** before they touch disk. One check with two legs, mirroring
``encryption.startup_gate_is_fail_closed``:

- **static:** the filesystem original store's ``put`` calls ``encrypt_bytes`` and never writes the
  raw ``data`` parameter to disk (a plaintext write is the failure this bars). AST-sniffable — and,
  like any AST leg, gameable by aliasing, which is why the second leg exists.
- **behavioural (real runs only; harder to game than the static leg):** execute a real
  ``FilesystemOriginalStore``, ``put`` a known plaintext, and assert the plaintext appears in NO
  file under the store root (a sidecar/aliased-write leak is caught, not just a literal
  ``write(data)``), does NOT decrypt under a wrong key, and DOES round-trip under the right one.

Fails closed on an unparseable file.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path

from apx.checks.import_contracts import CheckResult
from apx.checks.payload_schema import _fail_closed, _load_trees

_APX_ROOT = Path(__file__).resolve().parent.parent
_STORE_FILE = _APX_ROOT / "adapters" / "originals_fs" / "store.py"
_WRITE_ATTRS = {"write", "write_bytes"}  # a disk write of the raw param is the barred leak


def _put_method(trees: Iterable[tuple[Path, ast.Module]]) -> ast.FunctionDef | None:
    for _path, tree in trees:
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "put":
                return node
    return None


def _writes_raw_param(put: ast.FunctionDef, param: str = "data") -> bool:
    """True if ``put`` writes the raw plaintext parameter to disk — ``f.write(data)`` /
    ``path.write_bytes(data)`` — the exact leak the encrypt-before-write rule bars."""
    for node in ast.walk(put):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr in _WRITE_ATTRS):
            for arg in node.args:
                if isinstance(arg, ast.Name) and arg.id == param:
                    return True
    return False


def _calls_encrypt_bytes(put: ast.FunctionDef) -> bool:
    return any(
        isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        and node.func.attr == "encrypt_bytes"
        for node in ast.walk(put))


def _blob_is_ciphertext_at_rest() -> str | None:
    """Execute the REAL store: a put'd plaintext must appear as ciphertext on disk and NOWHERE in
    the clear, must not decrypt under a wrong key, and must round-trip under the right one. Returns
    an error string on the first failure, else None. Harder to game than the static leg — an
    adapter that skips encryption, or writes a plaintext sidecar via an alias, is caught here
    because the whole store root is swept, not just the canonical blob path."""
    import hashlib
    import os
    import tempfile

    from apx.adapters.originals_fs import FilesystemOriginalStore
    from apx.core.domain.crypto import Cipher, DecryptionError

    root = Path(tempfile.mkdtemp(prefix="apx-orig-gate-"))
    store = FilesystemOriginalStore(root, Cipher(os.urandom(32)))
    plaintext = b"APX-ORIGINAL-AT-REST-PROBE-\x00\x01\x02-confidential-bytes"
    ch = hashlib.sha256(plaintext).hexdigest()
    store.put("probe", ch, plaintext)

    # the plaintext must appear in NO file under the root — not only the canonical blob — so a store
    # that also drops a plaintext sidecar, or writes through an alias, is caught (not just the
    # literal `write(data)` the static leg sees).
    for f in root.rglob("*"):
        if f.is_file() and plaintext in f.read_bytes():
            return f"a plaintext original was found on disk ({f.name}) — not encrypted (AD-31)"
    # a wrong key must not decrypt the retained original (authenticated encryption, not obfuscation)
    try:
        FilesystemOriginalStore(root, Cipher(os.urandom(32))).open("probe", ch)
        return "the retained original decrypted under a WRONG key — not authenticated (AD-31)"
    except DecryptionError:
        pass  # good — a wrong key fails closed
    if store.open("probe", ch) != plaintext:
        return "the retained original did not round-trip under the right key"
    return None


def originals_are_encrypted_at_rest(roots: Iterable[Path] | None = None) -> CheckResult:
    """The filesystem original store encrypts before writing (static) and, on the real store,
    provably leaves ciphertext at rest (behavioural)."""
    name, ad = "retained originals are encrypted at rest", "AD-31"
    is_real = roots is None
    roots = list(roots) if roots is not None else [_STORE_FILE]
    trees, unparseable = _load_trees(roots)
    if unparseable:
        return _fail_closed(name, ad, unparseable)

    put = _put_method(trees)
    if put is None:
        return CheckResult(name, ad, False,
                           "no put() found in the original store — cannot verify encrypt-at-rest")
    if not _calls_encrypt_bytes(put):
        return CheckResult(name, ad, False,
                           "the original store's put() does not call encrypt_bytes — a retained "
                           "original must be application-encrypted before it touches disk (AD-31)")
    if _writes_raw_param(put):
        return CheckResult(name, ad, False,
                           "the original store's put() writes the raw plaintext `data` to disk — "
                           "the original must be encrypted first (AD-31)")
    if is_real:  # the ungameable leg: prove the on-disk blob is ciphertext
        problem = _blob_is_ciphertext_at_rest()
        if problem is not None:
            return CheckResult(name, ad, False, problem)
    return CheckResult(name, ad, True,
                       "the retained-original store encrypts before writing and leaves ciphertext "
                       "at rest (a wrong key never decrypts it)")


def run() -> list[CheckResult]:
    return [originals_are_encrypted_at_rest()]
