"""Composition-root wiring shared by every process that performs an act (Story 7.3).

The *judgment cascade* used to be composed inside ``apx/api/app.py``, which was fine while the API
was the only process that judged. It stopped being fine the moment a *ranking version* had to
record the model that produced it: the identity is hashed into an immutable fingerprint and printed
on the header a lawyer reads, so *which judge was actually built* is now a recorded fact, and a
second composition site would be a second answer to it.

One door, therefore — the same reason ``store_postgres.opening`` exists for the store.
"""

from __future__ import annotations

import os

from apx.adapters.judge.criteria import CriteriaJudge
from apx.adapters.llm_openai_compat.judge import CascadeJudge, LLMJudge
from apx.adapters.store_postgres.store import SqlStore
from apx.core.domain.config import default_of
from apx.core.ports.judge import Judge


def chat_url(base: str) -> str:
    """Normalise a base endpoint to the OpenAI-compatible chat-completions URL the judge posts."""
    base = base.rstrip("/")
    return base if base.endswith("/chat/completions") else base + "/chat/completions"


def open_llm_judge(store: SqlStore, tenant: str) -> Judge | None:
    """The LLM tier (provider-agnostic, AD-27). None when no credential is configured — then the
    cascade is the deterministic filter alone and the system stays fully offline. The API **key**
    is a SECRET, read from the environment only (LLM_API_KEY/MISTRAL_API_KEY), never stored as
    config-as-data. The **endpoint** and **model** ARE configuration-as-data (AD-24): a tenant's
    non-default `model_endpoint`/`model_name` is honoured live; otherwise the deployment default
    (LLM_BASE_URL/LLM_MODEL env) applies, then the Mistral EU default. The `model_provider` key is
    config-as-data too, and the code still never branches on it (AD-27) — it is now handed to the
    judge so the judge can report it, rather than read a second time beside the judge and possibly
    disagree with it."""
    key = os.environ.get("LLM_API_KEY") or os.environ.get("MISTRAL_API_KEY")
    if not key:
        return None
    endpoint = store.get_config(tenant, "model_endpoint")
    base_url = (
        chat_url(str(endpoint)) if endpoint != default_of("model_endpoint")
        else os.environ.get("LLM_BASE_URL", "https://api.mistral.ai/v1/chat/completions"))
    model = store.get_config(tenant, "model_name")
    if model == default_of("model_name"):
        model = os.environ.get("LLM_MODEL", "mistral-small-latest")
    return LLMJudge(
        base_url=base_url, api_key=key, model=str(model),
        provider=str(store.get_config(tenant, "model_provider")))


def open_judge(store: SqlStore, tenant: str) -> Judge:
    """The judgment cascade, composed at the edge: the deterministic criteria filter first, and —
    when a model is configured — the LLM only on the uncertain band it leaves, at the tenant's
    configured endpoint/model. The core imports neither an LLM SDK nor these adapters (AD-27).

    Whatever comes back **answers for itself** through ``judge.identity``, and that is the point of
    having one door: when no credential is present this returns the bare ``CriteriaJudge``, and a
    caller that read the model from configuration instead would stamp *mistral-small-latest* onto
    an order decided by a keyword matcher."""
    criteria = CriteriaJudge()
    llm = open_llm_judge(store, tenant)
    return CascadeJudge(criteria, llm) if llm is not None else criteria


def judge_workers() -> int:
    """How many judgments run concurrently (JUDGE_WORKERS, default 8). The LLM tier is
    network-bound, so concurrency — not CPU — is what makes a large band tractable."""
    try:
        return max(1, int(os.environ.get("JUDGE_WORKERS", "8")))
    except ValueError:
        return 8
