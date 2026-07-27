import { useEffect, useRef, useState } from "react";
import {
  changePassword, createUser, grantScope, ingestUpload, judgeMatter, listMatters, listUsers,
  login, logout, me, readAudit, readLabels, readTriage, recallReview, recallSample, revokeScope,
  searchCorpus,
  type AdminUser, type AuditTrail, type Identity, type IngestResponse, type Labels,
  type MatterSummary, type RecallBound, type RecallSample, type SearchResults, type Triage,
} from "./api";

/** Owned auth gate (AD-15): the session — not the request — carries the tenant and
 *  the held scopes. Nothing loads until you are who you say you are. */
export default function App() {
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [ready, setReady] = useState(false);
  const [view, setView] = useState<"console" | "cockpit">("console");

  useEffect(() => {
    me().then(setIdentity).catch(() => setIdentity(null)).finally(() => setReady(true));
  }, []);

  if (!ready) return <main className="apx-shell">…</main>;
  if (!identity) return <Login onLogin={setIdentity} />;

  const onLogout = async () => {
    await logout();
    setIdentity(null);
    setView("console");
  };
  if (view === "cockpit" && identity.is_admin) {
    return <Cockpit onBack={() => setView("console")} onLogout={onLogout} />;
  }
  return (
    <Console identity={identity} onLogout={onLogout}
      onCockpit={identity.is_admin ? () => setView("cockpit") : undefined} />
  );
}

