"""The tenant-isolation structural checks are live (story 1.4, AD-12): each holds on the
real tree AND fires on a violation — a synthetic metadata for the write-boundary check, a
tmp source file for the matter-carries-tenant check.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import Column, MetaData, String, Table

from apx.checks import tenant_isolation


def test_both_checks_pass_on_the_real_tree() -> None:
    for result in tenant_isolation.run():
        assert result.ok, f"{result.name} should hold on the real tree:\n{result.detail}"


def test_tenant_not_null_fires_on_a_nullable_tenant() -> None:
    md = MetaData()
    Table("piece", md, Column("id", String, primary_key=True), Column("tenant", String))
    result = tenant_isolation.tenant_not_null_on_owned_tables(md)
    assert not result.ok and "nullable" in result.detail


def test_tenant_not_null_fires_on_a_missing_tenant() -> None:
    md = MetaData()
    Table("chunk", md, Column("chunk_id", String, primary_key=True))  # no tenant column
    result = tenant_isolation.tenant_not_null_on_owned_tables(md)
    assert not result.ok and "no tenant" in result.detail


def test_scoped_access_fires_on_a_scope_filter_without_a_tenant(tmp_path: Path) -> None:
    (tmp_path / "bad_reader.py").write_text(
        "def read_scoped(self, matter, scopes):\n    return (matter, scopes)\n"
    )
    result = tenant_isolation.scoped_access_carries_tenant([tmp_path])
    assert not result.ok and "read_scoped" in result.detail


def test_scoped_access_check_fails_closed_on_an_unparseable_file(tmp_path: Path) -> None:
    (tmp_path / "broken.py").write_text("def oops(:\n")
    result = tenant_isolation.scoped_access_carries_tenant([tmp_path])
    assert not result.ok and "parse" in result.detail.lower()
