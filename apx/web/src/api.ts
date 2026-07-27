export type Inventory = {
  submitted: number; in_corpus: number; failures: number; exclusions: number; consistent: boolean;
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
export type SearchHit = { matter: string; provenance: string; snippet: string };
export type SearchResults = { query: string; total: number; returned: number; hits: SearchHit[] };
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

// Deterministic exhaustive search, scope-constrained server-side (the wall pre-filters it).
export async function searchCorpus(q: string): Promise<SearchResults> {
  const res = await fetch(`/api/search?${new URLSearchParams({ q })}`);
  if (!res.ok) throw new Error(await detail(res));
  return res.json();
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
