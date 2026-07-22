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
  persisted: boolean;
};

// The one data path: an HTTP call to the API (AD-14). No fixtures, no fallback.
// Files are uploaded with their folder-relative path so the server rebuilds the tree.
export async function ingestUpload(
  files: FileList,
  matter: string,
  tenant: string,
): Promise<IngestResponse> {
  const form = new FormData();
  form.append("matter", matter);
  form.append("tenant", tenant);
  for (const file of Array.from(files)) {
    const rel = (file as File & { webkitRelativePath?: string }).webkitRelativePath || file.name;
    form.append("files", file, rel);
  }
  const res = await fetch("/api/ingest-upload", { method: "POST", body: form });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail ?? `ingestion échouée (${res.status})`);
  }
  return res.json();
}
