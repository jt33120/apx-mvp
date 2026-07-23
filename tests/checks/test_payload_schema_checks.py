"""The frozen-payload-schema structural checks are live, not decorative (story 1.3,
AD-9/AD-40/AD-7). Each check must hold on the real tree AND fire on a deliberately
violating fixture — a guard that cannot fail is worthless.
"""

from __future__ import annotations

from pathlib import Path

from apx.checks import payload_schema

FIX = Path(__file__).resolve().parents[1] / "_fixtures" / "payload_schema_violations"


def test_all_frozen_schema_checks_pass_on_the_real_tree() -> None:
    for result in payload_schema.run():
        assert result.ok, f"{result.name} should hold on the real tree:\n{result.detail}"


def test_one_chunk_writer_fires_on_two_writers() -> None:
    result = payload_schema.one_chunk_writer([FIX / "two_writers"])
    assert not result.ok and "more than one" in result.detail.lower()


def test_scope_required_fires_on_a_defaulted_scope() -> None:
    result = payload_schema.scope_arg_required([FIX / "scope_defaulted"])
    assert not result.ok and "default" in result.detail.lower()


def test_forbidden_column_fires_on_an_rbac_scope_column() -> None:
    result = payload_schema.chunk_columns_enumerated([FIX / "forbidden_column"])
    assert not result.ok and "rbac_scope" in result.detail


def test_no_cascade_fires_on_a_cascade_foreign_key() -> None:
    result = payload_schema.no_cascade_delete([FIX / "cascade_fk"])
    assert not result.ok and "CASCADE" in result.detail.upper()


def test_one_chunk_writer_reports_the_single_real_writer() -> None:
    """A positive sanity check: on the real tree there is exactly one, and it is named."""
    result = payload_schema.one_chunk_writer()
    assert result.ok and "write_chunk" in result.detail
