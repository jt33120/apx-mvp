import { useEffect, useMemo, useRef, useState } from "react";
import { Navigate, useNavigate, useParams, useSearchParams } from "react-router";
import {
  ApiError, getLayout, getPiece, getRender, me, pieceOriginalUrl, piecePageUrl,
  type Identity, type OcrLayout, type OcrWord, type PieceMeta, type PieceRender,
} from "./api";

/** Story 3.5d-1 — the pièce viewer surface. A lawyer reads the ACTUAL document, at the passage the
 *  tool sent her to, inside the cabinet — no byte leaves for a third party (the render happens
 *  server-side in the tenant boundary; the client only reads /pieces/… endpoints). The scope
 *  pre-filter runs FIRST server-side (AD-13/14): an out-of-scope OR absent pièce is the SAME
 *  non-disclosing 404 (FR-14/FR-44). Opening content is an audited act (FR-45), surfaced in the bar.
 *
 *  This sub-part covers every format the existing endpoints fully back: scanned PDF (page image +
 *  OCR box overlay + passage, progressive), .docx/.xlsx/.msg (sanitised HTML in a SANDBOXED frame),
 *  inline images, and the honest fallback (born-digital PDF, over-bound, un-renderable → offer the
 *  original). Born-digital-PDF inline (PDF.js) + the image region box are 3.5d-2. */

// ── the focused route ─────────────────────────────────────────────────────────────────────
export function ViewerRoute() {
  const { pieceId } = useParams();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    me().then(setIdentity).catch(() => setIdentity(null)).finally(() => setReady(true));
  }, []);

  if (!ready) return <main className="apx-shell">…</main>;
  if (!identity) return <Navigate to="/" replace />;      // owned auth: nothing loads unauthenticated
  if (!pieceId) return <Navigate to="/" replace />;

  const passage = params.get("passage") ?? undefined;
  const pageParam = params.get("page");
  const page = pageParam != null && /^\d+$/.test(pageParam) ? Number(pageParam) : undefined;
  return (
    <Viewer key={pieceId} pieceId={pieceId} passage={passage} page={page}
      onClose={() => navigate(-1)} />
  );
}

// ── the viewer: metadata peek → format dispatch ───────────────────────────────────────────
function Viewer({ pieceId, passage, page, onClose }: {
  pieceId: string; passage?: string; page?: number; onClose: () => void;
}) {
  const [meta, setMeta] = useState<PieceMeta | null>(null);
  const [status, setStatus] = useState<"loading" | "denied" | "error" | "ok">("loading");

  useEffect(() => {
    let live = true;
    setStatus("loading");
    setMeta(null);
    getPiece(pieceId)
      .then((m) => { if (live) { setMeta(m); setStatus("ok"); } })
      .catch((e) => {
        if (!live) return;
        // 404 is the non-disclosing denial (out-of-scope OR absent — indistinguishable). Any other
        // failure is a genuine error, NOT a "does not exist" (never mis-claim absence).
        setStatus(e instanceof ApiError && e.status === 404 ? "denied" : "error");
      });
    return () => { live = false; };
  }, [pieceId]);

  if (status === "loading") return <Frame onClose={onClose}><LoadingCanvas label="Ouverture…" /></Frame>;
  if (status === "denied") return <DenialFrame onClose={onClose} />;
  if (status === "error" || !meta) {
    return (
      <Frame onClose={onClose}>
        <Centre glyph="⚠" tone="review" title="La pièce n'a pas pu être ouverte">
          <p>Une erreur est survenue à l'ouverture. Réessayez ; si elle persiste, l'original reste
            disponible.</p>
          <div className="pv-row"><a className="pv-btn" href={pieceOriginalUrl(pieceId)}>⤓ Ouvrir
            l'original</a></div>
        </Centre>
      </Frame>
    );
  }
  return <PieceView meta={meta} passage={passage} page={page} onClose={onClose} />;
}

type Route = "scan" | "html" | "image" | "fallback";

function classify(meta: PieceMeta): Route {
  if (meta.media_kind === "pdf" && meta.ocr) return "scan";       // a scanned PDF (has an OCR layer)
  if (["document", "spreadsheet", "email"].includes(meta.media_kind)) return "html";
  if (meta.media_kind === "image" && meta.renderable_inline) return "image";
  return "fallback";  // born-digital PDF (pdf ∧ ¬ocr), over-bound, or an un-renderable format
}

