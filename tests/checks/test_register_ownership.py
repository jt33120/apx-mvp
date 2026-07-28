"""The AD-37 register-ownership check is live, not decorative (Story 2.6).

It holds on the real tree AND fires on a deliberately violating fixture — a `resolution_state`
write outside the store adapter. A read DTO that merely carries the value is not a write.
"""

from __future__ import annotations

from pathlib import Path

from apx.checks import register_ownership


def test_register_ownership_holds_on_the_real_tree() -> None:
    result = register_ownership.register_state_written_once()
    assert result.ok, result.detail


def test_fires_on_a_failure_construction_outside_the_store(tmp_path: Path) -> None:
    (tmp_path / "rogue.py").write_text(
        "def bad():\n    return Failure(id='x', resolution_state='resolved')\n")
    result = register_ownership.register_state_written_once([tmp_path])
    assert not result.ok and "resolution_state" in result.detail


def test_fires_on_an_attribute_assignment_outside_the_store(tmp_path: Path) -> None:
    (tmp_path / "rogue.py").write_text("def bad(f):\n    f.resolution_state = 'resolved'\n")
    result = register_ownership.register_state_written_once([tmp_path])
    assert not result.ok and "resolution_state" in result.detail


def test_fires_on_core_and_raw_sql_transition_idioms(tmp_path: Path) -> None:
    # the natural bulk/raw idioms a second transition owner would use (mirrors one_chunk_writer's
    # coverage of insert(Chunk)) — the Core update, the ORM bulk update, setattr, and raw SQL.
    for src in (
        "def bad():\n    return update(Failure).values(resolution_state='resolved')\n",
        "def bad(s):\n    return s.query(Failure).update({'resolution_state': 'resolved'})\n",
        "def bad(f):\n    setattr(f, 'resolution_state', 'resolved')\n",
        "def bad(c):\n    return c.execute(text('UPDATE failure SET resolution_state = 1'))\n",
    ):
        (tmp_path / "rogue.py").write_text(src)
        result = register_ownership.register_state_written_once([tmp_path])
        assert not result.ok, src


def test_does_not_fire_on_a_read_dto_carrying_the_value(tmp_path: Path) -> None:
    # a response/reads DTO that merely carries resolution_state is NOT a state write.
    (tmp_path / "ok.py").write_text(
        "def read(f):\n    return FailureOut(resolution_state=f.resolution_state)\n")
    result = register_ownership.register_state_written_once([tmp_path])
    assert result.ok, result.detail


def test_fails_closed_on_an_unparseable_file(tmp_path: Path) -> None:
    (tmp_path / "broken.py").write_text("def oops(:\n")
    result = register_ownership.register_state_written_once([tmp_path])
    assert not result.ok and "parse" in result.detail.lower()
