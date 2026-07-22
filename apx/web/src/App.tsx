import { useState } from "react";
import { ingest, type IngestResponse } from "./api";

/** Slice A — drop a folder, see the inventory.
 *  The honest core of triage: submitted = in corpus + failures + exclusions,
 *  nothing lost silently. Behavioural only; a UX pass is still owed. */
export default function App() {
  const [folder, setFolder] = useState("");
  const [matter, setMatter] = useState("");
  const [result, setResult] = useState<IngestResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function run(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      setResult(await ingest(folder, matter, "cabinet"));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  const inv = result?.inventory;
  return (
    <main style={{ padding: "var(--apx-space-2)", maxWidth: 720, margin: "0 auto" }}>
      <h1>APX — Inventaire d'un dossier</h1>
      <form onSubmit={run} style={{ display: "flex", gap: "var(--apx-space-1)", flexWrap: "wrap" }}>
        <input
          aria-label="Dossier"
          placeholder="Chemin du dossier (ex. /chemin/vers/le/dossier)"
          value={folder}
          onChange={(e) => setFolder(e.target.value)}
          style={{ flex: "1 1 20rem", padding: ".5rem" }}
        />
        <input
          aria-label="Affaire"
          placeholder="Affaire"
          value={matter}
          onChange={(e) => setMatter(e.target.value)}
          style={{ flex: "0 1 10rem", padding: ".5rem" }}
        />
        <button type="submit" disabled={busy || !folder || !matter} style={{ padding: ".5rem 1rem" }}>
          {busy ? "Analyse…" : "Analyser"}
        </button>
      </form>

      {error && <p role="alert" style={{ color: "#a3161c" }}>{error}</p>}

      {inv && (
        <section aria-live="polite">
          <p style={{ fontSize: "1.1rem" }}>
            <strong>{inv.submitted}</strong> pièces soumises&nbsp;=&nbsp;
            <strong>{inv.in_corpus}</strong> indexées&nbsp;+&nbsp;
            <strong>{inv.failures}</strong> non traitées&nbsp;+&nbsp;
            <strong>{inv.exclusions}</strong> exclues
            {inv.consistent ? " · rien perdu" : " · ⚠ incohérent"}
          </p>

          {result!.failure_list.length > 0 && (
            <>
              <h2>Non traitées — à revoir</h2>
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <tbody>
                  {result!.failure_list.map((f) => (
                    <tr key={f.path} style={{ borderTop: "1px solid #ddd" }}>
                      <td style={{ padding: ".4rem 0" }}>{f.path}</td>
                      <td style={{ padding: ".4rem 0", textAlign: "right", color: "#555" }}>
                        {f.error_class}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}

          {result!.exclusion_list.length > 0 && (
            <p style={{ color: "#777" }}>
              Exclues comme bruit système : {result!.exclusion_list.join(", ")}
            </p>
          )}
        </section>
      )}
    </main>
  );
}
