"""The secret-management structural checks are live, not decorative (story 1.8, AD-47/FR-51).
Each must hold on the real tree AND fire on a deliberately violating fixture — a hardcoded
high-entropy key, a GitHub PAT, a stored-credential column — without false-positiving on env
references or placeholders, and fail closed on an unreadable file.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import Column, MetaData, String, Table

from apx.checks import secrets

FIX = Path(__file__).resolve().parents[1] / "_fixtures" / "secret_violations"


def test_both_secret_checks_pass_on_the_real_tree() -> None:
    for result in secrets.run():
        assert result.ok, f"{result.name} should hold on the real tree:\n{result.detail}"


def test_fires_on_a_hardcoded_high_entropy_key() -> None:
    result = secrets.no_secret_in_source([FIX / "hardcoded_key"])
    assert not result.ok and "high-entropy" in result.detail


def test_fires_on_a_github_pat() -> None:
    result = secrets.no_secret_in_source([FIX / "github_pat"])
    assert not result.ok and "GitHub" in result.detail


def test_fires_on_a_hex_key_below_the_entropy_floor() -> None:
    # the app's own key format: hex entropy sits under 4.0, caught by the length leg not entropy
    result = secrets.no_secret_in_source([FIX / "hex_key"])
    assert not result.ok and "high-entropy" in result.detail


def test_fires_on_an_unquoted_config_value() -> None:
    # a Dockerfile ENV=key — an unquoted value a quoted-only scan missed
    result = secrets.no_secret_in_source([FIX / "unquoted_config"])
    assert not result.ok


def test_fires_on_a_password_embedded_in_a_dsn() -> None:
    result = secrets.no_secret_in_source([FIX / "url_password"])
    assert not result.ok and "connection URL" in result.detail


def test_a_placeholder_elsewhere_on_the_line_does_not_excuse_a_real_token(tmp_path: Path) -> None:
    # the per-line-bypass fix: a real quoted key must still fire even with 'example' in a comment
    (tmp_path / "s.py").write_text('DEFAULT = "Zx9Kq2Wm7Pv4Lr8Ny5Tb3Jc6Hf1Gd0Se"  # example\n')
    assert not secrets.no_secret_in_source([tmp_path]).ok


def test_does_not_fire_on_env_references_or_placeholders(tmp_path: Path) -> None:
    (tmp_path / "ok.py").write_text(
        'KEY = os.environ.get("APX_ENCRYPTION_KEY")\n'
        'URL = "${DATABASE_URL}"  # a placeholder, not a value\n'
    )
    assert secrets.no_secret_in_source([tmp_path]).ok


def test_does_not_fire_on_a_url_or_namespace(tmp_path: Path) -> None:
    (tmp_path / "ns.py").write_text(
        '_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"\n'
    )
    assert secrets.no_secret_in_source([tmp_path]).ok


def test_fails_closed_on_an_unreadable_file(tmp_path: Path) -> None:
    (tmp_path / "bad.py").write_bytes(b"\xff\xfe not valid utf-8 \x00")
    result = secrets.no_secret_in_source([tmp_path])
    assert not result.ok and "cannot read" in result.detail.lower()


def test_no_secret_column_fires_on_a_stored_credential() -> None:
    md = MetaData()
    Table("creds", md, Column("id", String), Column("api_key", String))
    result = secrets.no_secret_column_in_models(md)
    assert not result.ok and "api_key" in result.detail


def test_no_secret_column_fires_on_a_token_or_credential_column() -> None:
    for colname in ("access_token", "credential", "webhook_secret", "passphrase"):
        md = MetaData()
        Table("t", md, Column("id", String), Column(colname, String))
        assert not secrets.no_secret_column_in_models(md).ok, colname


def test_no_secret_column_permits_the_encrypted_totp_secret() -> None:
    md = MetaData()
    Table("u", md, Column("id", String), Column("mfa_secret", String))  # a TOTP secret is allowed
    assert secrets.no_secret_column_in_models(md).ok
