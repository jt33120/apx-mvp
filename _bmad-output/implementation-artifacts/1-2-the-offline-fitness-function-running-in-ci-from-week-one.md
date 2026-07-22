---
baseline_commit: 79f59e09352cbf21ab7c62714d8986ee38dd30bb
---

# Story 1.2: The offline fitness function, running in CI from week one

Status: done

## Story

As the APX build,
I want a CI job that boots the application in a network-isolated container and drives it end to end,
so that "portable to an air-gapped firm machine" is measured continuously rather than discovered in front of the first client.

**Scope in one line:** the *fitness frame* — network isolation, the offline env, the no-hosted-SDK egress guard, and an offline boot — plus a growing end-to-end driver. The frame exists from week one (AD-2); its end-to-end coverage grows as later stories add ingest/index/rank/export.

## Acceptance Criteria

Reproduced from `epics.md` Story 1.2, then read against the honest state of the scaffold (nothing to ingest, index, rank or export exists yet — those are epics 2–5).

> **Given** a network-isolated container with no hosted-provider service reachable and no outbound network except a stubbed model-provider endpoint,
> **When** the fitness job runs,
> **Then** it asserts the application starts, ingests a folder, indexes it, retrieves over both engines, ranks, places **the line**, produces an *audit record* and exports — and a failure of any step fails the build (FR-55).
> **And** the job enumerates which capabilities do **not** survive the model provider's absence — the ranking, the justifications, the priced statement — rather than describing them.
> **And** the *confidence bound* sentence is asserted to be regenerable from the *audit record* with **no** model call.
> **And** *(failure path)* introducing a hard dependency on a hosted-provider SDK in the core turns this job red.

1. **AC1 — Network-isolated boot.** A CI job runs the application's boot + checks inside a network-isolated context (no outbound network) with the offline env set (`HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, `DO_NOT_TRACK=1`, `SCARF_NO_ANALYTICS=1`), and the app starts. A failure of the boot fails the build.
2. **AC2 — The end-to-end driver exists and grows.** A single fitness driver enumerates the FR-55 pipeline stages (start · ingest · index · retrieve · rank · place the line · audit · export) and, for each, either **asserts** it (where the capability exists) or records it **PENDING (story N)** (where it does not yet). The driver fails if a stage that is marked asserted regresses. Today only *start* and *checks-green* are asserted; the rest are PENDING with their owning story. The driver never fakes a stage.
3. **AC3 — The no-hosted-SDK egress guard (the failure path, AD-45/AD-3).** A structural check fails the build if any runtime module imports a hosted-provider SDK from a deny-list. A committed fixture that imports a denied SDK proves the guard fires (BROKEN), and the real tree passes green.
4. **AC4 — Capability degradation is enumerated, not described.** The driver prints which capabilities do **not** survive the model provider's absence (ranking, justifications, the priced statement), each tagged with its owning story, so the list is generated from the pipeline stages rather than hand-written prose.
5. **AC5 — The confidence-bound-offline principle is scaffolded honestly.** The *confidence bound* does not exist yet (epic 5). The driver records this stage as PENDING (5.4) with the invariant it must later satisfy — regenerable from the *audit record* with no model call — so the assertion is ready to be switched on rather than invented now.

## Tasks / Subtasks

