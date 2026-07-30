"""Run the timed-run gate on demand — a MEASUREMENT, not a product feature (Story 2.13 / U2).

    python -m apx.timedrun [N] [WORKERS]

Prints two things: the judgment-cascade metrics (dedup + the concurrent LLM band) and the machine
envelope of the full four-stage concurrent pipeline (extraction + OCR + embedding + LLM judgement)
— wall-clock, peak RSS, peak VRAM.

Offline it uses the deterministic stub (set STUB_LATENCY to simulate an LLM round-trip) and a fake
embedder — no real model, no GPU, so the orchestration and the metric capture are provable without
spend. Set MISTRAL_API_KEY / LLM_API_KEY to time the real model — mind the cost, one call per
residual-band piece. The REAL 5 000-pièce figures need the CCBE target hardware (both inference
profiles, the real BGE-M3, Tesseract on real scans) and are recorded `pending` in measurements.json
until then — never faked (NFR-2). Edge tooling like ``apx/fitness/``, never run in CI.
"""

from __future__ import annotations

import os
import sys

from apx.adapters.llm_openai_compat.judge import LLMJudge
from apx.timedrun.harness import StubJudge, stub_stages, synthetic, timed_cascade, timed_pipeline

TERM = "pertinent"


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    workers = int(sys.argv[2]) if len(sys.argv) > 2 else 16
    raw = synthetic(n, term=TERM)

    key = os.environ.get("LLM_API_KEY") or os.environ.get("MISTRAL_API_KEY")
    if key:
        fallback = LLMJudge(
            base_url=os.environ.get("LLM_BASE_URL", "https://api.mistral.ai/v1/chat/completions"),
            api_key=key,
            model=os.environ.get("LLM_MODEL", "mistral-small-latest"),
        )
        print(f"Run chronométré — {n} docs, {workers} workers, juge RÉEL ({fallback.name})")
    else:
        fallback = StubJudge(latency=float(os.environ.get("STUB_LATENCY", "0")))
        print(f"Run chronométré — {n} docs, {workers} workers, juge STUB (hors-ligne, "
              f"latence {fallback.latency}s)")

    print("\nCascade de jugement (dédup + band LLM concurrent) :")
    print(timed_cascade(raw, TERM, fallback, workers=workers).report())

    stages = stub_stages()
    stages["judge"] = lambda text: fallback.judge(question=TERM, text=text)
    print("\nEnvelope machine (4 étages concurrents : extraction + OCR + embedding + LLM) :")
    print(timed_pipeline(raw, workers=workers, **stages).report())


if __name__ == "__main__":
    main()
