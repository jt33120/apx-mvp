"""The structural-property MANIFEST and its meta-checks (story 1.12; AD-33/FR-56).

AD-33: *"a property with no check is not a property."* This module makes that a build failure. The
manifest enumerates every structural property — its FR, governing AD, name, **verb**, the **check**
callable it names and the **file/pattern it inspects** — and five meta-checks make the manifest
itself a gate:

- ``every_structural_property_has_a_registered_check`` — a ``structural`` row must name a check that
  is registered in the runner (``apx.checks.registry.CHECKS``): a property whose check never runs is
  not a property.
- ``every_registered_check_is_in_the_manifest`` — the reverse: an orphan check absent from the
  manifest fails the build, so the two never drift.
- ``verbs_are_not_conflated`` — only ``structural`` rows name a check; a ``test`` / ``review`` /
  ``not-enforceable`` / ``deferred`` row names none and is never counted as a passing structural
  check (NFR-51: "the third is never counted as a passing test").
- ``manifest_matches_readme`` / ``readme_lists_every_property`` — the shipped README reference block
  (``<!-- structural-properties:start/end -->``) is kept in lock-step with the manifest both ways,
  so a doc edit cannot silently neuter the harness (the config-keys pattern, generalised).

The ``check`` is the callable ITSELF (not a dotted string), so a typo cannot slip past and a rename
moves both sides together. The three verbs — *asserted by test*, *enforced as a structural
property*, *asserted by review* — plus the fourth label ``[NOT ENFORCEABLE]`` are all representable,
so the harness accounts for every guarantee without inflating what the suite proves. Fails closed.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from apx.checks import (
    configuration,
    credential_storage,
    encryption,
    forward_looking,
    import_contracts,
    isolation_harness,
    payload_schema,
    projection,
    scope_admin,
    secrets,
    tenant_isolation,
)
from apx.checks.import_contracts import CheckResult

_REPO_ROOT = Path(__file__).resolve().parents[2]
_README = _REPO_ROOT / "README.md"
_DOC_START = "<!-- structural-properties:start -->"
_DOC_END = "<!-- structural-properties:end -->"
_BACKTICKED = re.compile(r"`([a-z0-9][a-z0-9-]*)`")

# The four verbs of AD-33. Only `structural` is machine-decided and counted; the rest are tracked
# documentation — a `review` row is NEVER counted as a passing check (NFR-51).
STRUCTURAL, TEST, REVIEW, NOT_ENFORCEABLE, DEFERRED = (
    "structural", "test", "review", "not-enforceable", "deferred")
_VERBS = frozenset({STRUCTURAL, TEST, REVIEW, NOT_ENFORCEABLE, DEFERRED})


@dataclass(frozen=True)
class StructuralProperty:
    """One row of the manifest. ``key`` is a unique, stable slug (the README token and the primary
    key). ``check`` is the check CALLABLE for a ``structural`` row, else None."""

    key: str
    fr: str
    ad: str
    name: str
    verb: str
    check: Callable[[], CheckResult] | None
    inspects: str


def _p(key: str, fr: str, ad: str, name: str, check: Callable[[], CheckResult],
       inspects: str) -> StructuralProperty:
    """A structural row (verb=structural); ``check`` (the callable) is required."""
    return StructuralProperty(key, fr, ad, name, STRUCTURAL, check, inspects)


# ── the meta-checks (defined before the manifest so the manifest can name them) ───────────────
def _registered_checks() -> list[Callable[[], CheckResult]]:
    """The live runner registry, imported lazily so this module carries no import cycle with it."""
    from apx.checks.registry import CHECKS

    return CHECKS


def _structural(rows: list[StructuralProperty]) -> list[StructuralProperty]:
    return [r for r in rows if r.verb == STRUCTURAL]


def every_structural_property_has_a_registered_check(
    manifest: list[StructuralProperty] | None = None,
    checks: list[Callable[[], CheckResult]] | None = None,
) -> CheckResult:
    """Every ``structural`` manifest row names a check that is registered in the runner (AD-33/
    FR-56) — a property whose check is missing or unregistered would never run, so it is not a
    property. Also rejects duplicate keys (the manifest primary key must be unique)."""
    name, ad = "every property has a registered check", "AD-33"
    rows = PROPERTY_MANIFEST if manifest is None else manifest
    registered = set(map(id, checks if checks is not None else _registered_checks()))
    keys = [r.key for r in rows]
    dupes = sorted({k for k in keys if keys.count(k) > 1})
    if dupes:
        return CheckResult(name, ad, False, f"duplicate manifest key(s): {dupes}")
    for row in _structural(rows):
        if row.check is None:
            return CheckResult(name, ad, False,
                               f"structural property {row.key!r} names no check (AD-33)")
        if id(row.check) not in registered:
            return CheckResult(
                name, ad, False,
                f"{row.key!r} names a check NOT registered in the runner, so it never runs; a "
                "property with no running check is not a property (AD-33)")
    n = len(_structural(rows))
    return CheckResult(name, ad, True, f"every structural property ({n}) has a registered check")


def every_registered_check_is_in_the_manifest(
    manifest: list[StructuralProperty] | None = None,
    checks: list[Callable[[], CheckResult]] | None = None,
) -> CheckResult:
    """Every callable registered in the runner appears as a ``structural`` manifest row (AD-33) —
    an orphan check absent from the manifest fails the build, so the manifest and the runner never
    drift out of lock-step."""
    name, ad = "every registered check is in the manifest", "AD-33"
    rows = PROPERTY_MANIFEST if manifest is None else manifest
    registry = checks if checks is not None else _registered_checks()
    manifest_ids = {id(r.check) for r in _structural(rows) if r.check is not None}
    for fn in registry:
        if id(fn) not in manifest_ids:
            label = getattr(fn, "__module__", "?") + "." + getattr(fn, "__qualname__", "?")
            return CheckResult(
                name, ad, False,
                f"registered check {label} is not named by any manifest row — an untracked check "
                "(AD-33: the manifest names every property and its check)")
    return CheckResult(name, ad, True, f"every registered check ({len(registry)}) is in manifest")


def verbs_are_not_conflated(
    manifest: list[StructuralProperty] | None = None,
    checks: list[Callable[[], CheckResult]] | None = None,
) -> CheckResult:
    """Only ``structural`` rows name a check; a ``test`` / ``review`` / ``not-enforceable`` /
    ``deferred`` row names none and is not registered in the runner (AD-33/NFR-51). This is
    "the third is never counted as a passing test", made a machine decision, not a discipline."""
    name, ad = "the three verbs are not conflated", "AD-33"
    rows = PROPERTY_MANIFEST if manifest is None else manifest
    registered = set(map(id, checks if checks is not None else _registered_checks()))
    for row in rows:
        if row.verb not in _VERBS:
            return CheckResult(name, ad, False, f"{row.key!r} has an unknown verb {row.verb!r}")
        if row.verb == STRUCTURAL:
            continue
        if row.check is not None:
            registered_note = " (and it is REGISTERED)" if id(row.check) in registered else ""
            return CheckResult(
                name, ad, False,
                f"{row.key!r} is a {row.verb!r} row but names a check{registered_note} — a non-"
                "structural claim is never counted as a passing check (AD-33/NFR-51)")
    return CheckResult(name, ad, True, "verbs are partitioned: only structural rows name a check")


# FR-56's enumerated floor of 13 — each MUST have a live structural check, else a floor item was
# silently dropped (the FR-33-half-shipped review finding, made impossible). AD-33: the self-check
# reconciles the manifest against the document's enumeration, not only against itself.
FLOOR_FRS = frozenset({
    "FR-9", "FR-10", "FR-14", "FR-8", "FR-30", "FR-33", "FR-34", "FR-35", "FR-32", "FR-48",
    "FR-51", "FR-42", "FR-23"})


def floor_of_13_has_a_structural_check(
    manifest: list[StructuralProperty] | None = None,
) -> CheckResult:
    """Every FR in FR-56's enumerated floor of 13 has at least one ``structural`` manifest row
    (AD-33/FR-56) — so a floor property omitted from the manifest fails the build, not only one
    whose check was dropped. Without this the meta-checks guard only what is already enumerated, and
    a silently-absent floor item is invisible (the FR-33 half-ship the review caught)."""
    name, ad = "the FR-56 floor of 13 all have a check", "AD-33"
    rows = PROPERTY_MANIFEST if manifest is None else manifest
    covered = {r.fr for r in rows if r.verb == STRUCTURAL}
    missing = sorted(FLOOR_FRS - covered)
    if missing:
        return CheckResult(name, ad, False,
                           f"FR-56 floor item(s) with no structural check: {missing} — a property "
                           "silently dropped from the manifest is a build failure (AD-33/FR-56)")
    return CheckResult(name, ad, True, f"all {len(FLOOR_FRS)} FR-56 floor items have a check")


def _read_block(path: Path) -> tuple[str | None, str | None]:
    """(block-text, error). Between the two markers; a missing marker → (None, None); an unreadable
    file → (None, error) (fail closed)."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None, f"cannot read {path.name} (failing closed, cannot verify)"
    start, end = text.find(_DOC_START), text.find(_DOC_END)
    if start == -1 or end == -1 or end < start:
        return None, None
    return text[start + len(_DOC_START):end], None


