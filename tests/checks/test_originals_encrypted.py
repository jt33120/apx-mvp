"""The retained-original encryption-at-rest gate (story 3.5a; AD-31). The real store passes
(static + the behavioural on-disk-ciphertext leg); a store that writes the raw plaintext, or one
that never encrypts, fails; an unparseable file fails closed. Registered in CHECKS + manifest."""

from __future__ import annotations

from pathlib import Path

from apx.checks.originals_encrypted import originals_are_encrypted_at_rest


def _mod(tmp_path: Path, name: str, src: str) -> Path:
    d = tmp_path / name
    d.mkdir()
    (d / f"{name}.py").write_text(src, encoding="utf-8")
    return d


def test_the_real_original_store_passes_including_the_behavioural_leg() -> None:
    # no roots → the real store, and the ungameable leg runs: put a plaintext, prove it is
    # ciphertext on disk, undecryptable under a wrong key, round-tripping under the right one.
    r = originals_are_encrypted_at_rest()
    assert r.ok, r.detail


def test_fires_when_put_writes_the_raw_plaintext(tmp_path: Path) -> None:
    src = (
        "class S:\n"
        "    def put(self, tenant, content_hash, data):\n"
        "        token = self._cipher.encrypt_bytes(data)\n"   # calls encrypt_bytes (leg 1 passes)
        "        with open('b', 'wb') as f:\n"
        "            f.write(data)\n"                            # but writes the RAW plaintext
    )
    r = originals_are_encrypted_at_rest([_mod(tmp_path, "leaky", src)])
    assert not r.ok and "raw plaintext" in r.detail


def test_fires_when_put_never_encrypts(tmp_path: Path) -> None:
    src = (
        "class S:\n"
        "    def put(self, tenant, content_hash, data):\n"
        "        with open('b', 'wb') as f:\n"
        "            f.write(data)\n"                            # no encrypt_bytes at all
    )
    r = originals_are_encrypted_at_rest([_mod(tmp_path, "plain", src)])
    assert not r.ok and "encrypt_bytes" in r.detail


def test_fails_closed_on_an_unparseable_file(tmp_path: Path) -> None:
    d = tmp_path / "broken"
    d.mkdir()
    (d / "broken.py").write_text("def put(  <<< syntax error", encoding="utf-8")
    r = originals_are_encrypted_at_rest([d])
    assert not r.ok


def test_registered_in_checks_and_manifest() -> None:
    from apx.checks.manifest import PROPERTY_MANIFEST
    from apx.checks.registry import CHECKS

    assert originals_are_encrypted_at_rest in CHECKS
    keys = {r.key for r in PROPERTY_MANIFEST}
    assert "originals-encrypted-at-rest" in keys
