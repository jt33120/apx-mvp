"""The FR-17 gate (Story 4.8): the line is stored by the identity of the last retained pièce, never
a bare integer position. The line_placement model must declare last_retained_piece_id and NO
ordinal-position column. Passes the real tree; fires on fixtures; fails closed."""

from __future__ import annotations

from pathlib import Path

from apx.checks.line_stored_by_piece_identity import line_is_stored_by_piece_identity


def _mod(tmp_path: Path, name: str, src: str) -> Path:
    d = tmp_path / name
    d.mkdir()
    (d / f"{name}.py").write_text(src, encoding="utf-8")
    return d


def test_passes_the_real_tree() -> None:
    assert line_is_stored_by_piece_identity().ok


def test_fires_on_an_ordinal_position_column(tmp_path: Path) -> None:
    # a model that stores the line as a bare integer position — the FR-17 anti-pattern
    src = (
        "from sqlalchemy.orm import Mapped, mapped_column\n"
        "class Bad:\n"
        "    __tablename__ = 'line_placement'\n"
        "    last_retained_piece_id: Mapped[str] = mapped_column()\n"
        "    position: Mapped[int] = mapped_column()\n")
    r = line_is_stored_by_piece_identity([_mod(tmp_path, "ordinal", src)])
    assert not r.ok and "ordinal line position" in r.detail


def test_fires_on_a_positional_db_name_behind_an_innocent_attribute(tmp_path: Path) -> None:
    # the real DB column name is read, so a positional mapped_column('cut_index') is caught
    src = (
        "from sqlalchemy.orm import Mapped, mapped_column\n"
        "class Bad:\n"
        "    __tablename__ = 'line_placement'\n"
        "    last_retained_piece_id: Mapped[str] = mapped_column()\n"
        "    n: Mapped[int] = mapped_column('cut_index')\n")
    r = line_is_stored_by_piece_identity([_mod(tmp_path, "pos", src)])
    assert not r.ok and "ordinal line position" in r.detail


def test_fires_when_the_identity_column_is_missing(tmp_path: Path) -> None:
    src = (
        "from sqlalchemy.orm import Mapped, mapped_column\n"
        "class Bad:\n"
        "    __tablename__ = 'line_placement'\n"
        "    seq: Mapped[int] = mapped_column()\n")
    r = line_is_stored_by_piece_identity([_mod(tmp_path, "noid", src)])
    assert not r.ok and "last_retained_piece_id" in r.detail


def test_fails_closed_when_the_model_is_absent(tmp_path: Path) -> None:
    # no line_placement model in scope — the guarantee cannot be verified, so it fails closed
    src = "class Other:\n    __tablename__ = 'other'\n"
    r = line_is_stored_by_piece_identity([_mod(tmp_path, "absent", src)])
    assert not r.ok and "not found" in r.detail


def test_fails_closed_on_an_unparseable_file(tmp_path: Path) -> None:
    d = tmp_path / "broken"
    d.mkdir()
    (d / "broken.py").write_text("def (:\n", encoding="utf-8")
    r = line_is_stored_by_piece_identity([d])
    assert not r.ok and ("cannot parse" in r.detail or "failing closed" in r.detail)
