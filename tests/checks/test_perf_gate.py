"""The perf-ceiling gate (Story 2.13, AC4 / NFR-2): no latency/throughput/wall-clock ceiling may be
asserted in the runtime while the timed-run measurement is unrecorded — so no number is quoted
before it is measured. Vacuous until such a ceiling is declared; a ceiling DERIVED from the
measurement record is permitted. Mirrors the Story 2.12 gold-set gate; structural detection is
best-effort, the honest pending record is the substrate."""

from __future__ import annotations

from pathlib import Path

from apx.checks.perf_gate import no_perf_ceiling_before_measurement


def _mod(tmp_path: Path, name: str, src: str) -> Path:
    d = tmp_path / name
    d.mkdir()
    (d / f"{name}.py").write_text(src, encoding="utf-8")
    return d


def test_it_fires_on_a_bare_perf_ceiling_while_the_measurement_is_pending(tmp_path: Path) -> None:
    root = _mod(tmp_path, "svc", "MAX_QUERY_LATENCY_MS = 500\n")
    r = no_perf_ceiling_before_measurement([root], measured=False)
    assert not r.ok and "MAX_QUERY_LATENCY_MS" in r.detail


def test_a_ceiling_derived_from_the_measurement_record_is_permitted(tmp_path: Path) -> None:
    src = "from apx.timedrun.record import load_records\nMAX_QUERY_LATENCY_MS = 500  # derived\n"
    root = _mod(tmp_path, "derived", src)
    r = no_perf_ceiling_before_measurement([root], measured=False)
    assert r.ok


def test_it_fires_on_common_ceiling_spellings(tmp_path: Path) -> None:
    # an SLA, a deadline, and a response-time limit are all latency ceilings a developer would write
    for i, src in enumerate([
        "RETRIEVAL_SLA_MS = 200\n",
        "QUERY_DEADLINE_S = 5\n",
        "RESPONSE_TIME_LIMIT_MS = 300\n",
        "P99_MS = 900\n",
    ]):
        root = _mod(tmp_path, f"ceil{i}", src)
        r = no_perf_ceiling_before_measurement([root], measured=False)
        assert not r.ok, f"should fire on: {src.strip()}"


def test_it_is_vacuous_when_no_perf_ceiling_is_declared(tmp_path: Path) -> None:
    root = _mod(tmp_path, "plain", "GREETING = 'bonjour'\nRETRY_COUNT = 3\n")
    r = no_perf_ceiling_before_measurement([root], measured=False)
    assert r.ok and "vacuous" in r.detail


def test_it_does_not_flag_lookalikes(tmp_path: Path) -> None:
    # names that merely CONTAIN a token substring but are not perf ceilings must NOT fire:
    # a bare timeout (no perf dimension), a translation key ("sla" ⊂ "translation"), a retry count.
    for i, src in enumerate([
        "REQUEST_TIMEOUT_S = 30\n",
        "TRANSLATION_KEYS = ('a', 'b')\n",
        "MAX_RETRIES = 3\n",
        "MAX_CHUNK_CHARS = 1200\n",
        "MEASURED_LATENCY_MS = None\n",       # a recorded figure, not a ceiling (NFR-2 permits it)
        "OBSERVED_THROUGHPUT = 0.0\n",
    ]):
        root = _mod(tmp_path, f"ok{i}", src)
        r = no_perf_ceiling_before_measurement([root], measured=False)
        assert r.ok, f"should NOT fire on: {src.strip()}"


def test_it_fails_closed_on_an_unreadable_measurement_state(tmp_path: Path, monkeypatch) -> None:
    # a corrupt/missing measurements.json must fail the check closed, not crash it (fail-closed).
    import apx.checks.perf_gate as pg

    def _boom() -> bool:
        raise ValueError("measurements.json is corrupt")

    monkeypatch.setattr(pg, "any_measured", _boom)
    root = _mod(tmp_path, "svc", "MAX_QUERY_LATENCY_MS = 500\n")
    r = no_perf_ceiling_before_measurement([root])   # measured=None → reads the (broken) state
    assert not r.ok


def test_once_a_measurement_exists_a_ceiling_is_permitted(tmp_path: Path) -> None:
    root = _mod(tmp_path, "svc", "MAX_QUERY_LATENCY_MS = 500\n")
    r = no_perf_ceiling_before_measurement([root], measured=True)
    assert r.ok


def test_it_is_vacuous_on_the_real_runtime_tree_today() -> None:
    # measured reads measurements.json (False today); the runtime declares no ceiling → vacuous.
    r = no_perf_ceiling_before_measurement()
    assert r.ok and "vacuous" in r.detail


def test_it_fails_closed_on_an_unparseable_file(tmp_path: Path) -> None:
    root = _mod(tmp_path, "broken", "def (:\n")
    r = no_perf_ceiling_before_measurement([root], measured=False)
    assert not r.ok
