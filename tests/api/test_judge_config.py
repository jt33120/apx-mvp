"""The judge honours the tenant's model endpoint/name as configuration-as-data (story 1.9,
AD-24/AD-27): a non-default `model_endpoint`/`model_name` is used live; otherwise the deployment
default (env) applies. The API key stays a SECRET (env only). No network — the judge is only
composed, never called.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from apx import wiring  # Story 7.3 — the judge has ONE composition site now
from apx.adapters.store_postgres.models import Base
from apx.adapters.store_postgres.store import SqlStore


def _store(tmp_path: Path) -> SqlStore:
    engine = create_engine(f"sqlite:///{tmp_path / 'apx.db'}", future=True)
    Base.metadata.create_all(engine)
    return SqlStore(sessionmaker(bind=engine, future=True))


def test_judge_honours_a_tenant_configured_endpoint_and_model(tmp_path: Path, monkeypatch) -> None:
    store = _store(tmp_path)
    monkeypatch.setenv("LLM_API_KEY", "a-key")
    store.set_config("t", "boss", "model_endpoint", "https://onprem.local/v1")
    store.set_config("t", "boss", "model_name", "ministral-3")
    judge = wiring.open_llm_judge(store, "t")
    assert judge is not None
    # the base is normalised to the chat-completions URL, and the model is the tenant's
    assert judge._base_url == "https://onprem.local/v1/chat/completions"
    assert judge._model == "ministral-3"


def test_judge_falls_back_to_env_when_the_tenant_endpoint_is_default(
    tmp_path: Path, monkeypatch
) -> None:
    store = _store(tmp_path)  # the tenant never set model_endpoint → the deployment default applies
    monkeypatch.setenv("LLM_API_KEY", "a-key")
    monkeypatch.setenv("LLM_BASE_URL", "https://deploy.example/v1/chat/completions")
    judge = wiring.open_llm_judge(store, "t")
    assert judge is not None and judge._base_url == "https://deploy.example/v1/chat/completions"


def test_judge_is_none_without_a_credential(tmp_path: Path, monkeypatch) -> None:
    store = _store(tmp_path)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    assert wiring.open_llm_judge(store, "t") is None  # no key → offline, deterministic filter only
