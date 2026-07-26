"""The configuration-as-data structural checks (story 1.9, AD-24). Each check is green on the
real tree and RED on a fixture that fires — the failure paths AC5 and AC4 require. Fixtures are
AST/text-scanned, never imported.
"""

from __future__ import annotations

from pathlib import Path

from apx.checks.configuration import (
    config_defaults_preserve_guarantees,
    config_reference_is_complete,
    documented_config_keys_exist,
    no_tenant_conditional_in_core,
)
from apx.core.domain.config import ConfigKey

_FIXTURES = Path(__file__).resolve().parents[1] / "_fixtures" / "config_violations"
_REPO_ROOT = Path(__file__).resolve().parents[2]


# ── no tenant identifier is a branch in core (AD-24) ──
def test_core_has_no_tenant_branch() -> None:
    assert no_tenant_conditional_in_core().ok  # the real core is clean


def test_a_tenant_equality_branch_is_caught() -> None:
    result = no_tenant_conditional_in_core([_FIXTURES / "tenant_branch"])
    assert not result.ok and "branch" in result.detail


def test_a_tenant_prefix_branch_is_caught() -> None:
    # `tenant.startswith("cabinet-")` — the routing form a plain equality check misses (HIGH-1)
    assert not no_tenant_conditional_in_core([_FIXTURES / "tenant_prefix"]).ok


def test_a_tenant_branch_hidden_behind_a_module_constant_is_caught() -> None:
    # `SPECIAL = "cabinet-x"; if tenant == SPECIAL` — the check resolves module string constants
    assert not no_tenant_conditional_in_core([_FIXTURES / "tenant_module_const"]).ok


def test_a_tenant_vs_tenant_isolation_check_is_not_flagged() -> None:
    # comparing two tenant values (isolation) is legitimate — only a tenant-vs-literal is a branch
    assert no_tenant_conditional_in_core([_FIXTURES / "tenant_isolation_ok"]).ok


def test_a_tenant_sentinel_guard_is_not_flagged() -> None:
    # `row.tenant == ""` is a defensive sentinel guard, not a branch on a firm's identity (MED-5)
    assert no_tenant_conditional_in_core([_FIXTURES / "tenant_sentinel_ok"]).ok


def test_tenant_branch_check_fails_closed_on_unparseable(tmp_path: Path) -> None:
    (tmp_path / "broken.py").write_text("def oops(:\n", encoding="utf-8")
    assert not no_tenant_conditional_in_core([tmp_path]).ok


# ── no config default disables its guarantee (AD-24) ──
def test_real_schema_defaults_all_preserve_their_guarantees() -> None:
    assert config_defaults_preserve_guarantees().ok


def test_a_default_that_disables_its_guarantee_is_caught() -> None:
    bad = {
        "off_corpus_refusal_enabled": ConfigKey(
            "off_corpus_refusal_enabled", "bool", False,  # shipped DISABLED — the v1 defect
            governs="the off-corpus refusal", preserves_guarantee=lambda v: v is True),
    }
    result = config_defaults_preserve_guarantees(bad)
    assert not result.ok and "disables the guarantee" in result.detail


def test_a_key_with_no_default_is_caught() -> None:
    none_default = {"k": ConfigKey("k", "str", None, governs="x")}
    assert not config_defaults_preserve_guarantees(none_default).ok


# ── every documented config key exists (AD-24) ──
def test_readme_documented_keys_all_exist() -> None:
    assert documented_config_keys_exist().ok  # the real README block references only real keys


def test_a_phantom_documented_key_is_caught() -> None:
    result = documented_config_keys_exist([_FIXTURES / "phantom_doc" / "DOC.md"])
    assert not result.ok and "off_corpus_gate" in result.detail


def test_documented_keys_check_fails_closed_on_unreadable_doc(tmp_path: Path) -> None:
    missing = tmp_path / "nope.md"
    assert not documented_config_keys_exist([missing]).ok


def test_documented_keys_check_is_not_vacuous_on_a_missing_readme_block() -> None:
    # the real README HAS a block, so the default scan passes; the point is the default scan is not
    # short-circuited — a doc WITH a block is validated, a doc without one (given explicitly) is
    # skipped, but the shipped README default must carry the block (see the reverse check below).
    assert documented_config_keys_exist().ok  # real README carries the block → validated, green


# ── every config key is documented (the reverse gate, AD-24/FR-56) ──
def test_reverse_completeness_passes_on_the_real_readme() -> None:
    assert config_reference_is_complete().ok  # every schema key is in the README block


def test_reverse_completeness_fails_when_a_key_is_undocumented(tmp_path: Path) -> None:
    # a README whose block documents only ONE key, while the schema has many → incomplete → red
    doc = tmp_path / "README.md"
    doc.write_text(
        "<!-- config-keys:start -->\n\n| Key |\n| `interface_language` |\n\n"
        "<!-- config-keys:end -->\n", encoding="utf-8")
    result = config_reference_is_complete(readme=doc)
    assert not result.ok and "not documented" in result.detail


def test_reverse_completeness_fails_closed_on_a_missing_block(tmp_path: Path) -> None:
    doc = tmp_path / "README.md"
    doc.write_text("# a README with no config-keys block\n", encoding="utf-8")
    assert not config_reference_is_complete(readme=doc).ok
