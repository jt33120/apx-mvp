export type Inventory = {
  submitted_pieces: number; in_corpus: number; open_register_entries: number;
  excluded_as_noise: number; retired: number; unknown_cardinality_entries: number;
  unknown_cardinality_phrase: string; consistent: boolean;
};
export type Failure = { filename: string; path: string; error_class: string };
export type IngestResponse = {
  matter: string; inventory: Inventory; failure_list: Failure[]; exclusion_list: string[]; persisted: boolean;
};
export type MatterSummary = { matter: string; scope: string; inventory: Inventory };
export type AuditEntry = { seq: number; actor: string; action: string; detail: string; timestamp: string };
export type AuditTrail = { entries: AuditEntry[]; verified: boolean };
export type DuplicateGroup = { representative: string; members: string[]; size: number };
export type Triage = { submitted: number; distinct: number; duplicates: number; groups: DuplicateGroup[] };
export type LabelledPiece = { provenance: string; label: string; rationale: string };
export type Labels = { relevant: number; uncertain: number; discarded: number; judged: number; pieces: LabelledPiece[] };
export type JudgeResult = { judged: number; relevant: number; uncertain: number; discarded: number; judge: string };
// Story 3.4 — the two engines each carry their truth status; the client never combines them.
export type SemanticResult = { piece_id: string; chunk_id: string; similarity: number };
export type SuggestiveResult = {
  truth_status: "suggestive"; query: string; k: number; similarity_threshold: number;
  wording: string; results: SemanticResult[]; header?: string;
};
export type Denominator = {
  submitted_pieces: number; in_corpus: number; open_register_entries: number;
  excluded_as_noise: number; retired: number; unknown_cardinality_entries: number;
};
export type RegisterHit = { matter: string; filename: string; error_class: string };
export type DeterministicResult = { matter: string; piece_id: string; snippet: string };
export type ExhaustiveResult = {
  truth_status: "exhaustive"; query: string; denominator: Denominator; ocr_share: number;
  below_quality_share: number; register_hits: RegisterHit[]; normalization: string;
  results: DeterministicResult[]; header?: string;
};
export type Identity = { actor: string; tenant: string; scopes: string[]; is_admin: boolean };
export type AdminUser = {
  id: string; email: string; display_name: string; is_admin: boolean; scopes: string[];
};
export type SampledDiscard = { piece_id: string; provenance: string; excerpt: string };
export type RecallSample = { population: number; sample: SampledDiscard[] };
export type RecallBound = {
  population: number; sample_size: number; relevant_found: number;
  confidence: number; count_upper: number; prevalence_upper: number;
};

// The session cookie (owned auth) carries tenant + scopes; the client never sends them.
async function detail(res: Response): Promise<string> {
  return (await res.json().catch(() => ({}))).detail ?? `échec (${res.status})`;
}

// An error that keeps the HTTP status, so the UI can branch on it — e.g. a 409 is the
// moving-population refusal (an honest "wait"), never a red error (Story 3.4).
export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}
async function fail(res: Response): Promise<never> {
  throw new ApiError(res.status, await detail(res));
}

export async function me(): Promise<Identity | null> {
  const res = await fetch("/api/me");
  if (res.status === 401) return null;
  if (!res.ok) throw new Error(await detail(res));
  return res.json();
}

export async function login(tenant: string, email: string, password: string): Promise<Identity> {
  const res = await fetch("/api/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tenant, email, password }),
  });
  if (!res.ok) throw new Error(await detail(res));
  return res.json();
}

export async function logout(): Promise<void> {
  await fetch("/api/logout", { method: "POST" });
}

// Change your own password (confirms the current one server-side).
export async function changePassword(current_password: string, new_password: string): Promise<void> {
  const res = await fetch("/api/me/password", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ current_password, new_password }),
  });
  if (!res.ok) throw new Error(await detail(res));
}

// Cockpit (admin only): the server enforces the admin gate and tenant scope.
export async function listUsers(): Promise<AdminUser[]> {
  const res = await fetch("/api/admin/users");
  if (!res.ok) throw new Error(await detail(res));
  return res.json();
}

export async function createUser(
  email: string, password: string, display_name: string, scopes: string[], is_admin = false,
): Promise<AdminUser> {
  const res = await fetch("/api/admin/users", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password, display_name, scopes, is_admin }),
  });
  if (!res.ok) throw new Error(await detail(res));
  return res.json();
}

