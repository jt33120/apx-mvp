"""The three override structural checks fire on the defect and pass on the real tree (Story 5.6).

A check that only ever passes proves nothing, so each is driven against a fixture committing
exactly the defect it exists to catch: an override written without asking for its sentence, a
detail composed by hand instead of by the one renderer, a second definition of "blank", and a count
taken over the act class — the one that reports zero on a matter with forty pins.
"""

from __future__ import annotations

from pathlib import Path

from apx.checks.override import (
    override_names_its_ground,
    override_reason_has_one_validator,
    override_reason_reaches_the_record,
)
from apx.core.domain import audit, override

_FIXTURES = Path(__file__).resolve().parents[1] / "_fixtures" / "override_violations"


def _fixture(name: str) -> list[Path]:
    return [_FIXTURES / name]


# ── on the real tree ──────────────────────────────────────────────────────────────────────────

def test_all_three_pass_on_the_real_runtime() -> None:
    for check in (override_reason_has_one_validator, override_reason_reaches_the_record,
                  override_names_its_ground):
        result = check()
        assert result.ok, f"{result.name}: {result.detail}"


def test_the_clean_fixture_passes_both_ast_checks() -> None:
    # the shape a correct write path has, so the failures below are about the defect and not about
    # the fixture being unlike real code
    assert override_reason_has_one_validator(_fixture("clean")).ok
    assert override_reason_reaches_the_record(_fixture("clean")).ok


# ── one validator ─────────────────────────────────────────────────────────────────────────────

def test_an_override_written_without_validating_fails_the_build() -> None:
    result = override_reason_has_one_validator(_fixture("no_validator"))
    assert not result.ok and "validate_override_reason" in result.detail


def test_a_second_definition_of_blank_fails_the_build() -> None:
    result = override_reason_has_one_validator(_fixture("second_blank_test"))
    assert not result.ok and "blankness" in result.detail


def test_the_validator_check_fails_closed_on_an_unparseable_file(tmp_path: Path) -> None:
    (tmp_path / "broken.py").write_text("def oops(:\n")
    result = override_reason_has_one_validator([tmp_path])
    assert not result.ok and "parse" in result.detail.lower()


# ── the reason in the record ──────────────────────────────────────────────────────────────────

def test_a_hand_composed_detail_fails_the_build() -> None:
    result = override_reason_reaches_the_record(_fixture("hand_composed_detail"))
    assert not result.ok and "override_detail" in result.detail


def test_the_record_check_fails_closed_on_an_unparseable_file(tmp_path: Path) -> None:
    (tmp_path / "broken.py").write_text("def oops(:\n")
    result = override_reason_reaches_the_record([tmp_path])
    assert not result.ok and "parse" in result.detail.lower()


# ── the ground, and never the class ───────────────────────────────────────────────────────────

def test_counting_by_the_act_class_fails_the_build() -> None:
    result = override_names_its_ground(_fixture("count_by_class"))
    assert not result.ok and "CLASS" in result.detail


def test_an_override_without_a_ground_fails_the_build(monkeypatch) -> None:  # noqa: ANN001
    rogue = audit.RecordableAct(
        "rogue_override", audit.CLASS_OVERRIDE, audit.CHAIN_TENANT, False, None)
    monkeypatch.setitem(audit.ACTS, "rogue_override", rogue)
    result = override_names_its_ground(_fixture("clean"))
    assert not result.ok and "names no FR-25 ground" in result.detail


def test_a_ground_outside_fr25s_three_fails_the_build(monkeypatch) -> None:  # noqa: ANN001
    # constructed around __post_init__ (which refuses it) so the check is proven to refuse it too:
    # the runtime guard and the build guard must not depend on each other
    rogue = audit.RecordableAct.__new__(audit.RecordableAct)
    object.__setattr__(rogue, "verb", "rogue_override")
    object.__setattr__(rogue, "act_class", audit.CLASS_OVERRIDE)
    object.__setattr__(rogue, "chain", audit.CHAIN_TENANT)
    object.__setattr__(rogue, "system", False)
    object.__setattr__(rogue, "override", "because-the-user-insisted")
    monkeypatch.setitem(audit.ACTS, "rogue_override", rogue)
    result = override_names_its_ground(_fixture("clean"))
    assert not result.ok and "three grounds" in result.detail


def test_the_pending_declaration_and_the_writer_cannot_both_be_true(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setitem(audit.PENDING_CLASSES, audit.CLASS_OVERRIDE, "5.6")
    result = override_names_its_ground(_fixture("clean"))
    assert not result.ok and "pending" in result.detail


def test_the_catalogue_legs_are_about_the_real_grounds() -> None:
    # the check reads FR-25's grounds from the domain, not from a copy of its own
    assert set(audit.override_ground(v) for v in audit.override_verbs()) <= set(override.GROUNDS)
