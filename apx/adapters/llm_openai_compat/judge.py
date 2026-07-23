"""The LLM tier of the judgment cascade — a provider-agnostic, OpenAI-compatible judge.

This is the "LLM only on the uncertain band" tier. It speaks the OpenAI chat-completions
shape over plain HTTP (stdlib urllib — no SDK, nothing for the egress guard to forbid),
so it points at any compatible endpoint: Mistral (EU-hosted), OpenRouter, or a model
the firm runs on its own hardware (vLLM / Ollama) — the last keeps the whole system
offline. The core imports none of this (AD-27); the edge composes it.

Recall over precision is enforced at every seam: the prompt forbids a discard in doubt
and forbids inventing anything (no hallucination), an unrecognised label falls to
UNCERTAIN, and any transport or parse error degrades to UNCERTAIN — never to a silent
discard or a fabricated keep. So an outage sends pieces to human review, it does not
lose them.
"""

from __future__ import annotations

import json
import urllib.request
from collections.abc import Callable

from apx.core.domain.triage import Label, Verdict

_SYSTEM = (
    "Tu es un assistant de tri documentaire pour un cabinet d'avocats français. On te "
    "donne un CRITÈRE de tri et le TEXTE d'une pièce d'un dossier. Décide si la pièce "
    'répond au critère : "relevant" (pertinente), "discard" (clairement hors sujet), '
    '"uncertain" (tu n\'es pas certain). Règle absolue : le RAPPEL prime sur la '
    'précision — dans le moindre doute, réponds "uncertain", jamais "discard". '
    "N'invente aucune information ; juge uniquement d'après le texte fourni ; aucune "
    "hallucination. Réponds STRICTEMENT en JSON, sans texte autour : "
    '{"label": "relevant|uncertain|discard", "rationale": "une phrase courte en français"}.'
)

_LABELS = {"relevant": Label.RELEVANT, "uncertain": Label.UNCERTAIN, "discard": Label.DISCARD}


def _parse(content: str) -> Verdict:
    """Map the model's JSON answer to a Verdict; anything unexpected -> UNCERTAIN."""
    try:
        data = json.loads(content)
        label = str(data.get("label", "")).strip().lower()
        rationale = str(data.get("rationale", "")).strip() or "sans motif"
    except (ValueError, TypeError, AttributeError):
        return Verdict(Label.UNCERTAIN, "réponse illisible du juge — à revoir")
    return Verdict(_LABELS.get(label, Label.UNCERTAIN), rationale)


class LLMJudge:
    """Implements the Judge port against an OpenAI-compatible chat endpoint."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float = 30.0,
        max_chars: int = 16000,
        transport: Callable[[list[dict]], str] | None = None,
    ) -> None:
        self._base_url = base_url
        self._api_key = api_key
        self._model = model
        self._timeout = timeout
        self._max_chars = max_chars
        self._transport = transport or self._http
        self.name = f"llm:{model}"

    def judge(self, *, question: str, text: str) -> Verdict:
        body = text[: self._max_chars]
        if len(text) > self._max_chars:
            body += "\n[…texte tronqué…]"
        messages = [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": f"CRITÈRE : {question}\n\nTEXTE DE LA PIÈCE :\n{body}"},
        ]
        try:
            content = self._transport(messages)
        except Exception:  # noqa: BLE001 — any transport failure degrades safely to UNCERTAIN
            return Verdict(Label.UNCERTAIN, "erreur du juge (indisponible) — à revoir")
        return _parse(content)

    def _http(self, messages: list[dict]) -> str:
        payload = json.dumps({
            "model": self._model,
            "messages": messages,
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }).encode()
        request = urllib.request.Request(  # noqa: S310 — configured HTTPS endpoint
            self._base_url,
            data=payload,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self._timeout) as response:  # noqa: S310
            data = json.loads(response.read())
        return data["choices"][0]["message"]["content"]


class CascadeJudge:
    """The judgment cascade as a single Judge: the deterministic ``primary`` promotes
    the obvious matches for free (RELEVANT), and only what it leaves UNCERTAIN — the
    uncertain band — is spent on the ``fallback`` (the LLM). Per-piece judgment on
    100,000 documents is the system's biggest cost, so this is where it is saved."""

    def __init__(self, primary: object, fallback: object) -> None:
        self._primary = primary
        self._fallback = fallback
        self.name = f"{primary.name}+{fallback.name}"  # type: ignore[attr-defined]

    def judge(self, *, question: str, text: str) -> Verdict:
        verdict = self._primary.judge(question=question, text=text)  # type: ignore[attr-defined]
        if verdict.label is Label.RELEVANT:
            return verdict  # deterministic promotion — the LLM is not spent
        return self._fallback.judge(question=question, text=text)  # type: ignore[attr-defined]
