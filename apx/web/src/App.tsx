import { useEffect, useRef, useState } from "react";
import {
  ingestUpload, listMatters, readAudit,
  type AuditTrail, type IngestResponse, type MatterSummary,
} from "./api";

const TENANT = "cabinet";

/** Slice A — drop a folder, see the inventory; re-open matters already ingested;
 *  read a matter's audit journal. Reads are pre-filtered by the Chinese-wall
 *  scope (AD-13); the journal is append-only and tamper-evident (FR-24/FR-53). */
export default function App() {
  const [matter, setMatter] = useState("");
  const [scope, setScope] = useState("");
  const [actor, setActor] = useState("");
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
      const r = await ingestUpload(files, matter, TENANT, scope || matter, actor || "inconnu");
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
        rien perdu en silence. Vous ne voyez que les dossiers de votre périmètre, et chaque
        dépôt est inscrit au journal.
      </p>

      <form onSubmit={run} style={{ display: "flex", gap: "var(--apx-space-1)", flexWrap: "wrap", alignItems: "center" }}>
        {/* @ts-expect-error non-standard but supported: pick a whole folder */}
        <input ref={inputRef} type="file" multiple webkitdirectory=""
          onChange={(e) => setFileCount(e.target.files?.length ?? 0)} aria-label="Dossier" />
        <input aria-label="Affaire" placeholder="Affaire" value={matter}
          onChange={(e) => setMatter(e.target.value)} style={{ ...box, flex: "0 1 10rem" }} />
        <input aria-label="Périmètre" placeholder="Périmètre (mur)" value={scope}
          onChange={(e) => setScope(e.target.value)} style={{ ...box, flex: "0 1 10rem" }} />
        <input aria-label="Intervenant" placeholder="Vous (intervenant)" value={actor}
          onChange={(e) => setActor(e.target.value)} style={{ ...box, flex: "0 1 10rem" }} />
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
                <MatterRow key={m.matter} m={m} scope={scope} />
              ))}
            </tbody>
          </table>
        </section>
      )}
    </main>
  );
}

/** A matter, expandable to its audit journal (fetched on demand, scope-checked). */
function MatterRow({ m, scope }: { m: MatterSummary; scope: string }) {
  const [open, setOpen] = useState(false);
  const [trail, setTrail] = useState<AuditTrail | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function toggle() {
    const next = !open;
    setOpen(next);
    if (next && !trail) {
      try {
        setTrail(await readAudit(m.matter, TENANT, scope));
      } catch (e) {
        setErr(e instanceof Error ? e.message : String(e));
      }
    }
  }

  return (
    <>
      <tr style={{ borderTop: "1px solid #ddd", cursor: "pointer" }} onClick={toggle}>
        <td style={{ padding: ".5rem 0" }}>
          <span aria-hidden style={{ color: "#999", marginRight: ".4rem" }}>{open ? "▾" : "▸"}</span>
          {m.matter}
        </td>
        <td style={{ padding: ".5rem 0", textAlign: "right", color: "#555" }}>
          {m.inventory.in_corpus} indexées · {m.inventory.failures} à revoir · journal
        </td>
      </tr>
      {open && (
        <tr>
          <td colSpan={2} style={{ padding: ".25rem 0 1rem 1.4rem" }}>
            {err && <p role="alert" style={{ color: "#a3161c", margin: 0 }}>{err}</p>}
            {trail && <Journal trail={trail} />}
          </td>
        </tr>
      )}
    </>
  );
}

function Journal({ trail }: { trail: AuditTrail }) {
  return (
    <div>
      <p style={{ margin: "0 0 .5rem", fontSize: ".9rem",
        color: trail.verified ? "#2f6f4f" : "#a3161c" }}>
        {trail.verified
          ? "🔒 Journal intègre — la chaîne se recalcule sans rupture."
          : "⚠ Journal altéré — la chaîne ne se recalcule pas."}
      </p>
      <ol style={{ margin: 0, paddingLeft: "1.2rem", fontSize: ".9rem", color: "#444" }}>
        {trail.entries.map((e) => (
          <li key={e.seq} style={{ marginBottom: ".2rem" }}>
            <strong>{e.action}</strong> — {e.detail}{" "}
            <span style={{ color: "#777" }}>· {e.actor} · {e.timestamp.replace("T", " ").slice(0, 19)}</span>
          </li>
        ))}
      </ol>
    </div>
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
