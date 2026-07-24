"""The credential-storage structural checks are live (story 1.5, AD-15/FR-56): each holds
on the real tree AND fires on a violation — a synthetic metadata with a plaintext password
column, and tmp source files with a bare jwt.decode / a forbidden JWK client.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import Column, MetaData, String, Table

from apx.checks import credential_storage


def test_both_checks_pass_on_the_real_tree() -> None:
    for result in credential_storage.run():
        assert result.ok, f"{result.name} should hold on the real tree:\n{result.detail}"


def test_no_reversible_storage_fires_on_a_plaintext_password_column() -> None:
    md = MetaData()
    Table("user_account", md, Column("id", String, primary_key=True), Column("password", String))
    result = credential_storage.no_reversible_credential_storage(md)
    assert not result.ok and "password" in result.detail


def test_jwt_decode_fires_without_a_literal_algorithm_list(tmp_path: Path) -> None:
    (tmp_path / "svc.py").write_text("import jwt\n\ndef read(t, k):\n    return jwt.decode(t, k)\n")
    result = credential_storage.jwt_decode_pins_algorithms([tmp_path])
    assert not result.ok and "algorithms" in result.detail


def test_jwt_decode_passes_with_a_literal_algorithm_list(tmp_path: Path) -> None:
    (tmp_path / "svc.py").write_text(
        "import jwt\n\ndef read(t, k):\n    return jwt.decode(t, k, algorithms=['HS256'])\n"
    )
    result = credential_storage.jwt_decode_pins_algorithms([tmp_path])
    assert result.ok


def test_jwt_check_fires_on_a_forbidden_jwks_client(tmp_path: Path) -> None:
    (tmp_path / "svc.py").write_text("from jwt import PyJWKClient\n\nc = PyJWKClient('u')\n")
    result = credential_storage.jwt_decode_pins_algorithms([tmp_path])
    assert not result.ok and "PyJWKClient" in result.detail


def test_jwt_check_fails_closed_on_an_unparseable_file(tmp_path: Path) -> None:
    (tmp_path / "broken.py").write_text("def oops(:\n")
    result = credential_storage.jwt_decode_pins_algorithms([tmp_path])
    assert not result.ok and "parse" in result.detail.lower()
