"""The ranking append-only / one-owner gate (Story 4.3, AD-37/AD-7): a RankingVersion/RankedEntry
construction outside the store adapter, or any UPDATE/DELETE of either table, fails the build.
Passes
the real tree; fires on fixtures; fails closed."""

from __future__ import annotations

from pathlib import Path

from apx.checks.ranking_ownership import ranking_version_is_append_only


def _mod(tmp_path: Path, name: str, src: str) -> Path:
    d = tmp_path / name
    d.mkdir()
    (d / f"{name}.py").write_text(src, encoding="utf-8")
    return d


def test_passes_the_real_tree() -> None:
    assert ranking_version_is_append_only().ok


def test_fires_on_a_version_construction_outside_the_store_adapter(tmp_path: Path) -> None:
    src = "def leak():\n    return RankingVersion(id='x', tenant='t', matter='m')\n"
    r = ranking_version_is_append_only([_mod(tmp_path, "leak", src)])
    assert not r.ok and "outside the store adapter" in r.detail


def test_fires_on_an_entry_construction_outside_the_store_adapter(tmp_path: Path) -> None:
    src = "def leak():\n    return RankedEntry(id='x', piece_id='p')\n"
    r = ranking_version_is_append_only([_mod(tmp_path, "leakb", src)])
    assert not r.ok and "outside the store adapter" in r.detail


def test_fires_on_a_core_update_of_a_ranking_table(tmp_path: Path) -> None:
    src = ("from sqlalchemy import update\n"
           "def bad(s):\n    s.execute(update(RankedEntry).values(rank=1))\n")
    r = ranking_version_is_append_only([_mod(tmp_path, "upd", src)])
    assert not r.ok and "UPDATE/DELETE" in r.detail


def test_fires_on_a_raw_delete_sql(tmp_path: Path) -> None:
    src = 'def bad(conn):\n    conn.execute("DELETE FROM ranking_version")\n'
    r = ranking_version_is_append_only([_mod(tmp_path, "raw", src)])
    assert not r.ok and "UPDATE/DELETE" in r.detail


def test_fires_on_a_bulk_orm_delete(tmp_path: Path) -> None:
    src = "def bad(s):\n    s.query(RankedEntry).delete()\n"
    r = ranking_version_is_append_only([_mod(tmp_path, "bulk", src)])
    assert not r.ok


def test_fires_on_session_delete_of_a_loaded_instance(tmp_path: Path) -> None:
    src = ("def bad(s):\n"
           "    row = s.get(RankingVersion, 'x')\n"
           "    s.delete(row)\n")
    r = ranking_version_is_append_only([_mod(tmp_path, "instdel", src)])
    assert not r.ok and "deleted/mutated" in r.detail


def test_fires_on_attribute_mutation_of_a_loaded_instance(tmp_path: Path) -> None:
    src = ("from sqlalchemy import select\n"
           "def bad(s):\n"
           "    row = s.scalar(select(RankedEntry))\n"
           "    row.rank = 2\n")
    r = ranking_version_is_append_only([_mod(tmp_path, "instmut", src)])
    assert not r.ok and "deleted/mutated" in r.detail


def test_fires_on_an_aliased_construction_outside_the_store(tmp_path: Path) -> None:
    # the store imports the model as ``RankingVersionRow``; the check matches that alias too, so an
    # aliased construction outside the store is still caught (the summary's residual-limit exception
    # is the NAMED-import alias resolving to a DIFFERENT identifier — here the alias name matches).
    src = "def leak():\n    return RankingVersionRow(id='x')\n"
    r = ranking_version_is_append_only([_mod(tmp_path, "alias", src)])
    assert not r.ok and "outside the store adapter" in r.detail


def test_fails_closed_on_an_unparseable_file(tmp_path: Path) -> None:
    d = tmp_path / "broken"
    d.mkdir()
    (d / "broken.py").write_text("def (:\n", encoding="utf-8")
    r = ranking_version_is_append_only([d])
    assert not r.ok and "cannot parse" in r.detail