function PieceView({ meta, passage, page, onClose }: {
  meta: PieceMeta; passage?: string; page?: number; onClose: () => void;
}) {
  const route = classify(meta);
  // "ouvert · consigné HH:MM" — set once the CONTENT (the audited open) has loaded. The fallback
  // reads nothing yet (the audit fires when she clicks ⤓ original), so it shows no timestamp.
  const [openedAt, setOpenedAt] = useState<string | null>(null);
  const onOpened = () => setOpenedAt((prev) => prev ?? hhmm(new Date()));

  const [rail, setRail] = useState<React.ReactNode>(null);
  const showOriginal = route !== "fallback";  // the fallback's canvas already carries the original CTA

  const canvas =
    route === "scan"
      ? <ScanCanvas meta={meta} passage={passage} page={page} onOpened={onOpened} setRail={setRail} />
      : route === "html"
        ? <HtmlCanvas meta={meta} passage={passage} onOpened={onOpened} />
        : route === "image"
          ? <ImageCanvas meta={meta} onOpened={onOpened} />
          : <FallbackCanvas meta={meta} />;

  return (
    <Frame meta={meta} openedAt={openedAt} showOriginal={showOriginal} rail={rail} onClose={onClose}
      foot={route === "scan"
        ? "Image et OCR rendus sur place — aucun envoi à un service de reconnaissance tiers."
        : "Rendu dans le périmètre du cabinet — aucun contenu n'a quitté l'infrastructure."}>
      {canvas}
    </Frame>
  );
}

// ── the shell (bar · rail · canvas · foot) ────────────────────────────────────────────────
function Frame({ meta, emptyName = "Ouverture…", openedAt, showOriginal, rail, foot, onClose, children }: {
  meta?: PieceMeta; emptyName?: string; openedAt?: string | null; showOriginal?: boolean;
  rail?: React.ReactNode; foot?: string; onClose: () => void; children: React.ReactNode;
}) {
  return (
    <div className="pv">
      <div className="pv-bar">
        <button className="pv-back" onClick={onClose}>‹ retour</button>
        <div className="pv-id">
          {/* filename is UNTRUSTED text metadata — a text node, never innerHTML. With no pièce yet,
              show a neutral placeholder — never the denial phrase while merely loading. */}
          <span className="name">{meta ? meta.filename : emptyName}</span>
          {meta && <FormatBadge meta={meta} />}
          {meta && <span className="apx-chip apx-chip--scope">{meta.matter}</span>}
        </div>
        <div className="pv-right">
          {openedAt && (
            <span className="pv-audit"><span className="dot" />ouvert · consigné {openedAt}</span>
          )}
          {meta && showOriginal && (
            <a className="pv-orig" href={pieceOriginalUrl(meta.piece_id)}>⤓ original</a>
          )}
          <button className="pv-close" aria-label="Fermer" onClick={onClose}>×</button>
        </div>
      </div>
      <div className="pv-body" style={rail ? undefined : { gridTemplateColumns: "1fr" }}>
        {rail && <aside className="pv-rail">{rail}</aside>}
        <div className="pv-canvas">{children}</div>
      </div>
      <div className="pv-foot">
        <span className="lock">▪</span>{" "}
        {foot ?? "Pré-filtre de périmètre appliqué avant tout rendu (AD-13/AD-14)."}
      </div>
    </div>
  );
}

function formatLabel(meta: PieceMeta): string {
  if (meta.media_kind === "pdf" && meta.ocr) return "PDF scanné · OCR";
  return ({ pdf: "PDF", document: "Document", spreadsheet: "Tableur", email: "Courriel",
    image: "Image" } as Record<string, string>)[meta.media_kind] ?? meta.media_kind;  // unknown names itself
}

function FormatBadge({ meta }: { meta: PieceMeta }) {
  const ocr = meta.media_kind === "pdf" && meta.ocr;
  return <span className={`pv-fmt ${ocr ? "pv-ocr" : ""}`}>{formatLabel(meta)}</span>;
}

// ── the RBAC denial (screen 6): identical to an absent pièce, discloses nothing ───────────
function DenialFrame({ onClose }: { onClose: () => void }) {
  return (
    <Frame onClose={onClose} emptyName="Pièce introuvable">
      <Centre glyph="∅" tone="muted" title="Cette pièce est introuvable dans votre périmètre">
        <p>Aucune pièce ne correspond à cette référence pour votre session. Si vous pensez y avoir
          droit, demandez l'accès au périmètre concerné à un administrateur.</p>
        <p className="pv-note">Par principe, le produit ne révèle jamais l'existence d'une pièce hors
          de votre périmètre — cette réponse est la même dans tous les cas.</p>
      </Centre>
    </Frame>
  );
}

