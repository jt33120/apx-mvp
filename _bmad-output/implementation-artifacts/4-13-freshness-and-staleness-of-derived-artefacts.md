---
baseline_commit: 6ec9898
---

# Story 4.13: Freshness and staleness of derived artefacts

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a lawyer who must not read a false number off the screen,
I want any derived artefact marked stale the instant an input changes — including a new import,
So that the north-star sentence can never be exported as current while its population has grown
underneath it.

## Scope note — the last story of Epic 4, and the one that makes every earlier count honest

Epic 4 built a *ranking version* (4.3), a derived confidence (4.4), a version-independent label
ledger (4.5), a justification (4.6), the retained/discarded **views** (4.7), **the line** (4.8), its
priced move (4.9), the editable table (4.10), the pin (4.11) and the never-delete probe (4.12).

Every one of those artefacts is **derived from inputs that can move afterwards**. Nothing in the
build today notices when they do. The Story 4.10 review found this and correctly deferred it here:
*the denominator's total is the ranking version's population but is labelled "pièces au dossier"* —
an import after the ranking is invisible on the surface that counts the sets.

4.13 closes it. It is the story AD-23's second half names: *"staleness is explicit and never
self-resolving"*.

**Why now:** the trigger list can only be enumerated once the things that trigger it exist. All
eight triggers now have a real cause in the build (a re-rank, a line move, a pin, a case-theory
revision, a config change, a re-scope, an ingestion, a re-extraction). Building this earlier would
have enumerated an empty room — the same reason 4.12 came last but one.

**The load-bearing design decision — staleness is a DERIVED VIEW, never a stored flag.**
A stored `stale` boolean must be *set* by every writer. A writer that forgets leaves the artefact
**falsely fresh**, which is precisely the failure AD-23 names. A **comparison cannot forget**: an
input that changed is visible whether or not anyone remembered to announce it. So an artefact
records the **stamp** of its inputs at production time, and freshness is decided by comparing that
stamp to the current one at read time — the same shape as the retained/discarded sets (AD-39), the
current label (4.5), the current line (4.8) and the current pin (4.11).

**What 4.13 must NOT do:**
- must not add a background job, a TTL, a cache expiry or any clock into the freshness decision —
  staleness resolved by time is the defect, not the feature;
- must not mutate a produced artefact to "refresh" it — resolution produces a **new** artefact;
- must not weaken any existing check or exempt a trigger it finds inconvenient to observe;
- must not build Epic 5 (the hypergeometric estimator, the sampling run, the audit chain). The
  *confidence bound* it binds here is the **existing** recall bound (`recall_review`), not a new one.

**IN scope:**

1. `apx/core/domain/freshness.py` — the pure vocabulary: the **enumerated trigger list**, the
   `FreshnessStamp` (one observable per trigger), and the pure comparison `assess_freshness` that
   returns **which inputs changed** — never a bare boolean.
2. `apx/core/ports/freshness.py` — `FreshnessReader` / the stamp writer protocol.
3. `apx/core/app/read/freshness.py` — the read seams (freshness of an artefact, the matter's
   worklist, the current bound), each fail-closed on an empty scope set.
4. `apx/core/domain/worklist.py` — the **derived** worklist: pure functions turning staleness into
   the lines FR-58 requires ("offering a re-rank", "offering a re-sample"). Nothing stored.
5. Migration `0030_artefact_stamp.py` + the `ArtefactStamp` model — the append-only stamp ledger.
6. Store: write the stamp inside the producing transaction for the ranked order, the line and the
   bound; read stamps; compute the current stamp; the corpus/extraction observables.
7. `apx/api/app.py` — 4 new routes (freshness, worklist, bound, bound export) + the corrected
   denominator fields on the triage table.
8. `apx/checks/user_actions.py` — the 4 new routes and 3 new seams declared (4.12's registry turns
   the build red until they are).
9. **3 new structural checks** (74 → 77) + the `registry.py` / `manifest.py` / `README.md` lockstep.
10. `apx/web/src/` — the stale banner naming the changed input, the honest denominator with the
    unranked count, the bound with its staleness in the copy string, the worklist panel.

**OUT of scope, named with its reason (never silently dropped):**
- **The review-effort estimate.** AD-23 binds it, but no story has built it — there is no artefact
  to stamp. When it lands it must record a stamp; the completeness check (below) is written over the
  *trigger* list, not the artefact list, so it will not falsely claim coverage.
- **An exhaustive result set's stamp.** AD-23 binds it, but an exhaustive set is computed at read
  time and never persisted (Story 3.2 / AD-20): it is **fresh by construction** because it has no
  lifetime in which an input could move. A stamp on an object that dies inside its own request would
  be theatre. Assert it instead: a test that the exhaustive path stores nothing.
- **The hypergeometric estimator, the sampling run and the invalidated-in-flight state** — Epic 5
  (5.1/5.2). This story makes the *existing* recall bound stale-aware and unexportable-when-stale;
  Epic 5 inherits that machinery rather than inventing a second one.
- **The home-screen worklist** (backups overdue, open import jobs, matters list — PRD §4.x). Only
  the Epic-4 staleness lines are built here, on the matter's own surface.
- **Retiring over-bound ranking versions** (`retained_ranking_versions_max`) — already deferred by
  Story 4.7 and untouched here.

---

## Acceptance Criteria