def _readme_rows(block: str) -> list[dict[str, str]]:
    """Parse each table row into ``{key, fr, ad, verb, check}`` from the first FIVE cells
    (Key | FR | AD | Verb | Check); the 6th cell (Inspects) is human prose and is NOT machine-
    compared. The key is the backticked token in cell 0; a header/separator row (no backtick) is
    skipped. This is what makes the lock-step cover the factual columns, not only the key."""
    out: list[dict[str, str]] = []
    for line in block.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if len(cells) < 5:
            continue
        m = _BACKTICKED.search(cells[0])
        if m is None:
            continue  # the header ("Key") and separator ("---") rows carry no backtick
        out.append({"key": m.group(1), "fr": cells[1], "ad": cells[2],
                    "verb": cells[3], "check": cells[4]})
    return out


def _expected_row(p: StructuralProperty) -> dict[str, str]:
    """The README cells a manifest row must show — the check is named by its function ``__name__``
    (a ``—`` for a non-structural row)."""
    return {"key": p.key, "fr": p.fr, "ad": p.ad, "verb": p.verb,
            "check": p.check.__name__ if p.check is not None else "—"}


def manifest_matches_readme(
    manifest: list[StructuralProperty] | None = None, readme: Path | None = None
) -> CheckResult:
    """Every README reference row matches a manifest row on EVERY factual column — key, FR, AD, verb
    and check (AD-33/FR-56) — so no phantom row and no mislabel (a ``structural`` row shown as
    ``review``, a wrong FR/AD/check) can drift while the build stays green. The 6th column
    (Inspects) is human prose, not machine-compared. Fails closed on a missing block/unreadable
    README."""
    name, ad = "the README block matches the manifest", "AD-33"
    rows = PROPERTY_MANIFEST if manifest is None else manifest
    block, error = _read_block(readme if readme is not None else _README)
    if error is not None:
        return CheckResult(name, ad, False, error)
    if block is None:
        return CheckResult(name, ad, False,
                           "README.md has no structural-properties block (the harness reference "
                           "would be silently neutered) — restore the markers (AD-33)")
    expected = {p.key: _expected_row(p) for p in rows}
    for row in _readme_rows(block):
        exp = expected.get(row["key"])
        if exp is None:
            return CheckResult(name, ad, False,
                               f"README documents `{row['key']}` with no manifest row (AD-33)")
        diff = {k: (row[k], exp[k]) for k in exp if row[k] != exp[k]}
        if diff:
            return CheckResult(name, ad, False,
                               f"README row `{row['key']}` mislabels {sorted(diff)}: {diff} — the "
                               "reference must not drift from the check (AD-33)")
    return CheckResult(name, ad, True, "every README row matches its manifest row (key/FR/AD/verb)")


