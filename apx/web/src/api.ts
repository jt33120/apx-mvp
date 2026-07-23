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
export type Identity = { actor: string; tenant: string; scopes: string[] };
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

// A lawyer drops files (or a folder) and files the matter under one of their walls.
export async function ingestUpload(files: FileList, matter: string, scope: string): Promise<IngestResponse> {
  const form = new FormData();
  form.append("matter", matter);
  form.append("scope", scope);
  for (const file of Array.from(files)) {
    const rel = (file as File & { webkitRelativePath?: string }).webkitRelativePath || file.name;
    form.append("files", file, rel);
  }
  const res = await fetch("/api/ingest-upload", { method: "POST", body: form });
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
