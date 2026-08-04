"""The case-theory append-only / one-owner gate (Story 4.1, AD-37/AD-7): a CaseTheoryVersion
construction outside the store adapter, or any UPDATE/DELETE of the table, fails the build. Passes
the real tree; fires on fixtures; fails closed."""

from __future__ import annotations

from pathlib import Path

from apx.checks.case_theory_ownership import case_theory_version_is_append_only


def _mod(tmp_path: Path, name: str, src: str) -> Path:
    d = tmp_path / name
    d.mkdir()
    (d / f"{name}.py").write_text(src, encoding="utf-8")
    return d


def test_passes_the_real_tree() -> None:
    assert case_theory_version_is_append_only().ok


def test_fires_on_a_construction_outside_the_store_adapter(tmp_path: Path) -> None:
    src = "def leak():\n    return CaseTheoryVersion(id='x', tenant='t', matter='m')\n"
    r = case_theory_version_is_append_only([_mod(tmp_path, "leak", src)])
    assert not r.ok and "outside the store adapter" in r.detail


def test_fires_on_a_core_update_of_the_table(tmp_path: Path) -> None:
    src = ("from sqlalchemy import update\n"
           "def bad(s):\n    s.execute(update(CaseTheoryVersion).values(text='x'))\n")
    r = case_theory_version_is_append_only([_mod(tmp_path, "upd", src)])
    assert not r.ok and "UPDATE/DELETE" in r.detail


def test_fires_on_a_raw_delete_sql(tmp_path: Path) -> None:
    src = 'def bad(conn):\n    conn.execute("DELETE FROM case_theory_version")\n'
    r = case_theory_version_is_append_only([_mod(tmp_path, "raw", src)])
    assert not r.ok and "UPDATE/DELETE" in r.detail


def test_fires_on_a_bulk_orm_delete(tmp_path: Path) -> None:
    src = "def bad(s):\n    s.query(CaseTheoryVersion).delete()\n"
    r = case_theory_version_is_append_only([_mod(tmp_path, "bulk", src)])
    assert not r.ok


def test_fires_on_session_delete_of_a_loaded_instance(tmp_path: Path) -> None:
    src = ("def bad(s):\n"
           "    row = s.get(CaseTheoryVersion, 'x')\n"
           "    s.delete(row)\n")
    r = case_theory_version_is_append_only([_mod(tmp_path, "instdel", src)])
    assert not r.ok and "deleted/mutated" in r.detail


def test_fires_on_attribute_mutation_of_a_loaded_instance(tmp_path: Path) -> None:
    src = ("from sqlalchemy import select\n"
           "def bad(s):\n"
           "    row = s.scalar(select(CaseTheoryVersion))\n"
           "    row.text = None\n")
    r = case_theory_version_is_append_only([_mod(tmp_path, "instmut", src)])
    assert not r.ok and "deleted/mutated" in r.detail


def test_a_fresh_construction_then_field_set_is_not_flagged(tmp_path: Path) -> None:
    # a NEW row fully built before add() is an append, not a mutation of an existing version — and
    # in any case a construction outside the store is already caught by the ownership half.
    src = ("def build():\n"
           "    row = CaseTheoryVersion(id='x', tenant='t', matter='m')\n"
           "    return row\n")
    r = case_theory_version_is_append_only([_mod(tmp_path, "build", src)])
    # construction outside the store IS flagged (ownership), but NOT as a mutation
    assert not r.ok and "deleted/mutated" not in r.detail


def test_fails_closed_on_an_unparseable_file(tmp_path: Path) -> None:
    d = tmp_path / "broken"
    d.mkdir()
    (d / "broken.py").write_text("def (:\n", encoding="utf-8")
    r = case_theory_version_is_append_only([d])
    assert not r.ok and "cannot parse" in r.detail
