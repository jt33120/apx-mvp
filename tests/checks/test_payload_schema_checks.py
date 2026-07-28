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


def test_forbidden_column_fires_on_a_scope_named_db_column() -> None:
    # the DB column is 'scope' even though the attribute is the innocent 'wall'
    result = payload_schema.chunk_columns_enumerated([FIX / "forbidden_column"])
    assert not result.ok and "scope" in result.detail


def test_column_check_fires_on_any_non_enumerated_column() -> None:
    # the allowlist is "exactly the AD-9 set" — a stray non-scope column also fails
    result = payload_schema.chunk_columns_enumerated([FIX / "stray_column"])
    assert not result.ok and "foo" in result.detail


def test_no_cascade_fires_on_a_cascade_foreign_key() -> None:
    result = payload_schema.no_cascade_delete([FIX / "cascade_fk"])
    assert not result.ok and "CASCADE" in result.detail.upper()


def test_no_custodian_on_piece_fires_on_a_custodian_column(tmp_path: Path) -> None:
    # AD-9 / Story 2.5: custodianship is the CUSTODIAN_LINK set — a custodian column on the pièce
    # re-creates the two-representations wall the enumeration forbids. The check must fire on it.
    (tmp_path / "m.py").write_text(
        "class Piece:\n"
        "    id: Mapped[str] = mapped_column(String, primary_key=True)\n"
        "    custodian: Mapped[str] = mapped_column(String, nullable=False)\n")
    result = payload_schema.no_custodian_or_scope_column_on_piece([tmp_path])
    assert not result.ok and "custodian" in result.detail


def test_no_custodian_on_piece_catches_a_scope_db_name_alias(tmp_path: Path) -> None:
    # the DB column is 'scope' even though the attribute is the innocent 'wall' — the check reads
    # the real DB name, so denormalising scope onto the pièce behind an alias is caught too.
    (tmp_path / "m.py").write_text(
        "class Piece:\n"
        "    id: Mapped[str] = mapped_column(String, primary_key=True)\n"
        "    wall: Mapped[str] = mapped_column('scope', String, nullable=False)\n")
    result = payload_schema.no_custodian_or_scope_column_on_piece([tmp_path])
    assert not result.ok and "scope" in result.detail


def test_no_custodian_on_piece_catches_a_bare_column_constructor(tmp_path: Path) -> None:
    # a custodian smuggled via the raw Column(...) constructor (not mapped_column) is caught too.
    (tmp_path / "m.py").write_text(
        "class Piece:\n"
        "    id = mapped_column(String, primary_key=True)\n"
        "    custodian = Column(String, nullable=False)\n")
    result = payload_schema.no_custodian_or_scope_column_on_piece([tmp_path])
    assert not result.ok and "custodian" in result.detail


def test_one_chunk_writer_reports_the_single_real_writer() -> None:
    """A positive sanity check: on the real tree there is exactly one, and it is named."""
    result = payload_schema.one_chunk_writer()
    assert result.ok and "write_chunk" in result.detail


def test_one_chunk_writer_counts_an_insert_core_statement(tmp_path: Path) -> None:
    # an ORM Chunk(...) writer AND a separate insert(Chunk) bulk path = two writers → fail.
    # Proves the check counts the Core bulk path (the natural way to smuggle a 2nd writer).
    (tmp_path / "a.py").write_text("def w1(p):\n    return Chunk(chunk_id='x')\n")
    (tmp_path / "b.py").write_text("def w2(rows):\n    return insert(Chunk).values(rows)\n")
    result = payload_schema.one_chunk_writer([tmp_path])
    assert not result.ok and "more than one" in result.detail.lower()


def test_checks_fail_closed_on_an_unparseable_file(tmp_path: Path) -> None:
    (tmp_path / "broken.py").write_text("def oops(:\n")  # a syntax error
    for check in (
        payload_schema.one_chunk_writer,
        payload_schema.scope_arg_required,
        payload_schema.chunk_columns_enumerated,
        payload_schema.no_custodian_or_scope_column_on_piece,
        payload_schema.no_cascade_delete,
    ):
        result = check([tmp_path])
        assert not result.ok and "parse" in result.detail.lower()


def test_checks_do_not_crash_on_a_nul_byte(tmp_path: Path) -> None:
    # a NUL byte makes ast.parse raise ValueError (not SyntaxError) — must fail closed,
    # never propagate and crash `python -m apx.checks`.
    (tmp_path / "nul.py").write_bytes(b"x = 1\x00\n")
    result = payload_schema.no_cascade_delete([tmp_path])
    assert not result.ok and "parse" in result.detail.lower()