def readme_lists_every_property(
    manifest: list[StructuralProperty] | None = None, readme: Path | None = None
) -> CheckResult:
    """Every manifest row appears in the README reference block (AD-33/FR-56) — the reverse of
    ``manifest_matches_readme``, so a new property cannot be added without documenting it. Fails
    closed on a missing block or an unreadable README."""
    name, ad = "the README lists every property", "AD-33"
    rows = PROPERTY_MANIFEST if manifest is None else manifest
    block, error = _read_block(readme if readme is not None else _README)
    if error is not None:
        return CheckResult(name, ad, False, error)
    if block is None:
        return CheckResult(name, ad, False, "README.md has no structural-properties block (AD-33)")
    documented = {r["key"] for r in _readme_rows(block)}
    missing = [r.key for r in rows if r.key not in documented]
    if missing:
        return CheckResult(name, ad, False,
                           f"manifest rows not documented in the README block: {sorted(missing)} "
                           "— every property must be listed (AD-33)")
    return CheckResult(name, ad, True, f"every manifest property ({len(rows)}) is in the README")


# ── the manifest itself (names every check callable + the meta-checks above) ──────────────────
PROPERTY_MANIFEST: list[StructuralProperty] = [
    # ── story 1.1–1.10: the harness this story promotes into a manifest ───────────────────────
    _p("layering-egress-imports", "FR-56", "AD-4/45/27", "layering + egress import deny-list",
       import_contracts.run, "the import graph (pyproject [tool.importlinter])"),
    _p("one-chunk-writer", "FR-8", "AD-9", "one chunk write boundary",
       payload_schema.one_chunk_writer, "Chunk(...) / insert(Chunk) sites in apx/**"),
    _p("chunk-scope-arg-required", "FR-8", "AD-9", "chunk writer requires a scope argument",
       payload_schema.scope_arg_required, "the chunk writer's signature (no default)"),
    _p("chunk-columns-enumerated", "FR-8", "AD-9", "chunk columns are exactly the enumeration",
       payload_schema.chunk_columns_enumerated, "the chunk model column set"),
    _p("no-cascade-delete", "FR-4", "AD-7", "no cascade delete on chunk/piece",
       payload_schema.no_cascade_delete, "ON DELETE clauses on chunk/piece FKs"),
    _p("tenant-not-null", "FR-30", "AD-12", "tenant NOT NULL on owned tables",
       tenant_isolation.tenant_not_null_on_owned_tables, "tenant columns in the models"),
    _p("scoped-access-carries-tenant", "FR-30", "AD-12", "scope never applied without a tenant",
       tenant_isolation.scoped_access_carries_tenant, "scope predicates in apx/**"),
    _p("identity-tenant-qualified", "FR-30", "AD-12", "matter/piece identity is tenant-qualified",
       tenant_isolation.identity_is_tenant_qualified, "identity keys in the models"),
    _p("no-reversible-credential", "FR-48", "AD-15", "no reversible credential storage",
       credential_storage.no_reversible_credential_storage, "credential columns in the models"),
    _p("jwt-pins-algorithms", "FR-48", "AD-15", "jwt.decode pins an explicit algorithm list",
       credential_storage.jwt_decode_pins_algorithms, "jwt.decode call sites in apx/**"),
    _p("scope-mutations-audited", "FR-49", "AD-33", "scope mutations are audited",
       scope_admin.scope_mutations_are_audited, "the scope-mutating store methods"),
    _p("sensitive-columns-encrypted", "FR-47", "AD-31", "content-bearing columns are encrypted",
       encryption.sensitive_columns_are_encrypted, "content columns in the models"),
    _p("startup-gate-fail-closed", "FR-47", "AD-31", "the start-up gate fails closed",
       encryption.startup_gate_is_fail_closed, "apx/api/startup.py"),
    _p("no-secret-in-source", "FR-51", "AD-47", "no secret in source or committed config",
       secrets.no_secret_in_source, "apx/, docker/, deploy/, .github/, root config"),
    _p("no-secret-column", "FR-51", "AD-47", "no secret column in the data model",
       secrets.no_secret_column_in_models, "the model columns"),
    _p("no-tenant-branch-core", "FR-30", "AD-24", "no tenant identifier is a branch in core",
       configuration.no_tenant_conditional_in_core, "conditionals under apx/core/**"),
    _p("config-defaults-preserve", "FR-30", "AD-24", "no config default disables its guarantee",
       configuration.config_defaults_preserve_guarantees, "apx/core/domain/config.py"),
    _p("documented-config-keys-exist", "FR-30", "AD-24", "every documented config key exists",
       configuration.documented_config_keys_exist, "the README config-keys block"),
    _p("config-reference-complete", "FR-30", "AD-24", "every config key is documented",
       configuration.config_reference_is_complete, "the README config-keys block"),
    _p("projection-registry-only", "FR-31", "AD-26", "projections emitted only by the registry",
       projection.projection_emitted_only_by_registry, "Projection(...) sites in apx/**"),
    _p("snapshot-content-free", "FR-31", "AD-26", "the projector Snapshot is content-free",
       projection.snapshot_fields_are_content_free, "the Snapshot type fields"),
    _p("projectors-declare-attestation", "FR-31", "AD-26",
       "every projector declares an attestation",
       projection.projectors_declare_attestation, "the projection registry"),
    # ── story 1.12: the enumerated FR-56 floor — real-now checks ──────────────────────────────
    _p("no-runtime-import-from-tests", "FR-33", "AD-16", "no runtime import from the test tree",
       isolation_harness.no_runtime_import_from_tests, "imports in the runtime tree"),
    _p("no-fixture-path", "FR-33", "AD-16", "no fixture path in runtime",
       isolation_harness.no_fixture_path_in_runtime, "_fixtures/fixtures path literals in runtime"),
    _p("no-egress-call-site", "FR-32", "AD-45", "no outbound call site outside the adapters",
       isolation_harness.no_egress_call_site_outside_adapters,
       "network imports + call sites in apx/** (excl. the egress adapters)"),
    _p("no-tenant-identifier-source", "FR-30", "AD-24",
       "no tenant identifier is a branch in source",
       isolation_harness.no_tenant_identifier_in_source, "conditionals in the runtime tree"),
    # ── story 2.2: the queue is sealed behind one submodule (AD-17) ────────────────────────────
    _p("queue-sealed", "FR-2", "AD-17", "the queue is sealed behind one submodule",
       isolation_harness.no_queue_import_outside_submodule,
       "procrastinate imports in the runtime tree (excl. the queue submodule)"),
    # ── story 2.3: extraction runs out-of-process & licence-isolated (AD-28) ───────────────────
    _p("extract-msg-sealed", "FR-3", "AD-28", "extract_msg imported only in the isolated worker",
       isolation_harness.no_extract_msg_import_outside_worker,
       "extract_msg imports in the runtime tree (excl. adapters/extraction/msg_worker.py)"),
    _p("subprocess-only-in-extraction", "FR-3", "AD-28", "no subprocess call outside extraction",
       isolation_harness.no_subprocess_call_outside_extraction,
       "subprocess imports in the runtime tree (excl. adapters/extraction)"),
    _p("no-stderr-none-in-extraction", "FR-3", "AD-28", "no stderr=None in extraction adapters",
       isolation_harness.no_stderr_none_in_extraction,
       "stderr=None kwargs in adapters/extraction"),
    # ── story 1.12: the enumerated FR-56 floor — forward-looking checks ───────────────────────
    _p("no-fallback-embedder", "FR-9", "AD-11", "no fallback embedder",
       forward_looking.embedder_has_one_implementation,
       "embed/encode-method classes + except-handlers in the runtime tree (vacuous until 2.8)"),
    _p("destructive-index-one-entry", "FR-10", "AD-7", "destructive index ops from one entry point",
       forward_looking.destructive_index_ops_single_entry,
       "index drop/truncate call sites (vacuous until 2.8)"),
    _p("no-post-filter-retrieval", "FR-14", "AD-14", "no post-filter in retrieval",
       forward_looking.no_post_filter_in_retrieval,
       "functions taking a result set + a scope (vacuous until 3.x)"),
    _p("no-nl-translation-key", "FR-34", "conventions", "no natural-language translation key",
       forward_looking.no_natural_language_translation_key,
       "t()/gettext() call args (vacuous until 6.3)"),
    _p("no-hardcoded-locale", "FR-35", "AD-24", "no hard-coded locale",
       forward_looking.no_hardcoded_locale,
       "locale= / setlocale / Locale literals (vacuous until 6.4)"),
    _p("no-model-reported-confidence", "FR-42", "AD-19", "no model-reported confidence consumed",
       forward_looking.no_model_reported_confidence,
       "confidence fields read off a model response (vacuous until 4.x)"),
    _p("no-banned-confidence-phrasing", "FR-23", "FR-23", "no banned confidence-bound phrasing",
       forward_looking.no_banned_confidence_phrasing,
       "banned phrases in string literals / locale resources (vacuous until 5.4/6.x)"),
    # ── story 1.12: the harness checks ITSELF (the meta-checks) ───────────────────────────────
    _p("meta-property-has-check", "FR-56", "AD-33", "every property has a registered check",
       every_structural_property_has_a_registered_check, "this manifest vs CHECKS"),
    _p("meta-check-in-manifest", "FR-56", "AD-33", "every registered check is in the manifest",
       every_registered_check_is_in_the_manifest, "CHECKS vs this manifest"),
    _p("meta-verbs-not-conflated", "FR-56", "AD-33", "the three verbs are not conflated",
       verbs_are_not_conflated, "this manifest's verbs"),
    _p("meta-manifest-matches-readme", "FR-56", "AD-33", "the README block matches the manifest",
       manifest_matches_readme, "the README structural-properties block"),
    _p("meta-readme-lists-every", "FR-56", "AD-33", "the README lists every property",
       readme_lists_every_property, "the README structural-properties block"),
    _p("meta-floor-of-13", "FR-56", "AD-33", "the FR-56 floor of 13 all have a check",
       floor_of_13_has_a_structural_check, "the 13 enumerated FR-56 floor items vs the manifest"),
    # ── non-structural rows: tracked, NEVER counted as a passing check (AD-33/NFR-51) ─────────
    StructuralProperty(
        "deferred-action-registry", "FR-21", "AD-33", "the user-reachable-actions registry",
        DEFERRED, None,
        "deferred to the usability-probe story (FR-21) — the action registry is itself a "
        "structural property, but the actions it enumerates do not exist yet"),
    StructuralProperty(
        "deferred-fixture-env-source", "FR-33", "AD-16", "env-var selects a data source (leg 3)",
        DEFERRED, None,
        "the third FR-33 leg — an env-var conditional selecting a data source outside the "
        "configured-source list — deferred: a bare os.getenv branch is not precisely separable "
        "from legitimate config without false positives (the fixture-path leg catches a demo "
        "override that reads a fixture dir)"),
    StructuralProperty(
        "not-enforceable-denylist-depends", "FR-30", "AD-3", "'depended on' a managed capability",
        NOT_ENFORCEABLE, None,
        "no check can decide whether the core 'depends on' a managed capability (AD-33/AD-3) — the "
        "package/extension deny-list (import_contracts) stands in as the enforceable half"),
    StructuralProperty(
        "not-enforceable-rejection-record", "FR-48", "AD-15", "the auth rejection record is honest",
        NOT_ENFORCEABLE, None,
        "AD-15's rejection-record honesty is asserted by review, not a static check (AD-33) — the "
        "no-reversible-credential and jwt-pins-algorithms checks stand in where decidable"),
    StructuralProperty(
        "not-enforceable-plausible", "FR-19", "AD-19", "a justification is 'plausible-looking'",
        NOT_ENFORCEABLE, None,
        "no check can decide plausibility (AD-33) — asserted by review; the derived-confidence and "
        "gold-set calibration checks stand in where they exist"),
    StructuralProperty(
        "not-enforceable-commercial", "FR-27", "AD-27", "the model provider's commercial posture",
        NOT_ENFORCEABLE, None,
        "a commercial statement is not a code property (AD-33) — the pre-flight screen stands in"),
    StructuralProperty(
        "review-refusal-phrasing", "FR-27", "AD-33", "the off-corpus refusal phrasing (human)",
        REVIEW, None,
        "phrasing quality is asserted by review against a checklist — never counted as a test"),
]


def run() -> list[CheckResult]:
    return [
        every_structural_property_has_a_registered_check(),
        every_registered_check_is_in_the_manifest(),
        verbs_are_not_conflated(),
        floor_of_13_has_a_structural_check(),
        manifest_matches_readme(),
        readme_lists_every_property(),
    ]
