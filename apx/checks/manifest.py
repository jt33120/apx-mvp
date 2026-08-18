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
    artefact_stamp_ownership,
    audit_record,
    backup_completeness,
    case_theory_ownership,
    confidence_derivation,
    configuration,
    continuity,
    credential_storage,
    encryption,
    estimator,
    forward_looking,
    freshness_never_time_based,
    gold_gate,
    import_contracts,
    inventory_record,
    isolation_harness,
    justification_names_its_evidence,
    justification_verified_at_show_time,
    label_not_a_ranking_input,
    line_placement_ownership,
    line_projection_not_a_bound,
    line_stored_by_piece_identity,
    matter_export,
    no_legacy_bound,
    no_truncation,
    originals_encrypted,
    override,
    payload_schema,
    perf_gate,
    pin_ledger_ownership,
    pin_not_a_ranking_input,
    projection,
    queue_open,
    ranking_identity_source,
    ranking_ownership,
    ranking_sets_are_views,
    read_path,
    register_ownership,
    renders_sanitized,
    sampling_freeze,
    sampling_population,
    scope_admin,
    secrets,
    staleness_triggers,
    statement,
    taxonomy_label_ownership,
    tenant_isolation,
    traversal,
    triage_sets_one_derivation,
    truth_status,
    truth_status_surface,
    user_actions,
    validation,
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
    _p("no-custodian-scope-column-on-piece", "FR-4", "AD-9", "no custodian/scope column on piece",
       payload_schema.no_custodian_or_scope_column_on_piece,
       "custodian/scope columns on the piece model"),
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
    _p("extraction-captures-stderr", "FR-3", "AD-28", "extraction subprocesses capture stderr",
       isolation_harness.extraction_subprocess_captures_stderr,
       "subprocess call sites in adapters/extraction (capture_output / stderr=PIPE|DEVNULL)"),
    # ── story 1.12: the enumerated FR-56 floor — forward-looking checks ───────────────────────
    _p("no-fallback-embedder", "FR-9", "AD-11", "no fallback embedder",
       forward_looking.embedder_has_one_implementation,
       "embed/encode-method classes + except-handlers in the runtime tree (live as of 2.8)"),
    _p("destructive-index-one-entry", "FR-10", "AD-7", "destructive index ops from one entry point",
       forward_looking.destructive_index_ops_single_entry,
       "index drop/truncate call sites (vacuous until 2.8)"),
    _p("no-post-filter-retrieval", "FR-14", "AD-14", "no post-filter in retrieval",
       forward_looking.no_post_filter_in_retrieval,
       "functions taking a result set + a scope (retrieval landed 3.x — live, no offender)"),
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
       "banned phrases + proximity shapes (fr/en/it) in runtime string literals, locale resources "
       "and apx/web/src — LIVE since Story 5.4, when the sentence it polices shipped"),
    # ── story 2.12: the gold-set merge gate — ranking code cannot merge before recall runs ──────
    _p("gold-set-merge-gate", "FR-54", "AD-34",
       "ranking code is gated by the gold-set recall harness",
       gold_gate.ranking_code_requires_the_gold_gate,
       "ranking/triage sites in apx/** + eval/harness.py recall gate (vacuous until Epic 4)"),
    # ── story 2.13: the perf-ceiling gate — no invented ceiling before the timed run is measured ──
    _p("no-perf-ceiling-before-measurement", "NFR-2", "AD-32",
       "no perf ceiling before the timed run is measured",
       perf_gate.no_perf_ceiling_before_measurement,
       "module-level latency/throughput/wall-clock ceiling constants in apx/** vs the pending "
       "measurement record (vacuous until a ceiling is declared)"),
    # ── story 3.1: the constant-truth-status gate — no config can forge an exhaustive label ──────
    _p("truth-status-constant-per-engine", "FR-12", "AD-20",
       "truth status is a constant construction site per engine",
       truth_status.truth_status_is_constant_per_engine,
       "truth_status fields on result-set types in apx/** (constant, non-overridable member)"),
    # ── story 3.2: the no-truncation gate — an exhaustive set is never truncated (AD-20) ────────
    _p("exhaustive-engine-no-limit", "FR-13", "AD-20",
       "an exhaustive engine takes no limit",
       no_truncation.exhaustive_engine_takes_no_limit,
       "params of functions returning an exhaustive result set in apx/** (no limit/top-k)"),
    # ── story 3.3: the single-read-path gate — scope is a query pre-filter, one path (AD-14) ──────
    _p("tenant-reads-one-entry-point", "FR-14", "AD-14", "tenant reads have one entry point",
       read_path.tenant_reads_have_one_entry_point,
       "select/query/join over a tenant-content model outside core/app/read/ + the store read "
       "modules"),
    _p("scoped-read-scope-in-query", "FR-14", "AD-14", "a scoped read puts its scope in the query",
       read_path.scoped_read_puts_scope_in_the_query,
       "scopes-taking functions that select a scoped content table filtered by tenant alone"),
    _p("corpus-read-no-admin-bypass", "FR-14", "AD-12", "a corpus read takes no admin bypass",
       read_path.corpus_read_takes_no_admin_bypass,
       "Piece/Chunk-reading functions that take an is_admin/super-user bypass parameter"),
    # ── story 3.4: the truth-status SURFACE gate — serialised, never combined (FR-15) ─────────────
    _p("result-response-serialises-truth-status", "FR-15", "AD-20",
       "a result-set response serialises its truth status",
       truth_status_surface.result_set_response_serialises_truth_status,
       "response/export models in apx/api/ carrying engine result items (need truth_status)"),
    _p("no-response-merges-engines", "FR-15", "AD-20", "no response merges the two engines",
       truth_status_surface.no_response_merges_the_two_engines,
       "response/export models in apx/api/ carrying a semantic AND a deterministic result item"),
    # ── story 3.5a: the pièce-viewer foundation — retained originals are encrypted at rest ────────
    _p("originals-encrypted-at-rest", "FR-44", "AD-31", "retained originals are encrypted at rest",
       originals_encrypted.originals_are_encrypted_at_rest,
       "the filesystem original store's put() (encrypt-before-write) + a behavioural probe"),
    # ── story 3.5c-2: the render-sanitisation gate — office renders emit only sanitised HTML ──────
    _p("rendered-html-is-sanitized", "FR-44", "AD-29", "rendered HTML is sanitised",
       renders_sanitized.rendered_html_is_sanitized,
       "the render_html package's one RenderedDocument construction site (inside _rendered, nh3) — "
       "office + .msg — + a behavioural XSS-battery + adversarial-.xlsx probe"),
    # ── story 2.6: the failure register — one owning module per state transition (AD-37) ──────
    _p("register-state-written-once", "FR-5", "AD-37", "register state written only in the store",
       register_ownership.register_state_written_once,
       "Failure.resolution_state writes across apx/**"),
    # ── story 4.1: the case theory — the version table is append-only, one owner (AD-37/AD-7) ───
    _p("case-theory-append-only", "FR-37", "AD-37", "case theory versions append-only, one owner",
       case_theory_ownership.case_theory_version_is_append_only,
       "CaseTheoryVersion construction + UPDATE/DELETE of case_theory_version across apx/**"),
    # ── story 4.3: the ranked order — versions append-only (AD-37/AD-7); sets are views (AD-39) ──
    _p("ranking-append-only", "FR-39", "AD-37", "ranking versions append-only, one owner",
       ranking_ownership.ranking_version_is_append_only,
       "RankingVersion/RankedEntry construction + UPDATE/DELETE of ranking_version/ranked_entry "
       "across apx/**"),
    _p("no-retained-discarded-set", "FR-16", "AD-39", "no retained/discarded set is stored",
       ranking_sets_are_views.no_retained_or_discarded_set_column,
       "table + column names across the ORM models (no retained/discarded set membership)"),
    # ── story 4.4: confidence is derived by one implementation, never self-reported (FR-42) ──────
    _p("confidence-one-derivation", "FR-42", "AD-19", "confidence has one derivation",
       confidence_derivation.confidence_has_one_derivation,
       "Confidence(...) construction sites across apx/** (built only in piece_confidence.py)"),
    # ── story 4.5: per-pièce taxonomy labelling — append-only ledger; the order ignores the label ─
    _p("taxonomy-label-append-only", "FR-40", "AD-37", "taxonomy labels append-only, one owner",
       taxonomy_label_ownership.taxonomy_label_is_append_only,
       "TaxonomyLabelEntry construction outside the store adapter + any UPDATE/DELETE of "
       "taxonomy_label_entry across apx/** (append-only, one owner — Story 4.5)"),
    _p("label-not-a-ranking-input", "FR-43", "AD-39", "the ranked order ignores the taxonomy label",
       label_not_a_ranking_input.ranking_order_ignores_the_taxonomy_label,
       "core/domain/ranking.py + core/app/rank.py import/reference of the taxonomy-label axis — a "
       "label is never an ordering input, so it never moves a pièce or the line (Story 4.5)"),
    # ── story 4.7: the retained/discarded sets are one derived view, never a stored membership ────
    _p("triage-sets-one-derivation", "FR-16", "AD-39", "the triage sets have one derivation",
       triage_sets_one_derivation.triage_sets_have_one_derivation,
       "TriageSets(...) construction sites across apx/** — the retained/discarded sets are one "
       "derived view (core/domain/triage_sets.py), never a stored membership (Story 4.7)"),
    # ── story 4.8: the line the tool draws — stored by pièce identity (FR-17), append-only ────────
    _p("line-stored-by-piece-identity", "FR-17", "AD-23",
       "the line is stored by pièce identity, not a bare integer",
       line_stored_by_piece_identity.line_is_stored_by_piece_identity,
       "the line_placement model's columns — it stores last_retained_piece_id and NO ordinal "
       "position column, so an import cannot silently move the line (Story 4.8/FR-17)"),
    _p("line-placement-append-only", "FR-17", "AD-37",
       "line placements are append-only, one owner",
       line_placement_ownership.line_placement_is_append_only,
       "LinePlacement construction outside the store adapter + any UPDATE/DELETE of line_placement "
       "across apx/** (append-only, one owner — Story 4.8)"),
    # ── story 4.9: the priced move is a projection from the ranking, never a sampling bound ───────
    _p("line-projection-not-a-bound", "FR-19", "AD-20",
       "the priced move is a projection, not a sampling bound",
       line_projection_not_a_bound.line_projection_is_not_a_sampling_bound,
       "core/domain/line_projection.py imports/references — it never depends on "
       "confidence.prevalence_upper_bound, so a projection is never computed by the bound (§0.2)"),
    # ── story 4.11: the pin — append-only ledger; the order ignores the pin axis ──────────────────
    _p("pin-ledger-append-only", "FR-43", "AD-37", "pins are append-only, one owner",
       pin_ledger_ownership.pin_ledger_is_append_only,
       "PinEntry construction outside the store adapter + any UPDATE/DELETE of pin_entry across "
       "apx/** — a pin and its removal are always new entries (append-only, one owner)"),
    _p("pin-not-a-ranking-input", "FR-43", "AD-39", "the ranked order ignores the pin",
       pin_not_a_ranking_input.ranking_order_ignores_the_pin,
       "core/domain/ranking.py + core/app/rank.py import/reference of the pin axis — a pin is not "
       "an ordering input, so it moves one pièce in the VIEW, never in the order (Story 4.11)"),
    # ── story 4.6: the justification derived from named evidence — its checkable part is the named
    # evidence, never the sentence; the read seam containment-verifies every extract at show time ──
    _p("justification-names-evidence", "FR-41", "AD-19",
       "a justification names its evidence, not just a sentence",
       justification_names_its_evidence.justification_names_its_evidence,
       "Justification(...) construction sites across apx/** (built only in justification.py, whose "
       "invariant requires named extracts or intrinsic signals) + record_justification's call to "
       "validate_named_evidence — the write seam re-runs it, so no unreadable row is persisted"),
    _p("justification-verified-show-time", "FR-11", "AD-10",
       "a justification is containment-verified at show time",
       justification_verified_at_show_time.justification_verified_at_show_time,
       "SqlStore.read_justification references resolve_chunk + verify_justification — every "
       "extract is re-verified by exact containment when shown, so an unresolved one is unverified "
       "(FR-11)"),
    # ── story 4.12: never hard-delete — the enumerated registry of user-reachable actions the
    # bounded runtime probe walks, and the reversal every deletion-shaped act must name ──────────
    _p("user-action-registry-complete", "FR-21", "AD-7",
       "the user-action registry is complete",
       user_actions.user_action_registry_is_complete,
       "every HTTP route declared anywhere under apx/api/ + every Ports-taking public callable "
       "anywhere under apx/core/app/, against USER_ACTIONS, both ways — an action outside the "
       "registry is outside the bounded probe that proves it destroys nothing (Story 4.12)"),
    _p("deletion-shaped-names-reversal", "FR-21", "AD-7",
       "a deletion-shaped action names its reversal",
       user_actions.deletion_shaped_actions_declare_their_reversal,
       "the HTTP verb and the word parts of every registered action's path/name — an act a user "
       "could read as deletion declares it and names how it is undone (Story 4.12/FR-5)"),
    # ── story 4.13: freshness and staleness of derived artefacts — the enumerated trigger list,
    # the clock that may not reach the decision, and the stamp nobody may rewrite ────────────────
    _p("staleness-trigger-has-observable", "FR-58", "AD-23",
       "every staleness trigger has an observable",
       staleness_triggers.every_staleness_trigger_has_an_observable,
       "the TRIGGERS enumeration and FreshnessStamp's fields in core/domain/freshness.py, both "
       "ways, plus each artefact kind's declared input subset — a trigger with no observable is a "
       "staleness nothing detects, and the confidence bound must depend on every one of them "
       "(Story 4.13)"),
    _p("freshness-names-no-clock", "FR-58", "AD-23", "the freshness decision names no clock",
       freshness_never_time_based.freshness_is_never_time_based,
       "time imports, clock calls and timedelta across the three modules that decide freshness — "
       "staleness is never resolved by the passage of time or by being viewed (Story 4.13)"),
    _p("artefact-stamp-append-only", "FR-58", "AD-37",
       "artefact stamps are append-only, one owner",
       artefact_stamp_ownership.artefact_stamp_is_append_only,
       "ArtefactStamp constructions outside the store adapter and every UPDATE/DELETE idiom "
       "against artefact_stamp — rewriting a recorded stamp would make a stale artefact read "
       "fresh (Story 4.13)"),
    # ── story 5.1: the sampling run — the population it draws over, the freeze that makes a seed
    # insufficient, and the legacy bound writer that cannot come back ────────────────────────────
    _p("sampling-population-derived", "FR-22", "AD-39",
       "the sampling population is the derived discarded set",
       sampling_population.sampling_population_is_the_derived_view,
       "the sampling-run functions in the store adapter — the draw and the discard_population "
       "observable must both go through derive_triage_sets, and none of them may read the "
       "Story-2.x label pile (Story 5.1, decision A1)"),
    _p("sampling-freeze-identifiers", "FR-22", "AD-23",
       "a sampling run freezes identifiers, not a seed",
       sampling_freeze.a_sampling_run_freezes_its_identifiers,
       "SamplingRun's five freeze columns and SamplingRunItem's identifier columns in models.py — "
       "FR-22 says a seed alone is insufficient, so the explicit identifier list is a shape "
       "(Story 5.1)"),
    _p("no-new-legacy-bound", "FR-23", "AD-7", "no new legacy bound is written",
       no_legacy_bound.no_new_legacy_bound_is_written,
       "RecallReview constructions across apx/** — the label-pile bound is readable history, "
       "never a second live writer over a second population (Story 5.1)"),
    # ── story 5.2: OQ-4's five hard inputs, one structural check each ────────────────────────────
    _p("estimator-piece-worst-case", "FR-38", "AD-19", "the pièce figure is a worst case",
       estimator.piece_figure_is_a_worst_case,
       "every count_upper_pieces= assignment and every multiplication across apx/** — the bound is "
       "over FAMILIES, and the pièce figure is the sum of the D largest frozen families, never "
       "prevalence × pièces (Story 5.2, OQ-4 input 1)"),
    _p("estimator-census-no-bound", "FR-22", "AD-19", "a census states no bound",
       estimator.a_census_states_no_bound,
       "_census_claim_fr and _counts_only_claim_fr in core/domain/statement.py (the WORDS, since "
       "Story 5.4) plus estimate_for_run in core/domain/sampling.py (the SHAPE) — a census "
       "carries an exact count and no percentage, the bound register carries no exact count "
       "(Story 5.2, OQ-4 input 2)"),
    _p("estimator-one-run-one-bound", "FR-22", "AD-37", "one run, one bound, chosen by recency",
       estimator.one_run_one_bound_chosen_by_recency,
       "prevalence_upper_bound call sites across apx/** and read_current_bound's ordering — runs "
       "are never pooled and the current bound is the most recent, never the most flattering "
       "(Story 5.2, OQ-4 input 3)"),
    _p("estimator-bound-from-the-freeze", "FR-22", "AD-23", "the bound is computed from the freeze",
       estimator.the_bound_is_computed_from_the_freeze,
       "complete_sampling_run in the store adapter — the estimator's population and sample are "
       "read off the frozen run row and no live derivation is reached (Story 5.2, OQ-4 input 4)"),
    # ── story 5.3: the estimator ships only if PROVEN ────────────────────────────────────────────
    _p("estimator-simulation-gate", "FR-23", "AD-33", "the simulation gate is wired",
       estimator.the_simulation_gate_is_wired,
       "ESTIMATOR_PROVEN in core/domain/confidence.py against the simulation harness and its test "
       "module — the flag cannot be true unless the harness exists, names its coverage target and "
       "trial floor, and a test asserts BOTH the coverage floor and the tightness ceiling with "
       "nothing skipped (Story 5.3)"),
    _p("estimator-no-model-number", "FR-42", "AD-19", "the bound consumes no model number",
       estimator.the_bound_consumes_no_model_number,
       "core/domain/confidence.py and core/domain/sampling.py — the estimator reaches neither the "
       "FR-19 projection nor any model-reported confidence field (Story 5.2, OQ-4 input 5)"),
    # ── story 5.5: the AUDIT RECORD — chains per (tenant, matter), a locked sequence authority ──
    _p("audit-catalogue-complete", "FR-24", "AD-43", "every recorded act is a catalogued act",
       audit_record.audit_catalogue_is_complete,
       "every _append_audit call site across apx/** (no literal verbs, every named ACT_* defined) "
       "and core/domain/audit.py's FR-24 classes — covered by a writer, or pending with its story"),
    _p("audit-sequence-not-generated", "FR-53", "AD-43", "the audit sequence is never generated",
       audit_record.audit_sequence_is_not_generated,
       "Sequence()/nextval/autoincrement anywhere in apx/** (docstrings exempt), and the head row "
       "in store.py must be taken with_for_update — allocated inside the entry's own transaction"),
    _p("audit-record-append-only", "FR-24", "AD-22", "an evidential row is never edited or removed",
       audit_record.audit_record_is_append_only,
       "delete()/update() built against any of the 8 evidential models across apx/** — the "
       "audit_chain_head allocator is deliberately exempt, being the counter and not the record"),
    # ── story 5.6: the OVERRIDE — one validator, the reason verbatim, a ground on every one ────
    _p("override-reason-one-validator", "FR-25", "AD-37", "the override reason has one validator",
       override.override_reason_has_one_validator,
       "every module that names an override act AND appends to the record, across apx/** — each "
       "validates through core/domain/override.py, and no second blank-reason test exists"),
    _p("override-reason-in-the-record", "FR-25", "AD-22", "the override reason reaches the record",
       override.override_reason_reaches_the_record,
       "every _append_audit call site whose verb is an override, across apx/** — the detail is "
       "composed by override_detail(), never by hand, so the verbatim reason cannot be dropped"),
    # ── story 5.7: the MATTER EXPORT — the tier is demanded, a pending section is a sentence ──
    _p("export-tier-never-defaulted", "FR-26", "AD-33", "the export tier is never defaulted",
       matter_export.export_tier_is_never_defaulted,
       "every function across apx/** taking a `tier` parameter — none defaults it: the one act "
       "that can move client content out of the firm does not choose for the caller (FR-26 §11)"),
    _p("pending-section-is-not-a-zero", "FR-26", "AD-33", "a pending section is a sentence",
       matter_export.a_pending_section_is_not_a_zero,
       "core/domain/matter_record.py's declared pending sections against the act catalogue "
       "(pending IFF uncatalogued) + any len()/sum() over them across apx/** — zero is a finding "
       "about the FIRM, not built is a finding about the BUILD"),
    _p("validation-act-sole-acceptor", "FR-45", "AD-33", "only the validation act accepts",
       validation.only_the_validation_act_accepts,
       "the FR-24 value_accepted class + every function across apx/** appending it — one verb, "
       "one writer, and never without the validation act it must accompany (FR-24 §614)"),
    _p("validation-provenance-never-a-literal", "FR-45", "AD-33",
       "the opened fact is read, never asserted",
       validation.the_opened_fact_is_never_a_literal,
       "every `opened_at=` call site across apx/** — a constant is the blanket stamp over a batch "
       "that FR-45(c) exists to forbid ('not opened, unless it was')"),
    _p("acceptance-is-never-manufactured", "FR-45", "AD-33",
       "no acceptance from time, scroll or presence",
       validation.acceptance_is_never_manufactured,
       "every name and French string literal across apx/** — no dwell/scroll/visit path to an "
       "acceptance, and ONE home for the sentence the record attributes to the lawyer"),
    _p("validation-version-never-defaulted", "FR-45", "AD-33",
       "the accepted ranking version comes from the caller",
       validation.the_accepted_version_is_never_defaulted,
       "every call to validate_pieces/batch_split across apx/**, and every layer that reaches one "
       "— a default resolves whatever version is current AT THE COMMIT, on the record of what a "
       "person accepted (retro B2/H7)"),
    # ── story 5.9: the record cannot be SHORTENED (FR-53/AD-35/AD-22) ─────────────────────────
    _p("store-has-one-door", "FR-53", "AD-35", "every writing store is journalled",
       continuity.the_store_has_one_door,
       "every SqlStore(...) construction across apx/** — the head journal is what makes a "
       "truncation detectable, and the worker and both provisioning commands built the store "
       "without it"),
    _p("continuity-claim-is-derived", "FR-53", "AD-33",
       "the continuity claim is derived from the document",
       continuity.the_continuity_claim_is_derived_from_the_document,
       "every recomputable_from_this_document= keyword across apx/** — the flag asserts a property "
       "of the READER's bytes and used to be handed over carrying a fact about the database"),
    _p("audit-write-never-swallowed", "FR-53", "AD-22",
       "an audit write failure is never swallowed",
       continuity.an_audit_write_failure_is_never_swallowed,
       "every try/except around an _append_audit call across apx/** — a handler that logs and "
       "continues is the unaudited mode AD-22 forbids by name"),
    # ── story 7.1: the ingestion boundary (FR-1 / C1) ────────────────────────────────────────
    _p("filesystem-has-one-walk", "FR-1", "AD-33", "the filesystem has one walk",
       traversal.the_filesystem_has_one_walk,
       "every rglob/glob/iterdir/walk/scandir/listdir call across apx/** — the confined walk is "
       "where the submitted subtree's boundary is applied, and the route validated a "
       "caller-supplied absolute path with is_dir() before handing it to a second traversal"),
    # ── story 7.2: the backup is complete by construction (AD-32 / C2) ───────────────────────
    _p("backup-plan-is-total", "FR-52", "AD-32", "a tenant backup's coverage is total over the "
       "model",
       backup_completeness.the_backup_plan_is_total,
       "every table in the live SQLAlchemy metadata against the derived backup plan and its "
       "written exclusions — the hand-written tuple this replaces named 20 of 35 tables, had "
       "been added to by three separate stories, and a list cannot be reviewed for what is "
       "not in it"),
    # ── story 7.3: the ranking act gets a caller, and names what ran (AD-23 / C4) ────────────
    _p("ranking-identity-one-source", "FR-39", "AD-23", "the ranking identity has one source",
       ranking_identity_source.the_ranking_identity_has_one_source,
       "every RankingIdentityInputs construction across apx/** (one composer only) + every call "
       "passing model_provider/model_endpoint/model_name as a config key outside the module that "
       "composes the judge — configuration records a PREFERENCE, and this deployment silently "
       "composes the deterministic criteria judge whenever no LLM credential is present"),
    # ── story 7.4: the queue is opened by whoever defers onto it (AD-6) ──────────────────────
    _p("defer-opens-the-queue", "FR-2", "AD-6", "nothing defers onto a queue it has not opened",
       queue_open.every_defer_opens_the_queue,
       "every function in the sealed queue package that calls defer/defer_async — each must open "
       "the queue first. open_async lived in `manage worker` alone, a DIFFERENT process, so the "
       "API deferred onto a pool that did not exist and answered 503 to every upload on every "
       "real deployment; the suite runs on SQLite, whose in-memory connector is the one "
       "implementation with no such guard"),
    _p("override-ground-named", "FR-25", "AD-33", "an override names its FR-25 ground",
       override.override_names_its_ground,
       "the act catalogue (every override names one of FR-25's three grounds; the override class "
       "has a writer) + any comparison against the override act CLASS across apx/** — a pin is an "
       "override whose class is 'pin', so a class-based count reports zero on a matter with forty"),
    # ── story 5.4: the SENTENCE — one composer, offline, and the unfitness declaration ─────────
    _p("statement-one-composer", "FR-23", "AD-37", "the sentence has one composer",
       statement.the_sentence_has_one_composer,
       "confidence-bound wording in runtime string literals + apx/web/src — the sentence is "
       "composed only in core/domain/statement.py, never re-assembled by a reader or the client"),
    _p("statement-composed-offline", "FR-55", "AD-4", "the sentence is composed offline",
       statement.the_sentence_is_composed_offline,
       "the transitive import closure of core/domain/statement.py — Domain-only, no networking "
       "module, and the composer must exist and export statement_fr"),
    _p("unfitness-offers-no-line-move", "FR-23", "AD-33", "an unfit ranking offers no line move",
       statement.unfitness_offers_no_line_move,
       "core/domain/statement.py (never names the re-line offer), api/app.py (ships unfit_fr), and "
       "apx/web/src line-move sites (vacuous until Story 4.9's surface lands)"),
    # ── story 2.7: the inventory guarantee — the denominator record, unknown never summed ──────
    _p("inventory-record-fields", "FR-6", "AD-38", "the inventory record has exactly seven fields",
       inventory_record.inventory_record_fields_enumerated,
       "Inventory fields in core/domain — seven since Story 5.6 added the identity's third term, "
       "overridden_register_entries (a register entry closed by decision, never in the corpus)"),
    _p("unknown-cardinality-never-summed", "FR-6", "AD-38", "unknown cardinality never summed",
       inventory_record.unknown_cardinality_never_summed, "'+' operands across apx/**"),
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
