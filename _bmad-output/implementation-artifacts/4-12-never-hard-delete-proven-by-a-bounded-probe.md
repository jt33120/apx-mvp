---
baseline_commit: 540e3e5
---

# Story 4.12: Never hard-delete, proven by a bounded probe

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a firm,
I want no user-facing action anywhere to destroy data, proven by exercising every action,
So that "triage never destroys" is checked against reality, not asserted about all possible behaviour.

## Scope note — 4.12 proves an EXISTING promise; it builds no new product behaviour

Every story before this one made a local promise: the *failure register* resolves by state change
(2.6), the index never deletes itself (2.8), the *case theory* withdraws by appending a withdrawal
version (4.1), the taxonomy label reverts by a new ledger entry (4.5), retained/discarded are VIEWS
(4.7), **the line** moves by a new placement (4.8/4.9), a pin is removed by a `removed` entry (4.11),
a justification is rejected reversibly (4.6). Each was proven **in its own tests, about itself**.

Story 4.12 is the **capstone meta-test**: it stops being a promise kept story-by-story and becomes a
**property proven over the whole enumerated action surface at once**. It adds no user-facing
behaviour, no table and no migration. What it adds is the thing FR-21 actually asks for — *"asserted
by a bounded runtime probe over an enumerated registry of user-reachable actions"* — plus the FR-56
structural property that keeps the registry honest when the next action is written.

**Why now:** the registry is only worth building once the actions exist. Every triage-control act
now exists (label 4.5, line 4.8, priced move 4.9, pin 4.11, justification + rejection 4.6), so the
probe has a complete surface to walk. Building it earlier would have enumerated an empty room.

**What 4.12 must NOT do:** it must not weaken any existing check, must not introduce a new deletion
path "so the probe has something to test", and must not silently exempt an action it finds
inconvenient to exercise — an exemption that is not written down with a reason is the failure mode
this story exists to prevent.

**IN scope:**
1. `apx/checks/user_actions.py` — the **registry** `USER_ACTIONS`: one frozen `UserAction` row per
   user-reachable action, each naming its HTTP route (when one exists), its `core/app` use-case seam
   (when one exists), whether it **changes state**, whether a user could **read it as deletion**, and
   — when they could — the **named reversal** that undoes it. Plus `TRANSIENT_TABLES`: the written,
   reasoned allow-list of non-evidential tables whose rows may legitimately go away (AD-7's own
   "one named exception … written here so it is not invented elsewhere" pattern, generalised).
2. **Structural check 1 — `user_action_registry_is_complete`** (FR-56/FR-21): two legs, both ways.
   *Leg A (HTTP):* the set of route declarations found by scanning **all of `apx/api/`
   recursively** — **every verb**, on any object, in the decorator form, the `api_route(...,
   methods=[...])` form or the call form `app.post(path)(handler)` — equals the set of routes the
   registry names. **GET is not exempt**: eight GET endpoints here write an `audit_record` row on
   serve, and an audited read is a user-reachable action writing to the very table FR-21 protects.
   An unregistered route fails the build, and so does a stale registry row.
   *Leg B (use case):* the set of public callables found by scanning **all of `apx/core/app/`
   recursively, and the whole AST of each module**, that take a **Ports-typed parameter** (the
   Application-layer seam shape, AD-4) equals the set of use cases the registry names — including
   seams in subpackages, inside `try:`/`if:` blocks, and public methods of public classes.
   Both legs **fail closed**: on an unparseable file, on a route path that is not a literal, on an
   `api_route` whose `methods=` is unreadable, on an unresolvable registration shape
   (`include_router` / `add_api_route` / a non-static `mount` / a websocket), and on a module that
   imports from `apx.core.ports` in a shape the check cannot read.