**AC1 — Every trigger in the enumerated list marks the artefact stale, and names itself.**
**Given** a produced derived artefact (a ranked order, a position of **the line**, a *confidence
bound*),
**When** any of the **eight** enumerated inputs changes — a new *ranking version*; a move of **the
line**; a *pin* added or removed; a *case theory* revision; a configuration change affecting
retrieval, ranking or the estimator; an *RBAC scope* change affecting the population; **any
ingestion into the *matter***; **a re-extraction of any *pièce*** (FR-58 + AD-40),
**Then** the artefact reads as **stale**, and the assessment **names which input changed** — never a
bare "stale". Asserted by test **for each of the eight triggers separately**: perform the trigger,
assert stale, assert the named input, assert the worklist line exists.

**AC2 — A stale artefact is a comparison, not a flag; nothing has to remember to set it.**
**Given** a produced artefact and a changed input,
**When** the change is made by any writer — including one that knows nothing about freshness,
**Then** the artefact still reads stale. Asserted by test: mutate an input **directly through the
store's own existing seam** (no freshness call anywhere on the write path) and assert staleness.
**And** the structural check `every_staleness_trigger_has_an_observable` proves the enumerated
trigger list and the stamp's observable fields match **both ways** and **fails closed** — a trigger
with no observable, or an observable naming no trigger, turns the build red.

**AC3 — Staleness is never resolved by time, by a background job, or by being viewed.**
**Given** a stale artefact,
**When** it is read any number of times, and any amount of time passes,
**Then** it stays stale, with the same named inputs. Asserted by test (read it 5×, assert
unchanged).
**And** the structural check `freshness_is_never_time_based` proves no clock reaches the freshness
decision: the freshness domain module and its seam name no `datetime.now` / `utcnow` / `time.` /
`timedelta` / `monotonic`, and no stamp field is a timestamp. Fails closed on an unparseable module.
**And** staleness is resolved **only** by an explicit user-initiated recomputation that produces a
**NEW** artefact: asserted by test — re-ranking mints a new *ranking version*, the **old version
stays readable and stays stale**, and no row of the old artefact was mutated.

