"""Story 1.12 — the manifest is itself a checked object (AD-33/FR-56).

The manifest names every structural property and its check; the meta-checks make "a property with no
check" (and its converse, an orphan check) a build failure, keep the manifest and the runner in
lock-step, keep the README block in lock-step, and forbid conflating the three verbs.
"""

from __future__ import annotations

from apx.checks import manifest as m
from apx.checks.manifest import PROPERTY_MANIFEST, StructuralProperty
from apx.checks.registry import CHECKS


def _noop() -> None:  # a stand-in check callable; the meta-checks compare identity, never call it
    ...


def test_the_real_manifest_is_self_consistent() -> None:
    for result in m.run():                       # every meta-check green against the real manifest…
        assert result.ok, f"{result.name}: {result.detail}"


def test_the_manifest_covers_the_real_registry_both_ways() -> None:
    # a stronger statement of lock-step, run against the LIVE registry object explicitly
    assert m.every_structural_property_has_a_registered_check(PROPERTY_MANIFEST, CHECKS).ok
    assert m.every_registered_check_is_in_the_manifest(PROPERTY_MANIFEST, CHECKS).ok


def test_a_structural_property_with_an_unregistered_check_fails() -> None:
    rogue = m._p("rogue", "FR-X", "AD-X", "a check that never runs", _noop, "nowhere")
    r = m.every_structural_property_has_a_registered_check([rogue], checks=[])
    assert not r.ok and "not registered" in r.detail.lower()


def test_a_structural_property_naming_no_check_fails() -> None:
    row = StructuralProperty("k", "FR-X", "AD-X", "n", m.STRUCTURAL, None, "i")
    r = m.every_structural_property_has_a_registered_check([row], checks=[])
    assert not r.ok and "names no check" in r.detail


def test_an_orphan_registered_check_fails() -> None:
    # a check in the runner but named by NO manifest row
    r = m.every_registered_check_is_in_the_manifest([], checks=[_noop])
    assert not r.ok and "not named by any manifest row" in r.detail


def test_duplicate_manifest_keys_fail() -> None:
    a = m._p("dup", "FR-X", "AD-X", "one", _noop, "i")
    b = m._p("dup", "FR-Y", "AD-Y", "two", _noop, "i")
    r = m.every_structural_property_has_a_registered_check([a, b], checks=[_noop])
    assert not r.ok and "duplicate" in r.detail.lower()


def test_a_non_structural_row_that_names_a_check_is_rejected() -> None:
    # the crux (NFR-51): a review claim must never be counted as a passing structural check
    conflated = StructuralProperty("r", "FR-X", "AD-X", "a review claim", m.REVIEW, _noop, "i")
    r = m.verbs_are_not_conflated([conflated], checks=[_noop])
    assert not r.ok and "never counted" in r.detail.lower()


def test_an_unknown_verb_is_rejected() -> None:
    bad = StructuralProperty("b", "FR-X", "AD-X", "n", "made-up", None, "i")
    r = m.verbs_are_not_conflated([bad], checks=[])
    assert not r.ok and "unknown verb" in r.detail


_BLOCK = (
    "<!-- structural-properties:start -->\n"
    "| Property | FR |\n|---|---|\n| `only-one` | FR-X |\n"
    "<!-- structural-properties:end -->\n"
)


def test_readme_missing_a_manifest_row_fails(tmp_path) -> None:  # noqa: ANN001
    readme = tmp_path / "README.md"
    readme.write_text(_BLOCK, encoding="utf-8")
    present = m._p("only-one", "FR-X", "AD-X", "n", _noop, "i")
    missing = m._p("missing-from-readme", "FR-Y", "AD-Y", "n2", _noop, "i")
    assert not m.readme_lists_every_property([present, missing], readme=readme).ok


def test_readme_phantom_property_fails(tmp_path) -> None:  # noqa: ANN001
    readme = tmp_path / "README.md"
    readme.write_text(_BLOCK, encoding="utf-8")   # block names `only-one`
    phantom = m._p("different", "FR-Z", "AD-Z", "n", _noop, "i")   # manifest has no `only-one`
    assert not m.manifest_matches_readme([phantom], readme=readme).ok


def test_a_missing_readme_block_fails_closed(tmp_path) -> None:  # noqa: ANN001
    readme = tmp_path / "README.md"
    readme.write_text("no markers here\n", encoding="utf-8")
    assert not m.manifest_matches_readme([], readme=readme).ok
    assert not m.readme_lists_every_property([], readme=readme).ok