3. **Structural check 2 — `deletion_shaped_actions_declare_their_reversal`** (FR-21/AD-7): an action
   whose **source shape** reads as deletion — an HTTP `DELETE`, or a route path / use-case name
   carrying a deletion-shaped **word part** (`delete`, `remove`, `clear`, `purge`, `revoke`,
   `withdraw`, `drop`, `reset`, `wipe`, `reject`, `revert`, `discard`, `erase`, `destroy`, `expire`,
   `archive`, `truncate`, `unpin`, `retire`) — MUST carry `reads_as_deletion=True` **and** a
   non-blank `reversal`.
   Driven by the source, not by the registry author's flag, so the flag cannot be quietly set to
   `False` to dodge the rule (the two-legged pattern of `justification_names_its_evidence`).
4. **The bounded runtime probe** — `tests/probe/test_never_hard_delete.py`: against a real seeded
   *matter* (a real store, real ingestion, a real ranking, a real label/line/pin/justification), the
   probe **executes every registered HTTP route and every state-changing seam** and, after **each**
   one, asserts that **no `DELETE` statement touched an evidential table** — the statements, not the
   totals, because a delete masked by an insert in the same action leaves the counts flat. Evidential
   = every mapped table MINUS `TRANSIENT_TABLES`, so a table added later is evidential **by default**.
   The probe also **verifies `changes_state` by execution** (every True really writes, every False
   really does not) and asserts its own **coverage** — a silently skipped action fails.
5. The three-site lock-step (registry + manifest + README) and the story/sprint bookkeeping.

**OUT of scope (named so it is not smuggled in):**
- Any new HTTP route for label / line / pin / justification — that is Story 4.10's surface. The
  registry names those actions at their **use-case** seam, which is where they are reachable today.
- Resolving OQ-8 (lawful erasure vs. statutory retention). AD-7's position — deletion is structurally
  absent while the question is open — is what this story proves; it does not answer the question.
