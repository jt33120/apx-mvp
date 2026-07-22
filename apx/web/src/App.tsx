import { useEffect, useRef, useState } from "react";
import { ingestUpload, listMatters, type IngestResponse, type MatterSummary } from "./api";

const TENANT = "cabinet";

/** Slice A — drop a folder, see the inventory; re-open matters already ingested.
 *  Reads are pre-filtered by the Chinese-wall scope (AD-13). Behavioural only. */
export default function App() {
  const [matter, setMatter] = useState("");
  const [scope, setScope] = useState("");
  const [fileCount, setFileCount] = useState(0);
  const [result, setResult] = useState<IngestResponse | null>(null);
  const [matters, setMatters] = useState<MatterSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  async function refreshMatters(s: string) {
    if (!s) return setMatters([]);
    try {
      setMatters(await listMatters(TENANT, s));
    } catch {
      setMatters([]); // no database configured yet (503) — nothing to list
    }
  }
  useEffect(() => {
    void refreshMatters(scope);
  }, [scope]);

  async function run(e: React.FormEvent) {
    e.preventDefault();
    const files = inputRef.current?.files;
    if (!files || files.length === 0) return;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const r = await ingestUpload(files, matter, TENANT, scope || matter);
      setResult(r);
      await refreshMatters(scope || matter);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  const box = { padding: ".5rem" } as const;
  return (
    <main style={{ padding: "var(--apx-space-2)", maxWidth: 760, margin: "0 auto" }}>
      <h1>APX — Inventaire d'un dossier</h1>
      <p style={{ color: "#555" }}>
        Déposez un dossier. Vous verrez ce qui est entré, ce qui a échoué, ce qui a été écarté —
        rien perdu en silence. Vous ne voyez que les dossiers de votre périmètre.
      </p>

      <form onSubmit={run} style={{ display: "flex", gap: "var(--apx-space-1)", flexWrap: "wrap", alignItems: "center" }}>
        {/* @ts-expect-error non-standard but supported: pick a whole folder */}
        <input ref={inputRef} type="file" multiple webkitdirectory=""
          onChange={(e) => setFileCount(e.target.files?.length ?? 0)} aria-label="Dossier" />
        <input aria-label="Affaire" placeholder="Affaire" value={matter}
          onChange={(e) => setMatter(e.target.value)} style={{ ...box, flex: "0 1 11rem" }} />
        <input aria-label="Périmètre" placeholder="Périmètre (mur)" value={scope}
          onChange={(e) => setScope(e.target.value)} style={{ ...box, flex: "0 1 11rem" }} />
        <button type="submit" disabled={busy || fileCount === 0 || !matter} style={{ padding: ".5rem 1rem" }}>
          {busy ? "Analyse…" : `Analyser${fileCount ? ` (${fileCount})` : ""}`}
        </button>
      </form>

      {error && <p role="alert" style={{ color: "#a3161c" }}>{error}</p>}

      {result && <Inventory title={`Résultat — ${result.matter}`} r={result} />}

      {matters.length > 0 && (
        <section style={{ marginTop: "2rem" }}>
          <h2>Mes dossiers — périmètre « {scope} »</h2>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <tbody>
              {matters.map((m) => (
                <tr key={m.matter} style={{ borderTop: "1px solid #ddd" }}>
                  <td style={{ padding: ".5rem 0" }}>{m.matter}</td>
                  <td style={{ padding: ".5rem 0", textAlign: "right", color: "#555" }}>
                    {m.inventory.in_corpus} indexées · {m.inventory.failures} à revoir
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </main>
  );
}

function Inventory({ title, r }: { title: string; r: IngestResponse }) {
  const inv = r.inventory;
  return (
    <section aria-live="polite" style={{ marginTop: "1.5rem" }}>
      <h2>{title}</h2>
      <p style={{ fontSize: "1.1rem" }}>
        <strong>{inv.submitted}</strong> pièces = <strong>{inv.in_corpus}</strong> indexées +{" "}
        <strong>{inv.failures}</strong> non traitées + <strong>{inv.exclusions}</strong> exclues
        {inv.consistent ? " · rien perdu" : " · ⚠ incohérent"}
        {r.persisted ? " · enregistré" : ""}
      </p>
      {r.failure_list.length > 0 && (
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <tbody>
            {r.failure_list.map((f) => (
              <tr key={f.path} style={{ borderTop: "1px solid #ddd" }}>
                <td style={{ padding: ".4rem 0" }}>{f.path}</td>
                <td style={{ padding: ".4rem 0", textAlign: "right", color: "#555" }}>{f.error_class}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
