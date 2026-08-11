import { useEffect, useRef, useState } from "react";
import { Link } from "react-router";
import {
  ApiError, changePassword, createUser, exhaustiveExportUrl, grantScope, importStatus, ingestUpload,
  judgeMatter, listMatters, listUsers, login, logout, me, readAudit, readLabels, readTriage,
  abandonSamplingRun, completeSamplingRun, currentSamplingRun, recordSamplingVerdict,
  revokeScope, searchExhaustive, searchSuggestive, startSamplingRun, suggestiveExportUrl,
  type AdminUser, type AuditTrail, type ExhaustiveResult, type Identity, type ImportProgress,
  type ImportStarted, type Labels, type MatterSummary, type SamplingRun,
  type SuggestiveResult, type Triage,
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
  const importKey = `apx_import_${identity.tenant}`;
  const [job, setJob] = useState<ImportStarted | null>(() => {
    const jid = localStorage.getItem(importKey);   // survive a reload: rehydrate a live import
    return jid ? { job_id: jid, matter: "", state: "running" } : null;
  });
  const [progress, setProgress] = useState<ImportProgress | null>(null);
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

  // Poll the non-blocking import while it runs — a persistent, collapsed indicator (never a modal;
  // the app stays fully usable). Read from the ledger (AD-17); stops once the job is done.
  useEffect(() => {
    if (!job) {
      localStorage.removeItem(importKey);
      return;
    }
    localStorage.setItem(importKey, job.job_id);   // persist so the indicator survives a reload
    let live = true;
    const tick = async () => {
      try {
        const p = await importStatus(job.job_id);
        if (!live) return;
        setProgress(p);
        if (p.state !== "done") window.setTimeout(tick, 1000);
        else {
          localStorage.removeItem(importKey);
          void refreshMatters();
        }
      } catch {
        // the job is gone (finished + swept, or not visible) — drop the stale rehydrated indicator
        if (live) {
          setJob(null);
          localStorage.removeItem(importKey);
        }
      }
    };
    void tick();
    return () => {
      live = false;
    };
  }, [job, importKey]);

  // The custodian is mandatory; "détenteur inconnu" is an explicit choice, never a blank.
  const effectiveCustodian = custodianUnknown ? "custodian-undeclared" : custodian.trim();
  const canSubmit = fileCount > 0 && !!matter.trim() && !!scope && !!effectiveCustodian;

  async function run(e: React.FormEvent) {
    e.preventDefault();
    const files = inputRef.current?.files;
    if (!files || files.length === 0 || !scope || !matter.trim() || !effectiveCustodian) return;
    setBusy(true);
    setError(null);
    setJob(null);
    setProgress(null);
    try {
      setJob(await ingestUpload(files, matter, scope, effectiveCustodian, caseTheory));
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

          <label className="apx-field">
            <span>Détenteur *</span>
            <input aria-label="Détenteur" placeholder="nom du détenteur" value={custodian}
              disabled={custodianUnknown} onChange={(e) => setCustodian(e.target.value)} />
          </label>
          <label className="apx-hint"
            style={{ display: "flex", flexDirection: "row", alignItems: "center",
              gap: ".35rem", marginTop: "-.5rem" }}>
            <input type="checkbox" checked={custodianUnknown}
              onChange={(e) => setCustodianUnknown(e.target.checked)} />
            détenteur inconnu (jamais laissé vide)
          </label>

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

      {job && (
        <div className="apx-card apx-pad" style={{ marginTop: "1rem" }} aria-live="polite">
          <div style={{ display: "flex", alignItems: "center", gap: ".7rem", flexWrap: "wrap" }}>
            <span className="apx-num" style={{ fontWeight: 560 }}>
              Import — {progress?.processed ?? 0}
              {progress?.submitted != null ? ` / ${progress.submitted}` : ""}
              {progress?.provisional ? " · en cours d'inventaire" : ""}
            </span>
            <span style={{ flex: "1 1 8rem", height: 3, background: "var(--apx-line-2)",
              borderRadius: 999, overflow: "hidden" }}>
              <span style={{ display: "block", height: "100%", background:
                "linear-gradient(90deg, var(--apx-gold), var(--apx-gold-2))",
                width: progress?.submitted
                  ? `${Math.round((100 * progress.processed) / Math.max(1, progress.submitted))}%`
                  : "12%" }} />
            </span>
            <span className="apx-hint">
              {progress?.state === "done"
                ? `Terminé — ${progress.processed} pièce${progress.processed > 1 ? "s" : ""}` +
                  (progress.quarantined ? ` · ${progress.quarantined} en quarantaine` : "")
                : "vous pouvez continuer à travailler"}
            </span>
          </div>
        </div>
      )}

      <CorpusSearch scopes={identity.scopes} />

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

/** Story 3.4 — the two engines, each DECLARING its truth status, never combined in one list
 *  (FR-15). One field, an EXPLICIT mode: Suggestions (≈ suggestif, by topic — never a proof) or
 *  Preuve (= exhaustif, exact term — the complete set + its denominator, the defensible answer). */
function CorpusSearch({ scopes }: { scopes: string[] }) {
  const [q, setQ] = useState("");
  const [mode, setMode] = useState<"suggestive" | "exhaustive">("exhaustive");
  const [sug, setSug] = useState<SuggestiveResult | null>(null);
  const [exh, setExh] = useState<ExhaustiveResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [refused, setRefused] = useState(false);

  async function runSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!q.trim()) return;
    setBusy(true);
    setErr(null);
    setRefused(false);
    setSug(null);
    setExh(null);
    try {
      if (mode === "suggestive") setSug(await searchSuggestive(q));
      else setExh(await searchExhaustive(q));
    } catch (e2) {
      // the moving-population refusal is a 409 (an honest "wait"), branched on the STATUS — never a
      // regex on an English message, and the raw exception text is never shown to the lawyer.
      if (e2 instanceof ApiError && e2.status === 409) setRefused(true);
      else setErr(e2 instanceof Error ? e2.message : String(e2));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="apx-panel">
      <h2>Recherche — dans votre périmètre</h2>
      <p className="apx-hint" style={{ margin: "0 0 .5rem", maxWidth: "64ch" }}>
        Deux moteurs, deux vérités distinctes. <b>Suggestions</b> trouve les pièces les plus proches
        d'un sujet — jamais une preuve. <b>Preuve</b> renvoie l'ensemble complet d'un terme exact,
        avec son dénominateur — la seule réponse défendable devant un tribunal.
      </p>
      <p className="apx-hint" style={{ margin: "0 0 .7rem" }}>
        Recherché dans{" "}
        {scopes.length > 0
          ? scopes.map((s) => <span key={s} className="apx-chip apx-chip--scope">{s}</span>)
          : <span className="apx-chip apx-chip--scope">aucun périmètre</span>}
        {" "}— résultats et dénominateur calculés dans ce seul périmètre.
      </p>
      <form onSubmit={runSearch} className="apx-controls">
        <div className="apx-search-mode" role="group" aria-label="Mode de recherche">
          <button type="button" aria-pressed={mode === "suggestive"}
            onClick={() => setMode("suggestive")}>≈ Suggestions</button>
          <button type="button" aria-pressed={mode === "exhaustive"}
            onClick={() => setMode("exhaustive")}>= Preuve</button>
        </div>
        <input value={q} onChange={(e) => setQ(e.target.value)}
          placeholder={mode === "suggestive" ? "un sujet…" : "un terme exact…"}
          aria-label="Recherche" style={{ flex: "1 1 18rem" }} />
        <button type="submit" disabled={busy || !q.trim()}>{busy ? "Recherche…" : "Chercher"}</button>
      </form>
      {err && <p className="apx-error" role="alert">{err}</p>}
      {refused && (
        <div className="apx-refuse" role="status">
          <b>La recherche exhaustive attend un corpus stable.</b> Un import est en cours sur ce
          dossier — une preuve d'absence ne peut être faite sur une population qui bouge. Terminez
          l'import, puis relancez. (Le mode <b>Suggestions</b> reste disponible.)
        </div>
      )}
      {sug && <SuggestivePanel q={q} res={sug} />}
      {exh && <ExhaustivePanel q={q} res={exh} />}
    </section>
  );
}

/** A ranked, non-complete SUGGESTION set: the ≈ badge, the dashed-open frame, "les N plus proches"
 *  (never "N résultats"), a relative proximity meter — never a false-precise percentage. */
function SuggestivePanel({ q, res }: { q: string; res: SuggestiveResult }) {
  return (
    <div className="apx-rset apx-rset--sug" aria-label="Suggestions, non exhaustives">
      <div className="apx-rset-head">
        <span className="apx-ts apx-ts--sug"><span className="g">≈</span> Suggestif</span>
        <span className="apx-hint">classé par proximité · ne prouve pas l'absence</span>
        <span className="count">les <b>{res.results.length}</b> plus proches</span>
      </div>
      {res.results.length === 0 && (
        <div className="apx-hit"><div className="apx-hint">
          Aucune suggestion au-dessus du seuil de proximité. Ce n'est pas une preuve d'absence —
          utilisez le mode <b>Preuve</b>.
        </div></div>
      )}
      {res.results.map((r, i) => (
        <div key={r.chunk_id} className="apx-hit">
          <div className="name">
            <span className="apx-num" style={{ color: "var(--apx-ink-3)" }}>{i + 1}ᵉ</span>{" "}
            {r.piece_id}
            <Link className="apx-open" style={{ marginLeft: ".5rem" }}
              to={`/piece/${encodeURIComponent(r.piece_id)}?passage=${encodeURIComponent(q)}`}>
              ouvrir au passage →
            </Link>
          </div>
          <div className="meta">
            <span className="apx-prox" title="proximité relative">
              {[0, 1, 2, 3].map((p) => (
                <i key={p} className={p < _pips(i, res.results.length) ? "on" : ""} />
              ))}
            </span>
            <span className="apx-mono">chunk {r.chunk_id.slice(0, 8)}</span>
          </div>
        </div>
      ))}
      <div style={{ padding: ".55rem 1rem", fontSize: ".84rem" }}>
        <a href={suggestiveExportUrl(q)} target="_blank" rel="noreferrer">
          Exporter (liste non exhaustive)…
        </a>
      </div>
    </div>
  );
}

/** The EXHAUSTIVE set: the = badge, the solid-closed frame, the scoped denominator, the
 *  absence-statement seal (its four qualifications, in words), register-hits SEPARATE (AD-21). */
function ExhaustivePanel({ q, res }: { q: string; res: ExhaustiveResult }) {
  const d = res.denominator;
  // fail-closed: no scope → a 0/0 denominator. This is NOT a searched-and-empty absence — it is
  // "nothing was searched" (never a green proof of absence over an empty corpus). (Story 3.4 M1.)
  const nothingSearched = d.submitted_pieces === 0;
  const clean =
    d.open_register_entries === 0 && d.unknown_cardinality_entries === 0 && res.ocr_share === 0;
  const claim = res.results.length > 0
    ? `${res.results.length} pièce(s) contenant « ${q} » — ensemble complet`
    : `Aucune occurrence de « ${q} ».`;
  if (nothingSearched) {
    return (
      <div className="apx-rset apx-rset--exh" aria-label="Aucun périmètre, rien recherché">
        <div className="apx-rset-head">
          <span className="apx-ts apx-ts--exh"><span className="g">=</span> Exhaustif</span>
        </div>
        <div className="apx-absence apx-absence--qual">
          <span className="lead">Aucun périmètre — rien n'a été recherché.</span>
          Vous ne détenez aucun périmètre sur ce dossier ; aucune recherche n'a été exécutée. Ce
          n'est pas une preuve d'absence.
        </div>
      </div>
    );
  }
  return (
    <div className="apx-rset apx-rset--exh" aria-label="Recherche exhaustive, ensemble complet">
      <div className="apx-rset-head">
        <span className="apx-ts apx-ts--exh"><span className="g">=</span> Exhaustif</span>
        <span className="apx-hint">ensemble complet sur ce périmètre · une capture</span>
      </div>
      <div className="apx-equation" style={{ padding: "1.1rem 1.3rem .4rem" }}>
        <div className="apx-eq-total">
          <div className="n">{d.submitted_pieces}</div><div className="l">recherché</div>
        </div>
        <div className="apx-eq-rows">
          <div className="apx-eq-row">
            <div className="n">{d.in_corpus}</div><div className="c">indexé — texte recherchable</div>
          </div>
          <div className="apx-eq-row">
            <div className="n">{d.open_register_entries}</div>
            <div className="c">au registre — illisibles / non indexées</div>
          </div>
          {d.unknown_cardinality_entries > 0 && (
            <div className="apx-eq-row">
              <div className="n">{d.unknown_cardinality_entries}</div>
              <div className="c">au contenu inconnu (cardinalité inconnue)</div>
            </div>
          )}
        </div>
      </div>
      <div className={`apx-absence ${clean ? "apx-absence--ok" : "apx-absence--qual"}`}>
        <span className="lead">{claim}</span>
        Recherché dans tout l'indexé de ce périmètre ({d.in_corpus} sur {d.submitted_pieces}).
        Le registre liste {d.open_register_entries} pièce(s)
        {d.unknown_cardinality_entries > 0
          ? `, dont ${d.unknown_cardinality_entries} au contenu inconnu`
          : ""}
        {" "}; {Math.round(res.ocr_share * 100)} % du corpus recherché provient d'un OCR
        {res.below_quality_share > 0
          ? `, ${Math.round(res.below_quality_share * 100)} % sous le seuil de qualité`
          : ""}.
      </div>
      {res.register_hits.length > 0 && (
        <div className="apx-regblock">
          <div className="rh">
            ⚑ Correspondances dans le registre — pièces non indexées, hors de l'ensemble recherché
          </div>
          {res.register_hits.map((h) => (
            <div key={h.filename} className="apx-hit">
              <div className="apx-hint">{h.filename} · {h.error_class}</div>
            </div>
          ))}
        </div>
      )}
      {res.results.map((r) => (
        <div key={r.piece_id} className="apx-hit">
          <div className="name">
            {r.piece_id} <span className="apx-hint">· {r.matter}</span>
            <Link className="apx-open" style={{ marginLeft: ".5rem" }}
              to={`/piece/${encodeURIComponent(r.piece_id)}?passage=${encodeURIComponent(q)}`}>
              ouvrir au passage →
            </Link>
          </div>
          <div className="snip">{r.snippet}</div>
        </div>
      ))}
      <div style={{ padding: ".55rem 1rem", fontSize: ".84rem" }}>
        <a href={exhaustiveExportUrl(q)} target="_blank" rel="noreferrer">
          Exporter (preuve défendable)…
        </a>
      </div>
    </div>
  );
}

/** A RELATIVE proximity read (4 pips for the top, fewer as the rank falls) — an ordering, never a
 *  false-precise percentage (the voice bars an invented number where a range is the truth). */
function _pips(rank: number, total: number): number {
  return Math.max(1, 4 - Math.floor((rank / Math.max(1, total)) * 4));
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
          {m.inventory.in_corpus} indexées · {m.inventory.open_register_entries} à revoir · tri &amp; journal
        </div>
      </div>
      {/* Story 4.10 — the triage surface, reached from the matter once a ranking exists */}
      <div style={{ padding: "0 1rem .55rem", fontSize: ".84rem" }}>
        <Link to={`/matter/${encodeURIComponent(m.matter)}/triage`}>
          Ouvrir le classement…
        </Link>
      </div>
      {open && (
        <div className="apx-detail">
          {err && <p className="apx-error" role="alert" style={{ marginTop: 0 }}>{err}</p>}
          {triage && <TriageView t={triage} />}
          <Judging question={question} setQuestion={setQuestion} judging={judging}
            onJudge={judge} labels={labels} />
          {/* Deliberately NOT gated on labels.discarded. The population a run draws over is the
              DERIVED discarded set — the ranked order cut by la ligne and overridden by the
              épingles — never the Story-2.x label pile (decision A1). Gating on the pile would
              hide the audit exactly when the two disagree, which is the case the decision is
              about. The panel renders "aucun tirage" as its own state. */}
          <SamplingPanel matter={m.matter} />
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

/** The *sampling run* (Story 5.1, FR-22): draw a random sample of the DERIVED discarded set —
 *  the pièces below **la ligne**, not the Story-2.x label pile — judge each drawn family, and
 *  close the run to get the bound.
 *
 *  Two things are deliberately NOT decided here. The population is the server's
 *  `derive_triage_sets(order, line, pins).discarded` (decision A1), and validity is the server's
 *  `invalidated_in_flight` — derived from the run's freshness stamp. A client that computed either
 *  could carry on judging against a population that had moved, which is the exact failure FR-22
 *  exists to prevent. */
function SamplingPanel({ matter }: { matter: string }) {
  const [run, setRun] = useState<SamplingRun | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    currentSamplingRun(matter)
      .then((r) => { if (live) { setRun(r); setLoaded(true); } })
      .catch((e) => { if (live) { setErr(e instanceof Error ? e.message : String(e)); setLoaded(true); } });
    return () => { live = false; };
  }, [matter]);

  async function act<T>(fn: () => Promise<T>, apply: (v: T) => void) {
    setBusy(true);
    setErr(null);
    try {
      apply(await fn());
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
      // a refusal (409 invalidated / closed) is authoritative — re-read the server's verdict
      currentSamplingRun(matter).then(setRun).catch(() => undefined);
    } finally {
      setBusy(false);
    }
  }

  const draw = () => act(() => startSamplingRun(matter, { sample_size: 20 }), setRun);
  const judge = (familyId: string, relevant: boolean) =>
    act(() => recordSamplingVerdict(matter, run!.run_id, familyId, relevant), setRun);
  const close = () => act(() => completeSamplingRun(matter, run!.run_id), setRun);
  const abandon = () => act(() => abandonSamplingRun(matter, run!.run_id), setRun);

  // `status` is what a person did to the run; `state` adds the DERIVED invalidation. The buttons
  // gate on `status`, because an invalidated run must still be abandonable — the banner tells the
  // lawyer to abandon and redraw, so hiding the button would leave her with nowhere to go.
  const stillOpen = run !== null && run.status === "open";
  const invalidated = run !== null && run.invalidated_in_flight;

  return (
    <div className="apx-block" style={{ borderTop: "1px dashed var(--apx-line)", paddingTop: ".7rem" }}>
      <button className="apx-btn-sm apx-ghost" onClick={draw} disabled={busy}>
        {run === null ? "Tirer un échantillon des écartées" : "Nouveau tirage"}
      </button>
      {err && <p className="apx-error" role="alert">{err}</p>}
      {loaded && run === null && !err && (
        <p className="apx-hint" style={{ margin: ".4rem 0 0" }}>
          Aucun tirage. Le tirage porte sur les pièces <strong>sous la ligne</strong> ; il faut donc
          un classement et une ligne posée.
        </p>
      )}
      {run && (
        <div style={{ marginTop: ".5rem" }}>
          {/* Every surface names its ranking version (AD-23 — no unqualified reference). */}
          <p className="apx-hint" style={{ margin: "0 0 .3rem" }}>
            Classement v{run.version_no} · {run.sample_size} famille(s) tirée(s) sur{" "}
            {run.population_families} ({run.population_pieces} pièces écartées)
            {run.is_census && <strong> · recensement</strong>}
            {run.run_ordinal > 1 && <> · tirage n° {run.run_ordinal} sur cette population</>}
          </p>
          {invalidated && (
            <p className="apx-stale" role="alert">
              ⚠ {run.state_fr}. Les verdicts déjà saisis restent consultables ; il faut abandonner
              ce tirage et en refaire un.
            </p>
          )}
          {run.drawn.map((d) => (
            <div key={d.unit.family_id}
              style={{ display: "flex", gap: ".4rem", alignItems: "center", marginBottom: ".2rem", fontSize: ".85rem" }}>
              <span className="apx-mono" style={{ flex: 1 }}>{d.unit.proxy_piece_id.slice(0, 12)}</span>
              {d.unit.member_piece_ids.length > 1 && (
                <span className="apx-chip apx-chip--review">
                  {d.unit.member_piece_ids.length} quasi-doublons
                </span>
              )}
              {d.relevant === null ? (
                <>
                  <button className="apx-btn-sm apx-ghost"
                    disabled={busy || !stillOpen || invalidated}
                    onClick={() => judge(d.unit.family_id, false)}>Non pertinente</button>
                  <button className="apx-btn-sm" disabled={busy || !stillOpen || invalidated}
                    onClick={() => judge(d.unit.family_id, true)}>Pertinente</button>
                </>
              ) : (
                <span className={d.relevant ? "apx-chip apx-chip--kept" : "apx-chip"}>
                  {d.relevant ? "pertinente" : "non pertinente"}
                </span>
              )}
            </div>
          ))}
          {stillOpen && (
            <div style={{ display: "flex", gap: ".4rem", marginTop: ".4rem" }}>
              <button className="apx-btn-sm" onClick={close}
                disabled={busy || invalidated || run.verdicts_recorded < run.sample_size}>
                Clore le tirage
              </button>
              <button className="apx-btn-sm apx-ghost" onClick={abandon} disabled={busy}>
                Abandonner
              </button>
            </div>
          )}
          {/* The two registers (Story 5.2, OQ-4 input 2). A census states a FACT and never a
              percentage; a sample states a bound over FAMILIES with the pièce figure beside it as
              an explicit worst case. They are told apart by `estimate_kind`, not by whether a
              number happens to be zero — a 39-of-40 draw can bound at zero and is still a sample. */}
          {run.estimate_kind === "census" && run.census_fr && (
            <p className="apx-seal apx-seal--ok" style={{ marginTop: ".5rem" }}>🛡 {run.census_fr}</p>
          )}
          {run.estimate_kind === "bound" && (
            <p className="apx-seal apx-seal--ok" style={{ marginTop: ".5rem" }}>
              🛡 {run.sample_size}/{run.population_families} familles relues ·{" "}
              {run.relevant_found} pertinente(s) → au plus <strong>{run.count_upper}</strong>{" "}
              familles ({((run.prevalence_upper ?? 0) * 100).toFixed(1)}%) à{" "}
              {Math.round(run.confidence * 100)}%
              {run.count_upper_pieces !== null
                ? <>, soit au plus <strong>{run.count_upper_pieces}</strong> pièces au pire.</>
                : <>. Le pire cas en pièces n’est pas calculable pour ce tirage.</>}
            </p>
          )}
          {/* FR-22: a later draw over the same population is presented ALONGSIDE the earlier ones,
              never merged with them — and the sentence travels alone, so the fact travels with it. */}
          {run.repeated_draw_fr && (
            <p className="apx-hint" style={{ marginTop: ".3rem" }}>{run.repeated_draw_fr}</p>
          )}
          {run.status === "abandoned" && (
            <p className="apx-hint" style={{ marginTop: ".5rem" }}>{run.state_fr}</p>
          )}
        </div>
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
