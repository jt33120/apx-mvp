"""The offline environment (AD-2), as data.

These are set for the fitness job and for any air-gapped run so that libraries
which phone home by default do not. Kept here as one source of truth rather than
scattered across CI YAML and docker files.
"""

from __future__ import annotations

# name -> value. Applied to the process environment before the app boots offline.
OFFLINE_ENV: dict[str, str] = {
    "HF_HUB_OFFLINE": "1",       # huggingface_hub: never reach the Hub
    "TRANSFORMERS_OFFLINE": "1",  # transformers: never reach the Hub
    "DO_NOT_TRACK": "1",          # generic opt-out honoured by many tools
    "SCARF_NO_ANALYTICS": "1",    # Scarf telemetry opt-out
}
