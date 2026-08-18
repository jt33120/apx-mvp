---
baseline_commit: 8504bf7
---

# Story 7.3: The ranking act gets a caller, and it names what ran

Status: done

## Story

As **a firm whose whole triage stands on one ranked order**,
I want the act that produces that order to be performable, and to record honestly which machinery
produced it,
So that twenty-two shipped stories stop standing on something nobody can do, and the *ranking
version* a *bâtonnier* reads is a fact rather than a plausible-looking configuration dump.

## Why this story exists

The B3/B4 audit, action item **C4** — filed *BLOCKING PLANNING*, and correctly so.

> the ranking act has no production caller. `apx/api/app.py` has ZERO references to
> `produce_ranking`, `record_ranking` or `run_cascade`; 8 test files call it. No HTTP route, no
> worker job, no manage command creates a *ranking version*.

A nine-agent reconnaissance over the act and its neighbours found the hole is **larger than C4 as
filed**, and the difference changes the shape of the work rather than its size:

**Seven Epic-4 acts have no HTTP surface, not one.** `apx/api/app.py` has 67 routes and none of them
reaches `produce_ranking`, `place_line`, `price_line_move`, `move_line`, `pin_piece`, `remove_pin` or
`record_justification`. Epic 5's routes exist and answer `404 — pas de classement, pas de ligne`:
their precondition can never be created, so the *sampling run*, the estimator, the *confidence
bound* and the *validation act* are all unreachable in production for the same one reason.

**A ranking route shipped alone would make the product worse.** A second ranking supersedes the
committed line (the live line is read off the latest version only), the worklist deliberately emits
no offer for a superseded artefact, and there is no route to place a line again — so a successful
re-rank leaves a *matter* with an order, no cut, an empty worklist, a drawer asserting *« aucune
justification »* for every *pièce*, and one surviving offer (*« Ré-échantillonner »*) that 404s.

**AD-6 names ranking by name.** *"Any operation whose cost scales with the size of a matter is a
queued job. The HTTP layer validates, authorises, enqueues and returns."* The cascade is one model
call per uncertain *pièce*. A synchronous route would be against the spine's most-cited decision,
and there is no ranking job ledger to enqueue onto.

So this story builds **the act's first honest caller** — an operator command — and story **7.4**
builds the lawyer's gesture on top of it (the queued job, the HTTP surface, the client, the line and
pin controls). The command is a strict prefix of the gesture: every hard part below is the part the
gesture would have had to solve anyway.

### The part that was not obvious: the identity was going to lie

The *ranking version* is an immutable fingerprint over how an order was produced, printed on the
header a lawyer reads and hashed into the value that decides whether two orders are the same
ranking. Every field is a permanent factual claim, and the obvious sources were wrong:

- **`temperature` and `sampling` had no source at all.** The temperature was a literal `0` inside
  the LLM adapter's private request body, exposed nowhere, and the live request sends **no sampling
  parameter of any kind** — so the `sampling={"top_p": 1.0}` that every fixture in the repository
  passed was pure invention, waiting to be copied into production.
- **`model_provider` / `model_endpoint` / `model_name` are configuration-as-data**, and
  configuration records a *preference*. This deployment composes the bare deterministic
  `CriteriaJudge` whenever no LLM credential is in the environment, and substitutes
  `LLM_BASE_URL`/`LLM_MODEL` whenever a tenant's value equals the schema default. A
  config-sourced identity would therefore have recorded *mistral-small-latest @ api.mistral.ai,
  temperature 0, top_p 1.0* over an order decided entirely by a comma-splitting keyword matcher —
  and FR-39's promise that a fixed *ranking version* reproduces the same order would have been
  asserted against a model that never ran.

## Acceptance Criteria

**AC-1 — the act has a caller.** `python -m apx.manage rank --tenant … --matter … --actor …
--scope …` produces one ranked order and mints its *ranking version*, through the real
`produce_ranking`, sourcing every input from the deployment rather than from a literal.

**AC-2 — the population is the *matter*.** The cascade's units are every *pièce*, with the chunk
ids stage 3 draws its extract from — never `representatives()`, which has already collapsed
near-duplicates and dropped the members.

**AC-3 — the identity names what ran.** Each judge reports its own `JudgeIdentity`, and the
identity's model half comes from the judge that was composed. A run with no credential records the
criteria judge, its rule version, and an **empty** sampling map.

