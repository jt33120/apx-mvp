// Story 5.6 — `overridden_register_entries` is the identity's THIRD term (FR-25): documents the
// firm decided to live without, never in the corpus and no longer open. It is never folded into
// `open_register_entries`; a surface that hid it would let an override shrink the denominator.
export type Inventory = {
  submitted_pieces: number; in_corpus: number; open_register_entries: number;
  overridden_register_entries: number;
  excluded_as_noise: number; retired: number; unknown_cardinality_entries: number;
  unknown_cardinality_phrase: string; consistent: boolean;
};
export type Failure = { filename: string; path: string; error_class: string };
export type IngestResponse = {
  matter: string; inventory: Inventory; failure_list: Failure[]; exclusion_list: string[]; persisted: boolean;
};
export type MatterSummary = { matter: string; scope: string; inventory: Inventory };
// Story 5.5 — an entry NAMES the chain it is counted on: the matter, or "" for the tenant chain
// (AD-43). Two chains carry one matter's history, so `seq` alone is no longer unique across the
// trail — key a row by chain + seq, never by seq.
// Story 5.6 — FR-25: an entry says whether it records an OVERRIDE and on which of FR-25's three
// grounds. Derived server-side from the act catalogue: a *pin* is an override although its FR-24
// class is `pin`, so the surface must never re-derive this from the verb.
export type AuditEntry = {
  seq: number; actor: string; action: string; detail: string; timestamp: string;
  chain_scope: string; chain_label_fr: string;
  override: boolean; override_ground: string | null; override_ground_fr: string | null;
};
// What the reader can conclude about ONE chain. `verifiable_in_isolation` is true only for the
// matter's own chain: the pre-5.5 slice on the tenant chain is verified server-side by recomputing
// the whole tenant chain, which the holder of a scoped export cannot do.
export type AuditSlice = {
  chain_scope: string; label_fr: string; entries: number; verified: boolean;
  verifiable_in_isolation: boolean; broken_at: number | null;
};
// `overrides` and `entries_total` count the WHOLE trail, never the filtered list — under
// `overridesOnly` the entries shrink and the counts do not, so the surface can say how much of the
// record it is not showing (FR-25).
export type AuditTrail = {
  entries: AuditEntry[]; verified: boolean; slices: AuditSlice[];
  overrides: number; entries_total: number;
};
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
  overridden_register_entries: number;
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
// ── Story 5.1 — the sampling run over the DERIVED discarded set (FR-22) ────────────────────
// The population is derive_triage_sets(order, line, pins).discarded, NEVER the Story-2.x label
// pile (decision A1). Everything the client renders about validity comes from the SERVER: `state`,
// `invalidated_in_flight`, `state_fr` and `census_fr` are derived server-side from the run's
// freshness stamp, so a client cannot decide a run is still good.
export type SamplingUnit = {
  family_id: string; proxy_piece_id: string; member_piece_ids: string[];
};
export type DrawnFamily = {
  unit: SamplingUnit; draw_index: number; relevant: boolean | null;
  verdict_by: string | null; verdict_at: string | null; verdict_seq: number | null;
};
export type SamplingRun = {
  run_id: string;
  version_id: string; version_no: number; last_retained_piece_id: string;
  pin_ledger_seq: number; scope: string;
  confidence: number; population_families: number; population_pieces: number;
  sample_size: number; is_census: boolean;
  status: string; state: string; invalidated_in_flight: boolean;
  changed: string[]; changed_fr: string[]; state_fr: string;
  // Story 5.4 — the run's own reading, composed by the SERVER in whichever of the four
  // registers applies. It replaced `census_fr` (one arm for one register, the other three
  // hand-assembled here). NOT copyable: only /bound holds the freshness verdict.
  statement_fr: string | null;
  run_qualification_fr: string;   // this run's MEASURED observables, never a freshness verdict
  unfit_fr: string | null;        // FR-23: K approaching N — the ORDER carries no signal
  started_by: string; started_at: string; completed_at: string | null;
  verdicts_recorded: number;
  relevant_found: number | null; count_upper: number | null; prevalence_upper: number | null;
  // Stories 5.2/5.3 — what the run supports, or null while it supports nothing. The registers are
  // disjoint: `counts_only` (the estimator is not proven) and `census` both carry NO bound, and a
  // census is the only one carrying an exact pièce count. This union was stale — it said
  // "no_population" and omitted `counts_only`, so the panel had no arm for a register that ships.
  estimate_kind: "census" | "bound" | "no_population" | "counts_only" | null;
  estimator_method: string | null;
  count_upper_pieces: number | null;   // WORST CASE in pièces; null = not computable, never 0
  relevant_pieces: number | null;      // EXACT, census only
  run_ordinal: number; repeated_draw_fr: string | null;
  drawn: DrawnFamily[];
};
export type Sizing = {
  population: number; target_prevalence: number; confidence: number;
  size: number | null; is_census: boolean; achievable_prevalence_upper: number;
  // Story 5.3 — whether the run this plan sizes will be allowed to state its bound at all.
  bound_will_be_stated: boolean; caveat_fr: string | null;
  reason_fr: string;
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

export async function readAudit(matter: string, overridesOnly = false): Promise<AuditTrail> {
  const q = overridesOnly ? "?overrides_only=true" : "";
  const res = await fetch(`/api/matters/${encodeURIComponent(matter)}/audit${q}`);
  if (!res.ok) throw new Error(await detail(res));
  return res.json();
}

// Close a *failure register* entry by OVERRIDE (FR-25/FR-5): the document never entered the corpus
// and never will. The reason is mandatory — the server refuses a blank one, and so does this.
export async function overrideRegisterEntry(
  entryId: string, reason: string,
): Promise<{ entry_id: string; resolution_state: string }> {
  const res = await fetch(`/api/register/${encodeURIComponent(entryId)}/override`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason }),
  });
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