// ── the scanned-PDF canvas (screen 2 + 7): page image + OCR overlay + passage box, progressive ──
function ScanCanvas({ meta, passage, page, onOpened, setRail }: {
  meta: PieceMeta; passage?: string; page?: number; onOpened: () => void;
  setRail: (r: React.ReactNode) => void;
}) {
  const [layout, setLayout] = useState<OcrLayout | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "unavailable">("loading");
  const [current, setCurrent] = useState(0);

  useEffect(() => {
    let live = true;
    getLayout(meta.piece_id)
      .then((l) => {
        if (!live) return;
        if (l == null || l.pages.length === 0) { setState("unavailable"); return; }  // not a usable scan
        // Resolve the opening page BEFORE the first ScanPage render (batched with setState), so no
        // throwaway /page/0 is ever fetched — that fetch is a server-audited serve, and would write a
        // phantom open-piece entry for a page the lawyer never navigated to (FR-45 integrity).
        setCurrent(page != null && page < l.pages.length ? page : findPassage(l, passage).page);
        setLayout(l);
        setState("ready");
      })
      .catch(() => { if (live) setState("unavailable"); });   // 409 tampered → offer the original
    return () => { live = false; };
  }, [meta.piece_id]);

  // The passage box, for the page that carries it (findPassage is cheap; recomputed here for the box).
  const found = useMemo(
    () => (layout ? findPassage(layout, passage) : { page: 0, box: null }),
    [layout, passage],
  );

  // The rail is navigable the instant the layout is known — the page image streams in beside it.
  useEffect(() => {
    if (!layout) { setRail(null); return; }
    setRail(<ScanRail layout={layout} current={current} onGo={setCurrent} />);
  }, [layout, current, setRail]);
  useEffect(() => () => setRail(null), [setRail]);

  if (state === "loading") return <LoadingCanvas label="Ouverture du scan…" />;
  if (state === "unavailable" || !layout) return <FallbackCanvas meta={meta} />;

  const box = current === found.page ? found.box : null;    // the passage box, on its page only
  // a labelled region: a screen reader announces the pièce + format (+ the passage) before the image
  const regionLabel = `${meta.filename}, ${formatLabel(meta)}${box ? ", ouvert au passage" : ""}`;
  return (
    <ScanPage pieceId={meta.piece_id} pageIndex={current} layoutPage={layout.pages[current]}
      box={box} regionLabel={regionLabel} onOpened={onOpened} />
  );
}

function ScanRail({ layout, current, onGo }: {
  layout: OcrLayout; current: number; onGo: (p: number) => void;
}) {
  const confs = layout.pages.flatMap((p) => p.words.map((w) => w.c));
  const mean = confs.length ? Math.round(confs.reduce((a, b) => a + b, 0) / confs.length) : null;
  return (
    <>
      <p className="rk">Pages · {layout.pages.length}</p>
      <div className="thumbs">
        {layout.pages.map((_, i) => (
          <button key={i} className={`thumb ${i === current ? "on" : ""}`} onClick={() => onGo(i)}
            aria-current={i === current} aria-label={`Page ${i + 1}`}>
            {i === current && <span className="marker" aria-hidden>▸</span>}{i + 1}
          </button>
        ))}
      </div>
      {mean != null && (
        <>
          <p className="rk" style={{ marginTop: "1rem" }}>Qualité OCR</p>
          <p className="out" style={{ color: "var(--apx-review)" }}>
            Texte reconnu à {mean} %. Certains mots peuvent différer de l'image.
          </p>
        </>
      )}
    </>
  );
}