**AC4 — Ingestion into a ranked matter is a trigger, and the unranked count is stated wherever the
sets are counted.**
**Given** a *matter* with a ranking,
**When** *pièces* are ingested,
**Then** the ranking reads stale naming the corpus input; a worklist line offers a re-rank; and the
triage table states `unranked_count` — the *pièces* in the *matter* that are in **neither** set
because they are not in the ranking at all (the third state FR-16 forbids, made visible rather than
imputed).
**And** the table's counts are honest both ways: `retained + discarded + unscored + unsplit ==
ranked_count`, and `ranked_count + unranked_count == corpus_count`, where `corpus_count` is the
*matter*'s pièce count — **the number the surface labels "pièces au dossier"**. Asserted by test,
including the case that closed the 4.10 review finding: rank, then import, then read the table.

**AC5 — A stale bound cannot be exported as current, and cannot be copied without its staleness.**
**Given** a recorded *confidence bound* and a changed input,
**When** the bound is exported,
**Then** the export is **refused** (409, a typed error naming the changed inputs) — never a
qualified or footnoted export. Asserted by test.
**And** the bound's read carries a server-produced `copy_text`; when stale that string **contains
the staleness and the changed inputs**, so copying it without them is structurally impossible.
Asserted by test on the string itself.
**And** the surface renders a stale bound visually distinct wherever it appears (the `review`
semantic tier, never gold).

**AC6 — The worklist is derived, and offers rather than acts.**
**Given** any staleness on a *matter*,
**When** the worklist is read,
**Then** it returns one line per stale artefact naming the artefact, the changed inputs and the
**offer** (re-rank / re-sample) — and reading it **writes nothing** and **starts nothing**. Asserted
by test: read the worklist, assert no state changed (the 4.12 probe covers this route by
construction).
**And** with nothing stale the worklist is `[]` — an empty list read successfully, never confused
with a failed read (the 4.10 lesson: a failure must not render as a verified absence).

**AC7 — The stamp ledger is append-only and owned by one use case per artefact.**
**Given** a produced artefact,
**When** it is written,
**Then** its stamp row is written **in the same transaction** (AD-22) by the artefact's own owning
use case (AD-37) — a produced artefact without a stamp is impossible.
**And** `artefact_stamp` is append-only: no row is ever updated or deleted (AD-7). Asserted by the
structural check `artefact_stamp_is_append_only` **and** already protected by 4.12's probe, because
`evidential_tables = all mapped tables − TRANSIENT_TABLES` makes a new table evidential by default.

**AC8 — The build stays green under the harnesses the epic installed.**
The 4 new routes and 3 new seams are declared in `USER_ACTIONS` and **walked by the 4.12 probe**;
the 3 new checks are in `registry.py`, `manifest.py` and the README block (74 → 77); import-linter
stays 3 kept / 0 broken; ruff clean; `tsc -b` and `vite build` clean.

---

## Tasks / Subtasks

- [x] **T1 — The pure domain (AC1, AC2, AC3)**
  - [x] `apx/core/domain/freshness.py`: `TRIGGERS` — the closed, enumerated tuple of the eight
        inputs, each an `Input(key, observable_field, fr, why)` naming its French human phrase and
        the AD/FR it comes from. `FreshnessStamp` — a frozen dataclass with **exactly one field per
        trigger** (see Dev Notes for the eight observables and their fidelity). `assess_freshness`
        — a **pure** comparison returning `Freshness(fresh, changed, recorded, current)` where
        `changed` is the ordered tuple of input keys that differ. No clock, no I/O, no store import.
  - [x] `FreshnessStamp.to_json` / `from_json` — canonical JSON, sorted keys (the store persists it
        in one text column, like `ranking_version.identity_json`). `from_json` **fails closed**: an
        unknown or missing field raises, never defaults — a stamp that cannot be read is not a fresh
        artefact.
  - [x] Unit tests: each trigger flips exactly one key; two changes name two keys; an identical
        stamp is fresh; round-trip; a truncated/extended stamp raises.

- [x] **T2 — The worklist domain (AC6)**
  - [x] `apx/core/domain/worklist.py`: `WorklistLine(kind, artefact, subject, changed, offer)` and
        the pure `worklist_lines(...)` that turns assessments into lines. `OFFER_RERANK` /
        `OFFER_RESAMPLE` are named constants — an offer, never an act.
  - [x] Unit tests including the empty case (`()` ≠ a failure).

- [x] **T3 — The port + the read seams (AC1, AC5, AC6)**
  - [x] `apx/core/ports/freshness.py` — `FreshnessReader` Protocol: `read_artefact_stamp`,
        `current_stamp`, `read_current_bound`. Every method takes `tenant` + `scopes`; `scopes` is a
        query **pre-filter** (AD-13); out-of-scope and absent are the same `None` (FR-14).
  - [x] `apx/core/app/read/freshness.py` — three seams: `read_freshness`, `read_worklist`,
        `read_bound`. Each returns `None` on an empty scope set (fail closed, AD-12). Pure
        orchestration over the port; imports no adapter (AD-4).
  - [x] Add the three seams to `USER_ACTIONS` (leg B of the 4.12 check reads `core/app/`
        recursively — an undeclared seam turns the build red).

- [x] **T4 — The stamp ledger (AC7)**
  - [x] `ArtefactStamp` model + migration `0030_artefact_stamp.py`: `(id, tenant, matter, kind,
        artefact_id, stamp_json, at)`, `UniqueConstraint(tenant, matter, kind, artefact_id)`, no
        cascade FK (AD-7), composite `ForeignKeyConstraint` to `matter_scope` per AD-12. `kind` is
        the closed vocabulary `ranking | line | bound`. `stamp_json` is **plaintext** — structural
        metadata like `identity_json`, carrying no PII and no content (state this in the docstring,
        the encryption check reads it).
  - [x] Migration is reversible (`downgrade` drops the table) and touches nothing existing.

- [x] **T5 — The store (AC1, AC2, AC4, AC7)**
  - [x] `current_stamp(tenant, matter, scopes, version_no)` — one method computing all eight
        observables, scope pre-filtered. See Dev Notes for the exact queries; the extraction digest
        is one ordered single-column scan, hashed in Python (portable, collation-independent).
  - [x] `read_artefact_stamp(...)` / `_write_stamp(session, ...)` — the writer is **private and
        called inside the producing transaction** of `produce_ranking`, `place_line`/`move_line` and
        `record_recall_review`. Never a second commit (AD-22).
  - [x] `read_current_bound(...)` — the latest `recall_review` for the matter + its stamp.
  - [x] Corpus/extraction observables + `unranked_count`: extend `read_triage_table` to carry
        `corpus_count` = the *matter*'s pièce count and `ranked_count` = len(rows). **This changes
        the meaning of the existing `corpus_count` field** — see Dev Notes, it is a deliberate
        correction of a wrong label, and the domain invariant moves with it.

- [x] **T6 — The domain invariant on the table (AC4)**
  - [x] `apx/core/domain/triage_table.py`: `TriageTable` gains `corpus_count` (the matter's pièces)
        and derives `ranked_count = len(rows)` and `unranked_count = corpus_count - ranked_count`.
        `__post_init__` raises when `corpus_count < len(rows)` (a corpus smaller than its own ranking
        is a miscount, never rendered) and keeps the existing conditional partition invariant over
        `ranked_count`.
  - [x] Tests for both invariants, including the pre-existing "before the line is placed" case.

- [x] **T7 — The API (AC1, AC4, AC5, AC6, AC8)**
  - [x] `GET /api/matters/{matter}/freshness` — the assessment for every stamped artefact of the
        matter (each naming its `kind`, its `artefact_id`, `fresh`, `changed`).
  - [x] `GET /api/matters/{matter}/worklist` — the derived lines. Writes nothing.
  - [x] `GET /api/matters/{matter}/bound` — the current recall bound, its freshness and its
        server-produced `copy_text`.
  - [x] `GET /api/matters/{matter}/bound/export` — **409** with the changed inputs when stale; the
        export naming its stamp when fresh.
  - [x] `TriageTableOut` gains `ranked_count` and `unranked_count`; `corpus_count` keeps its name and
        gains its true meaning.
  - [x] All four routes: 404 non-disclosing on out-of-scope/absent (FR-14), `Cache-Control:
        no-store` per the app's existing middleware (AD-…/no ETag), declared in `USER_ACTIONS`.

- [x] **T8 — The three structural checks (AC2, AC3, AC7) — 74 → 77**
  - [x] `apx/checks/staleness_triggers.py` → `every_staleness_trigger_has_an_observable` (FR-58 /
        AD-23): the enumerated `TRIGGERS` keys and the `FreshnessStamp` field names match **both
        ways**; every trigger names a non-blank French phrase and a source (FR/AD). Fails closed on
        an unreadable module.
  - [x] `apx/checks/freshness_never_time_based.py` → `freshness_is_never_time_based` (FR-58 /
        AD-23): AST over `core/domain/freshness.py`, `core/domain/worklist.py` and
        `core/app/read/freshness.py` — no `datetime`/`time`/`timedelta`/`monotonic` import or
        attribute reaches them, and no `FreshnessStamp` field is annotated `datetime`. Fails closed
        on a parse error or a missing module.
  - [x] `apx/checks/artefact_stamp_ownership.py` → `artefact_stamp_is_append_only` (FR-58 / AD-37):
        follow `line_placement_ownership.py` exactly — no `update()`/`delete()` against
        `ArtefactStamp` anywhere, and the stamp writer is called from exactly the enumerated owning
        use cases.
  - [x] Register all three in `apx/checks/registry.py` (import + `CHECKS`), add three `_p(...)` rows
        to `apx/checks/manifest.py`, and add three rows to the `README.md`
        `<!-- structural-properties -->` block. **The first FIVE cells must match the manifest
        exactly** (`manifest_matches_readme` compares only those).

- [x] **T9 — The 4.12 registry (AC8)**
  - [x] Declare the 4 routes and 3 seams in `apx/checks/user_actions.py`. `changes_state` is
        **verified by execution**, never asserted: all four routes are reads, but check whether any
        writes an `audit_record` row on serve (the bound export plausibly should — decide, then set
        the flag to what the probe *observes*).
  - [x] Run the probe; add each new route to a `_Step` so it is actually walked, with the correct
        expected status tuple.

- [x] **T10 — The surface (AC4, AC5, AC6)**
  - [x] `apx/web/src/triage.tsx`: the stale banner (EXPERIENCE-EPIC4 § *State Patterns* — the hook
        is already written there) naming **which input changed** in French, offering a re-rank,
        never acting; the denominator gains the unranked count.
  - [x] The bound + worklist panel: stale in the `review` tier (never gold), the copy button copying
        the server's `copy_text`, the export button disabled with its reason when stale.
  - [x] `api.ts` typed client for the 4 routes; the failed-read state distinct from the empty state
        (`null` = not read, `[]` = read and empty) — the 4.10 fix, applied from the start.

- [x] **T11 — Gate**
  - [x] `ruff check .` clean (line-length 100 — **accented characters push lines over; reflow by
        hand**), all checks green (77), import-linter 3 kept / 0 broken, full pytest green,
        `npm run typecheck` + `npm run build` clean.

---

## Dev Notes

### Which inputs each artefact depends on (`INPUTS_BY_KIND`)

The eight are the complete list of things that *can* move; they are not all inputs to every
artefact. A line move touches only `line_placement` — the ranked order is unchanged byte for byte —
so a banner saying *"votre classement date d'avant votre déplacement de la ligne"* would be **false**,
and a false alarm on the act the user just performed teaches her to dismiss the banner. Each kind
therefore narrows the list, and the narrowing is itself bounded by the structural check: no invented
input, the union over kinds must be the whole enumeration, and the **bound depends on all eight**
(FR-58 is written about the bound). An unlisted kind depends on all eight — over-invalidated, never
under.

| kind | excludes | why |
|---|---|---|
| `ranking` | `line_seq`, `pin_ledger_seq` | placing/moving the line and pinning write only their own ledgers; the ranked order is unchanged (asserted by `ranking_order_ignores_the_pin` and `place_line`'s own contract) |
| `line` | `pin_ledger_seq` | a pin overrides the line for one *pièce* (FR-43); it does not move the cut |
| `bound` | — | it is a statement about the population defined by *(the order, the cut, the pins)*, drawn from a corpus, under a scope, at a configuration |

### The eight observables — one per trigger, and the fidelity of each

`FreshnessStamp` has exactly these fields. Any change here must be mirrored in `TRIGGERS` or the
structural check turns the build red.

| # | trigger (FR-58 / AD-23 / AD-40) | observable | how it is read | fidelity |
|---|---|---|---|---|
| 1 | a new *ranking version* | `ranking_version_no: int` | max `ranking_version.version_no` for the matter | exact (monotonic) |
| 2 | a move of **the line** | `line_seq: int \| None` | max `line_placement.seq` for the version; `None` = unplaced | exact (monotonic per version) |
| 3 | a *pin* added or removed | `pin_ledger_seq: int` | `sum(max seq per pièce)` over `pin_entry` for the matter, `0` when none | exact — every pin act appends with a strictly greater per-pièce `seq`, so the sum strictly increases |
| 4 | a *case theory* revision | `case_theory_version_no: int` | max `case_theory_version.version_no`, `0` = none | exact (monotonic; a **withdrawal is a version**, so it triggers) |
| 5 | a configuration change affecting retrieval/ranking/the estimator | `config_digest: str` | sha256 over the canonical JSON of `{key: effective value}` for **every `CONFIG_SCHEMA` key with `affects_retrieval=True`** — `line_retain_bands` was **added to that set** during implementation: it decides where the recommended cut falls, so a firm that widened the retain policy would otherwise leave every placed line reading fresh | exact |
| 6 | an *RBAC scope* change affecting the population | `scope: str` | `matter_scope.scope` | exact (one scope per matter — the Chinese-wall unit) |
| 7 | any ingestion into the *matter* | `corpus_count: int` | `count(piece)` for the matter | exact — AD-7 + 4.12's probe prove no pièce is ever deleted, so the count is **monotonic**, so ingestion always moves it |
| 8 | a re-extraction of any *pièce* (AD-40) | `extraction_digest: str` | sha256 over `piece_id \x00 text_identity \n` for every pièce **ordered by `piece_id`** | exact |

**Why the config digest reuses `affects_retrieval`.** That flag already exists on `ConfigKey`
(`apx/core/domain/config.py`) and already drives the audit detail line
(`_config_change_detail`). Reusing it means the trigger list and the audited change reason cannot
drift apart, and a new key that affects ranking is covered the moment its author sets the flag they
already have to set.

**Why the extraction digest is a Python-side hash and not SQL.** It must be identical on SQLite (the
test DB) and Postgres, and it must be **collation-independent** (the same reason AD-23's tie-break
is byte-ordered over the pièce identity hash, never over collated text). `piece_id` and
`text_identity` are ASCII hex, so ordering by `piece_id` in SQL and hashing the bytes in Python is
stable on both. Select **only those two columns** — never the row.

**Cost.** `read_triage_table` already loads every ranked row and every pièce name for the matter, so
the digest's single-column scan is the same order of cost the surface already pays; it adds no new
asymptotic class. Do not add an index for it; do not cache it (a cache with an invalidation rule is
exactly the thing this story exists to distrust).

**Why observables 7 and 8 are separate.** Both change on ingestion, and collapsing them would be
cheaper. Keep them apart: FR-58 requires the assessment to **name which input changed**, and "300
pièces arrived" and "a pièce was re-read" are different sentences to a lawyer and different offers on
the worklist. `corpus_count` moves → ingestion. It did not move but the digest did → re-extraction.

*Implemented as `_IMPLIED_BY`:* since an ingestion necessarily moves the digest too, the comparison
**drops the implied name** when the implying one also fired — otherwise the surface would report a
re-extraction that never happened. It only ever removes a redundant name from an already non-empty
set, so no staleness can hide behind it (asserted both ways).

### `assess_freshness` — the shape

```python
@dataclass(frozen=True)
class Freshness:
    kind: str                  # ranking | line | bound
    artefact_id: str
    changed: tuple[str, ...]   # the trigger keys that differ, in TRIGGERS order

    @property
    def fresh(self) -> bool:
        return not self.changed