// ── the sampling run (Story 5.1, FR-22) ────────────────────────────────────────────────────
// A 404 here is the honest "nothing to audit / no draw yet" state, NOT an error to hide: the
// surface must render it as its own state rather than as an empty run.
const runsBase = (matter: string) => `/api/matters/${encodeURIComponent(matter)}/sampling/runs`;

export async function samplingSizing(
  matter: string, target: number, maxSize?: number,
): Promise<Sizing> {
  const params = new URLSearchParams({ target: String(target) });
  if (maxSize !== undefined) params.set("max_size", String(maxSize));
  const res = await fetch(
    `/api/matters/${encodeURIComponent(matter)}/sampling/sizing?${params}`);
  if (!res.ok) throw new Error(await detail(res));
  return res.json();
}

// Draw. The server freezes the ranking version, the line, the pins, the scope and the explicit
// identifier list — a seed alone would be insufficient (FR-22), so the client sends none.
export async function startSamplingRun(
  matter: string, body: { sample_size?: number; target_prevalence?: number },
): Promise<SamplingRun> {
  const res = await fetch(runsBase(matter), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await detail(res));
  return res.json();
}

export async function currentSamplingRun(matter: string): Promise<SamplingRun | null> {
  const res = await fetch(`${runsBase(matter)}/current`);
  if (res.status === 404) return null;   // no draw yet — its own state, not a failure
  if (!res.ok) throw new Error(await detail(res));
  return res.json();
}