function ScanPage({ pieceId, pageIndex, layoutPage, box, regionLabel, onOpened }: {
  pieceId: string; pageIndex: number; layoutPage: OcrLayout["pages"][number];
  box: Box | null; regionLabel: string; onOpened: () => void;
}) {
  const [phase, setPhase] = useState<"loading" | "shown" | "failed">("loading");
  const hitRef = useRef<HTMLDivElement>(null);
  useEffect(() => { setPhase("loading"); }, [pieceId, pageIndex]);
  // Bring the passage into view and give it focus — the passage is the first focus stop (a11y).
  useEffect(() => {
    if (phase === "shown" && hitRef.current) {
      hitRef.current.scrollIntoView({ block: "center" });
      hitRef.current.focus();
    }
  }, [phase]);

  if (phase === "failed") {
    // an over-bound / pixel-bomb / tampered page (a 409 on the PNG): offer the original, hide nothing
    return (
      <Centre glyph="⚠" tone="review" title="Cette page ne peut pas être rendue">
        <p>La page ne peut pas être rendue dans le produit (trop volumineuse, ou l'original n'est pas
          disponible). Ouvrez l'original, tel qu'il a été déposé.</p>
        <div className="pv-row"><a className="pv-btn" href={pieceOriginalUrl(pieceId)}>⤓ Ouvrir
          l'original</a></div>
      </Centre>
    );
  }
  const W = layoutPage.width || 1, H = layoutPage.height || 1;
  return (
    <div className="scan-wrap" role="region" aria-label={regionLabel}>
      {/* aspectRatio reserves the page shape before the image arrives (no layout shift); the image
          always renders (it must load to fire onLoad), the skeleton overlays it until it is shown. */}
      <div className="scan" style={{ aspectRatio: `${W}/${H}` }}>
        {/* the page IMAGE, rendered in the tenant boundary; fetching it is the audited open */}
        <img className="scan-img" src={piecePageUrl(pieceId, pageIndex)} alt={`Page ${pageIndex + 1}`}
          onLoad={() => { setPhase("shown"); onOpened(); }} onError={() => setPhase("failed")} />
        {box && (
          // the passage — a box on the image, positioned as a FRACTION of the layout page (so it is
          // correct at any display scale AND if the raster's pixel size differs from the layout's).
          <div ref={hitRef} className="ocr hit" tabIndex={0} aria-label="Passage"
            style={{
              left: `${(box.l / W) * 100}%`, top: `${(box.o / H) * 100}%`,
              width: `${(box.w / W) * 100}%`, height: `${(box.h / H) * 100}%`,
            }} />
        )}
        {phase === "loading" && (
          <div className="scan-load" aria-live="polite">
            <span className="progtag">◐ Chargement de la page {pageIndex + 1}…</span>
          </div>
        )}
      </div>
    </div>
  );
}

// ── the office/email canvas (screens 3 + 4): SANITISED html in a SANDBOXED frame ──────────
function HtmlCanvas({ meta, passage, onOpened }: {
  meta: PieceMeta; passage?: string; onOpened: () => void;
}) {
  const [render, setRender] = useState<PieceRender | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "unavailable">("loading");

  useEffect(() => {
    let live = true;
    getRender(meta.piece_id)
      .then((r) => {
        if (!live) return;
        setRender(r);
        setState(r.renderable ? "ready" : "unavailable");
        if (r.renderable) onOpened();     // a served render is the audited open (server-side)
      })
      .catch(() => { if (live) setState("unavailable"); });
    return () => { live = false; };
  }, [meta.piece_id]);

  if (state === "loading") return <LoadingCanvas label="Rendu du document…" />;
  if (state === "unavailable" || !render || !render.renderable || render.html == null) {
    return <FallbackCanvas meta={meta} reason={render?.reason ?? undefined} />;
  }
  const srcDoc = wrapHtml(render.html, passage);
  return (
    <div className="sheet-wrap" role="region" aria-label={`${meta.filename}, ${formatLabel(meta)}`}>
      {/* sandbox="" — no scripts, no same-origin: a belt to the server's nh3 sanitisation, so even a
          bypass cannot script the app origin or reach the session cookie. */}
      <iframe className="pv-frame" title={`Rendu de ${meta.filename}`} sandbox="" srcDoc={srcDoc} />
      {render.truncated && (
        <p className="pv-note pv-note--trunc">Aperçu tronqué — la pièce dépasse la borne de rendu.
          Ouvrez l'original pour la version complète.</p>
      )}
    </div>
  );
}