```

`fresh` is **derived from `changed`**, never stored beside it — the two cannot disagree. There is no
constructor path that produces `fresh=True` with a non-empty `changed`.

### What must NOT appear anywhere in this story's code

- `datetime.now()`, `utcnow()`, `time.time()`, `timedelta`, `monotonic` inside the freshness
  decision. (The stamp's `at` column on the row is fine — it is a record of when, never an input to
  the decision. Keep it out of `FreshnessStamp` itself; `freshness_is_never_time_based` checks
  exactly that.)
- Any `UPDATE` of a produced artefact to mark it stale.
- Any scheduled/queued job touching freshness.
- A `stale` boolean column anywhere.

### Files being modified (read them completely first)

| File | Current state | This story changes | Must not break |
|---|---|---|---|
| `apx/core/domain/triage_table.py` | `corpus_count` is `len(self.rows)` — **the ranking's population, mislabelled**. `__post_init__` asserts the partition against `len(self.rows)` and has the `SIDE_UNSPLIT` conditional. | `corpus_count` becomes a **constructor field** = the matter's pièces; add `ranked_count` and `unranked_count`; add the `corpus_count >= len(rows)` invariant. | the conditional partition invariant (it must now read `ranked_count`); `SIDE_UNSPLIT`; `pair_change_log`. |
| `apx/adapters/store_postgres/store.py` | `read_triage_table` resolves the version FIRST then passes `version_no` down so parts cannot drift. `_piece_names`, `_current_labels` batch their reads (no N+1). | add the stamp read/write, `current_stamp`, `read_current_bound`; pass `corpus_count` into `TriageTable`. | the version-first resolution order; the no-N+1 batching; `piece_is_in_matter`. |
| `apx/api/app.py` | 49 routes; `_MATTER_ABSENT` non-disclosing 404; `_require_piece_in_matter` at the trust boundary. | 4 new routes; `TriageTableOut` gains two fields. | the 404 shape; the `_require_piece_in_matter` guard on the label routes (a 4.10 review fix). |
| `apx/core/app/rank.py`, `line.py` | the owning use cases (AD-37), each writing its artefact + its audit entry atomically (AD-22). | each also writes its stamp **in the same transaction**. | the conditional commit; the single-owner property the `*_ownership` checks assert. |
| `apx/checks/user_actions.py` | 70 rows; complete both ways; fails closed. | +4 routes, +3 seams. | the fail-closed legs; `changes_state` verified by execution. |
| `apx/checks/registry.py` / `manifest.py` / `README.md` | 74 checks in three-site lockstep. | +3, all three sites. | `manifest_matches_readme` compares only the FIRST FIVE cells. |
| `apx/web/src/triage.tsx`, `api.ts` | the triage surface; `null` vs `[]` distinction on the change log. | the banner, the denominator, the bound + worklist. | the `?? 0` concurrency guard on `label_seq` (a 4.10 review fix — a never-labelled row reads `null`). |

### Previous-story intelligence (4.10, 4.11, 4.12 — the traps that actually fired)

- **A failed read must never render as a verified absence.** The 4.10 review's worst confirmed
  finding. Apply from the start here: `null` = not read, `[]` = read and empty, and the worklist and
  bound panels must say which.
- **Validate untrusted identifiers at the HTTP trust boundary**, not at the seam — the
  `_require_piece_in_matter` pattern. The bound/export routes take only `matter`, but if any route
  here grows an identifier parameter, guard it there.
- **`changes_state` is verified by execution, never by a naming rule.** 4.12 proved "a POST changes
  state" false in this build (`login`/`logout` write nothing evidential) and eight *GET*s write audit
  rows. Set each new flag to what the probe observes.
- **Accented characters push lines past ruff's 100 columns** — `pièce`, `é`, `→`, `§`. Reflow by
  hand; the formatter will not do it for you.
- **The story's prose is part of the diff.** 4.12's review confirmed a finding for story/README
  drift. If an observable's fidelity changes during implementation, change this table too.

### Commands (uv-managed — never `pip`)

```
cd /Users/juliantalou/Documents/PRO/01-CLIENTS/APX-Advisory/Dev/apx-mvp && export PATH="$PWD/.venv/bin:$PATH" && ruff check . && python -m apx.checks && python -m pytest -q
```
Run `cd` + `export` in the **same** Bash call (shell state does not persist). **Never export
`DATABASE_URL`.** Frontend: `cd apx/web && npm run typecheck && npm run build`.

### Architecture compliance

- **AD-23** — the whole story. The trigger list is complete and enumerated; staleness is explicit and
  never self-resolving.
- **AD-39** — staleness is a view over inputs, exactly as retained/discarded are views over the
  order. No stored membership, no stored flag.
- **AD-4** — `core/` imports no adapter; the domain is pure. Import-linter enforces it.
- **AD-13 / FR-14** — scope is a query pre-filter; out-of-scope and absent are the same 404.
- **AD-14** — reads go through `core/app/read/`.
- **AD-22 / AD-37** — the stamp is written atomically with its artefact, by that artefact's one
  owning use case.
- **AD-7** — nothing is deleted; `artefact_stamp` is append-only and evidential by default under
  4.12's `evidential_tables` rule.
- **AD-19** — never impute. An unranked pièce is counted as unranked, never sorted to the bottom,
  never folded into discarded.
- **AD-40** — re-extraction is a trigger.
- **FR-56** — each new property carries a registered check; a property with no check is not a
  property.

### UX contract

`_bmad-output/planning-artifacts/ux-designs/ux-apx-mvp-2026-07-27/EXPERIENCE-EPIC4.md` § *State
Patterns* already writes the banner hook and names this story as the owner:

> **Ranking stale** … a `review`-toned banner: *"Le classement date d'avant la dernière modification
> de la théorie du cas. Re-classer produira une nouvelle version ; vos valeurs saisies seront
> conservées."* Re-ranking is offered, never automatic.

Generalise that sentence over the eight inputs (the changed input is named in the banner), reuse
DESIGN.md tokens verbatim, keep the `review` tier **distinct from gold**, and keep the French legal
terms of art (*pièce*, *retenue/écartée*, *la ligne*, *épingler*, *classement*).

---

## Dev Agent Record

### Context Reference

- Epic: `_bmad-output/planning-artifacts/epics.md` § Story 4.13
- PRD: `…/prd.md` § FR-58 (and FR-16, FR-22, FR-23 for the bound)
- Architecture: `…/ARCHITECTURE-SPINE.md` § AD-23, AD-39, AD-40, AD-37, AD-22, AD-7, AD-19
- UX: `…/EXPERIENCE-EPIC4.md` § State Patterns

### Implementation Plan

Built T1→T11 in order. Two design decisions were forced by the tests rather than foreseen, and both
are recorded here because they changed the shape:

**1. Each artefact kind declares which inputs it depends on (`INPUTS_BY_KIND`).** The first run of
the test suite failed on `test_a_freshly_produced_artefact_is_fresh_and_names_nothing`: placing the
line marked the *ranking* stale, because `line_seq` had moved from `None` to `1`. That is false.
`place_line` writes only `line_placement` and the ranked order is unchanged, byte for byte — telling
a lawyer *"votre classement date d'avant votre déplacement de la ligne"* is a lie, and a banner that
raises a false alarm on the act the user just performed teaches her to dismiss it. The true alarm
(300 pièces arrived) is then dismissed with it.

So each kind narrows the eight, each narrowing is argued in the source, and the narrowing is itself
bounded by the structural check: no invented input, the union over kinds must be the whole
enumeration (a trigger every kind excluded is a staleness *deleted* rather than argued), and the
**confidence bound depends on all eight** because FR-58 is written about the bound and fixes its
list literally. The default for an unlisted kind is all eight — over-invalidated, never under.

**2. An ingestion is not reported as a re-extraction (`_IMPLIED_BY`).** The extraction digest covers
every pièce's text identity, so importing one moves it too — but nobody re-read anything. The
comparison drops the implied name when the implying one also fired. This only ever removes a
redundant name from an already non-empty set, so no staleness can hide behind it (asserted both
ways).



### Debug Log

- **The rerank test was ranking pièces the dossier did not hold.** `tests/app/test_labels_survive_a_rerank.py`
  seeded an empty `IngestionResult()` and then ranked three synthetic ids, so the new invariant
  (`corpus_count >= len(rows)`) fired: *"the dossier cannot be smaller than its own ranking"*. The
  test was the thing that was lying, not the product — fixed by seeding the three pièces for real.
  The invariant was NOT weakened, and a `max(corpus, len(rows))` clamp that had briefly been written
  was removed: clamping would defeat the exact miscount the invariant exists to refuse.
- **`artefact_stamp`'s columns had to be classified.** The AD-31 allowlist check failed on
  `kind`/`artefact_id`/`stamp_json` — correctly, since it is allowlist-shaped. Added table-qualified
  with the NFR-56 argument (the same one `RankingVersion.identity_json` carries): two counts, two
  seqs, the matter's own already-plaintext scope name and two sha256 digests. No PII, no content.
- **The 4.12 registry turned the build red twice**, exactly as designed: once for the 3 new
  `core/app/read/` seams, once for the 4 new routes. The probe then refused to run until each new
  route was walked.
- **`export-bound` needed its success path exercised.** Every write step in the probe moves an
  input, so the bound recorded early is stale by the time the read steps run and the export would
  (correctly) 409 — leaving `changes_state=True` unverified. The step records a FRESH bound as
  arrangement first; the proof is the 200 assertion, not the census, so a refusal fails loudly
  rather than passing because the arrangement happened to write.



### Completion Notes

**Gate:** ruff clean · **77** structural checks (74 → 77) · import-linter **3 kept / 0 broken** ·
**1426 passed / 12 skipped** (1359 → 1426) · `tsc -b` and `vite build` clean · the offline fitness
driver green.

Every AC is asserted by a named test:

- **AC1** — `tests/api/test_freshness_api.py`, one test per trigger, each moving the input through
  the product's own seam, plus `test_every_enumerated_trigger_has_a_test_here` which fails the build
  if a ninth trigger is added without one.
- **AC2** — `test_the_writer_that_moved_the_input_never_touched_freshness`: the ingest route knows
  nothing about staleness, and the stamp ledger is byte-identical before and after, yet the ranking
  reads stale. Plus `every_staleness_trigger_has_an_observable`.
- **AC3** — `test_reading_a_stale_artefact_five_times_leaves_it_stale` (identical verdict every
  time), `test_a_re_rank_produces_a_new_artefact_and_leaves_the_old_one_stale` (the old version is
  still readable and still stale — nothing was refreshed), and `freshness_is_never_time_based`.
- **AC4** — `test_pieces_imported_after_the_ranking_are_unranked_not_discarded` and
  `test_the_denominator_equation_holds_both_ways`. This is the 4.10 review's deferred finding, paid.
- **AC5** — the 409 refusal names what moved and writes nothing; the copy string carries the
  staleness; a bound with **no** stamp reads *unverifiable* and is refused too (an absence of
  evidence is not evidence of freshness).
- **AC6** — the worklist offers and starts nothing; `[]` (read, nothing stale) is distinct from a
  404 (not read).
- **AC7** — `artefact_stamp_is_append_only`, plus 4.12's probe, which protects the new table by
  default because `evidential_tables = all mapped tables − TRANSIENT_TABLES`.
- **AC8** — 4 routes and 3 seams in `USER_ACTIONS`, all walked by the probe.

**Deferred, as scoped:** the review-effort estimate (no artefact exists to stamp), a stamp on an
exhaustive result set (fresh by construction — it never outlives its own request), Epic 5's
estimator/sampling run, and the home-screen worklist.



### File List

**New (11)**
- `apx/core/domain/freshness.py` — the trigger enumeration, the stamp, the comparison
- `apx/core/domain/worklist.py` — the derived worklist
- `apx/core/ports/freshness.py` — the read port
- `apx/core/app/read/freshness.py` — the three seams + `BoundReading`
- `apx/adapters/store_postgres/migrations/versions/0030_artefact_stamp.py`
- `apx/checks/staleness_triggers.py`, `apx/checks/freshness_never_time_based.py`,
  `apx/checks/artefact_stamp_ownership.py`
- `tests/domain/test_freshness.py`, `tests/domain/test_worklist.py`,
  `tests/api/test_freshness_api.py`

**Updated (17)**
- `apx/adapters/store_postgres/models.py` — `ArtefactStamp`
- `apx/adapters/store_postgres/store.py` — `_compute_stamp`, `_retrieval_config`, `_write_stamp`,
  `current_stamp`, `read_artefact_stamps`, `read_current_bound`, `audit_bound_export`; the stamp
  written inside `record_ranking` / `place_line` / `move_line` / `record_recall_review`;
  `corpus_count` on the triage table
- `apx/core/domain/triage_table.py` — `corpus_count` a field, `ranked_count`, `unranked_count`, the
  new invariant
- `apx/core/domain/confidence.py` — `RecordedBound`
- `apx/api/app.py` — 4 routes + models; `ranked_count`/`unranked_count` on `TriageTableOut`
- `apx/checks/user_actions.py`, `registry.py`, `manifest.py`, `encryption.py`; `README.md`
- `apx/web/src/api.ts`, `triage.tsx`, `tokens.css`
- `tests/probe/test_never_hard_delete.py`, `tests/api/test_triage_table_api.py`,
  `tests/app/test_labels_survive_a_rerank.py`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`