function Wordmark({ tag }: { tag: string }) {
  return (
    <div className="apx-wordmark">
      A&nbsp;P<b>X</b>{" "}
      <span style={{ fontFamily: "var(--apx-sans)", fontSize: ".68rem", letterSpacing: ".14em",
        textTransform: "uppercase", color: "var(--apx-ink-3)", marginLeft: ".3rem" }}>{tag}</span>
    </div>
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

  return (
    <div className="apx-login">
      <div className="apx-card apx-login-card">
        <div className="apx-wordmark apx-login-mark">A&nbsp;P<b>X</b></div>
        <p className="apx-login-tag">
          Le triage documentaire des cabinets — confidentiel, à l'échelle, et prouvable.
        </p>
        <form onSubmit={submit} className="apx-login-form">
          <label className="apx-field">
            <span>Cabinet</span>
            <input aria-label="Cabinet" placeholder="cabinet" value={tenant}
              onChange={(e) => setTenant(e.target.value)} autoComplete="organization" />
          </label>
          <label className="apx-field">
            <span>Courriel</span>
            <input aria-label="Courriel" type="email" placeholder="vous@cabinet.fr" value={email}
              onChange={(e) => setEmail(e.target.value)} autoComplete="username" />
          </label>
          <label className="apx-field">
            <span>Mot de passe</span>
            <input aria-label="Mot de passe" type="password" placeholder="••••••••" value={password}
              onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
          </label>
          <button type="submit" className="apx-login-submit" disabled={busy || !email || !password}>
            {busy ? "Connexion…" : "Se connecter"}
          </button>
        </form>
        {err && <p className="apx-login-error" role="alert">{err}</p>}
        <p className="apx-login-foot">Hébergé en Europe · zéro rétention · accès cloisonné par affaire</p>
      </div>
    </div>
  );
}

/** Drop a folder, see the inventory; deduplicate, judge, search — all within the
 *  scopes the session holds. */
function Console({ identity, onLogout, onCockpit }: {
  identity: Identity; onLogout: () => void; onCockpit?: () => void;
}) {
  const [matter, setMatter] = useState("");
  const [scope, setScope] = useState(identity.scopes[0] ?? "");
  const [custodian, setCustodian] = useState("");
  const [custodianUnknown, setCustodianUnknown] = useState(false);
  const [caseTheory, setCaseTheory] = useState("");
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

  // The custodian is mandatory; "détenteur inconnu" is an explicit choice, never a blank.
  const effectiveCustodian = custodianUnknown ? "custodian-undeclared" : custodian.trim();
  const canSubmit = fileCount > 0 && !!matter.trim() && !!scope && !!effectiveCustodian;

  async function run(e: React.FormEvent) {
    e.preventDefault();
    const files = inputRef.current?.files;
    if (!files || files.length === 0 || !scope || !matter.trim() || !effectiveCustodian) return;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      setResult(await ingestUpload(files, matter, scope, effectiveCustodian, caseTheory));
      await refreshMatters();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="apx-shell">
      <header className="apx-appbar">
        <Wordmark tag="Triage" />
        <div className="apx-who">
          <span className="apx-badge">{identity.actor}</span>
          <span>{identity.scopes.join(" · ") || "aucun périmètre"}</span>
          {onCockpit && <button className="apx-ghost" onClick={onCockpit}>Cockpit</button>}
          <button className="apx-ghost" onClick={onLogout}>Déconnexion</button>
        </div>
      </header>

      <p className="apx-lede">
        Déposez un dossier. Vous verrez ce qui est entré, ce qui a échoué, ce qui a été écarté —
        rien perdu en silence. Vous ne voyez que les dossiers de votre périmètre.
      </p>

      <div className="apx-card apx-pad">
        <form onSubmit={run}
          style={{ display: "flex", flexDirection: "column", gap: "1rem", maxWidth: "34rem" }}>
          <label className="apx-field">
            <span>Dossier *</span>
            {/* @ts-expect-error non-standard but supported: pick a whole folder */}
            <input ref={inputRef} type="file" multiple webkitdirectory=""
              onChange={(e) => setFileCount(e.target.files?.length ?? 0)} aria-label="Dossier" />
            <span className="apx-hint">
              Sous-dossiers parcourus à toute profondeur.
              {fileCount ? ` ${fileCount} fichier${fileCount > 1 ? "s" : ""}.` : ""}
            </span>
          </label>

          <label className="apx-field">
            <span>Affaire *</span>
            <input aria-label="Affaire" placeholder="ex : Martin c/ Alpha Conseil" value={matter}
              onChange={(e) => setMatter(e.target.value)} />
          </label>

          <label className="apx-field">
            <span>Périmètre (accès) *</span>
            <select aria-label="Périmètre" value={scope} onChange={(e) => setScope(e.target.value)}>
              {identity.scopes.length === 0 && <option value="">aucun périmètre</option>}
              {identity.scopes.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
            <span className="apx-hint">Limité aux périmètres que vous détenez.</span>
          </label>

          <div className="apx-field">
            <span>Détenteur *</span>
            <input aria-label="Détenteur" placeholder="nom du détenteur" value={custodian}
              disabled={custodianUnknown} onChange={(e) => setCustodian(e.target.value)} />
            <label className="apx-hint"
              style={{ display: "flex", flexDirection: "row", alignItems: "center", gap: ".35rem" }}>
              <input type="checkbox" checked={custodianUnknown}
                onChange={(e) => setCustodianUnknown(e.target.checked)} />
              détenteur inconnu (jamais laissé vide)
            </label>
          </div>

          <label className="apx-field">
            <span>Thèse du dossier — facultatif</span>
            <textarea aria-label="Thèse du dossier" rows={2}
              placeholder="ce que vous cherchez à établir, dans vos mots — peut être ignoré"
              value={caseTheory} onChange={(e) => setCaseTheory(e.target.value)} />
            <span className="apx-hint">L'ignorer ne bloque rien.</span>
          </label>

          <button type="submit" disabled={busy || !canSubmit} style={{ alignSelf: "flex-start" }}>
            {busy ? "Import…" : "Lancer l'import"}
          </button>
        </form>
        {error && <p className="apx-error" role="alert">{error}</p>}
      </div>

      {result && <InventoryView title={`Résultat — ${result.matter}`} r={result} />}

      <CorpusSearch />

      {matters.length > 0 && (
        <section className="apx-panel">
          <h2>Mes dossiers</h2>
          <div className="apx-list">
            {matters.map((m) => <MatterRow key={m.matter} m={m} />)}
          </div>
        </section>
      )}

      <ChangePassword />
    </main>
  );
}

/** Self-service password change — confirms the current password server-side. */
function ChangePassword() {
  const [open, setOpen] = useState(false);
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setMsg(null);
    if (next !== confirm) {
      setErr("les deux nouveaux mots de passe diffèrent");
      return;
    }
    setBusy(true);
    try {
      await changePassword(current, next);
      setMsg("Mot de passe changé.");
      setCurrent("");
      setNext("");
      setConfirm("");
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : String(e2));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="apx-panel">
      <button className="apx-ghost apx-btn-sm" onClick={() => setOpen(!open)}>
        {open ? "▾" : "▸"} Changer mon mot de passe
      </button>
      {open && (
        <div className="apx-card apx-pad" style={{ marginTop: ".6rem", maxWidth: "26rem" }}>
          <form onSubmit={submit} style={{ display: "flex", flexDirection: "column", gap: ".7rem" }}>
            <label className="apx-field">
              <span>Mot de passe actuel</span>
              <input type="password" value={current} onChange={(e) => setCurrent(e.target.value)}
                autoComplete="current-password" />
            </label>
            <label className="apx-field">
              <span>Nouveau (min. 8 caractères)</span>
              <input type="password" value={next} onChange={(e) => setNext(e.target.value)}
                autoComplete="new-password" />
            </label>
            <label className="apx-field">
              <span>Confirmer</span>
              <input type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)}
                autoComplete="new-password" />
            </label>
            <button type="submit" disabled={busy || !current || next.length < 8}
              style={{ alignSelf: "flex-start" }}>
              {busy ? "…" : "Mettre à jour"}
            </button>
          </form>
          {err && <p className="apx-error" role="alert">{err}</p>}
          {msg && <p className="apx-seal apx-seal--ok" style={{ marginTop: ".6rem" }}>✓ {msg}</p>}
        </div>
      )}
    </section>
  );
}

