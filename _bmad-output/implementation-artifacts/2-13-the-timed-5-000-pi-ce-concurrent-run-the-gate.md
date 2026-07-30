---
baseline_commit: 8ada6b6
---

# Story 2.13: The timed 5 000-pièce concurrent run — the gate

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As the APX build,
I want a real measurement of OCR, embedding and inference running **concurrently** on one machine over 5 000 *pièces*,
so that every wall-clock promise downstream rests on a number rather than on three components each sized as if it owned the machine alone.

## Scope note — the measurement FRAMEWORK + the GATE; the real numbers are PENDING the target hardware

This is a **measurement, not a feature** (WORK-BREAKDOWN U2, "the measured machine — RISK GATE"; "FRs: none, it precedes them"). It ships **no user-visible capability**; it exists to falsify or confirm the €2 000-machine sizing, and it **closes Epic 2 and gates Epics 3, 4 and 5** — no wall-clock or throughput number may be quoted to a firm until it exists (Open Risk 3: *"nobody summed the machine"* — OCR at ~25 pages/min, BGE-M3 at 4 800 passages/s and a 24B model contending for the same 24 GB of VRAM were each sized as if alone).

**The hard constraint, stated up front:** the real 5 000-pièce concurrent measurement needs the **target hardware** — the CCBE €2 000 machine, the GPU profile (vLLM, Mistral Small 3.2 24B at Q4 on 24 GB VRAM) and the CPU profile (Ollama), the real BGE-M3, and Tesseract on real scanned PDFs. That hardware is **not available in dev/CI**. So — exactly as Story 2.12 deferred the recall NUMBER to a ranker — 2.13 builds the parts that are CI-verifiable now and records the real figures as **unmeasured / pending**, never faked (NFR-2, PRD §5/§7: *no per-operation target is invented*).

What 2.13 builds (CI-verifiable): the **concurrent measurement harness** (formalising the existing `apx/timedrun/` spike into the full four-stage pipeline — extraction, OCR, embedding, LLM judgement running concurrently — capturing wall-clock, peak RSS and peak VRAM, with stub/fake adapters at small N so the orchestration and the metric capture are proven without the model or GPU); the **measurement-record schema** (per inference profile, honestly `pending` until the hardware run); the **falsification criteria as code** (the four thresholds); and — the load-bearing deliverable — the **gate**: a structural check that NO latency or throughput ceiling is asserted anywhere until a measured figure exists (NFR-2), mirroring the Story 2.12 gold-set merge gate.

What is deferred, honestly (to the hardware run): the real 5 000-doc wall-clock / peak-VRAM / chunk yield / HNSW p95 / index-build / full-text-index-size figures, per GPU and CPU profile. They are recorded as `pending`, and the gate makes any downstream perf commitment reference them.

## Acceptance Criteria

1. **The concurrent measurement harness runs the full four-stage pipeline and captures the machine envelope (AC: U2, Open Risk 3).** The harness runs extraction, OCR, embedding and LLM judgement **concurrently** over N *pièces* (formalising the `apx/timedrun/` spike, which today times only dedup + judge), and captures **wall-clock, peak RSS and peak VRAM** (VRAM via `nvidia-smi` when a GPU is present, recorded `unavailable` otherwise — **no new dependency**; RSS via `resource.getrusage`). In CI it runs at a small N with stub/fake adapters (the real BGE-M3, the real LLM and Tesseract are never loaded), proving the orchestration and the metric capture without spend. *(test: a small concurrent run returns a populated envelope; concurrency is real; nothing loads a real model.)*

2. **The measurement record is per-profile and honestly `pending` — never a faked number (AC: NFR-2, AD-27).** A structured `MeasurementRecord` (per inference profile — `gpu` and `cpu`, config-as-data per AD-27) holds the figures the run must produce: wall-clock (+ its extrapolation to 100 000 *pièces*), peak RSS, peak VRAM, measured chunk yield, HNSW p95 under a *matter*-scoped filter, index build within `maintenance_work_mem`, full-text index size, per-*pièce* maxima, and the Tesseract-vs-LLM bottleneck. Until the target-hardware run exists it is recorded `measured: false` / `pending` for every real figure — the harness records `pending`, it never invents a number (NFR-2). *(tests: the record schema is complete; a pending record is not mistakable for a measured one; a test asserts every real figure is `pending` today.)*

