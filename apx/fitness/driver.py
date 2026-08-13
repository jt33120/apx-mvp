"""The end-to-end fitness driver (FR-55, AD-2).

Enumerates the FR-55 pipeline as stages. Each stage is either **ASSERTED** (the
capability exists and is checked here) or **PENDING** with its owning story (it
does not exist yet). The driver runs every ASSERTED stage and fails on
regression; it prints the PENDING stages and the model-degradation list from the
same source of truth. **It never marks a PENDING stage green** — faking a stage
would be the v1 "demo-shaped" failure in miniature.

A stage becomes ASSERTED in the story that builds it, and only for the half this
frame can actually reach: the frame runs with no network and no database, so a
capability whose proof needs either states which half it asserts and leaves the
other to the adapter tests and the CI ``db`` job. Reading the enumeration below
is the only way to know what is green today — this docstring deliberately does
not keep a copy that could drift out of date.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass, replace

ASSERTED = "ASSERTED"
PENDING = "PENDING"


@dataclass(frozen=True)
class Stage:
    name: str
    story: str
    state: str
    needs_model: bool = False
    invariant: str = ""
    check: Callable[[], None] | None = None  # raises on failure; only for ASSERTED


def _app_boots() -> None:
    """The FastAPI app imports and constructs — the 'start' stage."""
    from fastapi import FastAPI

    from apx.api.app import app

    assert isinstance(app, FastAPI), "apx.api.app.app is not a FastAPI application"


def _checks_pass() -> None:
    """Every registered structural-property check holds — the 'checks-green' stage. Runs
    the same registry as ``python -m apx.checks`` so a new guard (story 1.3's payload-schema
    checks included) is part of the fitness frame, not only the standalone runner."""
    from apx.checks.registry import CHECKS

    failed = [r for r in (check() for check in CHECKS) if not r.ok]
    assert not failed, "structural checks failed: " + "; ".join(
        f"{r.name} ({r.ad})" for r in failed
    )


def _schema_frozen() -> None:
    """The frozen payload schema is defined (story 1.3): the ``piece``, ``chunk`` and
    ``matter_scope`` tables exist and ``chunk`` carries no scope/custodian column. This is
    the offline, static half of AC7 — the migration that creates them in a *real* database
    is exercised by the CI ``db`` job (``alembic upgrade head``), which this frame does not
    reach (it runs with no database)."""
    from apx.adapters.store_postgres.models import Base

    tables = set(Base.metadata.tables)
    for required in ("piece", "chunk", "matter_scope"):
        assert required in tables, f"the frozen schema is missing the {required!r} table"
    chunk_cols = {c.name for c in Base.metadata.tables["chunk"].columns}
    forbidden = {c for c in chunk_cols if "scope" in c.lower() or "custodian" in c.lower()}
    assert not forbidden, f"chunk carries a forbidden scope/custodian column: {forbidden}"


def _estimator_proven_sound() -> None:
    """The estimator covers the truth at its stated confidence, offline (story 5.3, FR-23/SM-1).

    The runtime counterpart of the static ``estimator-simulation-gate``: the check asserts the proof
    EXISTS and runs, this asserts it PASSES — and it passes here, inside the offline frame, with no
    network and no database, because a statistical claim must never depend on either (FR-55/FR-36).

    A failure here is not a reason to adjust the statistic until it goes green. It is the reason
    ``ESTIMATOR_PROVEN`` exists: the product falls back to counts only and states no bound."""
    from apx.core.domain.confidence import ESTIMATOR_PROVEN
    from apx.eval.estimator_simulation import SCENARIOS, run_all, unsound

    if not ESTIMATOR_PROVEN:
        return  # counts-only is an honest state; nothing to prove
    verdicts = run_all()
    failed = unsound(verdicts)
    assert not failed, (
        "the estimator does NOT cover at its stated confidence: "
        + ", ".join(f"{v.scenario} (families lower-bound {v.family_coverage_lower:.4f}, pièces "
                    f"{v.piece_coverage_lower:.4f}, target {v.target})" for v in failed))
    # Soundness alone is satisfiable by an estimator answering "at most all of them" — CONFIRMED by
    # the review, which noted this stage asserted the floor and not the ceiling, so a vacuous
    # estimator reached the fitness frame green.
    ceilings = {s.name: s.tightness_ceiling for s in SCENARIOS}
    vacuous = [
        v for v in verdicts
        if ceilings.get(v.scenario) is not None
        and v.best_prevalence_upper > ceilings[v.scenario]]
    assert not vacuous, (
        "the estimator covers but states nothing useful: "
        + ", ".join(f"{v.scenario} ({v.best_prevalence_upper:.3f} at zero found)"
                    for v in vacuous))


def _the_sentence_renders_offline() -> None:
    """The *confidence bound* sentence renders here, in the offline frame (story 5.4, FR-55/FR-23).

    FR-55 names this stage in as many words: *"the confidence bound sentence is regenerable from
    the audit record WITHOUT a model call — a statistical statement must never depend on a network
    call — and this is asserted here."* FR-36 makes machine-generated user-facing text
    model-produced; FR-55's own assumption note resolves the contradiction in favour of templated,
    locally rendered text, and ``needs_model`` is therefore False for this stage on purpose — the
    sentence LEAVES the degradation list, which is the whole point of the requirement.

    It composes all four registers from flat inputs — no store, no clock, no provider — and asserts
    the two things a paste must carry: the wall, and the freshness state (FR-23/FR-58). A register
    that dropped either would still LOOK right on screen, where the panel says both; it is the
    copied string that would arrive without them."""
    from apx.core.domain.sampling import (
        KIND_BOUND,
        KIND_CENSUS,
        KIND_COUNTS_ONLY,
        KIND_NO_POPULATION,
    )
    from apx.core.domain.statement import StatementInputs, statement_fr

    unit = "familles de quasi-doublons écartées"
    common = dict(
        unit_fr=unit, population_units=1400, sample_units=200, relevant_units=0, confidence=0.95,
        piece_count=1400, scope="mur-a", freshness_fr="à jour")
    bound = statement_fr(StatementInputs(
        kind=KIND_BOUND, count_upper_units=21, prevalence_upper=0.015, count_upper_pieces=34,
        **common))
    census = statement_fr(StatementInputs(
        kind=KIND_CENSUS, relevant_pieces=0, **{**common, "sample_units": 1400}))
    counts = statement_fr(StatementInputs(kind=KIND_COUNTS_ONLY, **common))
    empty = statement_fr(StatementInputs(
        kind=KIND_NO_POPULATION, unit_fr=unit, population_units=0, sample_units=0,
        relevant_units=0, confidence=0.95))

    for name, sentence in (("bound", bound), ("census", census), ("counts_only", counts)):
        assert "mur-a" in sentence, f"the {name} sentence drops the RBAC scope (FR-23)"
        assert "à jour" in sentence, f"the {name} sentence drops its freshness state (FR-58)"
    # A census estimates nothing, so it never carries a percentage — §0.2 with better arithmetic.
    assert "%" not in census and "%" not in counts
    assert "%" in bound, "the bound register states a prevalence — that is what a sample bounds"
    # An empty discarded set is its own statement, never a flattering zero.
    assert "0" not in empty and "aucune borne" in empty.lower()
    # A bound whose wall was never recorded STATES that, rather than dropping the clause: the
    # review found the "named unconditionally" decision implemented as `if inputs.scope`, so a
    # legacy row's copied sentence said nothing at all about whose walls the number was counted
    # under. An absence of evidence is stated here exactly as an unstamped freshness is.
    unwalled = statement_fr(StatementInputs(
        kind=KIND_BOUND, count_upper_units=21, prevalence_upper=0.015,
        **{**common, "scope": None}))
    assert "périmètre non enregistré" in unwalled, (
        "a bound with no recorded wall must SAY so, never drop the clause (FR-23)")
    # A positive bound never renders as a zero share: two numbers in one parenthesis, one of them
    # false in the flattering direction, is §0.2 re-created by a format specifier.
    tiny = statement_fr(StatementInputs(
        kind=KIND_BOUND, count_upper_units=3, prevalence_upper=3 / 8000,
        **{**common, "population_units": 8000, "sample_units": 4217, "piece_count": 8000}))
    assert "0.0%" not in tiny, "a positive bound rendered as a zero percentage (FR-23/§0.2)"


def _the_record_verifies_offline() -> None:
    """The audit record's chain recomputes from the entries alone (story 5.5, FR-24/FR-53/AD-43).

    This is the offline half, on the ``_schema_frozen`` precedent. WRITING an entry allocates its
    sequence from a head row taken under ``SELECT … FOR UPDATE`` and needs a database, which this
    frame does not have; that half is exercised by the adapter tests and the CI ``db`` job. What
    is asserted here is the half the *bâtonnier* actually performs — recomputing a chain from the
    bytes in front of them, holding ONE matter's entries and nothing else.

    What is deliberately NOT claimed: a tail truncation. Dropping the last entries leaves a
    shorter chain that recomputes perfectly, and no reader can tell from the export alone. That is
    what the head journal outside the restorable store is for (AD-35) and what story 5.9 puts on
    the export's face. Asserting it here would be this project's recurring defect — a comparison
    whose right-hand side is not the same thing as its left, failing towards the flattering side.
    """
    from apx.core.domain import audit

    # The catalogue is a mechanism, not a list: every FR-24 class has a writer, or a story that
    # owns it. A class with neither is a hole that reads as coverage.
    covered = audit.covered_classes()
    orphan = [c for c in audit.FR24_CLASSES
              if c not in covered and c not in audit.PENDING_CLASSES]
    assert not orphan, f"FR-24 act classes with no writer and no owning story: {orphan}"
    # No entry is ever attributable to nobody (AC-3): the one attribution the record must not carry
    # is the countable, filterable, defensible-looking one.
    for nobody in ("unknown", "system", ""):
        try:
            audit.check_actor(nobody)
        except audit.UnknownActor:
            continue
        raise AssertionError(f"the record accepted {nobody!r} as an actor (FR-24)")

    def _chain(scope: str, verbs: list[str], anchor: str = "") -> list[audit.VerifiableEntry]:
        rows: list[audit.VerifiableEntry] = []
        prev = anchor
        for seq, verb in enumerate(verbs, start=1):
            row = audit.VerifiableEntry(
                tenant="cabinet", chain_scope=scope, seq=seq, matter=scope or None,
                actor="Me Dupont", action=verb, detail=f"d{seq}",
                timestamp=f"2026-08-13T10:0{seq}:00+00:00", chain="",
                content_version=audit.CONTENT_V2, app_version="0.1.0", schema_version="1")
            prev = audit.chain_value(prev, audit.chained_content(
                version=row.content_version, seq=row.seq, tenant=row.tenant,
                chain_scope=row.chain_scope, matter=row.matter, actor=row.actor,
                action=row.action, detail=row.detail, timestamp=row.timestamp,
                app_version=row.app_version or "", schema_version=row.schema_version or ""))
            rows.append(replace(row, chain=prev))
        return rows

    verbs = [audit.ACT_INGEST, audit.ACT_PIECE_LABELLED, audit.ACT_LINE_PLACED]
    export = _chain("affaire-a", verbs)

    def _verdict(rows: list[audit.VerifiableEntry]) -> audit.ChainVerdict:
        (only,) = audit.verify_chains(rows, {"affaire-a": ""})
        return only

    clean = _verdict(export)
    assert clean.verified and clean.anchored, f"an untampered export failed at {clean.broken_at}"

    # a rewritten field — the correction the record forbids, made in place
    forged = replace(export[1], detail="corrected after the fact")
    tampered = _verdict([export[0], forged, export[2]])
    assert not tampered.verified and tampered.broken_at == 2, "a rewritten entry passed (FR-53)"

    # a gap — one entry removed from the middle
    gapped = _verdict([export[0], export[2]])
    assert not gapped.verified and gapped.broken_at == 3, "a missing entry passed (FR-53)"

    # a reordering — two acts swapped while their sequence numbers stay put
    swapped = _verdict([
        export[0], replace(export[1], action=export[2].action),
        replace(export[2], action=export[1].action)])
    assert not swapped.verified and swapped.broken_at == 2, "a reordering passed (FR-53)"

    # AD-43's whole point: another matter's entries are neither needed nor consulted. The same
    # export verifies identically beside a sibling chain and alone — which is what a per-TENANT
    # chain could not do, reporting a gap wherever a sibling matter had written in between.
    sibling = _chain("affaire-b", verbs, anchor="0" * 64)
    both = audit.verify_chains(export + sibling, {"affaire-a": "", "affaire-b": "0" * 64})
    assert [v.chain_scope for v in both] == ["affaire-a", "affaire-b"]
    assert all(v.verified for v in both), "two chains of one tenant did not verify independently"


# The pipeline. Order is the FR-55 sequence. `needs_model=True` marks a capability
# that does NOT survive the model provider's absence (the degradation list, AC4).
STAGES: list[Stage] = [
    Stage("start (app boots offline)", "1.1/1.2", ASSERTED, check=_app_boots),
    Stage("structural checks pass", "1.1/1.2", ASSERTED, check=_checks_pass),
    Stage("frozen payload schema defined", "1.3", ASSERTED, check=_schema_frozen),
    Stage("ingest a folder", "2.1", PENDING),
    Stage("index the corpus", "2.8", PENDING),
    Stage("retrieve over both engines", "3.1/3.2", PENDING),
    Stage("rank (relevance judgement)", "4.2", PENDING, needs_model=True),
    Stage("justifications", "4.6", PENDING, needs_model=True),
    Stage("place the line", "4.8", PENDING, needs_model=True),
    Stage(
        "the estimator is proven sound (simulation)",
        "5.3",
        ASSERTED,
        check=_estimator_proven_sound,
        invariant="soundness, not reproducibility — and no network, no database",
    ),
    Stage(
        "produce an audit record",
        "5.5",
        ASSERTED,
        check=_the_record_verifies_offline,
        invariant="verifiable by a reader holding ONE matter's entries and nothing else; the "
                  "write path needs a database and is not reached here",
    ),
    Stage(
        "confidence bound as a sentence",
        "5.4",
        ASSERTED,
        check=_the_sentence_renders_offline,
        invariant="regenerable from the record with NO model call — templated, never generated",
    ),
    Stage("export the retained set", "6.1", PENDING),
]


def run() -> int:
    failures = 0
    print("APX offline fitness — end-to-end pipeline")
    for stage in STAGES:
        if stage.state == ASSERTED:
            assert stage.check is not None
            try:
                stage.check()
                print(f"  [ASSERTED] {stage.name}")
            except Exception as exc:  # noqa: BLE001 — report any regression, do not crash
                failures += 1
                print(f"  [FAIL]     {stage.name}: {exc}")
        else:
            inv = f" — invariant: {stage.invariant}" if stage.invariant else ""
            print(f"  [PENDING {stage.story}] {stage.name}{inv}")

    # AC4: the model-degradation list is GENERATED from the stages, not described.
    degraded = [s.name for s in STAGES if s.needs_model]
    print("\nWithout the model provider, these capabilities do not survive:")
    for name in degraded:
        print(f"  - {name}")

    if failures:
        print(f"\n{failures} asserted stage(s) regressed.", file=sys.stderr)
        return 1
    asserted = sum(1 for s in STAGES if s.state == ASSERTED)
    pending = sum(1 for s in STAGES if s.state == PENDING)
    print(
        f"\nFitness frame green: {asserted} asserted, {pending} pending "
        "(grows with the pipeline)."
    )
    return 0