### Change Log

- 2026-08-06 — Story 4.13 implemented (T1→T11). Staleness built as a derived comparison of recorded
  input stamps, never a stored flag; the eight enumerated triggers each with an exact observable;
  per-kind input sets so no artefact is claimed stale by an input it does not have; the unranked
  count made visible wherever the sets are counted; a stale bound refused as current and unable to
  be copied without its staleness. 3 structural checks (74 → 77), 4 routes, 3 seams, 1 migration.

_(dev agent fills)_

---

## Senior Developer Review (AI)

**Date:** 2026-08-07 · **Outcome:** Approved after fixes · **Scale:** 13 agents, ~2.4 M tokens,
three lenses (correctness / security-isolation / contract), every finding independently
skeptic-verified with the burden of proof on the claim (default REFUTED).

**Result: 10 findings → 4 confirmed verdicts over 3 distinct defects → all fixed → 6 refuted.**
Plus **2 defects I found and fixed myself** before the review returned. Every one of the five is
proven by a regression/control pair: the fix reverted makes a named test fail, restored makes it
pass.

**Coverage gap, stated rather than hidden:** the security-isolation lens **stalled on all six
attempts** and returned nothing. Its findings are lost. I ran that ground myself before the review
came back — scope pre-filtering on all four new routes, `(tenant, matter)` in every new query, the
non-disclosing 404 (asserted byte-identical in
`test_out_of_scope_and_absent_are_indistinguishable`), the AD-31 classification of `stamp_json`,
atomicity of the stamp with its artefact, and the per-read cost of the digests (which is what drove
the one-stamp-per-version fix) — but that is my own audit, not an adversarial one, and it should be
read as weaker evidence than the two lenses that did complete.