- [x] **Task 1 — The egress deny-list check** (AC: #3)
  - [x] `apx/checks/egress.py`: a static check (import-graph via import-linter `forbidden` contracts, and/or a source scan) that fails if any `apx` runtime module imports a hosted-provider SDK. Deny-list is *configuration-as-data* (a Python constant here; later a config key): at minimum `supabase`, `boto3`, `botocore`, `google.cloud`, `vercel`, `openai` used directly in `apx.core` (the LLM client lives behind the adapter, not the core). [Source: ARCHITECTURE-SPINE.md#AD-45, #AD-3]
  - [x] Register it in the `apx/checks` harness runner alongside the layering check, with the same "≥1 rule evaluated" floor so a dropped deny-list rule fails rather than passes. [Source: story 1.1 review — the guard-floor lesson]
  - [x] Failure-path fixture + test: a module importing a denied SDK makes the check report a violation (BROKEN); the real tree passes. [Source: AC5 pattern of 1.1]

- [x] **Task 2 — The offline env and the offline-boot test** (AC: #1)
  - [x] Define the offline env as data (a small `apx/fitness/offline_env.py` or a compose/CI env block): `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, `DO_NOT_TRACK=1`, `SCARF_NO_ANALYTICS=1`. [Source: story 1.1 Dev Notes › fitness function; AD-2]
  - [x] A test (`tests/fitness/test_offline_boot.py`) that boots the FastAPI app under the offline env with **no network** (block sockets in-process, e.g. monkeypatch `socket.socket` to refuse, or assert the app import + a TestClient GET on a health path make zero outbound connections) and asserts it starts. No hosted-provider service is reached. [Source: FR-55]

- [x] **Task 3 — The end-to-end fitness driver** (AC: #2, #4, #5)
  - [x] `apx/fitness/driver.py` (runnable `python -m apx.fitness`): a list of pipeline stages, each `(name, owning_story, state)` where state ∈ {ASSERTED, PENDING}. Today ASSERTED: *start*, *checks-green*. PENDING: ingest (2.x), index (2.8), retrieve (3.x), rank (4.x), place-the-line (4.8), audit (5.5), export (6.1), confidence-bound-offline (5.4). It runs each ASSERTED stage and fails on regression; it prints the PENDING stages and the degradation list (AC4) from the same source of truth. It never marks a PENDING stage green. [Source: FR-55; epics.md#Story-1.2]
  - [x] A test asserting the driver fails if an ASSERTED stage is made to fail, and that no stage is silently skipped.

- [x] **Task 4 — The fitness CI job** (AC: #1, #3)
  - [x] Add a `fitness` job to `.github/workflows/ci.yml` (or a new `fitness.yml`) that: sets the offline env; runs with network disabled where the runner allows (`docker run --network none` of a minimal step, or at minimum the in-process socket-block test of Task 2); runs `python -m apx.checks` (now incl. the egress guard), `python -m apx.fitness`, and the fitness tests. A failure of any fails the build. [Source: AD-2]
  - [x] Document that full container-level `--network none` end-to-end (vendoring the embedder weights, the stubbed model endpoint) grows with the pipeline; 1.2 ships the frame and the in-process isolation. [Source: story 1.1 Dev Notes]

- [x] **Task 5 — Verify green-on-empty, update README, commit** (AC: all)
  - [x] Full pipeline green: harness (layering + egress), fitness driver, all tests, web build, compose config, ruff. The egress guard proven live (a denied import turns it red; revert → green).
  - [x] README: a short "Offline fitness" section — what the frame guarantees today and how the end-to-end driver grows.

## Dev Notes

- **This story is the frame, not the pipeline.** Story 1.1's Dev Notes anticipated exactly this: 1.2 drives the structure 1.1 built and asserts the end-to-end path *as it comes to exist*. Faking ingest/index/rank/export today would be the v1 failure (demo-shaped) in miniature — so the driver marks them PENDING with their owning story and never green. [Source: ARCHITECTURE-SPINE.md#AD-2; story 1.1]
- **The egress guard is the real deliverable.** "Only code travels" and "runs air-gapped" are structural properties (AD-45, AD-3), and this is where the first one lands. The deny-list must have the same *floor* the layering check gained in the 1.1 review: a dropped rule fails, not passes. [Source: story 1.1 Senior Developer Review]
- **`openai` is denied *in the core only*.** The OpenAI-compatible client is legitimate inside `apx/adapters/llm_openai_compat` (it talks to vLLM/Ollama over a local HTTP endpoint, AD-27); it must never be imported by `apx.core`. So the deny-list is scoped: hosted SDKs (supabase, boto3, google.cloud, vercel) forbidden anywhere in `apx`; `openai` forbidden in `apx.core`. [Source: ARCHITECTURE-SPINE.md#AD-27, #AD-45]
- **In-process network isolation** (Task 2) is the portable, runner-agnostic form; a GitHub-hosted runner cannot always be put on `--network none` for the whole job. Blocking sockets in-process (refuse `connect`) proves "the boot makes no outbound call" deterministically. Container-level isolation is layered on where the runner allows. [ASSUMPTION on the exact socket-block mechanism.]

### What this story must NOT do

- No ingestion, index, retrieval, ranking, audit or export **implementation** — the driver only *marks* those PENDING (their stories: 2.x–6.1). Building any is a scope violation.
- No Dockerfile that vendors the embedder weights, no model stub server — those grow with the pipeline (later in Epic 1/2). 1.2 ships the frame.
- No schema, auth, encryption — unchanged from 1.1's NOT-list.

### Testing standards

Tests under `tests/fitness/` and `tests/checks/`, unreachable from runtime (AD-16). Same pytest runner. The egress guard, like the layering guard, is *enforced as a structural property* (AD-33) — a static check, with a committed failure-path test proving it fires.

### References

- [Source: ARCHITECTURE-SPINE.md#AD-2] — the offline fitness function as a network-isolated CI job from week one.
- [Source: ARCHITECTURE-SPINE.md#AD-3] — one artefact / three environments; the deny-list in `checks/`.
- [Source: ARCHITECTURE-SPINE.md#AD-45] — exactly three egress paths; the egress check owned in `checks/`.
- [Source: ARCHITECTURE-SPINE.md#AD-27] — the OpenAI-compatible client behind the adapter (why `openai` is core-forbidden, adapter-allowed).
- [Source: ARCHITECTURE-SPINE.md#AD-33] — structural properties are static checks with the three verbs.
- [Source: epics.md#Story-1.2] — the user story and acceptance criteria.
- [Source: implementation-artifacts/1-1-...md › Senior Developer Review] — the guard-floor and BROKEN-assertion lessons, applied to the egress guard.

## Dev Agent Record

### Agent Model Used

Claude Opus 4.8 (1M context) — dev-story.

### Debug Log References

- import-linter needed `include_external_packages = true` (the egress deny-list forbids external packages) and `google.cloud` had to become `google` (subpackages of external packages are not valid forbidden modules).
- `allow_indirect_imports = true` on the egress contracts is deliberate: the guard flags a runtime module *directly* reaching for a hosted SDK; a transitive third-party use is not our build's concern.
- starlette 1.3.1's TestClient requires `httpx2` (not httpx) — added to the dev group for the offline-boot test.
- The 1.1 guard-floor lesson generalised: the harness now enforces a per-contract floor (every REQUIRED contract present-and-KEPT), so dropping any of the three fails the build — verified by `test_a_dropped_required_contract_fails` and by hand.

### Completion Notes List

- **All 5 ACs met.** AC1 network-isolated boot (offline env + in-process socket block, `tests/fitness/test_offline_boot.py`); AC2 the driver enumerates the FR-55 pipeline with 2 ASSERTED / 9 PENDING (each tagged with its owning story) and never fakes a stage; AC3 the egress deny-list guard (BROKEN on a hosted-SDK import, proven by fixture + live demo); AC4 the degradation list is generated from the stages; AC5 the confidence-bound stage is PENDING (5.4) carrying its offline-regenerable invariant.
- **Refactor:** `apx/checks/layering.py` → `apx/checks/import_contracts.py`, generalised from one contract to the required set (layering + egress), keeping the cwd-independence and the floor. `__main__.py` updated; the 1.1 test renamed accordingly.
- **Scope respected:** no ingest/index/rank/audit/export *implementation* — only PENDING markers. No Dockerfile/model-stub (grows with the pipeline). No schema/auth/encryption.
- **Deviation recorded:** `httpx2` added to dev deps (test transport). Deny-list is a starting set (Open Q2).

### File List

**Added:** `apx/checks/import_contracts.py`, `apx/fitness/{__init__,offline_env,driver,__main__}.py`, `tests/checks/test_import_contracts.py`, `tests/fitness/{test_offline_boot,test_driver}.py`, `tests/_fixtures/egress_violation/{.importlinter,bad_egress/__init__.py}`.
**Modified:** `pyproject.toml` (egress contracts + include_external_packages + httpx2), `apx/checks/__main__.py`, `.github/workflows/ci.yml` (fitness job), `README.md` (Offline fitness), `uv.lock`.
**Removed:** `apx/checks/layering.py` (→ import_contracts.py), `tests/checks/test_layering_check.py` (→ test_import_contracts.py).

## Senior Developer Review (AI)

**Date:** 2026-07-22 · **Outcome:** Approved (focused adversarial self-review — the dispatched reviewer subagent glitched; findings were verified empirically by running the guard against each attack). Review depth deliberately lighter than 1.1's three-reviewer pass, per the risk calibration for this infrastructure story.

### Verified by attack

- **Floor holds, fails loudly.** Renaming a contract in `pyproject.toml` out of sync with `REQUIRED_CONTRACTS` → `required contract(s) missing — guard dropped` (safe direction). ✓
- **`from google import cloud` is caught** (top-level `google` forbidden). ✓
- **A hosted-SDK import in the core turns the harness red**, and reverting returns it green. ✓
- **Dynamic import bypasses the static guard** (`importlib.import_module("boto3")` is not caught). **Resolved by documentation, not a code change** — this is inherent to static import analysis. `import_contracts.py` now states the limitation explicitly and names the **network isolation** (offline boot, later `--network none`) as the *actual-egress* backstop. The two guards are complementary; neither is presented as complete. The static guard's job is to stop casual/accidental hosted-SDK code, which it does.

### Accepted, recorded (not code changes)

- **Deny-list is a starting set** (`supabase`, `boto3`, `botocore`, `google`, `vercel`; `openai` core-only). `anthropic`, `azure`, `cohere`, raw `requests`-to-a-hosted-URL are not enumerated — extensible per Open Q2. Acceptable for v1.
- **The CI `fitness` job runs on a GitHub-hosted runner that is not container-isolated**; the network claim rests on the in-process socket block, represented honestly here and in Open Q1. Container `--network none` grows with the pipeline.
- Refactor did not weaken the 1.1 layering guarantee (still one of the 3 required contracts; its BROKEN fixture test still passes).

## Change Log

- 2026-07-22 — Story 1.2 implemented and self-reviewed adversarially. One MEDIUM (dynamic-import bypass) resolved by documenting the static/runtime split; two LOWs accepted with rationale (deny-list extensibility, runner isolation). Egress guard proven live; floor generalised from 1.1.

## Open Questions for the human

1. **In-process socket block vs container `--network none`.** 1.2 uses in-process socket blocking for a deterministic, runner-agnostic "no outbound call" proof, and layers container isolation where the runner allows. Confirm that is the right trade-off for now, or require true container isolation immediately (heavier, and partly blocked until the embedder weights are vendored).
2. **Deny-list contents.** Starting deny-list: `supabase`, `boto3`, `botocore`, `google.cloud`, `vercel` (anywhere in `apx`); `openai` (in `apx.core` only). Confirm or extend — anything hosted a future contributor might reach for.
