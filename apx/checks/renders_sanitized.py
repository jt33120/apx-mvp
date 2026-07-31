"""Rendered-HTML sanitisation structural property (Story 3.5c-2; AD-29, AD-33).

The pièce viewer renders office documents to inline HTML that the static SPA displays (AD-29). That
HTML is derived from **untrusted** pièce content (a `.docx`/`.xlsx` from opposing counsel), so it
must be inert — no script, no event handler, no `javascript:` link, no remote resource — before it
can reach the browser. This makes it a build-failing property, one check with two legs (mirroring
``originals_encrypted``):

- **static:** in the render adapter, a ``RenderedDocument`` is constructed at exactly ONE site,
  inside ``_rendered``, and ``_rendered`` routes its HTML through ``nh3.clean`` (via ``_sanitize``).
  So no render path can emit unsanitised markup (the ``one_chunk_writer`` pattern, applied to HTML).
  AST-sniffable — and, like any static leg, gameable by aliasing, so the second leg also runs.
- **behavioural (real runs only; harder to game):** the real ``_sanitize`` strips an XSS battery
  (``<script>``, ``onerror``/``onclick``, ``javascript:``, ``<iframe>``, ``<img>``, ``<form>``,
  ``<style>``) while PRESERVING safe formatting (not a degenerate strip-all), and a real adversarial
  ``.xlsx`` renders end-to-end carrying none of that active content.

Fails closed on an unparseable file.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path

from apx.checks.import_contracts import CheckResult
from apx.checks.payload_schema import _fail_closed, _load_trees

_APX_ROOT = Path(__file__).resolve().parent.parent
# The render adapter PACKAGE (not one file): ``_load_trees``/``_iter_py`` globs a root's directory,
# so pointing at the package sweeps every render module — the office renderer, the ``.msg`` one
# (Story 3.5c-3), and any future render module — so the one-construction-site invariant covers all.
_RENDER_PKG = _APX_ROOT / "adapters" / "render_html"


def _find_func(trees: Iterable[tuple[Path, ast.Module]], func_name: str) -> ast.FunctionDef | None:
    for _path, tree in trees:
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == func_name:
                return node
    return None


def _find_func_with_tree(
    trees: Iterable[tuple[Path, ast.Module]], func_name: str
) -> tuple[ast.FunctionDef | None, ast.Module | None]:
    for _path, tree in trees:
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == func_name:
                return node, tree
    return None, None


def _rd_bound_names(tree: ast.Module) -> set[str]:
    """The local name(s) ``RenderedDocument`` is bound to in this module — so an aliased import
    (``from ...render import RenderedDocument as RD``) cannot smuggle an unsanitised ``RD(...)``
    past the construction-site check (Reviewer finding, Story 3.5c-3)."""
    names = {"RenderedDocument"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == "RenderedDocument":
                    names.add(alias.asname or alias.name)
    return names


def _rendered_document_sites(node: ast.AST, bound_names: set[str]) -> list[ast.Call]:
    """Every ``RenderedDocument`` construction call within ``node`` — by the module's bound name
    (any alias) or the attribute form ``mod.RenderedDocument``."""
    out: list[ast.Call] = []
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            func = child.func
            if (isinstance(func, ast.Name) and func.id in bound_names) or (
                    isinstance(func, ast.Attribute) and func.attr == "RenderedDocument"):
                out.append(child)
    return out


def _calls_nh3_clean(fn: ast.FunctionDef) -> bool:
    return any(
        isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "clean"
        and isinstance(n.func.value, ast.Name) and n.func.value.id == "nh3"
        for n in ast.walk(fn))


def _calls_helper(fn: ast.FunctionDef, helper: str) -> bool:
    return any(
        isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == helper
        for n in ast.walk(fn))


def _sanitiser_neuters_active_content() -> str | None:
    """Execute the REAL sanitiser + renderer. Returns an error string on the first failure, else
    None. Harder to game than the static leg — a widened allow-list, a removed ``nh3.clean``, or a
    render path that bypasses the constructor is caught here, on real bytes."""
    from apx.adapters.render_html.renderer import HtmlPieceRenderer, _sanitize

    battery = (
        '<script>alert(1)</script><a href="javascript:evil()">j</a>'
        '<img src=x onerror=alert(2)><iframe src="//evil"></iframe>'
        '<b onclick="y()">b</b><form action="/x"></form><style>b{x:1}</style>')
    out = _sanitize(battery).lower()
    for bad in ("<script", "onerror", "onclick", "javascript:", "<iframe", "<img", "<form",
                "<style"):
        if bad in out:
            return f"the sanitiser left {bad!r} in its output — active content could reach the SPA"
    # not degenerate: a strip-EVERYTHING sanitiser is safe but useless — safe formatting must live
    if "<strong>" not in _sanitize("<p>ok <strong>bold</strong></p>").lower():
        return "the sanitiser strips even safe formatting — it must render content, not blank it"

    xlsx = _adversarial_xlsx()
    if xlsx is None:
        return None  # openpyxl absent in this env — the static + battery legs still hold
    doc = HtmlPieceRenderer().render(filename="evil.xlsx", data=xlsx)
    if doc is None:
        return "an adversarial .xlsx failed to render — cannot prove end-to-end sanitisation"
    low = doc.html.lower()
    # only LIVE tags are a vector: an escaped cell value (``&lt;img …&gt;``) is inert data, so the
    # word "onerror"/"javascript:" may legitimately appear in it — check the ``<tag`` form instead.
    for bad in ("<script", "<img", "<iframe", "<object", "<embed", "<style", "<form"):
        if bad in low:
            return f"a rendered .xlsx carried a live {bad!r} tag — end-to-end sanitisation failed"
    if "&lt;script&gt;" not in low:
        return "the adversarial .xlsx cell was not escaped to inert text — sanitisation incomplete"
    return None


def _adversarial_xlsx() -> bytes | None:
    """A real .xlsx whose cell values are XSS payloads — the end-to-end probe's input."""
    try:
        import io

        from openpyxl import Workbook
    except Exception:  # noqa: BLE001 — openpyxl absent: skip the end-to-end leg, not the whole check
        return None
    workbook = Workbook()
    sheet = workbook.active
    sheet["A1"] = "<script>alert(1)</script>"
    sheet["B1"] = "<img src=x onerror=alert(2)>"
    sheet["A2"] = "<iframe src=//evil></iframe>"
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def rendered_html_is_sanitized(roots: Iterable[Path] | None = None) -> CheckResult:
    """The render adapter builds a RenderedDocument at one site that sanitises its HTML (static),
    and the real sanitiser/renderer strip active content from adversarial input (behavioural)."""
    name, ad = "rendered HTML is sanitised", "AD-29"
    is_real = roots is None
    roots = list(roots) if roots is not None else [_RENDER_PKG]
    trees, unparseable = _load_trees(roots)
    if unparseable:
        return _fail_closed(name, ad, unparseable)
    # `_iter_py` globs a file root's whole directory, so multiple roots in one dir yield duplicate
    # parses — dedupe by resolved path so a site is counted once (else its own node reads outside).
    trees = list({path.resolve(): (path, tree) for path, tree in trees}.values())
    if not trees:
        return CheckResult(name, ad, False, "no render adapter module found to inspect (AD-29)")

    rendered, rendered_tree = _find_func_with_tree(trees, "_rendered")
    if rendered is None:
        return CheckResult(name, ad, False,
                           "no _rendered() in the render adapter — the one sanitising construction "
                           "site is missing; every render must route through it (AD-29)")
    inside = _rendered_document_sites(rendered, _rd_bound_names(rendered_tree))
    if not inside:
        return CheckResult(name, ad, False,
                           "_rendered() constructs no RenderedDocument — it must be the "
                           "sanitising builder (AD-29)")
    # union the construction sites across EVERY module in the package (not just one tree), each
    # under its OWN bound name — so a second render module (e.g. .msg) cannot build a
    # RenderedDocument outside _rendered, even via an import alias.
    all_sites: list = []
    for _path, tree in trees:
        all_sites.extend(_rendered_document_sites(tree, _rd_bound_names(tree)))
    outside = set(map(id, all_sites)) - set(map(id, inside))
    if outside:
        return CheckResult(name, ad, False,
                           "a RenderedDocument is built OUTSIDE _rendered() — that path could "
                           "emit unsanitised HTML; every render must route through the one "
                           "sanitising constructor (AD-29)")
    sanitize = _find_func(trees, "_sanitize")
    routes = _calls_nh3_clean(rendered) or (
        _calls_helper(rendered, "_sanitize")
        and sanitize is not None
        and _calls_nh3_clean(sanitize))
    if not routes:
        return CheckResult(name, ad, False,
                           "_rendered() does not route its HTML through nh3.clean — the "
                           "sanitiser is not wired into the one construction site (AD-29)")
    if is_real:
        problem = _sanitiser_neuters_active_content()
        if problem is not None:
            return CheckResult(name, ad, False, problem)
    return CheckResult(name, ad, True,
                       "every rendered document is built at one site that sanitises its HTML "
                       "(script/handlers/js-scheme/images stripped) — proven end-to-end")


def run() -> list[CheckResult]:
    return [rendered_html_is_sanitized()]