### Confirmed and fixed

1. **[HIGH] The *confidence bound*'s actual population was observed by nothing.**
   Confirmed twice, by two independent lenses. `record_recall_review` computes the bound over
   `count(piece_label WHERE label='discard')` — but none of the eight observables watched
   `piece_label`. A re-judge (`POST /api/matters/{m}/judge` → `save_labels`) moves the discarded
   pile while touching no ranking version, no line, no pin and no corpus count. The reviewer drove
   it through the real routes with the production LLM tier stubbed: the pile went from 3 pièces to
   4, and `GET /bound` still returned `population=3`, `status_fr="à jour"`,
   `exportable_as_current=true`; `GET /bound/export` returned **200** and audited an egress; the
   clipboard string said *"au plus 0 des 3 pièces écartées… — à jour."* That is AD-23's named
   failure with a cause the story had not enumerated.
   **Fix:** a **ninth observable**, `discard_population`, sourced from FR-23's own clause — *"or the
   population it was drawn from"*. A **digest, not a count**: a re-judge that moves one pièce out of
   the pile and another in leaves the cardinality identical while the population is a different set,
   and a bound is a statement about a set. Only the bound depends on it (the relevance verdict is
   downstream of the order, never an input to it — `label_not_a_ranking_input`). AD-23's eight are
   now the check's **floor**, which may not shrink.

