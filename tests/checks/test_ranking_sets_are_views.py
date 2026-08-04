"""The AD-39 gate (Story 4.3): no ORM table or column names a retained/discarded set — those sets
are views over the order + the line + pins, never a stored membership. Passes the real tree; fires
on
fixtures; fails closed."""

from __future__ import annotations

from pathlib import Path

from apx.checks.ranking_sets_are_views import no_retained_or_discarded_set_column


def _mod(tmp_path: Path, name: str, src: str) -> Path:
    d = tmp_path / name
    d.mkdir()
    (d / f"{name}.py").write_text(src, encoding="utf-8")
    return d


def test_passes_the_real_tree() -> None:
    assert no_retained_or_discarded_set_column().ok


def test_fires_on_a_column_naming_a_discarded_set(tmp_path: Path) -> None:
    src = (
        "from sqlalchemy.orm import Mapped, mapped_column\n"
        "class Bad:\n"
        "    __tablename__ = 'thing'\n"
        "    discarded_set: Mapped[bool] = mapped_column()\n")
    r = no_retained_or_discarded_set_column([_mod(tmp_path, "col", src)])
    assert not r.ok and "discarded" in r.detail.lower()


def test_fires_on_a_positional_db_name_behind_an_innocent_attribute(tmp_path: Path) -> None:
    # the real DB column name is read, so a positional mapped_column("retained_set") is caught
    src = (
        "from sqlalchemy.orm import Mapped, mapped_column\n"
        "class Bad:\n"
        "    __tablename__ = 'thing'\n"
        "    flag: Mapped[bool] = mapped_column('retained_set')\n")
    r = no_retained_or_discarded_set_column([_mod(tmp_path, "pos", src)])
    assert not r.ok and "retained" in r.detail.lower()


def test_fires_on_a_table_naming_a_retained_set(tmp_path: Path) -> None:
    src = (
        "from sqlalchemy.orm import Mapped, mapped_column\n"
        "class Bad:\n"
        "    __tablename__ = 'retained_set'\n"
        "    id: Mapped[str] = mapped_column()\n")
    r = no_retained_or_discarded_set_column([_mod(tmp_path, "tbl", src)])
    assert not r.ok and "retained" in r.detail.lower()


def test_a_non_model_class_is_ignored(tmp_path: Path) -> None:
    # a plain class with no __tablename__ is not an ORM model — a `discarded` local is not a column
    src = "class NotAModel:\n    discarded = []\n"
    r = no_retained_or_discarded_set_column([_mod(tmp_path, "plain", src)])
    assert r.ok


def test_fails_closed_on_an_unparseable_file(tmp_path: Path) -> None:
    d = tmp_path / "broken"
    d.mkdir()
    (d / "broken.py").write_text("def (:\n", encoding="utf-8")
    r = no_retained_or_discarded_set_column([d])
    assert not r.ok and ("cannot parse" in r.detail or "failing closed" in r.detail)