- Re-asserting the live schema against cascades (AD-7's "re-asserted against the live schema by the
  AD-2 job"). The source-level cascade check already exists (`payload_schema.no_cascade_delete`); the
  live-schema assertion belongs to the AD-2 operational job, not to this probe.

## Acceptance Criteria

**AC-1 — the registry exists and its completeness is a structural property (FR-56).**
Given the registry of user-reachable actions,
When the structural harness runs,
Then `user_action_registry_is_complete` passes on the real tree, and an action added to the product
but **not** to the registry fails the build — on **both** legs (a new mutating HTTP route, and a new
Ports-taking public function in `core/app/`) — as does a **stale** registry row naming an action that
no longer exists.

**AC-2 — the bounded probe executes every state-changing action and no count falls (FR-21).**
Given a seeded *matter* with *pièces*, *chunks*, *audit record* entries, *change log* entries and
*failure register* entries,
When the probe executes each state-changing registered action in turn,
Then after every action no **evidential** table's row count is lower than before it, and the probe
asserts its own coverage: the union of actions its steps declare equals the set of state-changing
registered actions (no silent skip).

**AC-3 — an action a user could read as deletion is a reversible, labelled, recorded state change
(FR-21/FR-5).**
Given the actions whose **source shape** reads as deletion (`DELETE /api/matters/{matter}/case-theory`,
the pin removal, the label reversal, the justification rejection, the truncation clear, the scope
revocation),
When the structural harness runs,
Then each is registered with `reads_as_deletion=True` and a **named reversal**, and the probe shows
each of them **adding** rather than removing rows (or, for a named transient, leaving every evidential
count untouched).

**AC-4 — every table that may lose rows is named with a written reason; everything else is
evidential by default.**
Given `TRANSIENT_TABLES`,
When the probe runs,
Then every name in the allow-list is a real mapped table carrying a non-blank reason, and the
evidential set is *every other mapped table* — so a table introduced by a later story is protected
without anyone remembering to protect it.

**AC-5 — the harness accounts for itself (AD-33/FR-56).**
Given the two new checks,
When the meta-checks run,
Then both are registered in `apx.checks.registry.CHECKS`, both have a `PROPERTY_MANIFEST` row, and the
README structural-properties block matches the manifest — the check count moves 72 → 74.

## Tasks / Subtasks

- [x] **T1 — the registry module** (AC-1, AC-3, AC-4)
  - [x] `apx/checks/user_actions.py`: frozen `UserAction(name, changes_state, note, route, use_case,
        reads_as_deletion, reversal)`; `__post_init__` enforces route **XOR** use_case, and refuses a
        `reads_as_deletion` row with no reversal.
  - [x] `USER_ACTIONS`: **all 45 HTTP routes** (every verb) + the 25 Ports-taking public
        `core/app` seams — **70 rows**, of which **34 change state**; the probe executes **57**
        (every route whatever its flag, plus every state-changing seam).
  - [x] `TRANSIENT_TABLES`: `{table: reason}` for `session`, `user_scope`, `import_job`,
        `import_unit`. Each reason written in the module, not in a commit message.
  - [x] `evidential_tables(all_tables)`: `all - TRANSIENT_TABLES` (fail-closed by default).
- [x] **T2 — check 1: registry completeness, both legs, both ways** (AC-1)
  - [x] AST-walk **all of `apx/api/`** for `@<obj>.post/put/patch/delete("<literal>")`.
  - [x] AST-walk **all of `apx/core/app/`** (recursive): names imported from `apx.core.ports.*`; a
        public function with any parameter annotated by one of them is a seam; module labelled by
        its dotted path (`read.piece.open_piece`).
  - [x] Compare both sets to the registry **symmetrically**; report the missing and the stale side.
  - [x] Fails closed on an unparseable file, a non-literal route path, or an unresolvable routing
        shape (`include_router` / `add_api_route` / `add_route`). Targets injectable for fixtures.
- [x] **T3 — check 2: a deletion-shaped action names its reversal** (AC-3)
  - [x] Deletion shape from the SOURCE: HTTP `DELETE`, or a deletion-shaped **word part** of the
        route path / use-case name (word parts, never a loose substring).
  - [x] Such a row must carry `reads_as_deletion=True` and a non-blank `reversal`.
  - [x] Fixtures prove it fires on a `DELETE` route, on each deletion-shaped path token, and on a
        deletion-shaped use-case name — and that `cleared` does not match `clear`.
- [x] **T4 — the bounded runtime probe** (AC-2, AC-3, AC-4)
  - [x] `tests/probe/test_never_hard_delete.py` — a real seeded *matter* over the API test harness
        (`_prepare` / `_login` / `FakeEmbedder` / `FakeScorer` / `FixedJudge`): a real corpus, a real
        *failure register* entry, a real ranking, label, line, pin, justification.
  - [x] `_census(store)` → `{table: count}` over `Base.metadata.sorted_tables`.
  - [x] 27 probe steps, each declaring `covers`; every HTTP step asserts a 200/202 so a silently
        failing action cannot count as exercised; after each step assert `after[t] >= before[t]` for
        every **evidential** `t`, naming the table and the action on failure.
  - [x] Coverage assertion: `⋃ covers == {a.name for a in USER_ACTIONS if a.changes_state}`.
  - [x] Allow-list assertion (AC-4): every `TRANSIENT_TABLES` key is a real mapped table with a
        non-blank reason; the FR-21 five and every triage ledger are evidential.
  - [x] AC-3 directly: each deletion-shaped act is shown to **append** a row to a named ledger, and
        the truncation marker is shown to be *cleared*, never removed.
  - [x] A deliberate negative: deleting an `audit_record` row makes the assertion fire.
- [x] **T5 — the three-site lock-step** (AC-5)
  - [x] `apx/checks/registry.py`: import + two `CHECKS` entries.
  - [x] `apx/checks/manifest.py`: import + two `_p(...)` rows (FR-21 / AD-7).
  - [x] `README.md` `<!-- structural-properties -->` block: two rows, first five cells matching.
- [x] **T6 — check tests** (AC-1, AC-3)
  - [x] `tests/checks/test_user_actions.py` — 28 tests: passes the real tree; fires on an
        unregistered route, an unregistered seam, a stale row of either kind, a seam hidden in a
        subpackage, a route on a router object, a route module beside `app.py`; fails closed on an
        unparseable file (either tree), a non-literal path, an `include_router`.
- [x] **T7 — gate + bookkeeping**
  - [x] ruff clean, **74** structural checks, import-linter 3 kept / 0 broken, full pytest green.
  - [x] Story → done; `sprint-status.yaml` 4-12 → done.

## Dev Notes

### What FR-21 names, and where it lives in this codebase

| FR-21 term | This codebase |
|---|---|
| *pièce* | `piece` |
| *chunk* | `chunk` |
| *audit record* entry | `audit_record` |
| *change log* entry | `taxonomy_label_entry`, `line_placement`, `pin_entry`, `justification_rejection`, `case_theory_version`, `piece_justification`, `recall_review`, `piece_label` |
| *failure register* entry | `failure` |

The probe does **not** hard-code that list. It asserts over **every mapped table minus the written
transient allow-list**, so the FR's five names are covered *and* every ledger a later story adds is
covered without an edit. This is the AD-7 posture: irreversibility should be unrepresentable, not
remembered.

### The deletes that exist today, and why each is (or is not) a hard delete

Verified by reading `apx/adapters/store_postgres/store.py`:

- `store.py:2019/2023/2040` — `session` rows reaped on expiry, on a vanished user, on logout.
  **Transient**: auth state, not evidential. The logout is in the audit record.
- `store.py:2045` — every `session` of a user whose admin flag changed. Same class.
- `store.py:2693` — `revoke_scope` deletes the `user_scope` row. **Transient with a reason**: a scope
  grant is authorisation state; the grant and the revocation are both `audit_record` entries, and the
  act is reversible by re-granting. FR-21's protected list does not include a grant.
- `store.py:1047-1054` — `delete_import_job` removes an `import_job` and its `import_unit` rows when
  an enqueue failed. **Transient**: job orchestration; no *pièce* it produced is touched.

Everything else is append-or-update. `save_labels` (2.x) uses `session.merge` — an upsert, so counts
never fall. `clear_truncation` sets `cleared_at`/`reason` on the marker — a state change, never a
removal. `append_case_theory_version(text=None)` is how a withdrawal is written. These four are the
whole deletion surface, and the probe is what keeps that sentence true tomorrow.

### The two legs of the completeness check, and why two

Leg A (HTTP) alone would let a new triage action ship at the `core/app` seam — which is exactly where
label / line / pin / justification live today, unrouted — and stay invisible to the registry. Leg B
alone would miss an admin route wired straight to the store. The AC's failure path ("an action added
to the product but not to the registry fails the build") is only true with both.

Leg B's rule is **precise, not fuzzy**: a `core/app` public function is a user-reachable seam iff it
takes a parameter annotated with a type imported from `apx.core.ports.*`. That is the shape AD-4
already forces on every Application-layer seam in this codebase — `recorder: PinRecorder`,
`store: JustificationStore`, `judge: Judge` — so the rule reads off the architecture rather than off a
naming convention. Verified against the tree: it selects `justification.*`, `label.*`, `line.*`,
`pin.*`, `rank.produce_ranking`, `ingest.ingest_folder`/`ingest_one_file`, `cascade.run_cascade`,
`triage.triage_pieces`, `embedding.*`, and the five `read.*` seams — **25 seams**, and nothing else.

**Both legs recurse — a blind spot found and closed during implementation.** The first cut of leg B
used `glob("*.py")`, which silently skipped `apx/core/app/read/` — a real subpackage holding five
Ports-taking seams. Nothing state-changing lives there today (all five are pure reads; the audit of
an open is the edge's separate write on serve), so no action was unprobed — but a *future*
state-changing seam placed in a subpackage would never have been registered, which is precisely the
failure AC-1 exists to prevent. Both legs now `rglob`, and leg A scans the whole `apx/api/` tree and
accepts a decorator on **any** object, so moving a route onto an `APIRouter` or into a new route
module beside `app.py` cannot hide it either. What the check *cannot* resolve, it refuses to guess:
a non-literal path or an `include_router` fails the check closed.

### Route inventory (leg A's expected set, verified against `apx/api/app.py`)

`POST /api/login` · `POST /api/logout` · `POST /api/me/password` · `POST /api/admin/users` ·
`POST /api/admin/users/{user_id}/grant` · `POST /api/admin/users/{user_id}/revoke` ·
`POST /api/admin/matters/{matter}/rescope` · `POST /api/admin/users/{user_id}/admin` ·
`PUT /api/admin/config/{key}` · `POST /api/admin/dr/truncation/clear` · `POST /api/ingest` ·
`POST /api/ingest-upload` · `PUT /api/matters/{matter}/case-theory` ·
`DELETE /api/matters/{matter}/case-theory` · `POST /api/matters/{matter}/judge` ·
`POST /api/matters/{matter}/recall/review` — **16**.

### Existing patterns to reuse (do not reinvent)

- **Check shape**: `CheckResult(name, ad, ok, detail)` from `apx.checks.import_contracts`; `_parse`,
  `_load_trees`, `_fail_closed`, `_parent_map`, `_enclosing_func` from `apx.checks.payload_schema`.
  Injectable targets so fixtures can drive the failure path (`no_truncation.py` is the cleanest
  model; `justification_names_its_evidence.py` is the two-legged model).
- **Probe harness**: `tests/api/test_ingest_api.py::_prepare` / `_login`, `tests/embedding_fakes.FakeEmbedder`,
  `apx.adapters.store_postgres.queue._run_import`. `tests/adapters/test_justification_store.py` shows
  how to get real *pièces* + *chunks* + a resolvable quote.
- **Three-site lock-step**: `registry.py` import + `CHECKS` entry; `manifest.py` import +
  `_p(key, fr, ad, verb, check_callable, inspects)`; the README block. `manifest_matches_readme`
  compares only the first five cells — the sixth (Inspects) is prose.

### Non-negotiables carried from the architecture

- **AD-7** — nothing hard-deleted; ledgers append-only; no cascade. This story is AD-7's proof.
- **AD-4** — `core` imports no adapter. The checks live in `apx/checks/` (which imports neither);
  the probe lives in `tests/` and may import both.
- **AD-33 / FR-56** — a property with no check is not a property; the manifest is the accounting.
- **AD-13 / FR-14** — the probe authenticates and stays inside one *tenant*; it never asserts across
  a wall.

### Testing standards

- `cd apx-mvp && export PATH="$PWD/.venv/bin:$PATH"` in the SAME shell call; never export
  `DATABASE_URL`. ruff line-length 100 — accented characters (*pièce*, é, →, §) push lines over it,
  so reflow by hand.
- Every new check gets a fixture that makes it **fire**, not only one that makes it pass.
- The probe gets its own negative: an intentionally destructive step must make the census assertion
  fail, proving the probe is not vacuous.

## Dev Agent Record

### Context Reference

- Epic 4, Story 4.12 (`_bmad-output/planning-artifacts/epics.md`)
- FR-21 (never hard-delete), FR-56 (structural properties), FR-5 (the failure register)
- AD-7 (nothing hard-deleted / no cascade), AD-33 (structural properties), AD-4 (layering)

### Implementation Plan

Registry first (it is the contract), then the two checks against it, then the probe that consumes it,
then the lock-step. The registry was written by **reading the tree, not by memory**: an AST script
enumerated the 16 mutating routes and the Ports-taking `core/app` seams before a single row was
typed, so the first run of `user_action_registry_is_complete` was green for the right reason.

### Debug Log

- **Leg B was blind to subpackages.** `glob("*.py")` skipped `apx/core/app/read/` entirely — five
  real Ports-taking seams (`open_piece`, `render_piece`, `read_scan_page`, `search_exhaustive`,
  `search_semantic`). All five are pure reads, so nothing state-changing went unprobed, but a future
  state-changing seam in a subpackage would have been invisible: the exact failure AC-1 forbids.
  Fixed by recursing and labelling modules by dotted path; the five are now registered rows
  (`changes_state=False`, with the reason: the audit of an open is the **edge's** separate write).
- **Leg A had the same class of blind spot**, twice over: it read only `apx/api/app.py`, and only
  decorators on the bare name `app`. Fixed by scanning `apx/api/` recursively and accepting a
  mutating decorator on **any** object. What it cannot resolve it now refuses to guess: a non-literal
  path or an `include_router`/`add_api_route` fails the check **closed**.
- **The probe's steps had to assert their own success.** A step that quietly 4xx'd would have
  satisfied the census assertion vacuously — "no count fell" is trivially true when nothing ran. Every
  HTTP step now asserts its status; `place_line` asserts the tool actually committed to a line.
- `_run_import` was initially called without an embedder, which would build the real one; the fake is
  now injected explicitly at the port (AD-11).
- ~9 E501s from accented characters (*pièce*, é, →, ─) reflowed by hand; ruff's isort moved the new
  `user_actions` import into place in both `registry.py` and `manifest.py`.

### Completion Notes

- **70 registry rows**: **45 HTTP routes** (every verb — see the review section on why GET is not
  exempt) + **25 `core/app` seams**. **34 change state**; the probe executes **57** actions (every
  route, whatever its flag, plus every state-changing seam).
- **The probe found no violation of FR-21** — which is the point: FR-21 was already true, and is now
  *proven by execution* over the whole surface rather than promised story by story. The four
  deletions that exist (`session` at four sites, `user_scope` via `revoke_scope`,
  `import_job`/`import_unit` via `delete_import_job`) are named in `TRANSIENT_TABLES` with written
  reasons; none touches a *pièce*, a *chunk*, an *audit record* entry, a *change log* entry or a
  *failure register* entry.
- **The probe did find three registry errors — in the registry, which is exactly what it is for**:
  `GET /api/me` refreshes its `session` row; `login`/`logout` write nothing evidential;
  `/api/register/export` writes an audit entry the first pass had missed. All three were corrected
  by the probe telling the truth about what ran.
- **AC-3 is proven positively, not negatively**: each deletion-shaped act is shown to append a row to
  a named ledger — `withdraw-case-theory` → `case_theory_version` +1, `revert_taxonomy_label` →
  `taxonomy_label_entry` +1, `remove_pin` → `pin_entry` +1, `reject_justification` →
  `justification_rejection` +1, `clear-truncation` → `audit_record` +1 with the marker *stamped and
  kept*, `revoke-scope` → `audit_record` +1 with every evidential count intact.
- **One written residual**, named in the probe as `_WRITE_NOT_OBSERVABLE_HERE`: `open-piece-render`
  and `open-piece-page` write their audit entry only when they actually **serve** content, which
  needs a renderable office document and a scanned page with an OCR layer — material this SQLite
  harness does not produce. Both are still executed and still asserted to delete nothing; their
  audited path is asserted by `tests/api/test_piece_render_endpoint.py` and
  `tests/api/test_scan_endpoints.py`. It is written down rather than silently skipped.
- Gate: ruff clean · **74** structural checks (72 → 74) · import-linter **3 kept / 0 broken** ·
  **1339 passed / 12 skipped** (1301 → 1339, +38 tests).
- No new table, no migration, no user-facing behaviour — as scoped.

## File List

| File | Change |
|---|---|
| `apx/checks/user_actions.py` | **NEW** — `UserAction`, `USER_ACTIONS` (41 rows), `TRANSIENT_TABLES`, `evidential_tables`, and the two structural checks |
| `apx/checks/registry.py` | UPDATED — import + 2 `CHECKS` entries |
| `apx/checks/manifest.py` | UPDATED — import + 2 `PROPERTY_MANIFEST` rows |
| `README.md` | UPDATED — 2 rows in the structural-properties block |
| `tests/probe/__init__.py` | **NEW** — the bounded-probe package |
| `tests/probe/test_never_hard_delete.py` | **NEW** — the probe (4 tests: the 27-step walk, the deletion-shaped-appends proof, non-vacuity, the allow-list) |
| `tests/checks/test_user_actions.py` | **NEW** — 28 tests over the two checks |
| `_bmad-output/implementation-artifacts/4-12-…md` | **NEW** — this story |
| `_bmad-output/implementation-artifacts/sprint-status.yaml` | UPDATED — 4-12 → done |

## Change Log

| Date | Change |
|---|---|
| 2026-08-06 | Story created (create-story). |
| 2026-08-06 | Implemented: registry + 2 structural checks + the bounded runtime probe (dev-story). |
| 2026-08-06 | Both completeness legs made recursive and fail-closed after a self-found blind spot. |
| 2026-08-06 | Adversarial review: 22 findings → 8 confirmed → all fixed; 12 refuted, 2 skeptics errored and were judged directly. |

## Senior Developer Review (AI)

**Reviewer:** adversarial 3-lens workflow (correctness · security-isolation · architecture-scope),
each finding independently skeptic-verified with the default set to REFUTED.
**Date:** 2026-08-06 · **Outcome:** Changes Requested → **all confirmed findings fixed** → Approve.

**22 findings → 8 CONFIRMED → all fixed · 12 refuted · 2 skeptics died mid-run (judged directly).**

The two lenses that found the same defect twice were right both times. Below is what changed.

### The confirmed defects and their fixes

**1. (high, found by both `correctness` and `security-isolation`) The census was a NET count, so a
hard delete masked by an insert in the same action passed green.** `_assert_nothing_lost` compared
`after[table] >= before[table]`. The skeptic reproduced the failure end to end: replacing
`save_labels`'s `session.merge` upsert with the ordinary ORM "delete the children, then re-add them"
idiom hard-deletes evidential `piece_label` rows on every re-judge — and the probe, the 74 structural
checks, ruff and all 1333 tests stayed **green**. The probe therefore proved "no net loss per table",
not FR-21's "nothing is hard-deleted", and the two differ exactly on the most plausible regression.
**Fixed:** the probe now installs an `Engine`-level `before_cursor_execute` listener for the duration
of each step and fails on **any** `DELETE` against an evidential table — reading the statements, not
the totals. Listening at class level (not on one instance) is what makes it honest: the TestClient's
app builds its own store and its own engine. Reading raw SQL rather than ORM mapper events is what
catches `session.execute(delete(X))`, the bulk form the ORM events never fire for.
*Re-verified with the reviewer's own scenario:* control → PASSED; regression → **FAILED**,
`judge-matter issued a DELETE against evidential table(s) ['piece_label']`.

**2. (high, found by both `correctness` and `security-isolation`) `changes_state` was an unvalidated
author flag — the one field the whole probe's bound rested on.** The story had deliberately hardened
`reads_as_deletion` against exactly this (the shape is read off the source, not off the flag) and
left the *more consequential* flag undefended: `changes_state=False` silently removed an action from
the probe and no check ever looked at it. **Fixed twice over, and deliberately NOT with a
name-based rule** — "a POST changes state" would be *false* here (`login`/`logout` write nothing but
a session row), and a false rule teaches people to work around it. Instead: (a) the probe now covers
**every route row regardless of its flag**, so no HTTP action can be exempted by setting it; and
(b) the probe **verifies the flag by execution** — every `changes_state=True` action must really
write an evidential row, every `changes_state=False` action must really write none. It caught three
registry errors on its first run.

**3. (medium) Leg A was blind to `@app.api_route(..., methods=[...])`, to `app.mount(...)` and to
the call form `app.post(path)(handler)`** — and `app.mount` is already in `app.py`, so the
"fail-closed" claim in its docstring was false. **Fixed:** `api_route` is parsed properly (its
literal `methods=` list is read, and an unreadable one fails closed); the non-decorator call form is
collected; `mount` fails the check closed **except** the one written exemption, the `StaticFiles`
front-end bundle, named in the source in AD-7's own "written here so it is not invented elsewhere"
style.

**4. (medium, found by both `architecture-scope` and `correctness`) Leg B failed OPEN on import and
seam shapes it did not recognise** — a module whose ports it could not read was skipped whole, with
no report. **Fixed:** module aliases (`import apx.core.ports.pin as p`) and attribute annotations
(`p.PinRecorder`) are recognised; the AST is walked in full, so a seam nested in `try:`/`if:` or
defined as a public method of a public class is found and named (`module.Class.method`); and a module
that imports from `apx.core.ports` in a shape the check cannot read now **fails it closed**.

**5. (medium) The registry's written reasons were factually wrong in three places.** `logout` writes
**no** audit entry (`store.delete_session` is unaudited), `change-own-password` does delete rows
(`delete_user_sessions`), and the `session` allow-list reason claimed each reaping act "is itself
recorded in the audit record". **Fixed:** all three notes rewritten to what the code actually does,
including the uncomfortable half — a written reason that is false is worse than no reason, because it
is the thing a reader trusts instead of reading the code.

**6. (medium, skeptic died mid-run — judged directly and accepted) The registry could not represent
a state-changing GET, and seven GET routes write `audit_record` rows on every call.** Those are
user-reachable actions writing to the very table FR-21 protects, and they were outside the registry
entirely. **Fixed:** leg A now discovers **every** HTTP verb; all 45 routes are registered and
probed. The probe then found an **eighth** the finding had missed — `/api/register/export`.

**7. (medium) Probe steps could be no-ops.** The `ingest-folder-route` step ingested a folder
byte-identical to the arrangement folder, so content-hash dedup (AD-8) made it persist nothing — a
step that "proves" a claim while doing nothing. **Fixed:** folders are salted per folder name, and
the runtime flag check (fix 2) now fails **any** `changes_state=True` step that writes nothing, which
closes this class of vacuity generally rather than one instance of it.

**8. (low) The story artifact and the README/manifest prose had drifted** — T7's bookkeeping was
ticked before it was done, and the documentation still described the check as scanning
`apx/api/app.py`, the exact narrowing the Debug Log says was fixed. **Fixed:** both corrected, and
this section is the record.

### Notable refutations (the skeptics were right to kill these)

- *"Leg A fails open on `app.mount`"* (as an architecture-lens finding) — refuted on the facts: the
  only `Mount` in the live app is `StaticFiles`, verified by introspecting the running app. The
  **correctness** lens's version of the same observation was nonetheless accepted, because it named a
  reproducible shape rather than the existing mount.
- *"`_DELETION_SHAPED` omits `discard`"* — refuted: no version of `discard_uncertain` that actually
  hard-deletes could be constructed, so the named failure scenario did not exist. Adopted anyway
  while the vocabulary was open: `discard` is this product's own word for setting a *pièce* aside,
  and the day an action carries it the honesty gate should apply.
- *"The AC-3 test hard-codes six acts with no coverage assertion"* — refuted with a proof I had not
  made myself: the literal list is *exactly* `{a for a in USER_ACTIONS if a.looks_like_deletion}`,
  which the skeptic verified by inserting that assertion into a copy.
- *"8 of 13 seam steps are vacuity-prone"* and *"the probe executes each action from a cold table"* —
  refuted as filed, but both pointed at the same real weakness as finding 7, which is fixed.

### Integrity

All work by the review agents happened in `/tmp` and in scratchpad copies. The repository was
**byte-identical** to its pre-review snapshot on every code file when the review returned (verified
against a SHA-256 manifest; the only difference was the story `.md`, which I had edited myself).