// A 409 means the run was invalidated in flight (or is already closed): the population moved
// under the verdicts. The server REFUSES rather than warns, and the message names what moved.
export async function recordSamplingVerdict(
  matter: string, runId: string, familyId: string, relevant: boolean,
): Promise<SamplingRun> {
  const res = await fetch(`${runsBase(matter)}/${encodeURIComponent(runId)}/verdicts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ family_id: familyId, relevant }),
  });
  if (!res.ok) throw new Error(await detail(res));
  return res.json();
}

export async function completeSamplingRun(
  matter: string, runId: string,
): Promise<SamplingRun> {
  const res = await fetch(`${runsBase(matter)}/${encodeURIComponent(runId)}/complete`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(await detail(res));
  return res.json();
}

export async function abandonSamplingRun(
  matter: string, runId: string,
): Promise<SamplingRun> {
  const res = await fetch(`${runsBase(matter)}/${encodeURIComponent(runId)}/abandon`, {
    method: "POST",
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

// ── Story 4.10 — the triage table ────────────────────────────────────────────────────────────
// One read for the whole surface, bound to ONE ranking version (AD-23): the parts cannot drift
// apart under a concurrent re-rank. `side` is a DERIVED view of (the order, the line, the pins) —
// there is deliberately no endpoint that sets one (FR-16/AD-39). `confidence_derived` is false when
// the cascade derived no confidence: show that, never a zero (AD-19). `name` and `label` are
// UNTRUSTED text — render as text nodes, never as HTML.

export type TriageSide = "retained" | "discarded" | "unscored" | "unsplit";
export type TriageRow = {
  piece_id: string; name: string; rank: number | null; side: TriageSide;
  confidence: number | null; confidence_derived: boolean; confidence_signals: string[];
  band: string | null; label: string; label_source: string | null; label_seq: number | null;
  in_current_taxonomy: boolean; pinned: boolean;
};
export type TriageLine = {
  placed: boolean; last_retained_piece_id: string | null; last_retained_rank: number | null;
  basis: string | null; seq: number | null; at: string | null;
};
export type TriageTable = {
  matter: string; version_no: number; version_id: string; basis: string;
  case_theory_version_id: string | null; created_at: string; rows: TriageRow[];
  retained_count: number; discarded_count: number; unscored_count: number;
  unsplit_count: number; corpus_count: number; ranked_count: number; unranked_count: number;
  pins_in_force: number; line: TriageLine; taxonomy: string[];
};
export type ChangeLogEntry = {
  piece_id: string; seq: number; previous: string; label: string; source: string;
  set_by: string; at: string;
};
export type LabelWrite = { piece_id: string; seq: number; entries: ChangeLogEntry[] };

export const UNLABELLED = "unlabelled";

export async function readTriageTable(matter: string, version?: number): Promise<TriageTable> {
  const qs = version === undefined ? "" : `?${new URLSearchParams({ version: String(version) })}`;
  const res = await fetch(`/api/matters/${encodeURIComponent(matter)}/triage-table${qs}`);
  if (!res.ok) return fail(res);
  return res.json();
}

// The ONE editable cell. `expected_seq` is the seq the client last saw: the server refuses a stale
// one with 409 rather than silently overwriting somebody else's edit — the caller reverts and
// re-reads (FR-20 extends to failure).
export async function setPieceLabel(
  matter: string, pieceId: string, label: string, expectedSeq: number | null,
): Promise<LabelWrite> {
  const res = await fetch(
    `/api/matters/${encodeURIComponent(matter)}/pieces/${encodeURIComponent(pieceId)}/label`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ label, expected_seq: expectedSeq }),
    });
  if (!res.ok) return fail(res);
  return res.json();
}

// A revert is a NEW change-log entry carrying the restored value — never an erasure (AD-7).
export async function revertPieceLabel(
  matter: string, pieceId: string, toSeq: number,
): Promise<LabelWrite> {
  const res = await fetch(
    `/api/matters/${encodeURIComponent(matter)}/pieces/${encodeURIComponent(pieceId)}/label/revert`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ to_seq: toSeq }),
    });
  if (!res.ok) return fail(res);
  return res.json();
}

export async function readPieceChangeLog(
  matter: string, pieceId: string,
): Promise<ChangeLogEntry[]> {
  const res = await fetch(
    `/api/matters/${encodeURIComponent(matter)}/pieces/${encodeURIComponent(pieceId)}/label/log`);
  if (!res.ok) return fail(res);
  return (await res.json()).entries;
}

export async function readMatterChangeLog(matter: string, limit = 200): Promise<ChangeLogEntry[]> {
  const qs = new URLSearchParams({ limit: String(limit) });
  const res = await fetch(`/api/matters/${encodeURIComponent(matter)}/change-log?${qs}`);
  if (!res.ok) return fail(res);
  return (await res.json()).entries;
}


// ── Story 4.13: freshness and staleness of derived artefacts (FR-58/AD-23) ────────────────────
// Staleness is a COMPARISON the server makes between the inputs an artefact was produced under and
// the inputs now — never a flag. `changed_fr` is what the banner says; it is never empty when
// `fresh` is false, so the surface can always name WHICH input moved rather than just "périmé".
// A `null` bound freshness means the artefact recorded no stamp: unverifiable, NOT fresh.

export type Freshness = {
  kind: "ranking" | "line" | "bound"; artefact_id: string;
  fresh: boolean; changed: string[]; changed_fr: string[]; reason: string;
  // a newer artefact of this kind exists: still readable and still stale, but not work — the
  // recomputation its line would offer has already been performed. The worklist excludes these.
  superseded: boolean;
};
export type WorklistLine = {
  kind: string; artefact_id: string; changed: string[]; changed_fr: string[];
  offer: string; offer_fr: string;
};
export type Bound = {
  artefact_id: string; population: number; sample_size: number; relevant_found: number;
  confidence: number; reviewed_at: string;
  freshness: Freshness | null; exportable_as_current: boolean;
  status_fr: string; copy_text: string;
  // Stories 5.2/5.3 — the registers, disjoint in the TYPE and not only by convention. `kind` says
  // which one applies; ONLY `bound` carries `count_upper`/`prevalence_upper`. At a census nothing
  // is bounded because everything was read; at `counts_only` the estimator has not passed its
  // simulation gate and the product states counts and nothing derived from them (FR-22/FR-23).
  kind: "census" | "bound" | "counts_only";
  count_upper: number | null; prevalence_upper: number | null;
  // The unit the bound was computed over, and the pièce figures that may sit BESIDE it but never
  // inside it. `count_upper_pieces` is a worst case; `relevant_pieces` is exact and census-only;
  // null means not computable and is never rendered as zero.
  unit_fr: string; piece_count: number | null; method: string | null;
  count_upper_pieces: number | null; relevant_pieces: number | null;
  // 1 = the first draw over this population, abandoned runs counted (OQ-4 input 3).
  run_ordinal: number;
  // Story 5.4 — FR-23's ACCOMPANYING RECORD: the four things the sentence may carry beside it
  // rather than inside it. `scope` is in BOTH, because only the sentence travels out of the app.
  scope: string | null;
  ranking_version_no: number | null;
  last_retained_piece_id: string | null;
  case_theory_version_id: string | null;
  // FR-23's seventh consequence. When present the surface must REMOVE any line-move affordance,
  // not grey it: a greyed control still proposes the act.
  unfit_fr: string | null;
  unfit_relevant_share: number | null;
  unfit_threshold: number | null;
};

export async function readFreshness(matter: string): Promise<Freshness[]> {
  const res = await fetch(`/api/matters/${encodeURIComponent(matter)}/freshness`);
  if (!res.ok) return fail(res);
  return res.json();
}

export async function readWorklist(matter: string): Promise<WorklistLine[]> {
  const res = await fetch(`/api/matters/${encodeURIComponent(matter)}/worklist`);
  if (!res.ok) return fail(res);
  return res.json();
}

export async function readBound(matter: string): Promise<Bound> {
  const res = await fetch(`/api/matters/${encodeURIComponent(matter)}/bound`);
  if (!res.ok) return fail(res);
  return res.json();
}

// ── Story 5.7: the audit drawer and the matter export (FR-26) ─────────────────────────────────
// An UNRESOLVED extract carries its cause and NO quoted text: the text is precisely what could not
// be confirmed at show time (FR-11). The surface must never fill that gap.
export type DrawerExtract = {
  chunk_id: string; verified: boolean; cause: string | null; cause_fr: string | null;
};
// The audit row an action WILL append. No timestamp and no seq — neither exists yet, and a shown
// value that is not the one written would be a lie in the one place that cannot afford one.
export type ProposedEntry = {
  action: string; action_fr: string; actor: string; chain_scope: string; chain_label_fr: string;
  override_ground: string | null; override_ground_fr: string | null; reason_required: boolean;
};
export type DrawerAction = {
  action: string; action_fr: string; reversal_fr: string; proposed: ProposedEntry;
};
export type DrawerPendingAction = { label_fr: string; story: string; disabled_reason_fr: string };
export type Drawer = {
  piece_id: string; matter: string; ranking_version_no: number | null;
  sentence: string | null; confidence: number | null; confidence_signals: string[];
  source_language: string | null; rejected: boolean;
  is_unverified: boolean; unresolved_extracts: number;
  extracts: DrawerExtract[]; actions: DrawerAction[]; pending_actions: DrawerPendingAction[];
  // FR-45/FR-44 — what a validation act performed NOW would record, stated before the act. The
  // server sends a timestamp rather than a flag: "ouverte" alone is equally true of an open six
  // months and three rankings ago, and the surface prints the date so the lawyer judges the
  // distance herself.
  validation_provenance: "read" | "from-the-list";
  validation_opened_at: string | null;
  validation_provenance_fr: string;
  validation_assertion_fr: string;
};

export async function readDrawer(matter: string, pieceId: string): Promise<Drawer | null> {
  const res = await fetch(
    `/api/matters/${encodeURIComponent(matter)}/pieces/${encodeURIComponent(pieceId)}/drawer`);
  if (res.status === 404) return null;   // out of scope and absent answer identically
  if (!res.ok) throw new Error(await detail(res));
  return res.json();
}

// The tier is chosen BEFORE production and has no default here either: this is the one act in the
// product that can move client content out of the firm on purpose (FR-26 §11).
export type ExportTier = "numbers-only" | "full";
export type MatterRecordDoc = {
  cover: Record<string, unknown>;
  denominator: Record<string, unknown>[];
  case_theory: Record<string, unknown>[];
  line_history: Record<string, unknown>[];
  pins: Record<string, unknown>[];
  sampling_runs: Record<string, unknown>[];
  overrides: Record<string, unknown>[];
  overrides_total: number;
  validations: Record<string, unknown>[];
  validation_summary: ValidationSummary | null;
  modified_values: number;
  accepted_values: number;
  pending: { key: string; heading_fr: string; story: string; sentence_fr: string }[];
};

/* ── Story 5.8: the VALIDATION ACT (FR-45) ─────────────────────────────────────────────────────
   "I have read this pièce and I accept the tool's assessment of it." The two registers below are
   never pooled: a reader of the export must always be able to tell 12 individual judgements from
   one gesture over 168. */
export type ValidationSummary = {
  read: number; from_the_list: number; individually: number;
  in_bulk: number; batches: number; withdrawn: number; never_validated: number;
};
export type ValidationEntry = {
  piece_id: string; seq: number; action: "validated" | "withdrawn"; actor: string; at: string;
  provenance: "read" | "from-the-list"; provenance_fr: string;
  ranking_version_id: string; opened_at: string | null;
  batch_id: string | null; batch_size: number | null;
  // the acceptance refers to a ranking version that is no longer the one shown (AD-23). NOT an
  // invalidation: the act happened and nothing erases it.
  stale: boolean;
};
export type ValidationLog = {
  entries: ValidationEntry[]; current_ranking_version_id: string | null;
};
export type ValidationSplit = {
  total: number; opened: number; not_opened: number; sentence_fr: string;
};

export async function readValidations(
  matter: string, pieceId?: string,
): Promise<ValidationLog | null> {
  const q = pieceId ? `?piece_id=${encodeURIComponent(pieceId)}` : "";
  const res = await fetch(`/api/matters/${encodeURIComponent(matter)}/validations${q}`);
  if (res.status === 404) return null;   // out of scope and absent answer identically
  if (!res.ok) throw new Error(await detail(res));
  return res.json();
}

export async function validatePiece(
  matter: string, pieceId: string,
): Promise<ValidationLog> {
  const res = await fetch(
    `/api/matters/${encodeURIComponent(matter)}/pieces/${encodeURIComponent(pieceId)}/validate`,
    { method: "POST" });
  if (!res.ok) throw new Error(await detail(res));
  return res.json();
}

export async function withdrawValidation(
  matter: string, pieceId: string,
): Promise<ValidationLog> {
  const res = await fetch(
    `/api/matters/${encodeURIComponent(matter)}/pieces/${encodeURIComponent(pieceId)}`
    + "/validation/withdraw",
    { method: "POST" });
  if (!res.ok) throw new Error(await detail(res));
  return res.json();
}

// The confirmation's own content (FR-45(a)) — the count AND the split. Writes nothing: a dialog
// naming only the total obtains consent while telling her nothing she did not already know.
export async function previewValidationBatch(
  matter: string, pieceIds: string[],
): Promise<ValidationSplit | null> {
  const res = await fetch(`/api/matters/${encodeURIComponent(matter)}/validate-batch/preview`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ piece_ids: pieceIds, confirmed_count: pieceIds.length }),
  });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(await detail(res));
  return res.json();
}

// `confirmedCount` is what the lawyer was SHOWN, not `pieceIds.length` re-derived here: the server
// refuses a mismatch, which is what catches a selection that changed under the dialog.
export async function validateBatch(
  matter: string, pieceIds: string[], confirmedCount: number,
): Promise<ValidationLog> {
  const res = await fetch(`/api/matters/${encodeURIComponent(matter)}/validate-batch`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ piece_ids: pieceIds, confirmed_count: confirmedCount }),
  });
  if (!res.ok) throw new Error(await detail(res));
  return res.json();
}

export async function exportMatterRecord(
  matter: string, tier: ExportTier,
): Promise<MatterRecordDoc> {
  const res = await fetch(
    `/api/matters/${encodeURIComponent(matter)}/record/export?tier=${encodeURIComponent(tier)}`,
    { method: "POST" });
  if (!res.ok) throw new Error(await detail(res));
  return res.json();
}