**AC-4 — one source, held by a check.** `RankingIdentityInputs` is built in exactly one place, and
the model-identity config keys are read only where the judge is composed. A structural check states
both, and fails closed when it cannot find the door it guards.

**AC-5 — the wall comes first.** The act refuses a *matter* the caller does not hold **before
anything is read**, because `read_case_theory` answers `None` for out-of-scope and for absent
alike, and a `None` theory is also how the act says *rank on intrinsic signals*.

**AC-6 — the line can be placed.** `manage place-line` draws and commits the line over the latest
*ranking version*, so a ranked *matter* is one the product can finish reasoning about.

## Tasks / Subtasks

- [x] T1 — `JudgeIdentity` on the domain and the port; each adapter reports its own (AC-3).
- [x] T2 — `apx/wiring.py`: one composition site for the judge, moved out of `api/app.py` (AC-3/4).
- [x] T3 — `core/app/rank.identity_inputs`: the one composer (AC-4).
- [x] T4 — `SqlStore.cascade_units` + `SqlStore.semantic_scorer` (AC-2).
- [x] T5 — `manage rank` and `manage place-line` (AC-1, AC-5, AC-6).
- [x] T6 — the `ranking-identity-one-source` check, registered in the three lockstep sites (AC-4).
- [x] T7 — tests: the act, the population, the identity, the wall, the line, the check's legs.

## Dev Agent Record

### Completion Notes

**The judge answers for itself.** `Judge` grew an `identity: JudgeIdentity` — provider, endpoint,
model, temperature, sampling. `CriteriaJudge` reports `criteria / local:criteria /
criteria-terms-v1`, and that rule version is new: this judge **promotes a pièce to RELEVANT with no
model call at all**, so an order it decided is reproducible only against the rule that decided it.
`LLMJudge` reports the endpoint and model it was built with and the temperature it actually sends
(now a parameter rather than a literal in the request body), with an **empty** sampling map — the
true answer, and a different fact from *nobody recorded one*. `CascadeJudge` names **both** deciders,
because an identity naming only the LLM would attribute to a model the very verdicts it never saw.

`endpoint` is non-blank even for a local judge (`local:criteria`), because AD-23's identity has no
optional fields: *no endpoint* and *an endpoint nobody recorded* must not be the same value.

**One door for the judge.** The factory moved from `api/app.py` to `apx/wiring.py`. It was fine
while the API was the only process that judged; it stopped being fine the moment *which judge was
built* became a recorded fact.

**`cascade_units` is not `representatives`.** The difference is not an optimisation. Stage 1 does its
own grouping and emits an `exact-duplicate-member` REJECTED row per member so it stays **in** the
recorded order (AD-36); `representatives` has already collapsed them and dropped the members. On a
thousand-*pièce* *matter* collapsing to a hundred texts, feeding representatives would have made
nine hundred documents that were in the dossier **before** the ranking read as *arrivées après ce
classement* — and it would have redefined SM-18 underneath its own docstring, since `stage3_share`
divides by `len(units)` and is meant to be the share of the *matter*, so the cost figure a firm bids
from would read 1.0 where it is 0.1.

**The scorer is composed by the store, not by reaching into it.** `SqlStore.semantic_scorer(embedder)`
returns the `PgSemanticScorer` — a factory rather than a public session factory, because the
alternative (`store._sf` from the composition root) is a test-only idiom and would put the store's
internals in the runtime tree.

**The wall gate comes first, and the reason is a conflation.** `read_case_theory` returns `None` for
out-of-scope and for absent alike (FR-14, non-disclosing), and `run_cascade` decides the basis from
the truthiness of the theory string alone. So *any* reason the caller hands it `None` — including
never having been allowed to read it — produces a complete, successful, permanently fingerprinted
**intrinsic** ranking whose header names a deliberate methodology. `produce_ranking` forwards
`scopes` only to the scorer, and the scorer is skipped entirely on the intrinsic path, so `scopes`
is dead there; `record_ranking` takes none at all and checks only that the *matter* row exists. The
act does not fail closed on its own, and the command says so in a comment rather than assuming it.

### Review

Run in-session across the three standing lenses, on top of a nine-agent reconnaissance whose
findings are cited above. **Coverage stated rather than implied**: the fleet mapped, one reviewer
adjudicated.

