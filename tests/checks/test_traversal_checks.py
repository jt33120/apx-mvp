"""`the filesystem has one walk` fires on the defect and passes on the real tree (Story 7.1).

The fixtures commit the exact shape the runtime shipped: a second traversal of the submitted tree,
on which the subtree boundary does not exist. That was not hypothetical — the API's capacity
pre-flight counted the files a job would contain through a `rglob` different from the one that
ingested them, and the worker's `enumerate_units` froze the unit set through a third.
"""

from __future__ import annotations

from pathlib import Path

from apx.checks.traversal import the_filesystem_has_one_walk

_FIXTURES = Path(__file__).resolve().parents[1] / "_fixtures" / "traversal_violations"


def _fixture(name: str) -> list[Path]:
    return [_FIXTURES / name]


def test_it_passes_on_the_real_runtime() -> None:
    result = the_filesystem_has_one_walk()
    assert result.ok, result.detail


def test_the_clean_fixture_passes() -> None:
    """So the failures below are about the defect, not about the fixture being unlike real code."""
    assert the_filesystem_has_one_walk(_fixture("clean")).ok


def test_it_fires_on_a_second_path_walk() -> None:
    result = the_filesystem_has_one_walk(_fixture("second_walk"))
    assert not result.ok
    assert "rglob" in result.detail


def test_it_fires_on_the_same_escape_spelled_through_os() -> None:
    # A check that saw only `Path.rglob` would report the property held while the walk moved one
    # import away — the evasion this project's reviews find in every static guard.
    result = the_filesystem_has_one_walk(_fixture("os_walk"))
    assert not result.ok
    assert "os.walk" in result.detail


def test_a_local_function_named_walk_is_not_a_filesystem_traversal() -> None:
    """The check's own first defect, kept as a regression.

    `core/projection.py` defines a recursive `walk(value)` over an in-memory mapping. Matching the
    bare attribute name reported it as a directory traversal — a guard inspecting the SHAPE of a
    call rather than the property it claims to hold, which is the family this whole story is about.
    The real tree contains that function, so `test_it_passes_on_the_real_runtime` would catch a
    regression; this names it so the next reader knows it was deliberate.
    """
    result = the_filesystem_has_one_walk()
    assert result.ok
    assert "projection.py" not in result.detail


def test_the_success_message_states_what_it_could_not_decide() -> None:
    # A pass that claims more than it inspected is how a check stops being evidence.
    result = the_filesystem_has_one_walk()
    assert "alias" in result.detail and "not" in result.detail
