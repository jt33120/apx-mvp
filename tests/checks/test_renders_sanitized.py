"""The render-sanitisation gate (Story 3.5c-2, AD-29/AD-33): it passes on the real adapter (static +
behavioural), and FAILS on a doctored adapter that builds a RenderedDocument outside the sanitising
``_rendered``, that never sanitises, or that has no constructor at all — so the invariant "no render
path emits unsanitised HTML" cannot be quietly broken while the build stays green."""

from __future__ import annotations

from pathlib import Path

from apx.checks.renders_sanitized import rendered_html_is_sanitized


def test_the_real_adapter_passes() -> None:
    result = rendered_html_is_sanitized()   # real run: static (one site → nh3) + behavioural probes
    assert result.ok, result.detail


def _write(tmp_path: Path, source: str) -> Path:
    f = tmp_path / "renderer.py"
    f.write_text(source, encoding="utf-8")
    return f


def test_a_construction_outside_the_sanitiser_fails(tmp_path: Path) -> None:
    # a render() that builds a RenderedDocument directly, bypassing _rendered's sanitiser
    bad = _write(tmp_path, '''
from apx.core.ports.render import RenderedDocument
def _sanitize(h):
    import nh3
    return nh3.clean(h)
def _rendered(title, raw, truncated=False):
    return RenderedDocument("html", title, _sanitize(raw), truncated)
class HtmlPieceRenderer:
    def render(self, *, filename, data):
        return RenderedDocument("html", filename, data.decode(), False)  # BYPASS — unsanitised
''')
    result = rendered_html_is_sanitized(roots=[bad])
    assert not result.ok and "OUTSIDE" in result.detail


def test_a_constructor_that_does_not_sanitise_fails(tmp_path: Path) -> None:
    bad = _write(tmp_path, '''
from apx.core.ports.render import RenderedDocument
def _rendered(title, raw, truncated=False):
    return RenderedDocument("html", title, raw, truncated)  # no nh3 — unsanitised
''')
    result = rendered_html_is_sanitized(roots=[bad])
    assert not result.ok and "nh3.clean" in result.detail


def test_no_constructor_fails(tmp_path: Path) -> None:
    bad = _write(tmp_path, "X = 1\n")
    result = rendered_html_is_sanitized(roots=[bad])
    assert not result.ok and "_rendered" in result.detail


_GOOD_RENDERER = (
    "from apx.core.ports.render import RenderedDocument\n"
    "def _sanitize(h):\n"
    "    import nh3\n"
    "    return nh3.clean(h)\n"
    "def _rendered(title, raw, truncated=False):\n"
    "    return RenderedDocument('html', title, _sanitize(raw), truncated)\n")


def test_a_second_module_constructing_outside_rendered_fails(tmp_path: Path) -> None:
    # Story 3.5c-3: the gate UNIONS construction sites across the WHOLE render_html package, so a
    # correct renderer.py cannot shelter a SECOND module that bypasses _rendered. The bad module is
    # named to sort AFTER renderer.py, so a first-tree-only check would MISS it — this test locks
    # the union-across-trees fix, not merely the single-tree behaviour it replaced.
    (tmp_path / "renderer.py").write_text(_GOOD_RENDERER, encoding="utf-8")
    bad = tmp_path / "scanned.py"   # sorts after 'renderer.py'
    bad.write_text(
        "from apx.core.ports.render import RenderedDocument\n"
        "class ScanRenderer:\n"
        "    def render(self, *, filename, data):\n"
        "        return RenderedDocument('html', filename, data.decode(), False)  # BYPASS\n",
        encoding="utf-8")
    result = rendered_html_is_sanitized(roots=[tmp_path])
    assert not result.ok and "OUTSIDE" in result.detail


def test_an_aliased_construction_outside_rendered_is_caught(tmp_path: Path) -> None:
    # a module that ALIASES the import (`RenderedDocument as RD`) and builds `RD(...)` outside
    # _rendered must still be caught — the static leg resolves each module's local binding, so the
    # alias cannot smuggle unsanitised HTML past the gate (Rev finding, Story 3.5c-3).
    (tmp_path / "renderer.py").write_text(_GOOD_RENDERER, encoding="utf-8")
    bad = tmp_path / "zzz_aliased.py"
    bad.write_text(
        "from apx.core.ports.render import RenderedDocument as RD\n"
        "class Aliased:\n"
        "    def render(self, *, filename, data):\n"
        "        return RD('html', filename, data.decode(), False)  # aliased BYPASS\n",
        encoding="utf-8")
    result = rendered_html_is_sanitized(roots=[tmp_path])
    assert not result.ok and "OUTSIDE" in result.detail
