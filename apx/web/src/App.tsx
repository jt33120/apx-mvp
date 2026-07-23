import { useEffect, useRef, useState } from "react";
import {
  ingestUpload, judgeMatter, listMatters, login, logout, me,
  readAudit, readLabels, readTriage, searchCorpus,
  type AuditTrail, type Identity, type IngestResponse, type Labels,
  type MatterSummary, type SearchResults, type Triage,
} from "./api";

/** Owned auth gate (AD-15): the session — not the request — carries the tenant and
 *  the held scopes. Nothing loads until you are who you say you are. */
export default function App() {
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    me().then(setIdentity).catch(() => setIdentity(null)).finally(() => setReady(true));
  }, []);

  if (!ready) return <main style={{ padding: "2rem", maxWidth: 760, margin: "0 auto" }}>…</main>;
  if (!identity) return <Login onLogin={setIdentity} />;
  return (
    <Console
      identity={identity}
      onLogout={async () => {
        await logout();
        setIdentity(null);
      }}
    />
  );
}

function Login({ onLogin }: { onLogin: (id: Identity) => void }) {
  const [tenant, setTenant] = useState("cabinet");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      onLogin(await login(tenant, email, password));
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : String(e2));
    } finally {
      setBusy(false);
    }
  }

  const box = { padding: ".5rem", width: "100%", boxSizing: "border-box" as const };
  return (
    <main style={{ padding: "3rem 1.25rem", maxWidth: 360, margin: "0 auto" }}>
      <h1>A P<span style={{ color: "#9a7a34" }}>X</span></h1>
      <p style={{ color: "#555", fontSize: ".9rem" }}>Accès au cabinet — identifiez-vous.</p>
      <form onSubmit={submit} style={{ display: "flex", flexDirection: "column", gap: ".6rem" }}>
        <input aria-label="Cabinet" placeholder="Cabinet" value={tenant}
          onChange={(e) => setTenant(e.target.value)} style={box} />
        <input aria-label="Courriel" placeholder="Courriel" type="email" value={email}
          onChange={(e) => setEmail(e.target.value)} style={box} />
        <input aria-label="Mot de passe" placeholder="Mot de passe" type="password" value={password}
          onChange={(e) => setPassword(e.target.value)} style={box} />
        <button type="submit" disabled={busy || !email || !password} style={{ padding: ".5rem 1rem" }}>
          {busy ? "Connexion…" : "Se connecter"}
        </button>
      </form>
      {err && <p role="alert" style={{ color: "#a3161c" }}>{err}</p>}
    </main>
  );
}

/** Drop a folder, see the inventory; deduplicate, judge, search — all within the
 *  scopes the session holds. */
function Console({ identity, onLogout }: { identity: Identity; onLogout: () => void }) {
  const [matter, setMatter] = useState("");
  const [scope, setScope] = useState(identity.scopes[0] ?? "");
  const [fileCount, setFileCount] = useState(0);
  const [result, setResult] = useState<IngestResponse | null>(null);
  const [matters, setMatters] = useState<MatterSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  async function refreshMatters() {
    try {
      setMatters(await listMatters());
    } catch {
      setMatters([]);
    }
  }
  useEffect(() => {
    void refreshMatters();
  }, []);

  async function run(e: React.FormEvent) {
    e.preventDefault();
    const files = inputRef.current?.files;
    if (!files || files.length === 0 || !scope) return;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      setResult(await ingestUpload(files, matter, scope));
      await refreshMatters();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  const box = { padding: ".5rem" } as const;
  return (
    <main style={{ padding: "var(--apx-space-2)", maxWidth: 760, margin: "0 auto" }}>
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline",
        gap: "1rem", flexWrap: "wrap", borderBottom: "1px solid #e7e2d8", paddingBottom: ".6rem" }}>
        <h1 style={{ margin: 0 }}>APX — Inventaire d'un dossier</h1>
        <div style={{ fontSize: ".85rem", color: "#555" }}>
          {identity.actor} · {identity.scopes.join(", ") || "aucun périmètre"}{" "}
          <button onClick={onLogout} style={{ marginLeft: ".5rem", padding: ".2rem .6rem" }}>
            Déconnexion
          </button>
        </div>
      </header>

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
        <select aria-label="Périmètre" value={scope} onChange={(e) => setScope(e.target.value)}
          style={{ ...box, flex: "0 1 11rem" }}>
          {identity.scopes.length === 0 && <option value="">aucun périmètre</option>}
          {identity.scopes.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <button type="submit" disabled={busy || fileCount === 0 || !matter || !scope}
          style={{ padding: ".5rem 1rem" }}>
          {busy ? "Analyse…" : `Analyser${fileCount ? ` (${fileCount})` : ""}`}
        </button>
      </form>

      {error && <p role="alert" style={{ color: "#a3161c" }}>{error}</p>}

      {result && <InventoryView title={`Résultat — ${result.matter}`} r={result} />}

      <CorpusSearch />

      {matters.length > 0 && (
        <section style={{ marginTop: "2rem" }}>
          <h2>Mes dossiers</h2>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <tbody>
              {matters.map((m) => <MatterRow key={m.matter} m={m} />)}
            </tbody>
          </table>
        </section>
      )}
    </main>
  );
}

