import { useEffect, useState } from "react";

import {
  exportMatterRecord,
  previewValidationBatch,
  readDrawer,
  readValidations,
  validateBatch,
  validatePiece,
  withdrawValidation,
  type ChainReading,
  type Drawer,
  type ExportTier,
  type ValidationEntry,
  type ValidationLog,
  type ValidationSplit,
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

        <ValidationAct matter={matter} pieceId={pieceId} drawer={drawer} />
      </section>
    </aside>
  );
}

/* ── Story 5.8: the VALIDATION ACT (FR-45) ──────────────────────────────────────────────────────
   The control's own text IS the assertion the record will attribute to her, in full. A button
   labelled « Valider » lets her assert it without reading it, and the entry it writes would then
   be a claim she never made in the words that were recorded.

   Beneath it, the CONSEQUENCE, before the click: whether this will be inscribed as *lue* or as
   *acceptée depuis la liste*. Neither state blocks the act. What is refused is doing it without
   knowing which the record will say. */
export function ValidationAct({ matter, pieceId, drawer }: {
  matter: string; pieceId: string; drawer: Drawer;
}) {
  const [log, setLog] = useState<ValidationLog | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    readValidations(matter, pieceId)
      .then((l) => { if (live) setLog(l); })
      .catch(() => { /* the band renders without the log rather than not at all */ });
    return () => { live = false; };
  }, [matter, pieceId]);

  const current = inForce(log?.entries ?? []);

  async function act(run: () => Promise<ValidationLog>) {
    setBusy(true); setErr(null);
    try { setLog(await run()); }
    catch (e) { setErr(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }

  if (current) {
    return (
      <div className="apx-act">
        <ValidationBadge entry={current} currentVersion={log?.current_ranking_version_id ?? null} />
        <div className="apx-act-row" style={{ marginTop: ".5rem" }}>
          <button
            type="button" className="apx-ghost apx-btn-sm" disabled={busy}
            onClick={() => act(() => withdrawValidation(matter, pieceId))}
          >
            Retirer ma validation
          </button>{" "}
          <span className="apx-hint">
            la validation et son retrait restent tous deux inscrits
          </span>
        </div>
        {err ? <p className="apx-seal apx-seal--bad">{err}</p> : null}
      </div>
    );
  }

  const read = drawer.validation_provenance === "read";
  return (
    <div className="apx-act">
      <button
        type="button"
        className="apx-validate"
        disabled={busy}
        aria-describedby="apx-validation-provenance"
        onClick={() => act(() => validatePiece(matter, pieceId))}
      >
        <span className="apx-validate-sentence">{drawer.validation_assertion_fr}</span>
        {drawer.ranking_version_no !== null ? (
          <span className="apx-validate-version">
            Appréciation du classement n° {drawer.ranking_version_no}.
          </span>
        ) : null}
      </button>
      {/* aria-describedby, never a separate region: the consequence is announced WITH the control,
          not as something a keyboard user could pass by */}
      <p
        id="apx-validation-provenance"
        className={`apx-provenance ${read ? "apx-provenance--read" : "apx-provenance--list"}`}
      >
        {drawer.validation_provenance_fr}
      </p>
      {err ? <p className="apx-seal apx-seal--bad">{err}</p> : null}
    </div>
  );
}

/* The in-force validation is the max-seq entry, and only when it is a validation — a withdrawal
   lifts it exactly as a pin removal lifts a pin. Never a stored membership (AD-39).

   Max-seq, never "the last element": the server orders by pièce then seq, and a renderer that
   trusted arrival order would show a withdrawn validation as in force the day that ordering
   changes. */
function inForce(entries: ValidationEntry[]): ValidationEntry | null {
  if (entries.length === 0) return null;
  const latest = entries.reduce((a, b) => (b.seq > a.seq ? b : a));
  return latest.action === "validated" ? latest : null;
}

/* FOUR facts, never one tick. Dropping *lue / depuis la liste* would launder acceptances into
   readings on the last surface before the court; dropping the version would keep a green check
   over values a re-rank has replaced. */
export function ValidationBadge({ entry, currentVersion }: {
  entry: ValidationEntry; currentVersion: string | null;
}) {
  const read = entry.provenance === "read";
  const tone = entry.stale || !read ? "apx-badge--review" : "apx-badge--kept";
  return (
    <div>
      <span className={`apx-badge ${tone}`}>
        ✓ Validée · {entry.actor} · {entry.at.slice(0, 16).replace("T", " ")} ·{" "}
        <b>{entry.provenance_fr}</b>
        {entry.batch_id ? <> · lot de {entry.batch_size}</> : null}
      </span>
      {entry.stale ? (
        <p className="apx-hint" style={{ margin: ".3rem 0 0" }}>
          Validée sur le classement <code>{entry.ranking_version_id.slice(0, 8)}</code> — le
          classement actuel est <code>{(currentVersion ?? "").slice(0, 8)}</code>. Rien n'est
          effacé et rien n'est invalidé : l'acceptation portait sur une appréciation qui n'est plus
          celle affichée.
        </p>
      ) : null}
    </div>
  );
}

/* ── Story 5.8: the BULK confirmation (FR-45) ───────────────────────────────────────────────────
   Permitted, and never undetectable. A 1 700-row grid grows a select-all because every grid does;
   forbidding it produces a workaround rather than compliance. The confirmation states the count
   AND THE SPLIT — a dialog naming only the total is friction that obtains consent while telling
   her nothing she did not already know. */
export function BulkValidationConfirm({ matter, pieceIds, onDone, onCancel }: {
  matter: string; pieceIds: string[]; onDone: (log: ValidationLog) => void; onCancel: () => void;
}) {
  const [split, setSplit] = useState<ValidationSplit | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    previewValidationBatch(matter, pieceIds)
      .then((s) => { if (live) setSplit(s); })
      .catch((e) => { if (live) setErr(e instanceof Error ? e.message : String(e)); });
    return () => { live = false; };
  }, [matter, pieceIds]);

  async function confirm() {
    if (!split) return;
    setBusy(true); setErr(null);
    try {
      // the count the lawyer was SHOWN, not one re-derived at the click: the server refuses a
      // mismatch, which is what catches a selection that changed under the dialog
      onDone(await validateBatch(matter, pieceIds, split.total));
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally { setBusy(false); }
  }

  return (
    <div className="apx-scrim" role="dialog" aria-modal="true" aria-labelledby="apx-bulk-h">
      <div className="apx-confirm">
        <span className="apx-eyebrow">Confirmation</span>
        <h3 id="apx-bulk-h" style={{ margin: ".1rem 0 .6rem" }}>
          Valider {pieceIds.length} pièces
        </h3>
        <p style={{ margin: ".4rem 0" }}>
          Vous êtes sur le point de déclarer avoir lu <b>{pieceIds.length} pièces</b> et d'accepter
          l'appréciation de l'outil pour chacune.
        </p>
        {split ? (
          <p className="apx-provenance apx-provenance--list">{split.sentence_fr}</p>
        ) : (
          <p className="apx-hint">Calcul de ce que le journal inscrira…</p>
        )}
        <p className="apx-hint" style={{ margin: ".5rem 0 0" }}>
          Chaque pièce recevra sa propre entrée au journal, portant la taille du lot et son
          identifiant. Un lecteur du dossier exporté pourra toujours distinguer les lectures des
          acceptations.
        </p>
        {err ? <p className="apx-seal apx-seal--bad">{err}</p> : null}
        <div className="apx-confirm-actions">
          {/* the cancel path is autoFocus, never the confirming verb: the keyboard's default
              gesture must not be to accept 180 documents */}
          <button type="button" className="apx-ghost" autoFocus onClick={onCancel}>Annuler</button>{" "}
          <button type="button" disabled={busy || !split} onClick={confirm}>
            Valider les {split?.total ?? pieceIds.length} pièces
          </button>
        </div>
      </div>
    </div>
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
  const [readings, setReadings] = useState<ChainReading[]>([]);
  const [err, setErr] = useState<string | null>(null);

  async function produce(tier: ExportTier) {
    // Everything the LAST document said is cleared first. A refused production used to leave the
    // previous document's continuity verdict on screen beside the error, where it reads as this
    // one's — a verdict about bytes nobody produced (review, confirmed).
    setErr(null);
    setDone(null);
    setReadings([]);
    try {
      const doc = await exportMatterRecord(matter, tier);
      const v = doc.validation_summary;
      // Story 5.8: §7 is a real section now, so the summary names the two registers SEPARATELY.
      // Pooling them into one "validated" total is exactly what makes 12 readings and 168
      // acceptances indistinguishable, which is the whole thing FR-45 exists to prevent.
      const validations = v
        ? ` ${v.read} lecture(s) et ${v.from_the_list} acceptation(s) depuis la liste`
          + `${v.in_bulk > 0 ? ` (dont ${v.in_bulk} en ${v.batches} lot(s))` : ""}.`
        : "";
      // Only sections whose ACT does not exist yet — an empty list is the honest state now, and
      // saying "sections non construites : " with nothing after it would invent a doubt.
      const pending = doc.pending.length > 0
        ? ` Sections non encore construites : ${doc.pending.map((p) => p.heading_fr).join(" · ")}.`
        : "";
      setDone(
        `Document produit (${tier === "full" ? "dossier complet" : "chiffres seuls"}) — `
        + `${doc.overrides_total} dérogation(s) au journal.${validations}${pending}`);
      // Story 5.9 (FR-53) — the continuity check ran ON THE DOCUMENT, and its result belongs on
      // the document's face rather than in a payload nobody reads. Every chain is shown, sound or
      // not: showing only the failures would make a page with nothing on it mean two things.
      setReadings(doc.continuity ?? []);
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
      {readings.length > 0 ? (
        <div className="apx-continuity">
          <span className="apx-eyebrow">Contrôle de continuité, effectué sur ce document</span>
          <ul>
            {readings.map((r) => (
              <li key={r.chain_scope} className={r.sound ? "apx-cont--ok" : "apx-cont--open"}>
                <strong>{r.label_fr}</strong> — {r.sentence_fr}
              </li>
            ))}
          </ul>
          <p className="apx-hint" style={{ margin: ".35rem 0 0" }}>
            Ce contrôle est refait à partir des seules données de l'export : un lecteur qui reçoit
            ce document obtient le même résultat sans APX.
          </p>
        </div>
      ) : null}
      {err ? <p className="apx-seal apx-seal--bad">{err}</p> : null}
    </section>
  );
}