**The wrong referent** — the fleet named five candidates before a line was written; three were about
this diff and all three are closed by construction: the units (population vs representatives), the
model identity (what ran vs what is configured), and the theory (*no theory* vs *not allowed to
read one*). Two are **not** closed and belong to 7.4, filed below: the freshness stamp computed at
commit time over a population the cascade never saw, and the embedder/chunking identity read from
*now* rather than from the rows.

**The seams** — the check's config-read leg was rewritten during review. The first draft matched any
string literal equal to a model key and flagged nine sites, every one of them legitimate: the config
schema *declaring* the keys, the identity dataclass's own *field names*, and the check module
itself. That is a check on a shape, and it is the kind that gets weakened. It matches a **call**
passing the key now — `get_config(t, "model_name")` — with the declaration site and the checks tree
named as what they are.

**Which decision does this implement** — FR-39 clause 1 names two triggers, *user-initiated* **or**
*import-completion-triggered*; this story builds neither, it builds an operator command, and says so
rather than letting a CLI stand in for a gesture. Clause 5 (the per-*matter* review-effort estimate)
has no artefact anywhere and is untouched. Clause 6's worklist line for a failed ranking is
structurally unreachable — a `WorklistLine` is derived from a `Freshness` assessment of an artefact
that exists, and a failed ranking produced none.

### Found while building, not fixed here

**C11 — the Epic-4 write surface (story 7.4).** Seven acts with no HTTP route; the queued ranking job
AD-6 requires with its ledger and poll route; the client controls and the four states it cannot
render (no ranking, in flight, failed, superseded); the case-theory editing surface, without which
FR-23's remedy *« Reclasser avec une théorie du cas révisée »* is unreachable; `STALE_SUBJECT`
rendering the raw identifier `ranking_unfit` on a lawyer's screen; and the re-rank blast radius —
the superseded line with no remedy, `read_line_history` emptying §3 of the exported *matter* record,
and acceptances of the old version counted in force against the new one, unqualified.

**C12 — AD-6's idempotency rule is unimplemented product-wide.** *"An action listed in the AD-33
registry as state-changing and reachable without an idempotency key fails the build."* There is no
key store and no registry check; `grep idempotency apx/` returns only content-hash dedup comments.
This is not about this story's command — it is about every state-changing route already shipped.

**C13 — a judge outage is invisible.** `LLMJudge.judge` catches every exception and returns
UNCERTAIN, and `run_cascade` marks a *pièce* UNSCORED only when the judge **raises**. So AD-19's
unscored path is unreachable with the shipped adapter, and a total LLM outage reads as a *matter*
full of *uncertain* rather than as a failure. Four test files assert behaviour the production judge
cannot produce.

**The fitness driver still lists `rank` and `place the line` as PENDING** (`apx/fitness/driver.py`).
They are now performable, so the stages can be flipped to ASSERTED — deliberately left to 7.4, with
the gesture, so the frame asserts the path a user takes rather than the one an operator does.

### File List

- `apx/core/domain/ranking.py` — `JudgeIdentity`.
- `apx/core/ports/judge.py` — the port asks for it.
- `apx/adapters/judge/criteria.py` — `RULE_VERSION` + its identity.
- `apx/adapters/llm_openai_compat/judge.py` — temperature is a parameter; both judges report.
- `apx/wiring.py` — **new**: the one composition site for the judge.
- `apx/api/app.py` — delegates to it.
- `apx/core/app/rank.py` — `identity_inputs`, the one composer.
- `apx/adapters/store_postgres/store.py` — `cascade_units`, `semantic_scorer`.
- `apx/manage.py` — `rank`, `place-line`.
- `apx/timedrun/harness.py` — the stub judge says it is a stub.
- `apx/checks/ranking_identity_source.py` — **new**, registered in the three lockstep sites.
- `tests/test_rank_command.py` — **new** (13).
- `tests/checks/test_ranking_identity_source.py` + fixtures — **new** (5).
- `tests/api/test_judge_config.py`, `tests/adapters/test_llm_judge.py` — re-pointed at the one door.

### Change Log

| When | What |
|---|---|
| 2026-08-18 | Written from C4 after a nine-agent reconnaissance; implemented; gate green at 107 checks / 2 191 tests. |
