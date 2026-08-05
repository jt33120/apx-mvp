"""The line-placement append-only / one-owner gate (Story 4.8, FR-17/AD-37/AD-7): a LinePlacement
construction outside the store adapter, or any UPDATE/DELETE of the table, fails the build. Passes
the real tree; fires on fixtures; fails closed."""

from __future__ import annotations

from pathlib import Path

from apx.checks.line_placement_ownership import line_placement_is_append_only


def _mod(tmp_path: Path, name: str, src: str) -> Path:
    d = tmp_path / name
    d.mkdir()
    (d / f"{name}.py").write_text(src, encoding="utf-8")
    return d


def test_passes_the_real_tree() -> None:
    assert line_placement_is_append_only().ok


def test_fires_on_a_construction_outside_the_store_adapter(tmp_path: Path) -> None:
    src = "def leak():\n    return LinePlacement(id='x', tenant='t', matter='m')\n"
    r = line_placement_is_append_only([_mod(tmp_path, "leak", src)])
    assert not r.ok and "outside the store adapter" in r.detail


def test_fires_on_a_core_update_of_the_table(tmp_path: Path) -> None:
    src = ("from sqlalchemy import update\n"
           "def bad(s):\n    s.execute(update(LinePlacement).values(basis='x'))\n")
    r = line_placement_is_append_only([_mod(tmp_path, "upd", src)])
    assert not r.ok and "UPDATE/DELETE" in r.detail


def test_fires_on_a_raw_delete_sql(tmp_path: Path) -> None:
    src = 'def bad(conn):\n    conn.execute("DELETE FROM line_placement")\n'
    r = line_placement_is_append_only([_mod(tmp_path, "raw", src)])
    assert not r.ok and "UPDATE/DELETE" in r.detail


def test_fires_on_a_bulk_orm_delete(tmp_path: Path) -> None:
    src = "def bad(s):\n    s.query(LinePlacement).delete()\n"
    r = line_placement_is_append_only([_mod(tmp_path, "bulk", src)])
    assert not r.ok


def test_fires_on_attribute_mutation_of_a_loaded_instance(tmp_path: Path) -> None:
    src = ("from sqlalchemy import select\n"
           "def bad(s):\n"
           "    row = s.scalar(select(LinePlacement))\n"
           "    row.basis = 'x'\n")
    r = line_placement_is_append_only([_mod(tmp_path, "instmut", src)])
    assert not r.ok and "deleted/mutated" in r.detail


def test_fails_closed_on_an_unparseable_file(tmp_path: Path) -> None:
    d = tmp_path / "broken"
    d.mkdir()
    (d / "broken.py").write_text("def (:\n", encoding="utf-8")
    r = line_placement_is_append_only([d])
    assert not r.ok and "cannot parse" in r.detail
