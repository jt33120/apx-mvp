"""Fakes for the relevance cascade (Story 4.2) — a semantic scorer and judges. Kept under ``tests/``
(never in ``apx/``), substituted at the port boundary so the cascade is exercised deterministically
with no network and no database, and the structural checks over ``apx/`` are unaffected."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

from apx.core.domain.triage import Label, Verdict


class FakeScorer:
    """Returns canned per-pièce scores; a pièce absent from the map is omitted (no-signal)."""

    def __init__(self, scores: Mapping[str, float]) -> None:
        self._scores = dict(scores)

    def score(
        self, *, tenant: str, matter: str, scopes: set[str], query_text: str,
        piece_ids: Sequence[str],
    ) -> Mapping[str, float]:
        return {pid: self._scores[pid] for pid in piece_ids if pid in self._scores}


class FixedJudge:
    """Returns a fixed verdict for every call and records the (question, text) pairs it saw."""

    name = "fake-judge"

    def __init__(self, label: Label = Label.RELEVANT) -> None:
        self._label = label
        self.calls: list[tuple[str, str]] = []

    def judge(self, *, question: str, text: str) -> Verdict:
        self.calls.append((question, text))
        return Verdict(self._label, "fixe")


class FailingJudge:
    """Raises for texts matching ``fails_on`` (default: all), else returns a verdict — the AD-19
    unscored path (a provider failure must NOT degrade to an in-band label)."""

    name = "failing-judge"

    def __init__(
        self, *, fails_on: Callable[[str], bool] = lambda _t: True, error: Exception | None = None,
    ) -> None:
        self._fails_on = fails_on
        self._error = error or RuntimeError("provider unavailable")
        self.calls: list[str] = []

    def judge(self, *, question: str, text: str) -> Verdict:
        self.calls.append(text)
        if self._fails_on(text):
            raise self._error
        return Verdict(Label.UNCERTAIN, "ok")
