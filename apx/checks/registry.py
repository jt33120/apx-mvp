"""The check registry — the single list the runner executes and the manifest checks against.

Extracted from ``__main__`` (story 1.12) so ``apx.checks.manifest`` can compare the manifest to the
LIVE registry by function identity without importing the runnable ``__main__`` module. Appending a
check here is one of the two edits a new structural property needs; the matching manifest row (and
its README line) is the other, and the meta-checks fail the build if the two ever drift apart.

Each entry names its pattern and the AD it enforces (AD-33). Later stories append; they do not
rewrite the runner. Green on the empty tree; a dropped or broken contract fails the build.
"""

from __future__ import annotations

from collections.abc import Callable

from apx.checks import (
    artefact_stamp_ownership,
    audit_record,
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
    manifest,
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
    triage_sets_one_derivation,
    truth_status,
    truth_status_surface,
    user_actions,
    validation,
)
from apx.checks.import_contracts import CheckResult

# The registry. Each entry names its pattern and the AD it enforces (AD-33). Kept in lock-step with
# `apx.checks.manifest.PROPERTY_MANIFEST` by the manifest meta-checks (a drift fails the build).
CHECKS: list[Callable[[], CheckResult]] = [
    import_contracts.run,
    # story 1.3 — the frozen payload schema (AD-9, AD-40, AD-7).
    payload_schema.one_chunk_writer,
    payload_schema.scope_arg_required,
    payload_schema.chunk_columns_enumerated,
    payload_schema.no_custodian_or_scope_column_on_piece,  # story 2.5 — CUSTODIAN_LINK (AD-9)
    payload_schema.no_cascade_delete,
    # story 1.4 — tenant isolation at the boundary (AD-12).
    tenant_isolation.tenant_not_null_on_owned_tables,
    tenant_isolation.scoped_access_carries_tenant,
    tenant_isolation.identity_is_tenant_qualified,
    # story 1.5 — owned auth (AD-15).
    credential_storage.no_reversible_credential_storage,
    credential_storage.jwt_decode_pins_algorithms,
    # story 1.6 — grant-time authorisation (FR-49).
    scope_admin.scope_mutations_are_audited,
    # story 1.7 — encryption at rest & a fail-closed start (AD-31).
    encryption.sensitive_columns_are_encrypted,
    encryption.startup_gate_is_fail_closed,
    # story 1.8 — secret & key management (AD-47/FR-51).
    secrets.no_secret_in_source,
    secrets.no_secret_column_in_models,
    # story 1.9 — configuration-as-data & the provisioning surface (AD-24/AD-25).
    configuration.no_tenant_conditional_in_core,
    configuration.config_defaults_preserve_guarantees,
    configuration.documented_config_keys_exist,
    configuration.config_reference_is_complete,
    # story 1.10 — the content-free projection primitive (AD-26/FR-31).
    projection.projection_emitted_only_by_registry,
    projection.snapshot_fields_are_content_free,
    projection.projectors_declare_attestation,
    # story 1.12 — the structural-properties harness: real-now checks (AD-16/AD-45/AD-24).
    isolation_harness.no_runtime_import_from_tests,
    isolation_harness.no_fixture_path_in_runtime,
    isolation_harness.no_egress_call_site_outside_adapters,
    isolation_harness.no_tenant_identifier_in_source,
    # story 2.2 — the resumable import job: the queue is sealed behind one submodule (AD-17).
    isolation_harness.no_queue_import_outside_submodule,
    # story 2.3 — extraction runs out-of-process & licence-isolated (AD-28).
    isolation_harness.no_extract_msg_import_outside_worker,
    isolation_harness.no_subprocess_call_outside_extraction,
    isolation_harness.extraction_subprocess_captures_stderr,
    # story 1.12 — forward-looking checks: live, vacuous now, fixture-proven (FR-9/10/14/…/23).
    forward_looking.embedder_has_one_implementation,
    forward_looking.destructive_index_ops_single_entry,
    forward_looking.no_post_filter_in_retrieval,
    forward_looking.no_natural_language_translation_key,
    forward_looking.no_hardcoded_locale,
    forward_looking.no_model_reported_confidence,
    forward_looking.no_banned_confidence_phrasing,
    gold_gate.ranking_code_requires_the_gold_gate,
    # story 2.13 — the perf-ceiling gate: no invented latency/throughput ceiling before the timed
    # 5000-pièce run is measured (NFR-2). Vacuous until such a ceiling is declared.
    perf_gate.no_perf_ceiling_before_measurement,
    # story 3.1 — the constant-truth-status gate: no config can forge an exhaustive label (AD-20).
    truth_status.truth_status_is_constant_per_engine,
    # story 3.2 — the no-truncation gate: an exhaustive set is never truncated (AD-20).
    no_truncation.exhaustive_engine_takes_no_limit,
    # story 3.3 — the single-read-path gate: scope is a query pre-filter, never a post-filter, and
    # tenant-content queries are constructed only in the one read path (AD-13/AD-14).
    read_path.tenant_reads_have_one_entry_point,
    read_path.scoped_read_puts_scope_in_the_query,
    read_path.corpus_read_takes_no_admin_bypass,
    # story 3.4 — the truth-status SURFACE gate: a result-set response serialises its status, and
    # the two engines are never combined into one list (FR-15).
    truth_status_surface.result_set_response_serialises_truth_status,
    truth_status_surface.no_response_merges_the_two_engines,
    # story 3.5a — the pièce viewer foundation: retained originals are encrypted at rest (AD-31).
    originals_encrypted.originals_are_encrypted_at_rest,
    # story 3.5c-2 — the render-sanitisation gate: office renders emit only sanitised HTML (AD-29).
    renders_sanitized.rendered_html_is_sanitized,
    # story 2.6 — the failure register: one owning module per state transition (AD-37).
    register_ownership.register_state_written_once,
    # story 4.1 — the case theory: the version table is append-only, one owning module (AD-37/AD-7).
    case_theory_ownership.case_theory_version_is_append_only,
    # story 4.3 — the ranked order: the version/entry tables are append-only, one owner
    # (AD-37/AD-7);
    # no table or column names a retained/discarded set — those are views (AD-39).
    ranking_ownership.ranking_version_is_append_only,
    ranking_sets_are_views.no_retained_or_discarded_set_column,
    # story 4.4 — confidence is derived by one implementation, never self-reported (FR-42/AD-19).
    confidence_derivation.confidence_has_one_derivation,
    # story 4.5 — per-pièce taxonomy labelling: the ledger is append-only, one owner (AD-37/AD-7);
    # the ranked order has no dependency on the label axis — a label never moves a pièce or the line
    # (FR-40/FR-43/AD-39).
    taxonomy_label_ownership.taxonomy_label_is_append_only,
    label_not_a_ranking_input.ranking_order_ignores_the_taxonomy_label,
    # story 4.7 — the retained/discarded sets are a single derived view, never a stored membership
    # (FR-16/AD-39).
    triage_sets_one_derivation.triage_sets_have_one_derivation,
    # story 4.8 — the line the tool draws: stored by the last-retained-pièce identity, never a bare
    # integer (FR-17); its placement ledger is append-only, one owner (AD-37/AD-7).
    line_stored_by_piece_identity.line_is_stored_by_piece_identity,
    line_placement_ownership.line_placement_is_append_only,
    # story 4.9 — the priced move is a projection from the ranking, never the sampling bound
    # (FR-19/§0.2).
    line_projection_not_a_bound.line_projection_is_not_a_sampling_bound,
    # story 4.11 — the pin: its ledger is append-only, one owner (AD-37/AD-7); the ranked order has
    # no dependency on the pin axis — a pin never reorders (FR-43/AD-39).
    pin_ledger_ownership.pin_ledger_is_append_only,
    pin_not_a_ranking_input.ranking_order_ignores_the_pin,
    # story 4.6 — the justification derived from named evidence: its checkable part is the NAMED
    # evidence, never the sentence alone (FR-41); the read seam containment-verifies every extract
    # at show time, so an unresolved extract is unverified, never ordinary (FR-11/FR-41).
    justification_names_its_evidence.justification_names_its_evidence,
    justification_verified_at_show_time.justification_verified_at_show_time,
    # story 4.12 — never hard-delete, proven by a bounded probe: the enumerated registry of
    # user-reachable actions the probe walks is complete both ways, and an act a user could read as
    # deletion declares itself and names its reversal (FR-21/FR-56/AD-7).
    user_actions.user_action_registry_is_complete,
    user_actions.deletion_shaped_actions_declare_their_reversal,
    # Story 4.13 — freshness and staleness of derived artefacts (FR-58/AD-23/AD-40).
    staleness_triggers.every_staleness_trigger_has_an_observable,
    freshness_never_time_based.freshness_is_never_time_based,
    artefact_stamp_ownership.artefact_stamp_is_append_only,
    # Story 5.1 — the sampling run over the DERIVED discarded set (FR-22/AD-39/AD-23/AD-7).
    sampling_population.sampling_population_is_the_derived_view,
    sampling_freeze.a_sampling_run_freezes_its_identifiers,
    no_legacy_bound.no_new_legacy_bound_is_written,
    # Story 5.2 — OQ-4's five answers, one check each (FR-22/FR-23/FR-38/FR-42).
    estimator.piece_figure_is_a_worst_case,
    estimator.a_census_states_no_bound,
    estimator.one_run_one_bound_chosen_by_recency,
    estimator.the_bound_is_computed_from_the_freeze,
    estimator.the_bound_consumes_no_model_number,
    # Story 5.3 — the simulation gate: "proven" is un-writable without the proof running (FR-23).
    estimator.the_simulation_gate_is_wired,
    # Story 5.4 — the SENTENCE: one composer, composed offline, and an unfit ranking that offers a
    # re-rank rather than a re-cut (FR-23/FR-55/FR-56).
    audit_record.audit_catalogue_is_complete,
    audit_record.audit_sequence_is_not_generated,
    audit_record.audit_record_is_append_only,
    # Story 5.6 — the OVERRIDE: one validator for "mandatory", the reason verbatim in the record,
    # and a classification counted by its ground and never by its act class (FR-25).
    override.override_reason_has_one_validator,
    override.override_reason_reaches_the_record,
    override.override_names_its_ground,
    # Story 5.7 — the matter export: the tier is never chosen for the caller, and a section whose
    # act does not exist yet is a sentence naming its story, never a zero (FR-26).
    matter_export.export_tier_is_never_defaulted,
    matter_export.a_pending_section_is_not_a_zero,
    # Story 5.8 — the VALIDATION ACT: an acceptance has one origin and it is a human gesture, the
    # opened fact is read rather than asserted, and nothing manufactures either (FR-45/FR-44).
    validation.only_the_validation_act_accepts,
    validation.the_opened_fact_is_never_a_literal,
    validation.acceptance_is_never_manufactured,
    # ── story 5.9: the record cannot be SHORTENED (FR-53/AD-35/AD-22) ──
    continuity.the_store_has_one_door,
    continuity.the_continuity_claim_is_derived_from_the_document,
    continuity.an_audit_write_failure_is_never_swallowed,
    statement.the_sentence_has_one_composer,
    statement.the_sentence_is_composed_offline,
    statement.unfitness_offers_no_line_move,
    # story 2.7 — the inventory guarantee: the denominator record, unknown never summed.
    inventory_record.inventory_record_fields_enumerated,
    inventory_record.unknown_cardinality_never_summed,
    # story 1.12 — the manifest meta-checks: the harness checks ITSELF (AD-33/FR-56).
    manifest.every_structural_property_has_a_registered_check,
    manifest.every_registered_check_is_in_the_manifest,
    manifest.verbs_are_not_conflated,
    manifest.floor_of_13_has_a_structural_check,
    manifest.manifest_matches_readme,
    manifest.readme_lists_every_property,
]