2. **The offered recomputation never discharged.** `read_artefact_stamps` returned every stamp ever
   written, so the worklist offered a re-rank for a superseded version forever: the lawyer accepts
   the offer, and the banner still demands one — growing by one paragraph per act.

3. **The banner named a superseded artefact with the definite article of the live one.** Reproduced
   through the real seams: immediately after a line move, *"**La ligne** — périmé depuis : un
   déplacement de la ligne"* — about a placement that is current. Exactly the false alarm on the act
   the user just performed that this story's own `INPUTS_BY_KIND` comment argues destroys the signal.
   **Fix for 2 and 3 (one root):** the reader now reports `superseded` per artefact — the live
   ranking version, the placement in force over it, the most recent bound — and a superseded
   artefact is **not work**. It keeps its verdict on the freshness surface (still readable, verdict
   still true of it, AD-7) but carries no worklist line. The banner additionally **names its
   version** (AD-23).

### Found and fixed before the review returned

4. **A line placed over a NON-latest ranking version read falsely fresh.** The stamp recorded
   `line_seq` for that version while the comparison used `ranking_version_no` — the *matter*'s
   maximum, a different number. Constructed the divergence: v1's cut moved twice, v2's once, and the
   artefact read **fresh**. Fixed by resolving each artefact's own version from the artefact itself.
