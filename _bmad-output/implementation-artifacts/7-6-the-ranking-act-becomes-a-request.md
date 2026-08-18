---
baseline_commit: 9825b02
---

# Story 7.6: The ranking act becomes a request, and its cost is stated before it is paid

Status: done

## Story

**As** a lawyer holding a *matter*,
**I want** to ask the tool to classer the *matter* and to be told what that will cost me before it
starts,
**so that** the ranked order, the line, the *sampling run*, the *confidence bound* and the validation
act stop being unreachable — and so that an hour of judged verdicts is never destroyed by a gesture
that said nothing.

## Why this story exists

Retro action **C11** filed *"the Epic-4 WRITE surface"* as one item. A six-reader reconnaissance over
the substrate found it is **five stories**, and this is the first: the server half, provable by the
Python suite, the structural checks and the bounded probe.

**The split, and why each seam is a seam.** Recorded here so the next story does not have to
re-derive it.

- **A — this story.** The queued ranking job: ledger, task, enqueue-with-consent, poll, and the
  place-line remedy. Server only.
- **B — the gesture and its four states** (client, plus a case-theory editing surface). It cannot
  merge with A: the client has **no test runner** — `apx/web/package.json` declares none, CI runs
  `npm run build` only, and `noUnusedLocals` exempts exports. Every property in A is falsifiable by
  something this repository owns; no property in B is. Merging puts an unfalsifiable half inside a
  falsifiable one and the green build stops discriminating.
- **C — the worklist names its subjects and discharges its offers.** A precondition of B in exactly
  the sense 7.5 was a precondition of A: the FR-23 unfitness line has **no discharge condition**
  (`read_worklist` gates only on `bound.unfitness_fr is not None`), which is harmless today only
  because no re-rank control exists. The first story that ships a re-rank button ships an
  undischargeable banner.
- **D — FR-27's tenant worklist as an object.** Ten line generators named in the PRD, one with code.
- **E — C9: the bulk confirmation becomes reachable.** `BulkValidationConfirm` is complete, correct
  and imported by nothing; the fix is an import and a selection state, not a component.

Order: **A → C → B → E → D**.

### What is broken today

`apx/api/app.py` has 67 routes and **none** of them reaches `produce_ranking`, `place_line`,
`price_line_move`, `move_line`, `pin_piece`, `remove_pin` or `record_justification`. Epic 5's routes
exist and answer *« pas de classement, pas de ligne »* — their precondition cannot be created from
the product, only from an operator's shell (`manage rank`, story 7.3; `manage place-line`, 7.5).

**AD-6 names ranking by name as a queued job**, and there is no ranking job ledger. The HTTP layer's
job — validate, authorise, enqueue, return — has exactly one implementation in this codebase
(`ingest_upload`) and no ranking analogue.

### The cost nobody states (C17)

`_guard_open_run` is a **write** guard, with two callers, both writes. A new *ranking version* moves
`ranking_version_no`; `INPUTS_BY_KIND[KIND_SAMPLING_RUN]` is `_ALL`, so **every open run in the
matter is invalidated**. The lawyer discovers it on her *next* verdict, as a 409 — after which
`abandon_sampling_run` audits `verdicts_kept=` the count of the hour she just threw away. Nothing
warns before, and the shape of the warning already exists (`check_confirmed_count` /
`BatchSplit.sentence_fr`, FR-45(a)) as does the read (`read_sampling_runs`).

The warning belongs in the **enqueue handler**, not in the store: a write guard fires when the
cascade has already been paid for and can only refuse to commit, and putting it in the store would
make the operator command refuse too. AD-6 gives the HTTP layer exactly the validate-authorise-
enqueue job.

## Acceptance Criteria

- **AC1 (AD-6).** `POST /api/matters/{matter}/ranking` answers **202** with a job handle and the
  *matter*'s ranking is unchanged by the request. `apx/api/app.py` imports nothing from
  `apx.core.app.rank` — asserted over the source. (It does import `line.place_line`: placing a
  cut is a read and one insert, which is why story 7.5 could ship it as a synchronous command.
  AD-6 is about cost, not about layer.)
- **AC2 (AD-17).** `GET /api/rankings/{job_id}` answers from the application-owned `ranking_job`
  ledger and never from a Procrastinate table.
- **AC3 (AD-6 / story 7.4).** `enqueue_ranking` calls `ensure_open()` **in its own body**;
  `every_defer_opens_the_queue` reports two enqueue helpers where it reported one, and removing the
  call turns it red.
- **AC4 (AD-19).** The ledger has a terminal `failed` state carrying a French reason, and it is
  reachable without killing a worker: an enqueue that raises marks the job `failed` and still
  returns the handle — **never** a 503 over a permanent cause.
- **AC5 (FR-14 / AD-13).** Out-of-scope, absent and never-created answer identically: 404 on the
  preview, the enqueue and the poll.
