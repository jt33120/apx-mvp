import { useEffect, useState } from "react";

import {
  exportMatterRecord,
  readDrawer,
  type Drawer,
  type ExportTier,
} from "./api";

/* ── Story 5.7: the AUDIT DRAWER (FR-26) ────────────────────────────────────────────────────────
   Four bands, in a FIXED order, because the order IS the argument: what the tool concluded, what
   that rests on, what will be written if she acts, what she can do. A panel, never a route —
   asking "pourquoi ?" must not cost the lawyer her place in the ranked order. */
export function AuditDrawer({ matter, pieceId, onClose }: {
  matter: string; pieceId: string; onClose: () => void;
}) {
  const [drawer, setDrawer] = useState<Drawer | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    let live = true;
    readDrawer(matter, pieceId)
      .then((d) => { if (live) setDrawer(d); })
      .catch((e) => { if (live) setErr(String(e.message ?? e)); });
    return () => { live = false; };
  }, [matter, pieceId]);

  if (err) return <aside className="apx-drawer"><p className="apx-seal apx-seal--bad">{err}</p></aside>;
  if (!drawer) return <aside className="apx-drawer"><p className="apx-hint">Chargement…</p></aside>;

  return (
    <aside className="apx-drawer" aria-label="Journal de la pièce">
      <div className="apx-drawer-head">
        <div>
          <h3 style={{ margin: 0 }}>Journal de la pièce</h3>
          <div className="apx-mono-id">{drawer.piece_id}</div>
        </div>
        <button type="button" className="apx-ghost apx-btn-sm" onClick={onClose}>Fermer</button>
      </div>

      {/* BAND 1 — la décision. The confidence is DERIVED (4.4) and says so: a bare figure is
          indistinguishable from a self-report, which is the reading FR-42 exists to prevent. */}
      <section className="apx-band">
        <span className="apx-eyebrow">La décision</span>
        {drawer.sentence ? (
          <>
            <p style={{ margin: ".35rem 0 .4rem" }}>{drawer.sentence}</p>
            {drawer.confidence !== null ? (
              <p className="apx-hint" style={{ margin: 0 }}>
                <span className="apx-tag">dérivée</span>{" "}
                {drawer.confidence_signals.length > 0
                  ? <>Dérivée de : {drawer.confidence_signals.join(", ")}.</>
                  : <>Dérivée d'observables nommés.</>}
                {drawer.ranking_version_no !== null
                  ? ` Version de classement n° ${drawer.ranking_version_no}.`
                  : ""}
              </p>
            ) : null}
            {drawer.rejected ? (
              <p className="apx-seal apx-seal--review" style={{ margin: ".5rem 0 0" }}>
                L'appréciation de l'outil a été écartée — elle reste lisible.
              </p>
            ) : null}
          </>
        ) : (
          /* stated as itself: "nothing was recorded" and "the justification is empty" are
             different facts, and only one of them can be true */
          <p className="apx-hint" style={{ margin: ".35rem 0 0" }}>
            L'outil n'a enregistré aucune justification pour cette pièce.
          </p>
        )}
      </section>

      {/* BAND 2 — ce sur quoi elle repose. Every extract is re-verified AT SHOW TIME (FR-11); an
          unresolved one shows its CAUSE and never its stored text. */}
      <section className="apx-band">
        <span className="apx-eyebrow">Ce sur quoi elle repose</span>
        {drawer.extracts.length === 0 ? (
          <p className="apx-hint" style={{ margin: ".35rem 0 0" }}>
            Aucun extrait nommé — l'appréciation repose sur des signaux intrinsèques, pas sur une
            citation. Ce n'est pas une justification « non vérifiée ».
          </p>
        ) : (
          drawer.extracts.map((e) => (
            <div key={e.chunk_id} className={e.verified ? "apx-quote" : "apx-quote apx-quote--bad"}>
              {e.verified ? (
                <p className="apx-hint" style={{ margin: 0 }}>
                  <span className="chip chip--kept">Vérifié</span> Recontrôlé dans la pièce à
                  l'instant de l'affichage.
                </p>
              ) : (
                <p style={{ margin: 0, color: "var(--apx-review)" }}>
                  <strong>Cet extrait ne se résout plus.</strong> {e.cause_fr}
                </p>
              )}
              <div className="apx-mono-id">{e.chunk_id}</div>
            </div>
          ))
        )}
        {drawer.is_unverified ? (
          <p className="apx-hint" style={{ margin: ".5rem 0 0" }}>
            {drawer.unresolved_extracts} extrait(s) n'ont pas pu être recontrôlés — cette
            justification est affichée <strong>non vérifiée</strong>, jamais comme ordinaire.
          </p>
        ) : null}
      </section>

      {/* BAND 3 + 4 — ce qui sera inscrit, et ce que vous pouvez faire. Each action carries the ROW
          it would append and names its OWN reversal. */}
      <section className="apx-band">
        <span className="apx-eyebrow">Ce que vous pouvez faire</span>
        {drawer.actions.map((a) => (
          <div key={a.action} className="apx-act">
            <b>{a.action_fr}</b>
            <span className="apx-hint">Pour revenir en arrière : {a.reversal_fr}.</span>
            <div className="apx-proposed">
              <span className="apx-eyebrow" style={{ color: "var(--apx-review)" }}>
                Sera inscrit au journal
              </span>
              <div className="apx-hint">
                {a.proposed.action_fr} · {a.proposed.actor} · {a.proposed.chain_label_fr} ·{" "}
                <em>à l'instant où vous validerez</em>
                {a.proposed.reason_required ? (
                  <>
                    {" · "}
                    <span className="apx-tag" title={a.proposed.override_ground_fr ?? ""}>
                      dérogation
                    </span>{" "}
                    motif obligatoire
                  </>
                ) : null}
              </div>
            </div>
          </div>
        ))}
        {drawer.pending_actions.map((p) => (
          <div key={p.label_fr} className="apx-act apx-act--disabled">
            <b>{p.label_fr}</b>
            <span className="apx-hint">{p.disabled_reason_fr}</span>
          </div>
        ))}
      </section>
    </aside>
  );
}

