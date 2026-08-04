import type { PDFDocumentProxy, PDFPageProxy, PageViewport } from "pdfjs-dist";
import workerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";

/** The PDF.js seam (Story 3.5d-2) — born-digital PDFs rendered inline, in the browser / tenant
 *  boundary. PDF.js is LAZY-loaded (dynamic import ⇒ Vite code-splits the ~450 kB library out of the
 *  main bundle; it loads only when a born-digital PDF is opened) and it makes ZERO network calls: the
 *  worker is bundled same-origin (never a CDN), `getDocument` is fed in-memory bytes (no range/stream
 *  fetch), and no external cMap/font URL is set — so no pièce byte leaves the cabinet and the AD-29
 *  offline guarantee holds. A document's embedded JavaScript is never executed (no scripting manager
 *  is wired); parsing runs in the isolated worker; `isEvalSupported:false` + the app CSP (no
 *  'unsafe-eval') keep font parsing off `eval`. */

type Pdfjs = typeof import("pdfjs-dist");
let _mod: Promise<Pdfjs> | null = null;

function loadPdfjs(): Promise<Pdfjs> {
  if (!_mod) {
    _mod = import("pdfjs-dist").then((m) => {
      m.GlobalWorkerOptions.workerSrc = workerUrl;   // bundled, same-origin — never a CDN
      return m;
    });
  }
  return _mod;
}

export type PdfDoc = PDFDocumentProxy;
export type PdfPage = PDFPageProxy;
export type PdfViewport = PageViewport;
export type PassageRect = { left: number; top: number; width: number; height: number };

/** Open a PDF from in-memory bytes (the `/original` fetch that produced them IS the audited open).
 *  Returns the document plus a `destroy` that aborts the worker + frees the document — the caller
 *  MUST call it on unmount (destroy lives on the loading task, not the document proxy). */
export async function openPdf(data: ArrayBuffer): Promise<{ doc: PdfDoc; destroy: () => void }> {
  const pdfjs = await loadPdfjs();
  // isEvalSupported is a valid runtime option the published types omit — pass it via a cast.
  const params = { data, isEvalSupported: false } as Parameters<typeof pdfjs.getDocument>[0];
  const task = pdfjs.getDocument(params);
  const doc = await task.promise;
  return { doc, destroy: () => { void task.destroy(); } };
}

// Lower-case + strip accents, so the passage match is accent-insensitive (consistent with the scan
// path's normalise): a search term "resiliation" still lands on "résiliation" in the PDF text.
function norm(s: string): string {
  return s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
}

// Bound the passage scan so opening a large born-digital PDF stays fast — most legal passages sit in
// the first pages; a term found later (or absent) opens page 1 rather than parsing the whole document.
const _PASSAGE_SCAN_CAP = 80;

/** The 1-indexed page carrying the passage (first occurrence of the whole term, else its first
 *  token), or 1 when absent/none/beyond the scan cap. A born-digital PDF over the render bound never
 *  reaches here (it stays the offer-the-original fallback). */
export async function findPassagePage(doc: PdfDoc, passage: string | undefined): Promise<number> {
  const needle = norm((passage ?? "").trim());
  if (!needle) return 1;
  const first = needle.split(/\s+/)[0];
  const limit = Math.min(doc.numPages, _PASSAGE_SCAN_CAP);
  for (let p = 1; p <= limit; p++) {
    const page = await doc.getPage(p);
    const tc = await page.getTextContent();
    const text = norm(tc.items.map((it) => ("str" in it ? it.str : "")).join(" "));
    if (text.includes(needle) || text.includes(first)) return p;
  }
  return 1;
}

/** The rect (in canvas/viewport pixels) of the first text run containing the passage on `page`, or
 *  null. Standard PDF.js recipe: combine the viewport transform with the item's text matrix for the
 *  origin + font height; width ≈ item.width × scale. The caller positions the wash as a FRACTION of
 *  the canvas, so it is correct at any display scale. */
export async function passageRectOnPage(
  page: PdfPage, viewport: PdfViewport, scale: number, passage: string | undefined,
): Promise<PassageRect | null> {
  const needle = norm((passage ?? "").trim());
  if (!needle) return null;
  const first = needle.split(/\s+/)[0];
  const pdfjs = await loadPdfjs();
  const tc = await page.getTextContent();
  for (const item of tc.items) {
    if (!("str" in item) || !item.str) continue;
    const s = norm(item.str);
    if (!s.includes(needle) && !s.includes(first)) continue;
    const tx = pdfjs.Util.transform(viewport.transform as number[], item.transform as number[]);
    const fontHeight = Math.hypot(tx[2], tx[3]);
    return { left: tx[4], top: tx[5] - fontHeight, width: item.width * scale, height: fontHeight };
  }
  return null;
}
