"""Deliberately violating fixture (story 1.7, AD-31): a start-up gate that checks only the
application-key layer and raises, but never the data-volume layer — AD-31 requires BOTH, so
startup_gate_is_fail_closed MUST fire on the missing layer. AST-parsed only; never imported."""

from typing import Any


def load_key_from_env(env: Any = None) -> bytes:
    return b""


def startup_gate(env: Any = None) -> None:
    load_key_from_env(env)  # only the key layer — the data volume is never attested
    raise RuntimeError("no application encryption key")
