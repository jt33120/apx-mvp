"""Deliberately violating fixture (story 1.7, AD-31): a start-up gate that inspects both
layers but only WARNS instead of raising — a warning-and-continue is not a fail-closed gate,
so startup_gate_is_fail_closed MUST fire. AST-parsed only; never imported."""

from typing import Any


def load_key_from_env(env: Any = None) -> bytes:
    return b""


def startup_gate(env: Any = None) -> None:
    load_key_from_env(env)  # the key layer is inspected...
    _volume_layer = "APX_VOLUME_ENCRYPTED"  # ...and the volume layer is named...
    if not _volume_layer:
        return
    # ...but a missing layer only prints — it never raises. Forbidden: no fail-closed refusal.
    print("warning: encryption not fully configured, continuing anyway")
