import { useRef, useState } from "react";
import { ingestUpload, type IngestResponse } from "./api";

/** Slice A — drop a folder in the browser, see the inventory.
 *  submitted = in corpus + failures + exclusions, nothing lost silently.
 *  Behavioural only; a UX pass is still owed. */
export default function App() {
  const [matter, setMatter] = useState("");
  const [fileCount, setFileCount] = useState(0);
  const [result, setResult] = useState<IngestResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  async function run(e: React.FormEvent) {
    e.preventDefault();
    const files = inputRef.current?.files;
    if (!files || files.length === 0) return;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      setResult(await ingestUpload(files, matter, "cabinet"));
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
      <p style={{ color: "#555" }}>
        Déposez un dossier. Vous verrez ce qui est entré, ce qui a échoué et ce qui a été écarté —
        rien perdu en silence.
      </p>
      <form onSubmit={run} style={{ display: "flex", gap: "var(--apx-space-1)", flexWrap: "wrap", alignItems: "center" }}>
        <input
          ref={inputRef}
          type="file"
          multiple
          // @ts-expect-error non-standard but supported: pick a whole folder
          webkitdirectory=""
          onChange={(e) => setFileCount(e.target.files?.length ?? 0)}
          aria-label="Dossier"
        />
        <input
          aria-label="Affaire"
          placeholder="Affaire"
          value={matter}
          onChange={(e) => setMatter(e.target.value)}
          style={{ flex: "0 1 12rem", padding: ".5rem" }}
        />
        <button type="submit" disabled={busy || fileCount === 0 || !matter} style={{ padding: ".5rem 1rem" }}>
          {busy ? "Analyse…" : `Analyser${fileCount ? ` (${fileCount})` : ""}`}
        </button>
      </form>

      {error && <p role="alert" style={{ color: "#a3161c" }}>{error}</p>}

      {inv && (
        <section aria-live="polite">
          <p style={{ fontSize: "1.1rem", marginTop: "1.5rem" }}>
            <strong>{inv.submitted}</strong> pièces&nbsp;=&nbsp;
            <strong>{inv.in_corpus}</strong> indexées&nbsp;+&nbsp;
            <strong>{inv.failures}</strong> non traitées&nbsp;+&nbsp;
            <strong>{inv.exclusions}</strong> exclues
            {inv.consistent ? " · rien perdu" : " · ⚠ incohérent"}
            {result!.persisted ? " · enregistré" : ""}
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
            <p style={{ color: "#777" }}>Exclues comme bruit : {result!.exclusion_list.join(", ")}</p>
          )}
        </section>
      )}
    </main>
  );
}