3. **The falsification criteria are code, and the failure path records a finding (AC: U2, Open Risk 1/3).** A pure function decides, from a `MeasurementRecord`, whether the run **falsifies** the sizing — breaching any of: chunk yield **> ~8 M** (extrapolated to 100 000), HNSW p95 **> ~2 s**, wall-clock extrapolating **past one weekend** for 100 000 *pièces*, **Tesseract overtaking the LLM** as the bottleneck, or the index build exceeding `maintenance_work_mem`. A breach is a **recorded finding** (which revises the hardware ask or the cascade aggressiveness), never smoothed over. *(tests: a record breaching each threshold is flagged with the specific finding; a passing record is clean; the thresholds are named constants, not magic numbers.)*

4. **The gate: no latency/throughput ceiling is asserted until a measured figure exists (AC: NFR-2, ties SM-C4) — the deliverable that closes Epic 2.** A structural-property check (registered in the manifest, `python -m apx.checks`) asserts that no runtime module or config declares a latency / throughput / wall-clock **ceiling** while the timed-run measurement is unrecorded — so no number is quoted before it is measured. It is **vacuous until such a ceiling is declared** and fires the moment one appears without a recorded measurement; a derived ceiling (from a user journey, per NFR-2) that references the measurement record is permitted. *(tests: it fires on a fixture declaring a perf ceiling with the measurement pending; it is vacuous on the real tree; the check count rises and README ↔ manifest stay in lockstep.)*

5. **A measurement, not a feature — it ships no product capability (AC: U2).** The harness is edge/measurement tooling (a throwaway harness with spike-quality adapters, "not a unit of the product"), documented as such and runnable on demand (`python -m apx.timedrun`); it exposes no API, no user surface, and adds no product runtime behaviour. *(test/structure: no API route or product surface references the harness; it is measurement tooling like `apx/fitness/`.)*

6. **The gate stays green, with no schema change.** `ruff` clean; the full suite green; `python -m apx.checks` passes with the new perf-ceiling check registered (count rises, README ↔ manifest lockstep); alembic remains single head **0021** (2.13 adds **no migration** — it is a harness, a record and a check).

## Tasks / Subtasks