- **AC6 (FR-45(a) / FR-22).** A re-rank over a *matter* with N open, not-yet-invalidated runs is
  refused **409** unless the request names N. The sentence names *« un nouveau classement »* and
  never the raw key `ranking_version_no`. The figure at risk is the same arithmetic
  `abandon_sampling_run` later audits as `verdicts_kept` — one per *family*, not one per row.
- **AC7 (FR-7 shape).** At most one open ranking job per *matter*, enforced by a partial unique
  index. A second request while one is open is refused **409** and is **never** handed the running
  job's handle.
- **AC8 (AD-23).** `version_no` is NULL at enqueue and filled only at completion; the poll answers
  `null` while in flight.
- **AC9 (FR-17 / story 7.5).** The task calls `rank_and_draw_the_line`, not `produce_ranking`. A job
  whose ranking committed and whose placement raised ends `failed` **with the minted version_no
  recorded**, and `POST /api/matters/{matter}/line` — `version_no` **required** — places the cut.
- **AC10 (AD-33 / FR-21).** Every new route has a `USER_ACTIONS` row and a probe `_Step`;
  `ranking_job` is **not** added to `TRANSIENT_TABLES`, so the probe forbids deleting a job row —
  which is what forces the mark-failed design.
- **AC11 (AD-4).** `_run_ranking` is store-typed and Procrastinate-free, driven directly against
  SQLite; `lint-imports` keeps all three contracts.
- **AC12 (AD-23).** The worker composes the judge through `apx.wiring.open_judge` and the identity
  through `rank.identity_inputs`; `the_ranking_identity_has_one_source` stays green.

## Tasks / Subtasks

- [x] T1 — migration `0038_ranking_job_ledger` + `RankingJob` model (AC7, AC8).
- [x] T2 — the store's ledger methods + `RankingJobView` (AC2, AC4, AC8).
- [x] T3 — `_run_ranking`, the `apx.run_ranking` task, `enqueue_ranking` (AC3, AC9, AC11, AC12).
- [x] T4 — `RerankCost`, `RerankCountMismatch`, `check_confirmed_runs` in the Domain (AC6).
- [x] T5 — `rerank_cost` read seam (AC6).
- [x] T6 — the preview route (AC5, AC6).
- [x] T7 — the enqueue route (AC1, AC4, AC5, AC6, AC7).
- [x] T8 — the poll route (AC2, AC5, AC8).
- [x] T9 — the place-line route (AC9).
- [x] T10 — registry rows and probe steps (AC10).
- [x] T11 — the structural check.
- [x] T12 — the regressions, each proven against the pre-story code.

## Dev Agent Record

### Decisions taken, with their reasons

- **The wall travels on the ledger row.** A *matter* has exactly one wall (`MatterScope`), and the
  worker runs in a different process from the request. `scope` is persisted exactly as `import_job`
  persists it, and the worker ranks under `{scope}` — never an empty or a wide scope set.
- **The partial unique index uses the negative form** — `state NOT IN ('done','failed')` — where
  `uq_import_job_open` uses `state != 'done'`. A `failed` job is terminal; under the import's form
  it would hold the *matter*'s re-rank shut permanently.
