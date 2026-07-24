"""The fail-closed start-up gate (story 1.7, AD-31, AC5): the deployment refuses to start
unless BOTH encryption layers are in place — the application key AND the attested data
volume — with no permissive default and no warning-and-continue. Each branch is driven on
the pure function with an explicit env; one test drives the real FastAPI lifespan wiring.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from apx.api.startup import StartupRefused, startup_gate
from apx.core.domain.crypto import generate_key

_GOOD_KEY = generate_key()


def _env(**overrides: str) -> dict[str, str]:
    base = {"APX_ENCRYPTION_KEY": _GOOD_KEY, "APX_VOLUME_ENCRYPTED": "1"}
    base.update(overrides)
    return base


def test_a_fully_provisioned_deployment_starts() -> None:
    startup_gate(_env())  # both layers present — returns without raising


def test_a_missing_key_refuses_start() -> None:
    env = _env()
    del env["APX_ENCRYPTION_KEY"]
    with pytest.raises(StartupRefused, match="application encryption key"):
        startup_gate(env)


def test_a_malformed_key_refuses_start() -> None:
    with pytest.raises(StartupRefused, match="application encryption key"):
        startup_gate(_env(APX_ENCRYPTION_KEY="too-short-to-be-a-key"))


def test_an_unattested_volume_refuses_start() -> None:
    env = _env()
    del env["APX_VOLUME_ENCRYPTED"]
    with pytest.raises(StartupRefused, match="data volume"):
        startup_gate(env)


def test_a_volume_flag_that_is_not_truthy_is_not_enough() -> None:
    # no permissive default: only an explicit truthy attestation counts
    with pytest.raises(StartupRefused, match="data volume"):
        startup_gate(_env(APX_VOLUME_ENCRYPTED="0"))


def test_one_gate_names_both_layers_at_once() -> None:
    with pytest.raises(StartupRefused) as excinfo:
        startup_gate({"APX_ENCRYPTION_KEY": "", "APX_VOLUME_ENCRYPTED": "no"})
    message = str(excinfo.value)
    assert "application encryption key" in message and "data volume" in message


def test_the_app_lifespan_refuses_to_boot_without_a_key(monkeypatch: pytest.MonkeyPatch) -> None:
    # the wiring, not just the pure function: with the key cleared, the real boot refuses
    from apx.api.app import app

    monkeypatch.delenv("APX_ENCRYPTION_KEY", raising=False)
    with pytest.raises(StartupRefused):  # lifespan surfaces the refusal; no server is served
        with TestClient(app):
            pass