export async function grantScope(userId: string, scope: string): Promise<void> {
  const res = await fetch(`/api/admin/users/${encodeURIComponent(userId)}/grant`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ scope }),
  });
  if (!res.ok) throw new Error(await detail(res));
}

export async function revokeScope(userId: string, scope: string): Promise<void> {
  const res = await fetch(`/api/admin/users/${encodeURIComponent(userId)}/revoke`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ scope }),
  });
  if (!res.ok) throw new Error(await detail(res));
}

// The onboarding gesture (Story 2.1/2.2): a lawyer picks a folder, names the matter, its wall
// and the custodian (mandatory); the case theory is the one optional field. The scope must be
// one the caller holds. Non-blocking (AD-6): the POST returns a job handle immediately; a worker
// fills the corpus. Poll importStatus for the processed-against-submitted figure.
export type ImportStarted = { job_id: string; matter: string; state: string };
export type ImportProgress = {
  job_id: string; matter: string; state: string; submitted: number | null;
  processed: number; committed: number; quarantined: number; pending: number; provisional: boolean;
};

export async function ingestUpload(
  files: FileList,
  matter: string,
  scope: string,
  custodian: string,
  caseTheory?: string,
): Promise<ImportStarted> {
  const form = new FormData();
  form.append("matter", matter);
  form.append("scope", scope);
  form.append("custodian", custodian);
  if (caseTheory && caseTheory.trim()) form.append("case_theory", caseTheory.trim());
  for (const file of Array.from(files)) {
    const rel = (file as File & { webkitRelativePath?: string }).webkitRelativePath || file.name;
    form.append("files", file, rel);
  }
  const res = await fetch("/api/ingest-upload", { method: "POST", body: form });
  if (!res.ok) throw new Error(await detail(res));
  return res.json();
}

// Poll an import's progress — read from the application-owned ledger, never the queue (AD-17).
export async function importStatus(jobId: string): Promise<ImportProgress> {
  const res = await fetch(`/api/imports/${encodeURIComponent(jobId)}`);
  if (!res.ok) throw new Error(await detail(res));
  return res.json();
}

// Every matter the session's scope covers (the Chinese wall, resolved server-side).
export async function listMatters(): Promise<MatterSummary[]> {
  const res = await fetch("/api/matters");
  if (!res.ok) throw new Error(await detail(res));
  return res.json();
}

export async function readTriage(matter: string): Promise<Triage> {
  const res = await fetch(`/api/matters/${encodeURIComponent(matter)}/triage`);
  if (!res.ok) throw new Error(await detail(res));
  return res.json();
}

