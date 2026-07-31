"""The server-side office HTML renderer (Story 3.5c-2): ``.docx`` (mammoth) and ``.xlsx`` (openpyxl)
render to **sanitised** inline HTML — an adversarial document can never inject active content — and
an unhandled or malformed input offers the original (``None``), never a raise, never a 500."""

from __future__ import annotations

import io
import zipfile

from openpyxl import Workbook

from apx.adapters.render_html.renderer import HtmlPieceRenderer, _sanitize

_CT = (
    '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/'
    'content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-'
    'package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-'
    'officedocument.wordprocessingml.document.main+xml"/></Types>')
_RELS = (
    '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/'
    'relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/'
    '2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
_WNS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def _docx(body_xml: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", _CT)
        z.writestr("_rels/.rels", _RELS)
        z.writestr(
            "word/document.xml",
            f'<?xml version="1.0"?><w:document {_WNS}><w:body>{body_xml}</w:body></w:document>')
    return buf.getvalue()


def _para(text: str) -> str:
    return f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>"


def _xlsx(rows: list[list[object]]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    for row in rows:
        sheet.append(row)
    buf = io.BytesIO()
    workbook.save(buf)
    return buf.getvalue()


# ── the sanitiser: the security spine ──
def test_sanitize_strips_active_content_but_keeps_safe_formatting() -> None:
    out = _sanitize(
        '<p>ok <strong>bold</strong> <a href="http://x.fr">l</a>'
        '<script>alert(1)</script><img src=x onerror=y()>'
        '<a href="javascript:z()">j</a><iframe></iframe><style>a{}</style><form></form></p>'
    ).lower()
    assert "<strong>" in out and "http://x.fr" in out       # safe formatting + a safe link survive
    for bad in ("<script", "onerror", "javascript:", "<img", "<iframe", "<style", "<form"):
        assert bad not in out


# ── .docx (mammoth) ──
def test_render_docx_to_sanitized_html() -> None:
    doc = HtmlPieceRenderer().render(filename="c.docx", data=_docx(_para("Article 4 : dépôt")))
    assert doc is not None and doc.format == "html" and doc.truncated is False
    assert "Article 4" in doc.html and "dépôt" in doc.html   # rendered text, accents preserved
    assert "<script" not in doc.html.lower()


def test_docx_markup_text_is_escaped_not_executed() -> None:
    # a paragraph whose TEXT is markup: mammoth escapes it, so it can never execute
    doc = HtmlPieceRenderer().render(
        filename="x.docx", data=_docx(_para("&lt;script&gt;alert(1)&lt;/script&gt;")))
    assert doc is not None and "<script" not in doc.html.lower()   # inert (escaped entities)


def test_an_empty_docx_offers_the_original() -> None:
    assert HtmlPieceRenderer().render(filename="empty.docx", data=_docx("")) is None


# ── .xlsx (openpyxl) ──
def test_render_xlsx_to_a_table() -> None:
    doc = HtmlPieceRenderer().render(
        filename="annexe.xlsx", data=_xlsx([["Poste", "Montant"], ["Dépôt", 0]]))
    assert doc is not None and doc.truncated is False
    assert "<table>" in doc.html and "<td>Poste</td>" in doc.html and "<td>Dépôt</td>" in doc.html
    assert "<td>0</td>" in doc.html                          # a numeric cell renders as its value


def test_xlsx_adversarial_cells_are_neutralised() -> None:
    doc = HtmlPieceRenderer().render(
        filename="evil.xlsx",
        data=_xlsx([["<script>alert(1)</script>", "<img src=x onerror=y()>"], ["javascript:z", 1]]))
    assert doc is not None
    low = doc.html.lower()
    # a dangerous cell VALUE becomes inert escaped text, never a live tag (the word may survive as
    # data — ``&lt;img …&gt;`` — but no live ``<img>``/``<script>`` element is produced).
    for live in ("<script", "<img", "<iframe"):
        assert live not in low
    assert "&lt;script&gt;" in low                            # proof it was escaped to inert text


def test_xlsx_over_the_row_bound_is_truncated_not_dropped_silently() -> None:
    doc = HtmlPieceRenderer(max_rows=2).render(
        filename="big.xlsx", data=_xlsx([["a"], ["b"], ["c"], ["d"]]))
    assert doc is not None and doc.truncated is True
    assert doc.html.count("<tr>") == 2                       # capped at the bound, honestly flagged


def test_xlsx_over_the_col_bound_is_truncated() -> None:
    doc = HtmlPieceRenderer(max_cols=2).render(
        filename="wide.xlsx", data=_xlsx([["a", "b", "c", "d"]]))
    assert doc is not None and doc.truncated is True
    assert doc.html.count("<td>") == 2


# ── the fallbacks (offer the original — FR-44, never a raise) ──
def test_an_unhandled_format_offers_the_original() -> None:
    r = HtmlPieceRenderer()
    assert r.render(filename="scan.pdf", data=b"%PDF") is None
    assert r.render(filename="photo.png", data=b"\x89PNG") is None
    assert r.render(filename="old.doc", data=b"\xd0\xcf\x11\xe0") is None   # legacy binary


def test_a_malformed_office_file_offers_the_original_never_raises() -> None:
    r = HtmlPieceRenderer()
    assert r.render(filename="broken.docx", data=b"not a zip at all") is None
    assert r.render(filename="broken.xlsx", data=b"not a zip at all") is None


def test_both_renderers_fail_closed_to_none_when_the_sanitiser_fails(monkeypatch) -> None:
    # If nh3 is unavailable/erroring, a render must fail CLOSED to None (offer the original) — not
    # a raise/500, and never unsanitised HTML. `.docx` and `.xlsx` must behave the same (AC1): the
    # review found `.xlsx` alone used to raise because its _rendered() call sat outside the guard.
    import nh3

    def _boom(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        raise RuntimeError("nh3 down")

    monkeypatch.setattr(nh3, "clean", _boom)
    r = HtmlPieceRenderer()
    assert r.render(filename="x.docx", data=_docx(_para("Article 4"))) is None
    assert r.render(filename="x.xlsx", data=_xlsx([["Poste", "Montant"]])) is None
