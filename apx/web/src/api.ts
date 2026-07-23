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

// The one data path: HTTP to the API (AD-14). No fixtures, no fallback.
export async function ingestUpload(
  files: FileList, matter: string, tenant: string, scope: string, actor: string,
): Promise<IngestResponse> {
  const form = new FormData();
  form.append("matter", matter);
  form.append("tenant", tenant);
  form.append("scope", scope);
  form.append("actor", actor);
  for (const file of Array.from(files)) {
    const rel = (file as File & { webkitRelativePath?: string }).webkitRelativePath || file.name;
    form.append("files", file, rel);
  }
  const res = await fetch("/api/ingest-upload", { method: "POST", body: form });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail ?? `échec (${res.status})`);
  return res.json();
}

// Pre-filtered by scope on the server (the Chinese wall). Empty scope -> nothing.
export async function listMatters(tenant: string, scope: string): Promise<MatterSummary[]> {
  const q = new URLSearchParams({ tenant, scopes: scope });
  const res = await fetch(`/api/matters?${q}`);
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail ?? `échec (${res.status})`);
  return res.json();
}

// The audit trail for a matter — scope-checked server-side (403 outside the wall).
// `verified` is the tamper-evidence: the tenant chain recomputes cleanly.
export async function readAudit(matter: string, tenant: string, scope: string): Promise<AuditTrail> {
  const q = new URLSearchParams({ tenant, scopes: scope });
  const res = await fetch(`/api/matters/${encodeURIComponent(matter)}/audit?${q}`);
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail ?? `échec (${res.status})`);
  return res.json();
}

// The deterministic triage — near-duplicate clustering, scope-checked (403 outside).
// submitted = distinct + duplicates: copies collapsed to one piece to examine.
export async function readTriage(matter: string, tenant: string, scope: string): Promise<Triage> {
  const q = new URLSearchParams({ tenant, scopes: scope });
  const res = await fetch(`/api/matters/${encodeURIComponent(matter)}/triage?${q}`);
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail ?? `échec (${res.status})`);
  return res.json();
}
