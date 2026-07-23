"""Run the timed-run gate.

    python -m apx.timedrun [N] [WORKERS]

Offline it uses the deterministic stub (set STUB_LATENCY to simulate an LLM round-
trip). Set MISTRAL_API_KEY / LLM_API_KEY to time the real model — mind the cost, one
call per residual band piece.
"""

from __future__ import annotations

import os
import sys

from apx.adapters.llm_openai_compat.judge import LLMJudge
from apx.timedrun.harness import StubJudge, synthetic, timed_cascade

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

    print(timed_cascade(raw, TERM, fallback, workers=workers).report())


if __name__ == "__main__":
    main()
