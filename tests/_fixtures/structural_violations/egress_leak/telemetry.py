"""An outbound network call outside the egress adapters (FR-32/AD-45 violation). AST-scanned."""

from __future__ import annotations

import requests


def phone_home(data: dict) -> None:
    requests.post("https://telemetry.example/collect", json=data)  # a fourth egress path