// ── the image canvas: an inline image from a same-origin blob (screen 2 pattern, no OCR) ───
function ImageCanvas({ meta, onOpened }: { meta: PieceMeta; onOpened: () => void }) {
  const [url, setUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let live = true;
    let obj: string | null = null;
    // fetching /original IS the audited open; the blob stays in the browser (inside the tenant).
    fetch(pieceOriginalUrl(meta.piece_id))
      .then((r) => { if (!r.ok) throw new Error("indisponible"); return r.blob(); })
      .then((b) => { if (!live) return; obj = URL.createObjectURL(b); setUrl(obj); onOpened(); })
      .catch(() => { if (live) setFailed(true); });
    return () => { live = false; if (obj) URL.revokeObjectURL(obj); };
  }, [meta.piece_id]);

  if (failed) return <FallbackCanvas meta={meta} />;
  if (!url) return <LoadingCanvas label="Ouverture de l'image…" />;
  return (
    <div className="pv-imgwrap" role="region" aria-label={`${meta.filename}, ${formatLabel(meta)}`}>
      <img className="pv-image" src={url} alt={meta.filename} />
    </div>
  );
}

// ── the honest fallback (screens 5 + 8): name the limit, offer the original, never an empty pane ──
function FallbackCanvas({ meta, reason }: { meta: PieceMeta; reason?: string }) {
  const overBound = !meta.renderable_inline;
  const size = meta.byte_size != null ? humanSize(meta.byte_size) : null;
  if (overBound) {
    return (
      <Centre glyph="⚠" tone="review" title="Cette pièce dépasse la borne de rendu">
        <p>{size ? <>À <b className="apx-num">{size}</b>, cette</> : "Cette"} pièce dépasse la limite
          de rendu dans le produit. Ouvrez l'original, tel qu'il a été déposé.</p>
        <div className="pv-row">
          <a className="pv-btn" href={pieceOriginalUrl(meta.piece_id)}>⤓ Ouvrir l'original</a>
        </div>
        <p className="pv-note">La borne est une donnée de configuration — elle protège votre poste,
          elle ne cache aucune pièce.</p>
      </Centre>
    );
  }
  return (
    <Centre glyph="▤" tone="muted" title="Ce format ne se rend pas dans le produit">
      <p>{reason
        ? reason
        : "Ce format n'est pas rendu ici. L'original est disponible, tel qu'il a été déposé."}</p>
      <div className="pv-row">
        <a className="pv-btn" href={pieceOriginalUrl(meta.piece_id)}>
          ⤓ Ouvrir l'original{size ? ` (${size})` : ""}
        </a>
      </div>
      <p className="pv-note pv-note--lock">▪ L'original n'a jamais quitté le cabinet.</p>
    </Centre>
  );
}

// ── shared small pieces ───────────────────────────────────────────────────────────────────
function LoadingCanvas({ label }: { label: string }) {
  return (
    <div className="sk" aria-live="polite">
      <span className="progtag">◐ {label}</span>
      <div className="progbar"><i /></div>
      <div style={{ marginTop: "1.4rem" }}>
        {[82, 96, 90, 70, 88, 48].map((w, i) => (
          <div key={i} className="ln" style={{ width: `${w}%` }} />
        ))}
      </div>
    </div>
  );
}

function Centre({ glyph, tone, title, children }: {
  glyph: string; tone: "muted" | "review"; title: string; children: React.ReactNode;
}) {
  const colour = tone === "review" ? "var(--apx-review)" : "var(--apx-ink-3)";
  return (
    <div className="center">
      <div className="glyph" style={{ color: colour }}>{glyph}</div>
      <h3>{title}</h3>
      {children}
    </div>
  );
}

// ── passage resolution over the OCR layout ────────────────────────────────────────────────
type Box = { l: number; o: number; w: number; h: number };

function normalise(s: string): string {
  return s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "")
    .replace(/[^a-z0-9]+/g, " ").trim();
}

/** Find the page + bounding box of the passage in the OCR layout. Best-effort: the first run of
 *  consecutive words matching the passage's tokens (a single-word term matches cleanly; a multi-word
 *  term boxes the run it can match). No match → the first page, no box (the page still opens). */
function findPassage(layout: OcrLayout, passage?: string): { page: number; box: Box | null } {
  const target = passage ? normalise(passage) : "";
  if (!target) return { page: 0, box: null };
  const tokens = target.split(" ").filter(Boolean);
  const first = tokens[0];
  for (let pi = 0; pi < layout.pages.length; pi++) {
    const words = layout.pages[pi].words;
    for (let i = 0; i < words.length; i++) {
      const w0 = normalise(words[i].t);
      if (w0 !== first && !w0.includes(first)) continue;
      const run: OcrWord[] = [words[i]];
      let ti = 1, wi = i + 1;
      while (ti < tokens.length && wi < words.length) {
        const wt = normalise(words[wi].t);
        if (wt === tokens[ti] || wt.includes(tokens[ti])) { run.push(words[wi]); ti++; wi++; }
        else break;
      }
      return { page: pi, box: bbox(run) };
    }
  }
  return { page: 0, box: null };
}