/** The safety net beneath triage: type a term, find every piece that contains it
 *  within your scope, whatever its label. Deterministic, exhaustive, scope-constrained. */
function CorpusSearch() {
  const [q, setQ] = useState("");
  const [res, setRes] = useState<SearchResults | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function runSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!q.trim()) return;
    setBusy(true);
    setErr(null);
    try {
      setRes(await searchCorpus(q));
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : String(e2));
      setRes(null);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section style={{ marginTop: "2rem" }}>
      <h2>Recherche — dans votre périmètre</h2>
      <p style={{ color: "#555", fontSize: ".9rem", margin: "0 0 .6rem" }}>
        Un nom, une partie, une référence : toute pièce qui le contient, où qu'elle soit dans
        votre périmètre, quel que soit son tri. Déterministe et exhaustif — rien n'est caché.
      </p>
      <form onSubmit={runSearch} style={{ display: "flex", gap: ".4rem", flexWrap: "wrap" }}>
        <input value={q} onChange={(e) => setQ(e.target.value)}
          placeholder="nom de pièce, partie, référence…" aria-label="Recherche"
          style={{ padding: ".4rem .5rem", flex: "1 1 20rem" }} />
        <button type="submit" disabled={busy || !q.trim()} style={{ padding: ".4rem .9rem" }}>
          {busy ? "Recherche…" : "Chercher"}
        </button>
      </form>
      {err && <p role="alert" style={{ color: "#a3161c" }}>{err}</p>}
      {res && (
        <div style={{ marginTop: ".8rem" }}>
          <p style={{ fontSize: ".9rem", color: "#333", margin: "0 0 .4rem" }}>
            <strong>{res.total}</strong> pièce{res.total > 1 ? "s" : ""} pour « {res.query} »
            {res.returned < res.total && <span style={{ color: "#777" }}> · {res.returned} affichées</span>}
          </p>
          {res.hits.map((h) => (
            <div key={`${h.matter}/${h.provenance}`}
              style={{ borderTop: "1px solid #eee", padding: ".45rem 0" }}>
              <div style={{ fontSize: ".8rem", color: "#777" }}>
                {h.matter} · <span style={{ fontFamily: "monospace" }}>{h.provenance}</span>
              </div>
              <div style={{ fontSize: ".88rem", color: "#333" }}>{h.snippet}</div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

/** A matter, expandable to its deterministic triage, the judgment-by-criteria, and
 *  its audit journal (all fetched on demand, all scope-checked server-side). */
function MatterRow({ m }: { m: MatterSummary }) {
  const [open, setOpen] = useState(false);
  const [triage, setTriage] = useState<Triage | null>(null);
  const [labels, setLabels] = useState<Labels | null>(null);
  const [trail, setTrail] = useState<AuditTrail | null>(null);
  const [question, setQuestion] = useState("");
  const [judging, setJudging] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function load() {
    const [tg, lb, au] = await Promise.all([
      readTriage(m.matter),
      readLabels(m.matter),
      readAudit(m.matter),
    ]);
    setTriage(tg);
    setLabels(lb);
    setTrail(au);
  }

  async function toggle() {
    const next = !open;
    setOpen(next);
    if (next && !triage) {
      try {
        await load();
      } catch (e) {
        setErr(e instanceof Error ? e.message : String(e));
      }
    }
  }

  async function judge(e: React.FormEvent) {
    e.preventDefault();
    setJudging(true);
    setErr(null);
    try {
      await judgeMatter(m.matter, question);
      await load(); // labels changed, and a "judge" entry was appended to the journal
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : String(e2));
    } finally {
      setJudging(false);
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
          {m.inventory.in_corpus} indexées · {m.inventory.failures} à revoir · tri & journal
        </td>
      </tr>
      {open && (
        <tr>
          <td colSpan={2} style={{ padding: ".25rem 0 1rem 1.4rem" }}>
            {err && <p role="alert" style={{ color: "#a3161c", margin: 0 }}>{err}</p>}
            {triage && <TriageView t={triage} />}
            <Judging question={question} setQuestion={setQuestion} judging={judging}
              onJudge={judge} labels={labels} />
            {trail && <Journal trail={trail} />}
          </td>
        </tr>
      )}
    </>
  );
}

function TriageView({ t }: { t: Triage }) {
  return (
    <div style={{ marginBottom: ".9rem" }}>
      <p style={{ margin: "0 0 .35rem", fontSize: ".95rem" }}>
        <strong>{t.submitted}</strong> pièces → <strong>{t.distinct}</strong> distinctes à examiner
        {t.duplicates > 0 && <> · <strong>{t.duplicates}</strong> doublon{t.duplicates > 1 ? "s" : ""} regroupé{t.duplicates > 1 ? "s" : ""}</>}
      </p>
      {t.groups.length > 0 && (
        <ul style={{ margin: 0, paddingLeft: "1.2rem", fontSize: ".85rem", color: "#444" }}>
          {t.groups.map((g) => (
            <li key={g.representative} style={{ marginBottom: ".15rem" }}>
              <span style={{ fontFamily: "monospace" }}>{g.representative}</span>{" "}
              <span style={{ color: "#777" }}>+ {g.size - 1} copie{g.size - 1 > 1 ? "s" : ""}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** Judge the distinct band by declared criteria (recall-first: a match is relevant,
 *  the rest stays "à juger" — never auto-discarded). Every label shows its reason. */
function Judging({ question, setQuestion, judging, onJudge, labels }: {
  question: string; setQuestion: (s: string) => void; judging: boolean;
  onJudge: (e: React.FormEvent) => void; labels: Labels | null;
}) {
  return (
    <div style={{ marginBottom: ".9rem" }}>
      <form onSubmit={onJudge} style={{ display: "flex", gap: ".4rem", marginBottom: ".5rem", flexWrap: "wrap" }}>
        <input value={question} onChange={(e) => setQuestion(e.target.value)}
          placeholder="critères de tri (ex : bail, résiliation)" aria-label="Critères de tri"
          style={{ padding: ".35rem .5rem", flex: "1 1 16rem" }} />
        <button type="submit" disabled={judging} style={{ padding: ".35rem .8rem" }}>
          {judging ? "Jugement…" : "Juger"}
        </button>
      </form>
      {labels && labels.judged > 0 && (
        <>
          <p style={{ margin: "0 0 .35rem", fontSize: ".9rem" }}>
            <strong style={{ color: "#2f6f4f" }}>{labels.relevant}</strong> pertinentes ·{" "}
            <strong style={{ color: "#9a5a12" }}>{labels.uncertain}</strong> à juger ·{" "}
            <strong style={{ color: "#7a7364" }}>{labels.discarded}</strong> écartées
          </p>
          <ul style={{ margin: 0, paddingLeft: "1.2rem", fontSize: ".85rem", color: "#444" }}>
            {labels.pieces.map((p) => (
              <li key={p.provenance} style={{ marginBottom: ".15rem" }}>
                <span style={{ fontFamily: "monospace" }}>{p.provenance}</span>{" "}
                <LabelChip label={p.label} />{" "}
                <span style={{ color: "#777" }}>{p.rationale}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

function LabelChip({ label }: { label: string }) {
  const map: Record<string, [string, string, string]> = {
    relevant: ["#2f6f4f", "#e8f1eb", "pertinente"],
    uncertain: ["#9a5a12", "#f6ecdd", "à juger"],
    discard: ["#7a7364", "#efece5", "écartée"],
  };
  const [fg, bg, txt] = map[label] ?? ["#555", "#eee", label];
  return (
    <span style={{ color: fg, background: bg, borderRadius: 999, padding: ".05rem .45rem", fontSize: ".76rem" }}>
      {txt}
    </span>
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

function InventoryView({ title, r }: { title: string; r: IngestResponse }) {
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