- [x] **Task 1 — formalise + extend the timed-run harness to the full concurrent pipeline (AC1).**
  - [x] Extend `apx/timedrun/harness.py` (keep the spike's shape — `synthetic`, the concurrency model, `Metrics`) so a run orchestrates **extraction + OCR + embedding + LLM judgement concurrently** over N units, not only dedup + judge. Real extraction on synthetic inputs; OCR / embedding / LLM behind their ports so a **stub OCR**, the **`FakeEmbedder`** (port boundary, AD-11) and the existing **`StubJudge`** stand in when the real components are absent (CI), the real ones when configured (hardware). *(Added `timed_pipeline(units, *, extract, ocr, embed, judge, workers)` — the four stages are injected callables so any can be swapped for the real component on hardware; `stub_stages()` is the canonical CI bundle, StubJudge + a fake 8-dim embedder + passthrough extract + empty OCR, so no real model loads. A scan whose extraction is empty falls back to OCR, as production does.)*
  - [x] Capture the machine envelope with **stdlib only** (no new dependency): wall-clock (`time.perf_counter`), peak RSS (`resource.getrusage(RUSAGE_SELF).ru_maxrss`), peak VRAM (a `nvidia-smi --query-gpu=memory.used` subprocess when present — reuse the AD-28 subprocess discipline — else `unavailable`). *(`Envelope` dataclass + `sample_vram_mb()` (capture_output, timeout, never inherits stderr) + `_VramPeak` background sampler (peak stays `None` with no GPU, never faked) + `_peak_rss_mb()` (platform-normalised: bytes on macOS, KiB on Linux → MiB on both). Because the nvidia-smi subprocess would trip `no_subprocess_call_outside_extraction` (AD-28), I applied the Task-5 exclusion early — `timedrun` added to `isolation_harness._RUNTIME_EXCLUDE` — so the per-task gate stays green.)*
  - [x] Tests (`tests/timedrun/`): a small concurrent run populates the envelope; the four stages run concurrently (a latent stage overlaps, as the existing `test_concurrency_speeds_up_a_latent_band` proves for the judge); no real model/OCR is loaded in CI. *(4 new tests: envelope populated + every unit through every stage; concurrency hides a latent judge (workers=12 < workers=1); stub_stages over the synthetic corpus with no real model; + a checks test that the timedrun subprocess does not trip AD-28.)*

- [x] **Task 2 — the per-profile measurement record, honestly pending (AC2).**
  - [x] A `MeasurementRecord` (frozen dataclass or a small module) keyed by inference profile (`gpu` / `cpu`, AD-27), with every figure from the research: `wall_clock_s`, `extrapolated_100k_s`, `peak_rss_mb`, `peak_vram_mb`, `chunk_yield`, `hnsw_p95_ms`, `index_build_within_work_mem`, `full_text_index_bytes`, `per_piece_max`, `tesseract_vs_llm`, and a `measured: bool`. A real figure is `None` / `pending` until the hardware run — the harness **records `pending`, never a fabricated number** (NFR-2). *(`apx/timedrun/record.py`: frozen `MeasurementRecord`, `REAL_FIGURES` tuple, `pending(profile)`; `is_measured` is True only when `measured` AND every figure is set — so a half-filled or `measured`-flipped-only record can never read as measured.)*
  - [x] A recorded artefact (`apx/timedrun/measurements.json` or similar) holding the current state — `measured: false` for both profiles today — that the gate (Task 4) reads and a test asserts is honestly pending. *(`measurements.json` — both profiles `measured: false`, every figure `null`, with a `note` stating the figures are pending the CCBE hardware; `load_records()` + `any_measured()` read it.)*
  - [x] Tests: the schema covers every research figure; `measured` is `false` today for both profiles; a `pending` record can never be read as a measured one.

- [x] **Task 3 — the falsification criteria as code (AC3).**
  - [x] `falsifies(record) -> list[str]` returning the breached thresholds, from **named constants** (`MAX_CHUNKS ≈ 8_000_000`, `MAX_P95_MS ≈ 2_000`, the weekend ceiling for 100 000 *pièces*, the Tesseract-over-LLM condition, `maintenance_work_mem`). A breach is a recorded finding (per the failure path); it revises the hardware ask or the cascade aggressiveness, never smoothed over. *(`falsifies` in `record.py` with named constants `MAX_CHUNKS`, `MAX_HNSW_P95_MS`, `WEEKEND_SECONDS`, `MAINTENANCE_WORK_MEM_GB`; each check runs only on a measured (non-None) figure. `is_clean` = measured AND no breach; `is_falsified` = any breach.)*
  - [x] Tests: a synthetic record breaching each threshold is flagged with the specific finding; a passing record is clean; a `pending` record is neither passing nor falsified (it is *unmeasured*). *(A pending record: `falsifies == []` yet `not is_clean` and `not is_measured` — unmeasured, never passing.)*

- [x] **Task 4 — the gate: no perf ceiling until measured (AC4) — the load-bearing deliverable (NFR-2).**
  - [x] `apx/checks/perf_gate.py`: a structural check `no_perf_ceiling_before_measurement` that fires if a runtime module/config declares a latency / throughput / wall-clock **ceiling** (a constant/config named for one) while the measurement record is unrecorded — a **derived** ceiling that references the measurement record is permitted. **Vacuous** until such a declaration exists. Anchor robustly and document it as best-effort (the Story 2.12 review's lesson: a guessed-name whitelist is a secondary net; the CI harness + the honest `pending` record are the substrate). Fail-closed on an unparseable file; injectable `roots`. *(Detection = a module-level assignment name carrying BOTH a perf DIMENSION token (latency/throughput/wall_clock/p95/…) AND a BOUND token (max/limit/budget/target/_ms/…); a module importing `apx.timedrun[.record]` is deriving from the record → permitted. `timedrun` is excluded from the scan so its falsification thresholds aren't mistaken for ceilings. `measured` reads `measurements.json` (False today) or is injectable for tests. Docstring states plainly it is best-effort and the pending record is the substrate.)*
  - [x] Register it in `apx/checks/manifest.py` + `apx/checks/registry.py` + the README property block (keep README ↔ manifest lockstep). *(Row `no-perf-ceiling-before-measurement`, NFR-2 / AD-32; `python -m apx.checks` rises 48 → 49; README ↔ manifest lockstep green.)*
  - [x] Tests (`tests/checks/`): fires on a fixture declaring a perf ceiling with the measurement pending; passes (permitted) on a derived ceiling that cites the measurement record; vacuous on the real tree. *(7 tests: fires on a bare `MAX_QUERY_LATENCY_MS`; permits a derived ceiling importing the record; a plain `REQUEST_TIMEOUT_S` is not a ceiling; permitted once measured; vacuous on the real tree; fails closed on an unparseable file.)*

- [x] **Task 5 — a measurement, not a feature; and take it out of the product-runtime scan (AC5).**
  - [x] Rewrite the harness docstrings + `apx/timedrun/README` (or the module header) to state plainly: a throwaway measurement harness (spike-quality adapters), not a product unit; run on demand `python -m apx.timedrun`; the real 5 000-doc figures are **pending the target hardware** and recorded as such. Document the four falsification thresholds and the two profiles. *(New `apx/timedrun/README.md` — a measurement not a feature, the two profiles (gpu/cpu, AD-27), the five falsification thresholds, pending on hardware. `__main__.py` docstring rewritten + now prints the four-stage machine envelope too; harness/record docstrings state `pending`/never-faked throughout.)*
  - [x] **Add `timedrun` to the structural checks' build-tooling exclusion** (`isolation_harness._RUNTIME_EXCLUDE`, today `{checks, fitness, __pycache__}`). This is **required**, not optional: the VRAM probe calls a `nvidia-smi` subprocess, and `no_subprocess_call_outside_extraction` (AD-28) forbids a subprocess call in the product runtime — `timedrun` is measurement tooling (U2: "not a unit of the product"), exactly like `apx/fitness/`, so it belongs in the same exclusion. Confirm no API route / product surface depends on `apx/timedrun`. *(Done in Task 1 — the subprocess required it for the per-task gate. `_RUNTIME_EXCLUDE` is now `{checks, fitness, timedrun, __pycache__}`. Confirmed: nothing under `apx/api` or `apx/core` imports `apx.timedrun`; the only importer is `apx/checks/perf_gate.py` (build tooling reading the pending record), which is itself outside the runtime scan.)*

- [x] **Task 6 — full re-gate (AC6).** `ruff check .`; `pytest` (no `DATABASE_URL` override — SQLite baseline); `python -m apx.checks` (count rises by the perf-ceiling check; README ↔ manifest lockstep); `alembic heads` = single **0021** (no migration). *(`ruff check .` clean; `pytest` 742 passed / 10 skipped; `python -m apx.checks` 49 passed (48 → 49); `alembic heads` = single `0021_chunk_embedding` — no migration.)*

## Dev Notes

### The load-bearing idea: the gate + the framework now; the number when the hardware exists

U2 is *"the number nobody has"* and it *"precedes"* the FRs. The architecture is explicit that this measurement **must happen before any retrieval code is written** (Open Risk 1) and that **until it exists every wall-clock promise in the PRD is speculation** (Open Risk 3). But the run needs the €2 000 machine, both inference profiles, the real BGE-M3 and Tesseract — none in dev/CI. So 2.13 delivers what CI can verify — the concurrent harness, the record schema, the falsification code, and the **gate** that forbids quoting a number before it is measured — and records the real figures as `pending`. This is the same shape as Story 2.12 (build the substrate + the gate; defer the real figure to the missing input, never fake it).

### Formalise the existing spike, don't rebuild it

`apx/timedrun/harness.py` already exists (from the pre-BMAD "slice A / thicken" spike): `synthetic(n)` (deterministic corpus shape — ~30 % duplicates, ~20 % filter-promoted, the rest the LLM band), `timed_cascade(...)` (times dedup then the **concurrent** judge over a thread pool), `Metrics`, `StubJudge`, `_Counting`, and `python -m apx.timedrun [N] [WORKERS]`. It times only **two** of the four stages (dedup + judge). 2.13 keeps its shape and its concurrency model and **adds extraction + OCR + embedding** so all four stages run concurrently, plus the peak-RSS / peak-VRAM capture. Its own docstring already says *"never in CI (a real 5,000-doc run costs money and minutes)"* — 2.13 makes the **stubbed** small-N run CI-safe while the real run stays on-demand on hardware.

### The measured outputs (record every one, all `pending` today)

From U2 + Open Risk 1/3 + the Story 2.13 ACs: (1) wall-clock, extrapolated to 100 000 *pièces*; (2) peak RSS; (3) peak VRAM; (4) chunk yield; (5) HNSW p95 under a *matter*-scoped filter; (6) index build within `maintenance_work_mem` (64 GB machine); (7) full-text (AD-21) index size; (8) per-*pièce* maxima; (9) the Tesseract-vs-LLM bottleneck determination. Two deferred questions are meant to fold into this same run (record the hooks): head-row contention rate (OQ-3) and the Mistral Small 3.2 24B vs Ministral 3 model comparison (OQ-6/Q6).

### The falsification thresholds (named constants, not magic numbers)

- chunk yield **> ~8 M** (extrapolated to 100 000 *pièces*) → the single-store (pgvector-only) decision is wrong (Open Risk 1; keep the vector column behind a migration you can change — it is, at head 0021).
- HNSW p95 **> ~2 s** under a *matter*-scoped filter → wrong (Open Risk 1).
- wall-clock extrapolating **past one weekend** for 100 000 *pièces* → the hardware recommendation and the €2 000 sales story are both wrong, and UJ-1 (retained set readable over a weekend) is **invalid**, not merely missed (Open Risk 3).
- **Tesseract overtakes the LLM** as the bottleneck (driven by the scanned-PDF proportion) → the hardware recommendation is wrong (Open Risk 3).
- index build **exceeds `maintenance_work_mem`** on a 64 GB machine → wrong (Open Risk 1).

### The gate (NFR-2) — no invented ceiling

NFR-2: *"No per-operation latency or throughput target is set anywhere, and none may be invented. Where a ceiling exists it is derived from a user journey … and a measured figure … is recorded from the first baseline and may then only improve."* The gate enforces the *"none may be invented"* half structurally: a declared perf ceiling (a latency/throughput/wall-clock constant or config) while the measurement is unrecorded fires the check; a **derived** ceiling that references the measurement record is permitted. Follow the Story 2.12 gold-set-gate pattern in `apx/checks/` — and its review's lessons: anchor as robustly as a static check can, state that structural detection is best-effort, and let the honest `pending` record + the CI harness be the real substrate. (The related enforced screen already in the architecture — AD-32's pre-flight, which states the configured profile's expected wall-clock before an import is accepted — will consume these figures once they exist; 2.13 does not rebuild it.)

### Architecture guardrails (binding)

- **U2 / Open Risk 1 & 3** — the measurement precedes retrieval code and gates every perf/throughput commitment; it is a throwaway harness, not a product unit.
- **AD-27** — two inference profiles (GPU vLLM / CPU Ollama) behind one OpenAI-compatible interface, selected by configuration-as-data; application code never knows which. The record is **per profile**; only Q4 fits the €2 000 machine.
- **AD-11** — the embedder is faked at the port boundary in CI; the real BGE-M3 is never loaded.
- **AD-28** — the OCR / `.msg` extractors run out-of-process. The `nvidia-smi` VRAM probe is itself a subprocess, which `no_subprocess_call_outside_extraction` forbids in the product runtime — so `timedrun` must be moved into the checks' build-tooling exclusion (Task 5), which is correct anyway (U2: it is not a product unit). Capture the probe's output, never inherit stderr (AD-28 discipline).
- **NFR-2 / SM-C4 / OQ-6** — no invented latency/throughput target; a ceiling is derived from UJ-1's weekend and rests on a measured, ratcheted figure.
- **AD-2 / FR-55** — the harness is measurement tooling alongside `apx/fitness/`; the perf gate is a structural property in the same `python -m apx.checks` frame.

### Files to touch (and blast radius)

**Modified (the existing spike → a formalised harness)**
- `apx/timedrun/harness.py` — the four-stage concurrent orchestration + the peak-RSS/peak-VRAM capture (keep `synthetic`/`Metrics`/`StubJudge`).
- `apx/timedrun/__main__.py` — the on-demand runner; document the profiles + the pending real run.

**New**
- `apx/timedrun/record.py` (or in `harness.py`) — the per-profile `MeasurementRecord` + `falsifies(record)`.
- `apx/timedrun/measurements.json` — the recorded state (`measured: false` for both profiles today).
- `apx/timedrun/README.md` — a measurement, not a feature; the thresholds; the two profiles; pending on hardware.
- `apx/checks/perf_gate.py` — the `no-perf-ceiling-before-measurement` structural check.
- Tests: `tests/timedrun/` (the concurrent envelope, the record pending, the falsification criteria) + `tests/checks/test_perf_gate.py`.

**Modified (source)**
- `apx/checks/manifest.py`, `apx/checks/registry.py`, `README.md` — register the perf-ceiling property.
- `apx/checks/isolation_harness.py` — add `timedrun` to the build-tooling exclusion `{checks, fitness}` (required — the VRAM `nvidia-smi` subprocess would otherwise trip `no_subprocess_call_outside_extraction`; `timedrun` is measurement tooling, U2).

**NOT touched** — no `models.py` change, **no alembic migration** (head stays 0021); no product-runtime app behaviour, no user surface.

### What NOT to build (scope discipline)

- No real 5 000-doc measurement, no invented wall-clock / VRAM / p95 numbers — deferred to the target hardware, recorded as `pending` (NFR-2: never invent).
- No retrieval, ranking, or the-line — 2.13 precedes them (it is the gate).
- No new dependency (no `nvidia-ml-py`, no `psutil`) — stdlib `resource` + a `nvidia-smi` subprocess.
- No rebuild of the AD-32 pre-flight screen or the LLM judge — reuse the ports + the existing adapters.
- No migration; no product surface.

### Project Structure Notes

- `apx/timedrun/` already exists as the spike home; 2.13 formalises it in place. It is measurement tooling (like `apx/fitness/`), not a product unit — Task 5 decides whether it joins the structural-check build-tooling exclusion.
- The perf gate is the only `apx/checks/` addition (a new module + its manifest/README rows), consistent with how every structural guard is registered — and with the Story 2.12 gold-set gate it mirrors.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-2.13] (lines 970–984) — the four ACs (concurrent measurement; no ceiling until measured; a measurement not a feature; the recorded-finding failure path).
- [Source: WORK-BREAKDOWN.md#U2] (lines 109–127, 843–848) — "the measured machine — RISK GATE"; delivers the concurrent run + chunk yield + HNSW p95 + FT index size; gates U5/U9/U11/U14/U15 + every perf commitment; the falsification thresholds.
- [Source: ARCHITECTURE-SPINE.md#Open-Risk-1] (1633–1647) and [#Open-Risk-3] (1663–1680) — chunk yield / p95 / index build; "nobody summed the machine"; the concurrent-envelope numbers.
- [Source: prd.md §9 Scale (1310–1313), SM-C4 (1269), SM-18 (1258), OQ-6 (1530)] and [epics.md#NFR-2 (160)] — no invented target; ceilings derived + measured + ratcheted.
- [Source: ARCHITECTURE-SPINE.md#AD-27] (758–785) — the two inference profiles, config-as-data, the €2 000 / Q4-24 GB envelope.
- Reuse: `apx/timedrun/harness.py` + `__main__.py` + `tests/timedrun/test_timedrun.py` (the spike to formalise), the extraction/OCR adapters, `tests/embedding_fakes.py` (the fake embedder), the LLM judge port + `StubJudge`, `apx/checks/gold_gate.py` (the Story 2.12 gate to mirror), `apx/fitness/` (the measurement-tooling pattern).

## Dev Agent Record

### Agent Model Used

claude-opus-4-8[1m] (Opus 4.8, 1M context) — dev-story.

### Debug Log References

- Full suite: 742 passed, 10 skipped (41 s), SQLite baseline (no `DATABASE_URL`).
- `python -m apx.checks`: 49 structural properties (48 → 49; the perf-ceiling gate added).
- `alembic heads`: single `0021_chunk_embedding` — 2.13 adds no migration.
- `python -m apx.timedrun 8 4` smoke: prints the cascade metrics AND the four-stage machine envelope; VRAM honestly `indisponible (pas de GPU)`, RSS captured.

### Completion Notes List

- **A measurement, not a feature (U2).** Formalised the existing `apx/timedrun/` spike into the full four-stage concurrent pipeline; the real 5 000-pièce figures are recorded **pending** (`measurements.json`, both profiles `measured: false`) and never faked (NFR-2), exactly as Story 2.12 deferred the recall number.
- **The envelope (AC1).** `timed_pipeline(units, *, extract, ocr, embed, judge, workers)` runs extraction + OCR + embedding + LLM judgement concurrently (up to `workers` in flight, stages overlapping — Open Risk 3) and captures wall-clock (`perf_counter`), peak RSS (`resource.getrusage`, platform-normalised to MiB) and peak VRAM (a background `nvidia-smi` sampler, `None` with no GPU). **Stdlib only — no new dependency.** `stub_stages()` is the CI bundle (no real model/GPU loaded).
- **The record (AC2).** `MeasurementRecord` (frozen, per profile gpu/cpu, AD-27) with every research figure; `is_measured` is True only when `measured` AND every figure is set, so a pending or half-filled record can never read as measured.
- **Falsification (AC3).** `falsifies(record)` from named constants (`MAX_CHUNKS`, `MAX_HNSW_P95_MS`, `WEEKEND_SECONDS`, `MAINTENANCE_WORK_MEM_GB`); each check runs only on a measured figure; a pending record is neither passing (`is_clean` False) nor falsified (unmeasured).
- **The gate (AC4, load-bearing).** `apx/checks/perf_gate.py::no_perf_ceiling_before_measurement` fires on a module-level latency/throughput/wall-clock ceiling constant declared while the measurement is unrecorded; a ceiling derived from the record (imports `apx.timedrun`) is permitted; vacuous until one is declared. Registered (manifest + registry + README lockstep); 48 → 49. Best-effort by name (no interface to anchor on) — the honest pending record is the substrate (the Story 2.12 gold-gate lesson).
- **Out of the runtime scan (AC5).** Because the VRAM probe is a subprocess (AD-28), `timedrun` was added to `isolation_harness._RUNTIME_EXCLUDE` (now `{checks, fitness, timedrun, __pycache__}`) — measurement tooling like `apx/fitness/`. No `apx/api` or `apx/core` module imports `apx.timedrun`.
- **No schema change (AC6).** No migration; alembic head stays `0021`.

### File List

**New**
- `apx/timedrun/record.py` — `MeasurementRecord` (per-profile gpu/cpu), `pending`/`load_records`/`any_measured`, the falsification constants + `falsifies`/`is_clean`/`is_falsified`.
- `apx/timedrun/measurements.json` — the recorded state, both profiles `measured: false` (pending the hardware).
- `apx/timedrun/README.md` — a measurement not a feature; the two profiles; the five thresholds; pending on hardware; the gate it installs.
- `apx/checks/perf_gate.py` — the `no_perf_ceiling_before_measurement` structural check.
- `tests/timedrun/test_record.py`, `tests/timedrun/test_falsification.py`, `tests/checks/test_perf_gate.py`.

**Modified**
- `apx/timedrun/harness.py` — `timed_pipeline`, `Envelope`, `sample_vram_mb`, `_VramPeak`, `_peak_rss_mb`, `stub_stages` (kept `synthetic`/`Metrics`/`StubJudge`/`timed_cascade`).
- `apx/timedrun/__main__.py` — measurement-not-a-feature docstring; now prints the four-stage envelope too.
- `apx/checks/isolation_harness.py` — `timedrun` added to `_RUNTIME_EXCLUDE` (+ docstring).
- `apx/checks/manifest.py`, `apx/checks/registry.py`, `README.md` — register the perf-ceiling property.
- `tests/timedrun/test_timedrun.py` — pipeline/envelope/stub_stages tests.
- `tests/checks/test_extraction_isolation.py` — timedrun subprocess does not trip AD-28.

### Change Log

- 2026-07-29 — Story 2.13 implemented (measurement + gate; real figures pending hardware). Four-stage concurrent envelope harness, per-profile pending `MeasurementRecord`, falsification-as-code, the NFR-2 perf-ceiling gate (48 → 49 checks), timedrun out of the runtime scan. No migration (head 0021). ruff clean; 742 passed / 10 skipped.
- 2026-07-30 — Adversarial 3-reviewer review + fixes. Resolved 5 findings (see Senior Developer Review): perf-gate fail-closed on an unreadable measurement state; broadened + tokenised ceiling detection (SLA/deadline/response-time now caught, `MEASURED_*` excluded, `sla`⊄`translation`); `sample_vram_mb` robust to garbage/non-UTF8 nvidia-smi output; `is_measured` fixed for the CPU profile (no VRAM owed); documented the gate's best-effort limits. ruff clean; 746 passed / 10 skipped; 49 checks; head 0021.

## Senior Developer Review (AI)

**Reviewers:** three independent adversarial lenses (gate load-bearing / measurement honesty / concurrency + isolation), execution-verified. The background subagents were unstable (two died on API errors, one produced injection-shaped text, one stopped); each lens was then completed directly with scratchpad probes and mutate-run-revert verification. **Outcome: Changes Requested → all resolved.**

**Findings (all fixed):**
1. **[MED] Gate did not fail closed on a corrupt/missing `measurements.json`.** `no_perf_ceiling_before_measurement(measured=None)` let `any_measured()` raise `JSONDecodeError`/`KeyError`/`FileNotFoundError` out of the check — every other structural check fails closed. **Fix:** wrap the measurement read in `try/except (OSError, ValueError, KeyError)` → fail-closed `CheckResult`. Test: `test_it_fails_closed_on_an_unreadable_measurement_state`.
2. **[MED] Gate missed common ceiling spellings.** `RETRIEVAL_SLA_MS`, `QUERY_DEADLINE_S`, `RESPONSE_TIME_LIMIT_MS` slipped through (the rule required a dimension token; SLA/deadline/response-time aren't dimensions). **Fix:** token-based detection — `sla`/`deadline` are self-sufficient ceiling words, `response_time` a dimension phrase, plus a `MEASURED_*`/`OBSERVED_*` exclusion (a recorded figure is not an invented ceiling, NFR-2) and whole-token matching so `sla ⊄ translation`. Real-tree vacuity re-verified. Tests: `test_it_fires_on_common_ceiling_spellings`, `test_it_does_not_flag_lookalikes`.
3. **[MED] `sample_vram_mb` crashed on garbage/non-UTF8 nvidia-smi output** (NVML errors print to stdout with exit 0), killing the sampler thread on the real hardware path though the docstring promised `None`. **Fix:** decode with `errors="replace"` and skip unparseable lines. Test: `test_sample_vram_survives_garbage_or_non_utf8_nvidia_smi_output`.
4. **[MED] `is_measured` was unreachable for the CPU profile.** `peak_vram_mb` is legitimately `None` on `cpu` (no GPU), but `is_measured` required every figure set — so a real CPU run would read "unmeasured" forever and `any_measured()` would ignore it. **Fix:** `pending_figures()` does not owe `peak_vram_mb` on the `cpu` profile. Test: `test_a_fully_measured_cpu_record_is_measured_even_though_it_has_no_vram`.
5. **[LOW] The "derived ceiling" exemption is a bare-import loophole** and detection is module-level-constant only. **Fix (doc):** the module docstring now states both as known best-effort limitations — the load-bearing guarantee is the honest `pending` record, not the name heuristic.

**Verified sound (no change):** the concurrency is real (a latent stage is hidden by more workers; pure-Python stages correctly flat — honestly a thread model whose heavy stages release the GIL), no sampler-thread leak, the no-GPU path returns `None` (never a fabricated 0), the `timedrun` runtime-scan exclusion is correctly scoped (only the subprocess check would fire on it — nothing else is hidden; `timedrun` imports only `apx.*` + stdlib), the gold-set gate still passes, `measurements.json` is honestly all-`null` with `measured: false`, `is_measured` cannot read a pending/partial record as measured, `falsifies` does not crash on a pending record, and README ↔ manifest stay in lockstep (49 checks).
