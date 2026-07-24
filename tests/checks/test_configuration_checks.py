"""The configuration-as-data structural checks (story 1.9, AD-24). Each check is green on the
real tree and RED on a fixture that fires — the failure paths AC5 and AC4 require. Fixtures are
AST/text-scanned, never imported.
"""

from __future__ import annotations

from pathlib import Path

from apx.checks.configuration import (
    config_defaults_preserve_guarantees,
    documented_config_keys_exist,
    no_tenant_conditional_in_core,
)
from apx.core.domain.config import CONFIG_SCHEMA, ConfigKey

_FIXTURES = Path(__file__).resolve().parents[1] / "_fixtures" / "config_violations"
_REPO_ROOT = Path(__file__).resolve().parents[2]


# ── no tenant identifier is a branch in core (AD-24) ──
def test_core_has_no_tenant_branch() -> None:
    assert no_tenant_conditional_in_core().ok  # the real core is clean


def test_a_tenant_branch_is_caught() -> None:
    result = no_tenant_conditional_in_core([_FIXTURES / "tenant_branch"])
    assert not result.ok and "branch" in result.detail


def test_a_tenant_vs_tenant_isolation_check_is_not_flagged() -> None:
    # comparing two tenant values (isolation) is legitimate — only a tenant-vs-literal is a branch
    assert no_tenant_conditional_in_core([_FIXTURES / "tenant_isolation_ok"]).ok


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


def test_every_schema_key_is_documented_in_the_readme() -> None:
    # the reverse of the build check: the README's config block stays COMPLETE, so a new key is
    # never shipped undocumented. (The build gate enforces doc→schema; this test enforces
    # schema→doc so the two never drift.)
    readme = (_REPO_ROOT / "README.md").read_text(encoding="utf-8")
    start = readme.find("<!-- config-keys:start -->")
    end = readme.find("<!-- config-keys:end -->")
    assert start != -1 and end != -1, "the README has no config-keys block"
    block = readme[start:end]
    missing = [k for k in CONFIG_SCHEMA if f"`{k}`" not in block]
    assert not missing, f"config keys missing from the README block: {missing}"
