# `apx/timedrun/` — the timed 5 000-pièce concurrent run (U2, the gate)

**A measurement, not a feature.** This is a throwaway harness with spike-quality adapters — *not a
unit of the product*. It ships no user surface, no API route, no product-runtime behaviour. It is
edge/measurement tooling, exactly like `apx/fitness/`, and is **excluded from the product-runtime
structural scan** (`isolation_harness._RUNTIME_EXCLUDE`) — its `nvidia-smi` VRAM probe is a
subprocess that `no_subprocess_call_outside_extraction` (AD-28) rightly forbids in the runtime.

It exists to **falsify or confirm** the CCBE €2 000-machine sizing before any performance number is
quoted downstream. Until it runs, every wall-clock promise in the PRD is speculation (Open Risk 3:
*"nobody summed the machine"* — OCR, BGE-M3 and a 24B model were each sized as if alone). It **gates
Epics 3, 4 and 5**.

## Run it (on demand — never in CI)

```
python -m apx.timedrun [N] [WORKERS]
```

Offline it uses a deterministic stub judge (set `STUB_LATENCY` to simulate an LLM round-trip) and a
fake embedder — no real model, no GPU — so the concurrent orchestration and the machine-envelope
capture are provable without spend. Set `MISTRAL_API_KEY` / `LLM_API_KEY` to time the real model.

It prints the judgment-cascade metrics (dedup + the concurrent LLM band) and the **machine
envelope** of the four-stage concurrent pipeline — extraction + OCR + embedding + LLM judgement
running concurrently — as wall-clock, peak RSS and peak VRAM.

## The real figures are PENDING the target hardware — never faked (NFR-2)

The real 5 000-pièce concurrent measurement needs the target hardware — the €2 000 machine, both
inference profiles, the real BGE-M3, and Tesseract on real scanned PDFs — none available in dev/CI.
So the real figures are recorded **`pending`** in `measurements.json` and the harness **records
`pending`, it never invents a number** (NFR-2, PRD §5/§7). `MeasurementRecord` (`record.py`) holds
every figure per profile; `measured` is `false` for both profiles today.

### The two inference profiles (AD-27, config-as-data)

| profile | inference                                             | VRAM |
| ------- | ----------------------------------------------------- | ---- |
| `gpu`   | vLLM · Mistral Small 3.2 24B at Q4 (only Q4 fits)     | 24 GB |
| `cpu`   | Ollama                                                | —    |

### The falsification thresholds (named constants in `record.py`, not magic numbers)

A breach is a **recorded finding** — it revises the hardware ask or the cascade aggressiveness,
never smoothed over. All figures extrapolate to the 100 000-pièce design target.

- **chunk yield > ~8 M** (`MAX_CHUNKS`) → the pgvector-only single store is wrong (Open Risk 1).
- **HNSW p95 > ~2 s** (`MAX_HNSW_P95_MS`) under a *matter*-scoped filter → wrong (Open Risk 1).
- **wall-clock past one weekend** (`WEEKEND_SECONDS`, 48 h) for 100 000 pièces → UJ-1 invalid and
  the €2 000 sizing wrong (Open Risk 3).
- **Tesseract overtakes the LLM** as the bottleneck → the hardware recommendation is wrong (Risk 3).
- **index build exceeds `maintenance_work_mem`** (`MAINTENANCE_WORK_MEM_GB`, 64 GB) → wrong (Risk 1).

## The gate it installs (NFR-2)

`apx/checks/perf_gate.py::no_perf_ceiling_before_measurement` is a structural property (run by
`python -m apx.checks`) that forbids asserting any latency / throughput / wall-clock ceiling in the
runtime while the measurement is unrecorded — so no number is quoted before it is measured. A ceiling
**derived** from the measurement record is permitted. It is vacuous until such a ceiling is declared.
