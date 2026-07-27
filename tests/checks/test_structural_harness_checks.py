"""Story 1.12 — the new structural checks: green on the real tree, red on a firing fixture.

Each check scans the shipped runtime by default (nothing to catch — several are forward-looking and
vacuous until a later epic) and FIRES on the violation its fixture demonstrates. AD-33's discipline:
a vacuous check with no firing fixture is not a property. Every fixture lives under
``tests/_fixtures/structural_violations/`` and is AST/text-scanned, never imported.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from apx.checks import forward_looking as fl
from apx.checks import isolation_harness as ih

_FX = Path(__file__).resolve().parents[1] / "_fixtures" / "structural_violations"

# (check callable, fixture directory) — each fixture fires exactly its check.
_CASES = [
    (ih.no_runtime_import_from_tests, "imports_tests"),
    (ih.no_fixture_path_in_runtime, "fixture_path"),
    (ih.no_egress_call_site_outside_adapters, "egress_leak"),
    (ih.no_tenant_identifier_in_source, "tenant_branch"),
    (fl.embedder_has_one_implementation, "two_embedders"),
    (fl.destructive_index_ops_single_entry, "two_index_deleters"),
    (fl.no_post_filter_in_retrieval, "post_filter"),
    (fl.no_natural_language_translation_key, "nl_translation_key"),
    (fl.no_hardcoded_locale, "hardcoded_locale"),
    (fl.no_model_reported_confidence, "model_confidence"),
    (fl.no_banned_confidence_phrasing, "banned_phrasing"),
]
_IDS = [d for _, d in _CASES]


@pytest.mark.parametrize("check", [c for c, _ in _CASES], ids=_IDS)
def test_check_is_green_on_the_real_tree(check) -> None:  # noqa: ANN001
    r = check()
    assert r.ok, f"{r.name} unexpectedly fired on the shipped tree: {r.detail}"


@pytest.mark.parametrize(("check", "fixture"), _CASES, ids=_IDS)
def test_check_fires_on_its_fixture(check, fixture) -> None:  # noqa: ANN001
    r = check([_FX / fixture])
    assert not r.ok, f"{r.name} did NOT fire on {fixture} — a vacuous check with no firing fixture"


def test_forward_looking_checks_name_their_deferral() -> None:
    # AC5: a forward-looking check says (in its green detail) that it is vacuous until its subject
    # lands, so 'green' is never mistaken for 'guarding live code today'.
    assert "vacuous until" in fl.embedder_has_one_implementation().detail
    assert "vacuous until" in fl.destructive_index_ops_single_entry().detail


def test_checks_fail_closed_on_an_unparseable_file(tmp_path) -> None:  # noqa: ANN001
    (tmp_path / "broken.py").write_text("def (:\n", encoding="utf-8")   # a syntax error
    for check in (ih.no_runtime_import_from_tests,
                  ih.no_fixture_path_in_runtime,
                  ih.no_egress_call_site_outside_adapters,
                  ih.no_tenant_identifier_in_source,
                  fl.no_post_filter_in_retrieval):
        r = check([tmp_path])
        assert not r.ok and "failing closed" in r.detail, f"{r.name} did not fail closed"


def test_parse_fails_closed_on_an_unreadable_file() -> None:
    # an OSError on read (here: reading a directory) lands the file in `unparseable` → graceful
    # fail-closed, not a crash that aborts the runner mid-sweep (review LOW-10).
    from pathlib import Path

    from apx.checks.payload_schema import _parse
    assert _parse(Path(__file__).resolve().parent) is None


def test_egress_check_does_not_flag_orm_get_or_the_db_driver() -> None:
    # the ubiquitous session.get()/dict.get() and the psycopg socket (inside the driver, not a
    # source call site) must NOT be flagged — only source-level urllib/socket/httpx/requests calls.
    assert ih.no_egress_call_site_outside_adapters().ok


def test_tenant_isolation_comparison_is_not_flagged_as_a_branch() -> None:
    # tenant-vs-tenant (piece.tenant == ident.tenant) is the isolation check, not a branch
    assert ih.no_tenant_identifier_in_source().ok