5. **`line_retain_bands` was not flagged `affects_retrieval`.** It decides where the recommended cut
   falls, so widening the retain policy left every placed line reading fresh.

Also fixed while there: the current stamp is now computed **once per distinct version** rather than
once per artefact — the observables are a full pass over the *matter*'s pièces, and one page load
was paying for three identical passes at the 100 000-pièce design target.

### Refuted (6)

- *A concurrent import during a ranking is stamped as if the ranking had seen it* — refuted on
  reachability: `produce_ranking` has no HTTP entry point, so there is no "Request A".
- *`_subsume` hides a re-extraction that coincides with an import* — refuted: no re-extraction path
  exists (`_insert_piece_if_absent` is the only `Piece` writer and it never updates), and the
  subsumption only ever removes a redundant name from an already non-empty set.
- *Rescoping contradicts the PRD's "a moved wall needs no staleness marking"* — refuted: FR-58 names
  an RBAC scope change in its trigger list verbatim; the FR-30 sentence is about propagation, not
  staleness.
- *The recall panel renders a bound in the gold seal with no freshness* — refuted: that panel only
  ever shows the response of the act the user just performed, computed in the same transaction.
- *`artefact_stamp_is_append_only` misses a for-loop bulk rewrite* — the AST gap is real but is the
  same documented residual the four sibling ledger checks carry; not a defect introduced here.
- *AC1's text no longer matches `INPUTS_BY_KIND`* — refuted as a code defect; the story prose was
  reconciled anyway (the per-kind table and the `_IMPLIED_BY` note are in Dev Notes).

### Final gate

ruff clean · **77** structural checks · import-linter **3 kept / 0 broken** · **1437 passed / 12
skipped** · `tsc -b` + `vite build` clean · offline fitness driver green. Integrity: of 14
snapshotted files, 5 byte-identical and 9 changed — exactly the ones edited to fix the findings
above. Secret scan of the 30 files in this diff: clean.

**Flagged for Julian, outside this story:** the repo-wide secret scan matched
`tests/api/test_log_redaction.py` and `tests/_fixtures/secret_violations/hardcoded_key/settings.py`,
both committed in Story 1.8 (`8b35467`) and labelled *"a fake key value, never a real one"*. The
string is the same as the live Mistral key. Neither file is in this diff and neither was touched
here. If the value is genuinely the live key, rotating it and purging it from history is a decision
for Julian, not a side effect of a story commit.