- **One cascade per job, capped in the ledger.** `bump_ranking_attempt` is committed in its own
  transaction **before** the work (AD-17's mechanic), and over the cap of 1 the job is marked
  `failed` rather than run again: `run_cascade` is a monolithic in-memory pass with no checkpoint, so
  a retry re-pays one model call per uncertain *pièce* over the whole *matter*. Procrastinate keeps
  a small retry so a transient failure of the **bookkeeping** recovers; the ledger cap means the
  second dispatch marks the job failed without running a second cascade.
- **No job-level audit entry.** `record_ranking` already writes `ACT_RANKING_RECORDED` atomically
  with the version and its `KIND_RANKING` stamp. A second entry is a second record of one act, on a
  table AD-7 forbids removing from.
- **`ranking_job` is captured by the backup plan** automatically (rule 1, a tenant column), which
  makes it consistent with `import_job`. 35 → 36 tables.
- **This story does not close C12.** AD-6's idempotency key is unimplemented product-wide. The
  partial unique index bounds a double-click **on this route specifically** — a second POST while one
  job is open is a 409, not a second job — and that is a narrower guarantee than an idempotency key.
  Recorded rather than inherited silently.

### Found while building, not fixed here

- **C18 — `_MUTATING_METHODS` is defined and referenced nowhere.** `apx/checks/user_actions.py:47`,
  under a comment asserting *"The mutating four additionally MUST declare `changes_state` (see the
  check)"*. No check reads it. The claim cannot be made true as written either: `preview-validation-
  batch` is a POST that legitimately declares `changes_state=False`, and this story adds a second
  (`ranking/preview`). The honest fix is a rule with a written preview exemption, or the deletion of
  a constant that reads as an enforcement.

### Review

Reconnaissance ran as a six-reader fan-out plus a synthesiser; every load-bearing claim was then
re-verified by hand before anything was written, and one was **false**: a map asserted that
`cascade_units` *"has no home in the runtime — it exists only in the test tree"*. It is at
`store.py:2409` and `manage.py:193` already calls it. Its paired "risk" was discarded with it.

**Coverage lost: none.** All six readers returned; the synthesiser named twelve claims it had read
only through the maps rather than opened itself, and the ones this story stands on — the freshness
triggers, `derive_run_state`, `check_confirmed_count`/`BatchSplit`, `place_line`'s signature,
`_guard_open_run`'s two callers, `_current_verdicts`' per-family arithmetic, the `ImportJob` DDL,
the migration head, `RetryStrategy`'s `max_attempts` semantics, the plaintext allowlist and
`ENCRYPTED_COLUMNS` — were each read directly before use.

**Two checks fired while building, and both were answered by strengthening.**

- *scope is never applied without a tenant (AD-12)* fired on `_rank_now`, which took `scopes` and
  carried the tenant inside a job view. The tenant is now an explicit parameter, which is what the
  rule is actually for: the wall and the tenant are one decision and reading one without the other
  is how a cross-tenant read gets written.
- *content-bearing columns are application-encrypted (AD-31)* fired on `RankingJob.state`. `state`
  is categorical and went onto the qualified plaintext allowlist with a written reason — but the
  check firing is what made me look at `detail` in the same breath, and `detail` **is**
  content-bearing: one of its branches interpolates an exception's own message, and an exception
  raised inside the cascade can name a *pièce*. It is now `EncryptedText` and registered in
  `ENCRYPTED_COLUMNS` (a column omitted there is silently skipped by a key rotation and then fails
  closed on read under the retired key).

**Two traps proven, not asserted.** The implementation was temporarily replaced with the plausible
wrong version and the suite re-run:

| The plausible move | What it breaks | Test that goes red |
|---|---|---|
| count runs whose **stored** status is open | promises *"three runs will be lost"* over runs already dead — in the number the server then re-checks | `test_an_already_invalidated_run_is_not_counted_as_about_to_be_lost` |
| return the in-flight handle on the FR-7 race, as `ingest_upload` does | tells a lawyer her re-rank was accepted while the running job computes on the **old** case theory | `test_a_second_request_while_one_is_open_is_refused_and_not_handed_the_handle` |

A third is proven by construction: `test_removing_the_open_call_turns_the_check_red` runs
`every_defer_opens_the_queue` over a tree with `ensure_open()` deleted from `enqueue_ranking`, and
asserts the check names the function. A green suite is **not** evidence here — the in-memory
connector is the one implementation with no `AppNotOpen` guard — so the check is exercised against
the failure rather than around it.

**`LineNotDrawn` was added to story 7.5's act.** The acceptance criterion *"a job whose ranking
committed and whose placement raised ends failed with the minted version_no recorded"* could not be
met by reading back *the latest* version — that is precisely the referent `rank.py` refuses. The act
now raises an exception carrying the number, which makes the remedy nameable instead of inferable.

### File List

- `apx/adapters/store_postgres/migrations/versions/0038_ranking_job_ledger.py` — **new**.
- `apx/adapters/store_postgres/models.py` — `RankingJob`.
- `apx/adapters/store_postgres/store.py` — `RankingJobView` + seven ledger methods.
- `apx/adapters/store_postgres/queue/__init__.py` — `_run_ranking`, `_rank_now`, `run_ranking`,
  `enqueue_ranking`, `_RANKING_MAX_ATTEMPTS`.
- `apx/adapters/store_postgres/backfill.py` — the two new encrypted columns, registered for rotation.
- `apx/core/app/rank.py` — `LineNotDrawn`.
- `apx/core/domain/sampling.py` — `RerankCost`, `RerankCountMismatch`, `check_confirmed_runs`.
- `apx/core/app/read/sampling.py` — `rerank_cost`.
- `apx/api/app.py` — four routes, four response models, `_matter_wall`, `_rerank_cost_or_404`.
- `apx/checks/rerank_cost.py` — **new** structural check; `registry.py`, `manifest.py`, `README.md`
  in lockstep (108 → 109).
- `apx/checks/encryption.py` — `("RankingJob", "state")` on the qualified plaintext allowlist.
- `apx/checks/user_actions.py` — three `_http` rows, one `_read`, one `_seam`.
- `tests/probe/test_never_hard_delete.py` — four probe steps, ordered before the sampling cut.
- `tests/scoring_fakes.py` — truthful `JudgeIdentity` on the two fake judges.
- `tests/api/test_ranking_is_a_request.py` — **new** (18).
- `tests/worker/test_ranking_job.py` — **new** (10).

### Change Log

| When | What |
|---|---|
| 2026-08-18 | Split C11+C5+C9+C17 into A–E after a six-reader reconnaissance; A written and built. |
| 2026-08-18 | Two checks fired and were answered by strengthening; two traps proven red. |