function bbox(words: OcrWord[]): Box {
  const l = Math.min(...words.map((w) => w.l));
  const o = Math.min(...words.map((w) => w.o));
  const r = Math.max(...words.map((w) => w.l + w.w));
  const b = Math.max(...words.map((w) => w.o + w.h));
  return { l, o, w: r - l, h: b - o };
}

// ── the sandboxed-frame document ──────────────────────────────────────────────────────────
const FRAME_CSS = `
:root{color-scheme:light;}
html,body{margin:0;}
body{padding:1.6rem 1.9rem;background:#fff;color:#1a2438;line-height:1.7;font-size:15px;
  font-family:"Iowan Old Style","Palatino Linotype",Palatino,"Book Antiqua",Georgia,serif;
  -webkit-text-size-adjust:100%;}
h1,h2,h3,h4{font-weight:600;text-wrap:balance;}
table{border-collapse:collapse;max-width:100%;}
td,th{border:1px solid #e6e0d5;padding:.3rem .55rem;text-align:left;vertical-align:top;}
th{background:#fbf9f5;font-size:.9em;}
img{max-width:100%;height:auto;}
a{color:#9a7a34;}
mark.apx-passage{background:rgba(154,122,52,0.20);box-shadow:0 0 0 1px rgba(154,122,52,0.25);
  border-radius:2px;padding:0 .05em;}
`;

/** Wrap the server's SANITISED html into a standalone document for the sandboxed frame, marking the
 *  passage. The passage mark is spliced only into a TEXT segment (never inside a tag) and is a
 *  constant, safe `<mark>` — no untrusted markup is introduced, and the frame is sandboxed regardless. */
function wrapHtml(html: string, passage?: string): string {
  const body = passage ? markFirst(html, passage) : html;
  // A restrictive CSP inside the frame — belt to the sandbox and to nh3 (which already strips img /
  // external resources): it forbids ALL subresource egress, so even a future sanitiser regression
  // cannot let a rendered pièce beacon a byte out of the cabinet. Only inline style is allowed.
  const csp = "default-src 'none'; img-src data:; style-src 'unsafe-inline'; font-src data:";
  return "<!doctype html><html lang=\"fr\"><head><meta charset=\"utf-8\">"
    + `<meta http-equiv="Content-Security-Policy" content="${csp}">`
    + "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
    + `<style>${FRAME_CSS}</style></head><body>${body}</body></html>`;
}

/** Wrap the first plain-text occurrence of `passage` in a `<mark class="apx-passage">`. Splits on
 *  tags so the match never straddles or lands inside a tag; the wrapped text is the ORIGINAL
 *  (already-sanitised) run, so this introduces no new markup beyond the constant <mark>. Searches the
 *  raw text for the WHOLE passage first (exact, case-insensitive) so the wash lands on the passage
 *  itself, falling back to the first token only if the whole phrase is not present verbatim. */
function markFirst(html: string, passage: string): string {
  const term = passage.trim();
  if (!term) return html;
  const whole = term.toLowerCase();
  const firstTok = whole.split(/\s+/)[0];
  const parts = html.split(/(<[^>]*>)/);   // odd indices are tags, even indices are text
  for (let i = 0; i < parts.length; i += 2) {
    const text = parts[i];
    const lower = text.toLowerCase();
    let start = lower.indexOf(whole), len = term.length;
    if (start < 0) { start = lower.indexOf(firstTok); len = firstTok.length; }  // fallback: first token
    if (start < 0) continue;
    parts[i] = text.slice(0, start) + "<mark class=\"apx-passage\">"
      + text.slice(start, start + len) + "</mark>" + text.slice(start + len);
    break;
  }
  return parts.join("");
}

// ── formatting ────────────────────────────────────────────────────────────────────────────
function hhmm(d: Date): string {
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

function humanSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} o`;
  const units = ["Ko", "Mo", "Go", "To"];
  let n = bytes / 1024, i = 0;
  while (n >= 1024 && i < units.length - 1) { n /= 1024; i++; }
  const v = n >= 100 ? Math.round(n) : n >= 10 ? Math.round(n * 10) / 10 : Math.round(n * 100) / 100;
  return `${String(v).replace(".", ",")} ${units[i]}`;
}
