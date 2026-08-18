"""The LLM judge (stubbed transport — no network) and the cascade composition.

The load-bearing properties: any failure degrades to UNCERTAIN (never a silent
discard), and the LLM is spent only on the band the deterministic filter left.
"""

from __future__ import annotations

from apx.adapters.judge.criteria import CriteriaJudge
from apx.adapters.llm_openai_compat.judge import CascadeJudge, LLMJudge
from apx.core.domain.ranking import JudgeIdentity
from apx.core.domain.triage import Label, Verdict


def _llm(content_or_exc):
    def transport(messages):
        if isinstance(content_or_exc, Exception):
            raise content_or_exc
        return content_or_exc
    return LLMJudge(base_url="x", api_key="k", model="test-model", transport=transport)


def test_parses_each_label() -> None:
    for token, label in [("relevant", Label.RELEVANT), ("uncertain", Label.UNCERTAIN),
                         ("discard", Label.DISCARD)]:
        v = _llm(f'{{"label": "{token}", "rationale": "motif"}}').judge(question="q", text="t")
        assert v.label is label and v.rationale == "motif"


def test_unknown_label_falls_to_uncertain() -> None:
    assert _llm('{"label": "peut-être", "rationale": "?"}').judge(
        question="q", text="t").label is Label.UNCERTAIN


def test_malformed_json_is_uncertain() -> None:
    assert _llm("not json at all").judge(question="q", text="t").label is Label.UNCERTAIN


def test_transport_error_degrades_to_uncertain_never_discard() -> None:
    v = _llm(RuntimeError("network down")).judge(question="q", text="t")
    assert v.label is Label.UNCERTAIN and "erreur" in v.rationale.lower()


def test_name_reflects_the_model() -> None:
    assert _llm('{"label":"relevant"}').name == "llm:test-model"


def test_long_text_is_truncated_before_sending() -> None:
    seen = {}

    def transport(messages):
        seen["user"] = messages[1]["content"]
        return '{"label":"relevant","rationale":"ok"}'

    LLMJudge(base_url="x", api_key="k", model="m", max_chars=100, transport=transport).judge(
        question="q", text="A" * 500)
    assert "tronqué" in seen["user"] and len(seen["user"]) < 500


class _Spy:
    name = "spy"
    identity = JudgeIdentity(
        provider="spy", endpoint="local:spy", model="spy", temperature=0.0, sampling={})

    def __init__(self, verdict: Verdict) -> None:
        self.verdict = verdict
        self.calls = 0

    def judge(self, *, question: str, text: str) -> Verdict:
        self.calls += 1
        return self.verdict


def test_cascade_promotes_deterministically_without_spending_the_llm() -> None:
    llm = _Spy(Verdict(Label.DISCARD, "llm"))
    v = CascadeJudge(CriteriaJudge(), llm).judge(question="bail", text="Contrat de bail signé.")
    assert v.label is Label.RELEVANT and llm.calls == 0  # criteria matched — LLM untouched


def test_cascade_sends_the_uncertain_band_to_the_llm() -> None:
    llm = _Spy(Verdict(Label.DISCARD, "hors sujet"))
    v = CascadeJudge(CriteriaJudge(), llm).judge(question="bail", text="Facture EDF.")
    assert v.label is Label.DISCARD and llm.calls == 1  # no match — the LLM decides


def test_cascade_name_composes_both() -> None:
    assert CascadeJudge(CriteriaJudge(), _Spy(Verdict(Label.UNCERTAIN, ""))).name == "criteria+spy"