/* ── Story 5.7: the export TIER FORK (FR-26 §11) ────────────────────────────────────────────────
   A fork reached BEFORE anything is produced, not a switch beside a download button. The default
   is described by what it CANNOT carry; the full tier by what it WILL, itemised, and it takes a
   second deliberate confirmation — because it is the one act in the product that moves client
   content out of the firm on purpose. */
export function ExportFork({ matter, scope }: { matter: string; scope?: string }) {
  const [confirming, setConfirming] = useState(false);
  const [done, setDone] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function produce(tier: ExportTier) {
    setErr(null);
    try {
      const doc = await exportMatterRecord(matter, tier);
      const pending = doc.pending.map((p) => p.heading_fr).join(" · ");
      setDone(
        `Document produit (${tier === "full" ? "dossier complet" : "chiffres seuls"}) — `
        + `${doc.overrides_total} dérogation(s) au journal. Sections non encore construites : `
        + `${pending}.`);
      setConfirming(false);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <section className="apx-block">
      <h3 style={{ margin: "0 0 .2rem" }}>Exporter le journal du dossier</h3>
      <p className="apx-hint" style={{ margin: 0 }}>
        {scope
          ? <>Affaire « {matter} » · mur <strong>{scope}</strong>. Ce document ne contiendra rien
            d'autre que ce périmètre, et le dira sur sa première page.</>
          : <>Ce document dira sur sa première page le périmètre sous lequel il a été produit.</>}
      </p>

      <div className="apx-fork">
        <div className="apx-tier">
          <span className="apx-eyebrow">Par défaut</span>
          <h4 style={{ margin: ".1rem 0 .1rem" }}>Chiffres seuls</h4>
          <p className="apx-hint" style={{ margin: 0 }}>
            Suffit à refaire chaque chiffre de ce document.
          </p>
          <ul>
            <li>Comptes, versions, verdicts, positions, bornes</li>
            <li><strong>Aucun extrait</strong></li>
            <li><strong>Aucun motif rédigé</strong></li>
            <li><strong>Aucun nom de fichier</strong></li>
            <li><strong>Aucun contenu client</strong></li>
          </ul>
          <button type="button" style={{ marginTop: ".8rem" }} onClick={() => produce("numbers-only")}>
            Produire l'export
          </button>
        </div>

        <div className="apx-tier apx-tier--full">
          <span className="apx-eyebrow" style={{ color: "var(--apx-review)" }}>
            Sort du contenu client
          </span>
          <h4 style={{ margin: ".1rem 0 .1rem" }}>Dossier complet</h4>
          <p className="apx-hint" style={{ margin: 0 }}>Tout ce qui précède, <strong>plus</strong> :</p>
          <ul>
            <li>les extraits retenus</li>
            <li>les motifs de dérogation <strong>mot pour mot</strong></li>
            <li>les justifications</li>
            <li>les noms et chemins des fichiers du registre</li>
          </ul>
          {confirming ? (
            <div style={{ marginTop: ".8rem" }}>
              <p className="apx-hint" style={{ margin: "0 0 .45rem" }}>
                Ce fichier contiendra du contenu client. Sa production est inscrite au journal.
              </p>
              <button type="button" onClick={() => produce("full")}>
                Produire l'export complet
              </button>{" "}
              <button type="button" className="apx-ghost apx-btn-sm" onClick={() => setConfirming(false)}>
                Annuler
              </button>
            </div>
          ) : (
            <button
              type="button"
              className="apx-ghost"
              style={{ marginTop: ".8rem", borderColor: "var(--apx-review)", color: "var(--apx-review)" }}
              onClick={() => setConfirming(true)}
            >
              Choisir le dossier complet…
            </button>
          )}
        </div>
      </div>

      <p className="apx-hint" style={{ marginTop: ".7rem" }}>
        Dans les deux cas, produire cet export est <strong>un acte inscrit au journal</strong> : le
        niveau, votre nom, l'affaire, le périmètre et l'instant.
      </p>
      {done ? <p className="apx-seal apx-seal--ok">{done}</p> : null}
      {err ? <p className="apx-seal apx-seal--bad">{err}</p> : null}
    </section>
  );
}