export async function judgeMatter(matter: string, question: string): Promise<JudgeResult> {
  const res = await fetch(`/api/matters/${encodeURIComponent(matter)}/judge`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
  if (!res.ok) throw new Error(await detail(res));
  return res.json();
}

export async function readLabels(matter: string): Promise<Labels> {
  const res = await fetch(`/api/matters/${encodeURIComponent(matter)}/labels`);
  if (!res.ok) throw new Error(await detail(res));
  return res.json();
}

export async function readAudit(matter: string): Promise<AuditTrail> {
  const res = await fetch(`/api/matters/${encodeURIComponent(matter)}/audit`);
  if (!res.ok) throw new Error(await detail(res));
  return res.json();
}

// The SUGGESTIVE engine (semantic): ranked, never a completeness claim (FR-12/FR-15).
export async function searchSuggestive(q: string, k = 20): Promise<SuggestiveResult> {
  const res = await fetch(`/api/search/suggestive?${new URLSearchParams({ q, k: String(k) })}`);
  if (!res.ok) return fail(res);
  return res.json();
}

// The EXHAUSTIVE engine (deterministic): the complete match set + its denominator (FR-13/FR-15).
// A 409 is the moving-population refusal (never a partial proof) — carried on ApiError.status.
export async function searchExhaustive(q: string): Promise<ExhaustiveResult> {
  const res = await fetch(`/api/search/exhaustive?${new URLSearchParams({ q })}`);
  if (!res.ok) return fail(res);
  return res.json();
}

// The export URLs — the truth status survives onto a court-readable page (opened in a new tab).
export function suggestiveExportUrl(q: string, k = 20): string {
  return `/api/search/suggestive/export?${new URLSearchParams({ q, k: String(k) })}`;
}
export function exhaustiveExportUrl(q: string): string {
  return `/api/search/exhaustive/export?${new URLSearchParams({ q })}`;
}

// Draw a random sample of a matter's discard pile to review (the recall guarantee).
export async function recallSample(matter: string, n = 30): Promise<RecallSample> {
  const params = new URLSearchParams({ n: String(n) });
  const res = await fetch(`/api/matters/${encodeURIComponent(matter)}/recall/sample?${params}`);
  if (!res.ok) throw new Error(await detail(res));
  return res.json();
}

// Record the reviewed sample and get the recall bound (persisted + audited server-side).
export async function recallReview(
  matter: string, verdicts: { piece_id: string; relevant: boolean }[], confidence = 0.95,
): Promise<RecallBound> {
  const res = await fetch(`/api/matters/${encodeURIComponent(matter)}/recall/review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ verdicts, confidence }),
  });
  if (!res.ok) throw new Error(await detail(res));
  return res.json();
}

// ── Story 3.5d — the pièce viewer ─────────────────────────────────────────────────────────
// Reading a pièce is the job: the server RENDERS each format inside the tenant boundary (3.5a–c),
// and the client reads these endpoints and NEVER sends a pièce byte to a third party. Out-of-scope
// OR absent is always the SAME non-disclosing 404 (FR-14/FR-44), carried on ApiError.status so the
// viewer can tell a denial (404) from a degraded blob (409). `filename`/`title` are UNTRUSTED text
// metadata — render as text nodes, never as HTML.

export type PieceMeta = {
  piece_id: string; matter: string; filename: string; media_kind: string;
  ocr: boolean; byte_size: number | null; renderable_inline: boolean;
};
export type PieceRender = {
  piece_id: string; renderable: boolean; format: string | null;
  title: string | null; html: string | null; truncated: boolean; reason: string | null;
};
// The stored OCR layout (kind=ocr-layout) served by /layout — compact keys mirror the at-rest blob:
// t=text, l=left, o=top, w=width, h=height, c=confidence (all in the page IMAGE's pixel space).
export type OcrWord = { t: string; l: number; o: number; w: number; h: number; c: number };
export type OcrPage = { width: number; height: number; words: OcrWord[] };
export type OcrLayout = { dpi: number; pages: OcrPage[] };

// The viewer's metadata peek — a peek, NOT an audited read (the content fetch is the audited open).
// 404 = out-of-scope OR absent (the same, non-disclosing) → surfaces as ApiError(404).
export async function getPiece(pieceId: string): Promise<PieceMeta> {
  const res = await fetch(`/api/pieces/${encodeURIComponent(pieceId)}`);
  if (!res.ok) return fail(res);
  return res.json();
}

// Render an office/email pièce to SANITISED inline HTML (audited when renderable). `renderable:false`
// (over the bound, an unhandled format, an unavailable blob) → the client offers the original.
export async function getRender(pieceId: string): Promise<PieceRender> {
  const res = await fetch(`/api/pieces/${encodeURIComponent(pieceId)}/render`);
  if (!res.ok) return fail(res);
  return res.json();
}

// The stored OCR layout for a SCAN (the overlay coordinates). After getPiece has passed (in scope),
// a 404 means "not a scan" (a born-digital / non-OCR pièce) → null; a 409 (tampered) throws so the
// viewer degrades to offer-the-original.
export async function getLayout(pieceId: string): Promise<OcrLayout | null> {
  const res = await fetch(`/api/pieces/${encodeURIComponent(pieceId)}/layout`);
  if (res.status === 404) return null;
  if (!res.ok) return fail(res);
  return res.json();
}

// The retained ORIGINAL bytes — fetching this IS the audited open (server-side). Same-origin; used as
// an <a download> for the fallback and as the blob source for an inline image.
export function pieceOriginalUrl(pieceId: string): string {
  return `/api/pieces/${encodeURIComponent(pieceId)}/original`;
}

// One rasterised PAGE image of a scan (0-indexed). Fetching a page is an audited serve (server-side).
export function piecePageUrl(pieceId: string, page: number): string {
  return `/api/pieces/${encodeURIComponent(pieceId)}/page/${page}`;
}