/** The admin cockpit: manage the firm's users and their walls. Admin-gated server-side. */
function Cockpit({ onBack, onLogout }: { onBack: () => void; onLogout: () => void }) {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [email, setEmail] = useState("");
  const [pw, setPw] = useState("");
  const [name, setName] = useState("");
  const [scopes, setScopes] = useState("");
  const [isAdmin, setIsAdmin] = useState(false);
  const [busy, setBusy] = useState(false);

  async function refresh() {
    try {
      setUsers(await listUsers());
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }
  useEffect(() => {
    void refresh();
  }, []);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      await createUser(email, pw, name, scopes.split(",").map((s) => s.trim()).filter(Boolean), isAdmin);
      setEmail("");
      setPw("");
      setName("");
      setScopes("");
      setIsAdmin(false);
      await refresh();
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : String(e2));
    } finally {
      setBusy(false);
    }
  }

  async function grant(id: string) {
    const s = window.prompt("Périmètre à accorder ?");
    if (!s || !s.trim()) return;
    try {
      await grantScope(id, s.trim());
      await refresh();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }
  async function revoke(id: string, s: string) {
    try {
      await revokeScope(id, s);
      await refresh();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <main className="apx-shell">
      <header className="apx-appbar">
        <Wordmark tag="Cockpit" />
        <div className="apx-who">
          <button className="apx-ghost" onClick={onBack}>← Console</button>
          <button className="apx-ghost" onClick={onLogout}>Déconnexion</button>
        </div>
      </header>

      {err && <p className="apx-error" role="alert">{err}</p>}

      <section className="apx-panel">
        <h2>Nouvel utilisateur</h2>
        <div className="apx-card apx-pad">
          <form onSubmit={create} className="apx-controls">
            <input aria-label="Courriel" placeholder="Courriel" type="email" value={email}
              onChange={(e) => setEmail(e.target.value)} style={{ flex: "1 1 12rem" }} />
            <input aria-label="Nom" placeholder="Nom affiché" value={name}
              onChange={(e) => setName(e.target.value)} style={{ flex: "1 1 9rem" }} />
            <input aria-label="Mot de passe" placeholder="Mot de passe" type="password" value={pw}
              onChange={(e) => setPw(e.target.value)} style={{ flex: "1 1 9rem" }} />
            <input aria-label="Périmètres" placeholder="périmètres (a, b)" value={scopes}
              onChange={(e) => setScopes(e.target.value)} style={{ flex: "1 1 9rem" }} />
            <label className="apx-hint" style={{ display: "flex", alignItems: "center", gap: ".3rem" }}>
              <input type="checkbox" checked={isAdmin}
                onChange={(e) => setIsAdmin(e.target.checked)} /> admin
            </label>
            <button type="submit" disabled={busy || !email || !pw || !name}>Créer</button>
          </form>
        </div>
      </section>

      <section className="apx-panel">
        <h2>Utilisateurs</h2>
        <div className="apx-list">
          {users.map((u) => (
            <div key={u.id} className="apx-item" style={{ alignItems: "start" }}>
              <div>
                <div>{u.email}{u.is_admin && <span style={{ color: "var(--apx-gold)" }}> · admin</span>}</div>
                <div className="apx-hint">{u.display_name}</div>
              </div>
              <div style={{ textAlign: "right" }}>
                {u.scopes.map((s) => (
                  <span key={s} className="apx-chip apx-chip--scope"
                    style={{ marginLeft: ".3rem", marginBottom: ".25rem" }}>
                    {s}{" "}
                    <button className="apx-x" onClick={() => revoke(u.id, s)} aria-label={`Retirer ${s}`}>×</button>
                  </span>
                ))}
                <button className="apx-btn-sm apx-ghost" onClick={() => grant(u.id)}
                  style={{ marginLeft: ".3rem" }}>+ périmètre</button>
              </div>
            </div>
          ))}
        </div>
      </section>
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
    <section className="apx-panel">
      <h2>Recherche — dans votre périmètre</h2>
      <p className="apx-hint" style={{ margin: "0 0 .7rem", maxWidth: "62ch" }}>
        Un nom, une partie, une référence : toute pièce qui le contient, où qu'elle soit dans
        votre périmètre, quel que soit son tri. Déterministe et exhaustif — rien n'est caché.
      </p>
      <form onSubmit={runSearch} className="apx-controls">
        <input value={q} onChange={(e) => setQ(e.target.value)}
          placeholder="nom de pièce, partie, référence…" aria-label="Recherche"
          style={{ flex: "1 1 20rem" }} />
        <button type="submit" disabled={busy || !q.trim()}>{busy ? "Recherche…" : "Chercher"}</button>
      </form>
      {err && <p className="apx-error" role="alert">{err}</p>}
      {res && (
        <div style={{ marginTop: ".9rem" }}>
          <p className="apx-hint" style={{ margin: "0 0 .5rem" }}>
            <strong className="apx-num">{res.total}</strong> pièce{res.total > 1 ? "s" : ""} pour «&nbsp;{res.query}&nbsp;»
            {res.returned < res.total && <> · {res.returned} affichées</>}
          </p>
          {res.hits.length > 0 && (
            <div className="apx-list">
              {res.hits.map((h) => (
                <div key={`${h.matter}/${h.provenance}`} className="apx-item" style={{ gridTemplateColumns: "1fr" }}>
                  <div>
                    <div className="apx-hint">{h.matter} · <span className="apx-mono">{h.provenance}</span></div>
                    <div style={{ marginTop: ".15rem" }}>{h.snippet}</div>
                  </div>
                </div>
              ))}
            </div>
          )}
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
    <div>
      <div className="apx-item apx-click" onClick={toggle}>
        <div>
          <span aria-hidden className="apx-caret">{open ? "▾" : "▸"}</span>
          {m.matter}
        </div>
        <div className="apx-hint">
          {m.inventory.in_corpus} indexées · {m.inventory.failures} à revoir · tri &amp; journal
        </div>
      </div>
      {open && (
        <div className="apx-detail">
          {err && <p className="apx-error" role="alert" style={{ marginTop: 0 }}>{err}</p>}
          {triage && <TriageView t={triage} />}
          <Judging question={question} setQuestion={setQuestion} judging={judging}
            onJudge={judge} labels={labels} />
          {labels && labels.discarded > 0 && (
            <RecallPanel matter={m.matter} discarded={labels.discarded} />
          )}
          {trail && <Journal trail={trail} />}
        </div>
      )}
    </div>
  );
}

function TriageView({ t }: { t: Triage }) {
  return (
    <div className="apx-block">
      <p style={{ margin: "0 0 .35rem" }}>
        <strong className="apx-num">{t.submitted}</strong> pièces →{" "}
        <strong className="apx-num">{t.distinct}</strong> distinctes à examiner
        {t.duplicates > 0 && <> · <strong className="apx-num">{t.duplicates}</strong> doublon{t.duplicates > 1 ? "s" : ""} regroupé{t.duplicates > 1 ? "s" : ""}</>}
      </p>
      {t.groups.length > 0 && (
        <ul className="apx-hint apx-inline-list">
          {t.groups.map((g) => (
            <li key={g.representative}>
              <span className="apx-mono">{g.representative}</span>{" "}
              + {g.size - 1} copie{g.size - 1 > 1 ? "s" : ""}
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
    <div className="apx-block">
      <form onSubmit={onJudge} className="apx-controls" style={{ marginBottom: ".5rem" }}>
        <input value={question} onChange={(e) => setQuestion(e.target.value)}
          placeholder="critères de tri (ex : bail, résiliation)" aria-label="Critères de tri"
          style={{ flex: "1 1 16rem" }} />
        <button type="submit" className="apx-btn-sm" disabled={judging}>
          {judging ? "Jugement…" : "Juger"}
        </button>
      </form>
      {labels && labels.judged > 0 && (
        <>
          <p style={{ margin: "0 0 .4rem", display: "flex", gap: ".3rem", flexWrap: "wrap" }}>
            <span className="apx-chip apx-chip--kept apx-num">{labels.relevant} pertinentes</span>
            <span className="apx-chip apx-chip--review apx-num">{labels.uncertain} à juger</span>
            <span className="apx-chip apx-chip--discard apx-num">{labels.discarded} écartées</span>
          </p>
          <ul className="apx-hint apx-inline-list">
            {labels.pieces.map((p) => (
              <li key={p.provenance}>
                <span className="apx-mono">{p.provenance}</span>{" "}
                <LabelChip label={p.label} />{" "}
                <span style={{ color: "var(--apx-muted)" }}>{p.rationale}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

/** The recall guarantee, from the UI: sample the discard pile, mark any wrongly
 *  discarded, and get the provable bound ("at most X% discarded in error, at 95%"). */
function RecallPanel({ matter, discarded }: { matter: string; discarded: number }) {
  const [sample, setSample] = useState<RecallSample | null>(null);
  const [marks, setMarks] = useState<Record<string, boolean>>({});
  const [bound, setBound] = useState<RecallBound | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function draw() {
    setBusy(true);
    setErr(null);
    setBound(null);
    try {
      setSample(await recallSample(matter, Math.min(30, discarded)));
      setMarks({});
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function compute() {
    if (!sample) return;
    setBusy(true);
    setErr(null);
    try {
      const verdicts = sample.sample.map((s) => ({ piece_id: s.piece_id, relevant: !!marks[s.piece_id] }));
      setBound(await recallReview(matter, verdicts));
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="apx-block" style={{ borderTop: "1px dashed var(--apx-line)", paddingTop: ".7rem" }}>
      <button className="apx-btn-sm apx-ghost" onClick={draw} disabled={busy}>
        Vérifier le rappel ({discarded} écartées)
      </button>
      {err && <p className="apx-error" role="alert">{err}</p>}
      {sample && (
        <div style={{ marginTop: ".5rem" }}>
          <p className="apx-hint" style={{ margin: "0 0 .3rem" }}>
            Cochez les pièces écartées <strong>à tort</strong> (population {sample.population},
            échantillon {sample.sample.length}) :
          </p>
          {sample.sample.map((s) => (
            <label key={s.piece_id}
              style={{ display: "block", fontSize: ".85rem", marginBottom: ".2rem", cursor: "pointer" }}>
              <input type="checkbox" checked={!!marks[s.piece_id]}
                onChange={(e) => setMarks((m) => ({ ...m, [s.piece_id]: e.target.checked }))} />{" "}
              <span className="apx-mono">{s.provenance}</span>{" "}
              <span style={{ color: "var(--apx-muted)" }}>— {s.excerpt}</span>
            </label>
          ))}
          <button className="apx-btn-sm" onClick={compute} disabled={busy} style={{ marginTop: ".3rem" }}>
            {busy ? "Calcul…" : "Calculer la garantie"}
          </button>
        </div>
      )}
      {bound && (
        <p className="apx-seal apx-seal--ok" style={{ marginTop: ".5rem" }}>
          🛡 Relu {bound.sample_size}/{bound.population} · {bound.relevant_found} à tort → au plus{" "}
          <strong>{bound.count_upper}</strong> pièces ({(bound.prevalence_upper * 100).toFixed(1)}%)
          écartées à tort, à {Math.round(bound.confidence * 100)}%.
        </p>
      )}
    </div>
  );
}

function LabelChip({ label }: { label: string }) {
  const map: Record<string, [string, string]> = {
    relevant: ["apx-chip--kept", "pertinente"],
    uncertain: ["apx-chip--review", "à juger"],
    discard: ["apx-chip--discard", "écartée"],
  };
  const [cls, txt] = map[label] ?? ["", label];
  return <span className={`apx-chip ${cls}`}>{txt}</span>;
}

function Journal({ trail }: { trail: AuditTrail }) {
  return (
    <div className="apx-block">
      <p className={trail.verified ? "apx-seal apx-seal--ok" : "apx-seal apx-seal--bad"}>
        {trail.verified
          ? "🔒 Journal intègre — la chaîne se recalcule sans rupture."
          : "⚠ Journal altéré — la chaîne ne se recalcule pas."}
      </p>
      <ol className="apx-hint apx-inline-list">
        {trail.entries.map((e) => (
          <li key={e.seq}>
            <strong style={{ color: "var(--apx-ink-2)" }}>{e.action}</strong> — {e.detail}{" "}
            <span style={{ color: "var(--apx-muted)" }}>· {e.actor} · {e.timestamp.replace("T", " ").slice(0, 19)}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}

function InventoryView({ title, r }: { title: string; r: IngestResponse }) {
  const inv = r.inventory;
  return (
    <section className="apx-panel" aria-live="polite">
      <h2>{title}</h2>
      <div className="apx-card apx-equation">
        <div className="apx-eq-total">
          <div className="n">{inv.submitted}</div>
          <div className="l">pièces soumises</div>
        </div>
        <div className="apx-eq-rows">
          <div className="apx-eq-row">
            <div className="n" style={{ color: "var(--apx-kept)" }}>{inv.in_corpus}</div>
            <div className="c">indexées — dans le corpus</div>
          </div>
          <div className="apx-eq-row">
            <div className="n" style={{ color: "var(--apx-review)" }}>{inv.failures}</div>
            <div className="c">non traitées — à revoir</div>
          </div>
          <div className="apx-eq-row">
            <div className="n" style={{ color: "var(--apx-discard)" }}>{inv.exclusions}</div>
            <div className="c">écartées — bruit système</div>
          </div>
        </div>
      </div>
      <div className={inv.consistent ? "apx-verdict" : "apx-verdict apx-verdict--bad"}>
        {inv.consistent
          ? `Inventaire cohérent : ${inv.submitted} = ${inv.in_corpus} + ${inv.failures} + ${inv.exclusions}`
          : "⚠ Inventaire incohérent"}
        {r.persisted ? " · enregistré" : ""}
      </div>
      {r.failure_list.length > 0 && (
        <div className="apx-list" style={{ marginTop: "1rem" }}>
          {r.failure_list.map((f) => (
            <div key={f.path} className="apx-item">
              <span className="apx-mono">{f.path}</span>
              <span className="apx-chip apx-chip--review">{f.error_class}</span>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
