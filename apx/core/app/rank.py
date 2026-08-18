"""The ranking act (Story 4.3, FR-39 / AD-23) — the explicit act that produces one ranked order.

A thin Application-layer orchestrator: run the 4.2 cascade, assemble the AD-23 ranking-version
identity from the caller's inputs, compute the pure deterministic order (`ranking.rank_cascade`),
and
persist it through the :class:`RankingRecorder` port. It imports Domain + Ports only (AD-4) and
touches no store. **A ranking that cannot be produced fails loudly** rather than emitting an
arbitrary
order (FR-39): an empty in-order set, or a missing identity input, raises — never a silent empty
artefact.
"""

from __future__ import annotations

from dataclasses import replace

from apx.core.app.cascade import run_cascade
from apx.core.domain.cascade import CascadeUnit
from apx.core.domain.config import CascadeConfig
from apx.core.domain.line import LinePlacementView
from apx.core.domain.ranking import (
    PROMPT_VERSION,
    JudgeIdentity,
    RankingIdentityInputs,
    RankingVersion,
    assemble_identity,
    rank_cascade,
)
from apx.core.ports.judge import Judge
from apx.core.ports.line import LinePlacementRecorder
from apx.core.ports.ranking import RankingRecorder
from apx.core.ports.scorer import SemanticScorer


def produce_ranking(
    units: list[CascadeUnit], *, case_theory: str | None, scorer: SemanticScorer, judge: Judge,
    config: CascadeConfig, inputs: RankingIdentityInputs, tenant: str, matter: str, actor: str,
    scopes: set[str], recorder: RankingRecorder,
) -> RankingVersion:
    """Run the cascade over ``units`` and record ONE deterministic ranked order against a freshly
    minted *ranking version* (FR-39). Returns the minted :class:`RankingVersion`. Raises
    ``ValueError`` when there is no *pièce* to rank (never an arbitrary/empty order) or a required
    identity input is blank; ``StaleRankingInput`` (from the recorder) when a recorded input changed
    under the act."""
    result = run_cascade(
        units, case_theory=case_theory, scorer=scorer, judge=judge, config=config,
        tenant=tenant, matter=matter, scopes=scopes)
    if not result.in_order:
        raise ValueError(
            "ranking: no pièce to rank — a ranking that cannot be produced fails loudly, never an "
            "arbitrary order (FR-39)")
    # the intrinsic path references no case-theory version — normalise the input so the identity
    # cannot carry a stale id the caller left in place (the case-theory basis keeps its id, and the
    # identity's own invariant rejects a case-theory basis with no id).
    resolved = inputs if result.basis == "case-theory" else replace(
        inputs, case_theory_version_id=None)
    identity = assemble_identity(
        inputs=resolved, basis=result.basis,
        uncertain_low=config.uncertain_low, uncertain_high=config.uncertain_high,
        calibration_sample=config.calibration_sample, stage3_max_share=config.stage3_max_share)
    order = rank_cascade(result, config)
    return recorder.record_ranking(
        tenant=tenant, matter=matter, actor=actor, identity=identity, order=order)


def identity_inputs(
    *, judge: JudgeIdentity, case_theory_version_id: str | None,
    embedder_model_id: str, embedder_model_version: str,
    chunking_config_version: str, schema_version: str,
) -> RankingIdentityInputs:
    """The **one** place a :class:`RankingIdentityInputs` is assembled (Story 7.3, AD-23).

    Story 4.3 left this to "a later surface story", and until then every construction site was a
    test fixture full of plausible literals — a model name, an endpoint, ``temperature=0.0``,
    ``sampling={"top_p": 1.0}``. Those literals are the danger: the identity is hashed into an
    immutable fingerprint and rendered on the header a lawyer reads, so an invented value is not a
    placeholder, it is a false statement about how an order was produced, recorded permanently.

    Two rules make that impossible here rather than merely discouraged:

    * **the model half comes from the judge that ran**, never from configuration — configuration
      records a preference, and this deployment silently substitutes a deterministic local judge
      whenever no LLM credential is present;
    * **there is one door**, so a second composer cannot grow somewhere else with a different set
      of literals. A structural check holds it (``ranking-identity-one-source``).

    The chunking and embedder halves are still the caller's, because they describe the *corpus*,
    not the act — and the caller is the only layer that knows which corpus it read.
    """
    return RankingIdentityInputs(
        case_theory_version_id=case_theory_version_id,
        model_provider=judge.provider,
        model_endpoint=judge.endpoint,
        model_name=judge.model,
        prompt_version=PROMPT_VERSION,
        temperature=judge.temperature,
        sampling=judge.sampling,
        embedder_model_id=embedder_model_id,
        embedder_model_version=embedder_model_version,
        chunking_config_version=chunking_config_version,
        schema_version=schema_version,
    )


def rank_and_draw_the_line(
    units: list[CascadeUnit], *, case_theory: str | None, scorer: SemanticScorer, judge: Judge,
    config: CascadeConfig, inputs: RankingIdentityInputs, tenant: str, matter: str, actor: str,
    scopes: set[str], recorder: RankingRecorder, placer: LinePlacementRecorder,
) -> tuple[RankingVersion, LinePlacementView | None]:
    """Produce a new *ranking version* **and** draw the tool's cut over it — one act, not two.

    A version with no placement leaves the *matter* **worse than before the re-rank**, and silently.
    The line in force is read over the *latest* version, so the previous placement reads superseded
    the instant version n+1 exists; a superseded artefact deliberately emits no *worklist* line; and
    the *worklist* has nothing it could honestly offer anyway — its own contract says a line names
    *the artefact the offer would supersede, never the artefact it would produce*, and a line that
    was never placed is neither. So the result would be an empty worklist over a *matter* where
    every ranked *pièce* has fallen into the unsplit set, no *sampling run* can start, and no
    *confidence bound* can exist.

    Drawing the cut needs no consent, and the codebase already says so: a first placement records
    ``priced_statement=None`` because *"a first placement is the tool drawing the cut, not a human
    move, so there was no price to show and none to record"*. The human act is **moving** the line
    (FR-19), and it is priced. What FR-17 does on version 1 is what this does on version n+1.

    **Two transactions, deliberately.** Each of ``record_ranking`` and ``place_line`` owns its own
    audited transaction, and a placement that fails must not roll back an order that cost one model
    call per uncertain *pièce*. ``None`` for the placement is a real answer, not a failure: no
    *pièce* in a retain band, and a line is never fabricated (AD-19).
    """
    version = produce_ranking(
        units, case_theory=case_theory, scorer=scorer, judge=judge, config=config, inputs=inputs,
        tenant=tenant, matter=matter, actor=actor, scopes=scopes, recorder=recorder)
    # Over the version JUST minted, named explicitly. Letting the placer resolve "the latest" would
    # be right by accident today and wrong the moment two acts overlap — and the failure direction
    # is the catastrophic one: a stamp whose line_seq belongs to another version reads FRESH.
    placement = placer.place_line(
        tenant=tenant, matter=matter, actor=actor, scopes=scopes, version_no=version.version_no)
    return version, placement
