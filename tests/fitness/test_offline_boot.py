"""The app boots with the offline env set and makes no outbound network call.

This is the in-process, runner-agnostic form of the network isolation (AD-2): we
refuse every real outbound socket connection, set the offline env, boot the
FastAPI app, and serve a built-in request. The app's own transport is in-process
(ASGI), so it works with sockets blocked — proving the boot needs no network.
Container-level `--network none` layers on top where the runner allows.
"""

from __future__ import annotations

import socket

import pytest

from apx.fitness.offline_env import OFFLINE_ENV


@pytest.fixture
def _no_outbound_network(monkeypatch):
    """Any attempt to open an outbound TCP connection raises."""

    def _refuse(*_args, **_kwargs):
        raise AssertionError("outbound network attempted during offline boot")

    monkeypatch.setattr(socket.socket, "connect", _refuse)
    monkeypatch.setattr(socket, "create_connection", _refuse)


def test_offline_env_is_the_expected_set() -> None:
    assert OFFLINE_ENV == {
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "DO_NOT_TRACK": "1",
        "SCARF_NO_ANALYTICS": "1",
    }


def test_app_boots_and_serves_with_no_outbound_network(monkeypatch, _no_outbound_network) -> None:
    for name, value in OFFLINE_ENV.items():
        monkeypatch.setenv(name, value)

    from fastapi.testclient import TestClient

    from apx.api.app import app

    with TestClient(app) as client:
        # A built-in route — proves the app booted and serves without the network.
        response = client.get("/openapi.json")

    assert response.status_code == 200
    assert response.json()["info"]["title"] == "APX"
