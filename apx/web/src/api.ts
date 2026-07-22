export type Inventory = {
  submitted: number;
  in_corpus: number;
  failures: number;
  exclusions: number;
  consistent: boolean;
};
export type Failure = { filename: string; path: string; error_class: string };
export type IngestResponse = {
  matter: string;
  inventory: Inventory;
  failure_list: Failure[];
  exclusion_list: string[];
};

// The one data path: an HTTP call to the API (AD-14). No fixtures, no fallback.
export async function ingest(folder: string, matter: string, tenant: string): Promise<IngestResponse> {
  const res = await fetch("/api/ingest", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ folder, matter, tenant }),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail ?? `ingest failed (${res.status})`);
  }
  return res.json();
}
