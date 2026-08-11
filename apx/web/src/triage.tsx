/**
 * The triage surface (Story 4.10, FR-20) — the north-star screen.
 *
 * Four zones, top to bottom, reading from *the whole* down to *the single pièce*: the header naming
 * the **ranking version** (AD-23), the denominator equation under its verdict seal, the honesty
 * banner, and the table.
 *
 * The one act performed here is the **label edit**. Everything else is a faithful rendering of a
 * derived view, and the surface offers no control that could contradict the substrate:
 *
 *  - the *côté* chip is not interactive and announces itself as a derived view (AD-39);
 *  - the confidence cell is read-only text with a `dérivée` marker — never an input (FR-42) — and a
 *    pièce with no derived confidence says so rather than showing a zero (AD-19);
 *  - the unscored tail is its own zone, never folded into the discarded set (AD-19/AD-36);
 *  - the line is a cut BETWEEN rows, named by the last retained pièce, and it speaks (FR-17);
 *  - a row NEVER moves on an edit, and an edit never re-ranks anything (FR-20).
 *
 * A commit is **confirmed-then-applied**, a deliberate strengthening of the contract's
 * "optimistic-then-confirmed": the cell shows a value only once the server has accepted it, so the
 * table never displays as committed something that is not. The user-visible outcome the contract
 * asks for is the same — the cell reverts on refusal and the reason is stated (FR-20 extends to
 * failure) — reached by never having moved rather than by moving back.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router";
import {
  ApiError,
  type Bound,
  type ChangeLogEntry,
  type TriageRow,
  type TriageTable,
  UNLABELLED,
  type WorklistLine,
  readBound,
  readMatterChangeLog,
  readTriageTable,
  readWorklist,
  setPieceLabel,
} from "./api";

const SIDE_WORDS: Record<string, string> = {
  retained: "Retenue",
  discarded: "Écartée",
  unscored: "Non scorée",
  unsplit: "Non départagée",
};

/** The lawyer's reading of a derived number — a band, never a false-precise percentage, and never
 *  the model's self-report (FR-42). `null` means the cascade derived nothing (AD-19). */
function band(confidence: number | null): string {
  if (confidence === null) return "";
  if (confidence >= 0.66) return "élevée";
  if (confidence >= 0.33) return "moyenne";
  return "faible";
}

function when(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString("fr-FR");
}

function labelWord(value: string): string {
  return value === UNLABELLED ? "Sans étiquette" : value;
}

export function TriageRoute() {
  const { matter = "" } = useParams();
  const [table, setTable] = useState<TriageTable | null>(null);
  const [log, setLog] = useState<ChangeLogEntry[] | null>(null);
  // Same rule as the change log, for the same reason: `null` = not read, `[]` = read and empty.
  // A worklist that could not be read must never render as "rien à faire" (FR-58's surface is an
  // audit surface too).
  const [worklist, setWorklist] = useState<WorklistLine[] | null>(null);
  // `undefined` = not read; `null` = read, and no bound has been recorded — a state of its own,
  // never a bound of zero.
  const [bound, setBound] = useState<Bound | null | undefined>(undefined);
  const [error, setError] = useState<string | null>(null);
  const [absent, setAbsent] = useState(false);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      // The change log is read beside the table, and its FAILURE is kept distinct from its being
      // empty: `null` means "not read", `[]` means "read, and there is nothing". Collapsing the two
      // would make the panel assert an absence it never verified — the one thing this product must
      // never do (it is the "honest 'not in the corpus'" rule, applied to the audit surface).
      const [t, l, w, b] = await Promise.all([
        readTriageTable(matter),
        readMatterChangeLog(matter).then(
          (entries) => entries as ChangeLogEntry[] | null,
          () => null),
        readWorklist(matter).then((lines) => lines as WorklistLine[] | null, () => null),
        // a 404 here means "no bound recorded" (its own state); any other failure stays unread
        readBound(matter).then(
          (value) => value as Bound | null | undefined,
          (e) => (e instanceof ApiError && e.status === 404 ? null : undefined)),
      ]);
      setTable(t);
      setLog(l);
      setWorklist(w);
      setBound(b);
      setAbsent(false);
      setError(null);
    } catch (e) {
      // out of scope, absent, or not yet ranked are the SAME 404 (FR-14) — the surface renders its
      // own honest state and never an empty table pretending to be a result.
      if (e instanceof ApiError && e.status === 404) setAbsent(true);
      else setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [matter]);

  useEffect(() => {
    void load();
  }, [load]);

  const onCommitted = useCallback((entries: ChangeLogEntry[], row: TriageRow) => {
    if (entries.length === 0) return;   // a write always returns its entries; guard rather than
                                        // dereference an empty list and blank the cell
    // the row keeps its place: only its own cell and its own log change (FR-20)
    setTable((current) => {
      if (!current) return current;
      const last = entries[entries.length - 1];
      return {
        ...current,
        rows: current.rows.map((r) =>
          r.piece_id === row.piece_id
            ? { ...r, label: last.label, label_source: last.source, label_seq: last.seq,
                in_current_taxonomy: true }
            : r),
      };
    });
    // if the log was never read, leave it unread — one entry is not the log
    setLog((current) => (current === null ? null : [entries[entries.length - 1], ...current]));
  }, []);

  return (
    <main className="apx-shell apx-triage" style={{ paddingBottom: "3rem" }}>
      <p style={{ margin: 0 }}>
        <Link to="/">← Dossiers</Link>
      </p>

      {loading && <p className="apx-hint">Chargement du classement…</p>}
      {error && <p className="apx-error" role="alert">{error}</p>}
      {absent && !loading && (
        <div className="apx-block">
          <h1 style={{ marginBottom: ".2rem" }}>{matter}</h1>
          <p className="apx-hint">
            Aucun classement pour ce dossier — ou il est hors de votre périmètre. Le classement est
            un acte explicite&nbsp;: rien n'est classé automatiquement.
          </p>
        </div>
      )}

      {table && (
        <>
          <Header table={table} />
          <StalenessBanner lines={worklist} version={table.version_no} />
          <Denominator table={table} />
          <p className="apx-honesty">
            Ordre proposé par l'outil, révisable — ce n'est pas une preuve. Rien n'est
            supprimé&nbsp;: une pièce écartée reste retrouvable par la recherche exhaustive.
          </p>
          <Table table={table} onCommitted={onCommitted} />
          <BoundPanel bound={bound} matter={table.matter} />
          <ChangeLogPanel entries={log} />
        </>
      )}
    </main>
  );
}

function Header({ table }: { table: TriageTable }) {
  const theory = table.case_theory_version_id;
  return (
    <header className="apx-block">
      <h1 style={{ margin: "0 0 .2rem" }}>{table.matter}</h1>
      <p className="apx-hint" style={{ margin: 0 }}>
        {/* AD-23 — every surface names its version; an unqualified reference is not sayable here */}
        Classement v{table.version_no} · {when(table.created_at)} ·{" "}
        {theory ? <>théorie du cas {theory}</> : <>signaux intrinsèques nommés</>}
      </p>
    </header>
  );
}

/** The permanent-denominator equation: the sets PARTITION the matter, and nothing has left the
 *  corpus (FR-16). Before the line is drawn there is no cut, so the ranked rows are counted as
 *  *non départagées* rather than being called discarded. */
function Denominator({ table }: { table: TriageTable }) {
  const split: [number, string][] = table.line.placed
    ? [
        [table.retained_count, "retenues"],
        [table.discarded_count, "écartées du jeu retenu — retrouvables par la recherche exhaustive"],
        [table.unscored_count, "non scorées — la cascade n'a pas pu les départager"],
      ]
    : [
        [table.unsplit_count, "classées, en attente de la ligne"],
        [table.unscored_count, "non scorées — la cascade n'a pas pu les départager"],
      ];
  // FR-58: pièces arrivées APRÈS ce classement. They are in NEITHER set, because they are in no
  // set — the third state FR-16 forbids anyone to invent, stated instead of imputed. The line is
  // shown only when there are any: a permanent "0 non classées" would be noise.
  const rows: [number, string][] = table.unranked_count > 0
    ? [...split, [table.unranked_count,
        "arrivées après ce classement — dans aucun des deux jeux tant qu'il n'est pas refait"]]
    : split;
  return (
    <section className="apx-card apx-equation" aria-label="Le dénominateur du dossier">
      <div className="apx-eq-total">
        <div className="n">{table.corpus_count}</div>
        <div className="l">pièces au dossier</div>
      </div>
      <div>
        <div className="apx-eq-rows">
          {rows.map(([n, caption]) => (
            <div className="apx-eq-row" key={caption}>
              <div className="n">{n}</div>
              <div className="c">{caption}</div>
            </div>
          ))}
        </div>
        <p className="apx-verdict">Rien n'a quitté le corpus.</p>
      </div>
    </section>
  );
}

function Table({ table, onCommitted }: {
  table: TriageTable; onCommitted: (e: ChangeLogEntry[], row: TriageRow) => void;
}) {
  const ranked = useMemo(() => table.rows.filter((r) => r.rank !== null), [table.rows]);
  const unscored = useMemo(() => table.rows.filter((r) => r.rank === null), [table.rows]);
  const cutAfter = table.line.placed ? table.line.last_retained_piece_id : null;

  return (
    <section className="apx-triage-scroll" aria-label="Le classement">
      <table className="apx-triage-table">
        <thead>
          <tr>
            <th scope="col" className="apx-rank-cell">Rang</th>
            <th scope="col">Pièce</th>
            <th scope="col">Confiance</th>
            <th scope="col">Étiquette</th>
            <th scope="col">Côté</th>
          </tr>
        </thead>
        <tbody>
          {table.line.placed && (
            <Zone label="Retenues" count={table.retained_count} />
          )}
          {ranked.map((row) => (
            <RowGroup
              key={row.piece_id}
              row={row}
              table={table}
              onCommitted={onCommitted}
              lineAfter={row.piece_id === cutAfter}
              discardedZoneAfter={row.piece_id === cutAfter ? table.discarded_count : null}
            />
          ))}
          {unscored.length > 0 && (
            <>
              {/* its OWN set — never folded into the discarded one (AD-19/AD-36) */}
              <Zone
                label="Non scorées — la cascade n'a pas pu les départager"
                count={unscored.length}
              />
              {unscored.map((row) => (
                <RowGroup key={row.piece_id} row={row} table={table} onCommitted={onCommitted} />
              ))}
            </>
          )}
        </tbody>
      </table>
    </section>
  );
}

function Zone({ label, count }: { label: string; count: number }) {
  return (
    <tr className="apx-zone">
      <td colSpan={5}>
        <span className="c">{count}</span> {label}
      </td>
    </tr>
  );
}

function RowGroup({ row, table, onCommitted, lineAfter = false, discardedZoneAfter = null }: {
  row: TriageRow; table: TriageTable;
  onCommitted: (e: ChangeLogEntry[], row: TriageRow) => void;
  lineAfter?: boolean; discardedZoneAfter?: number | null;
}) {
  return (
    <>
      <Row row={row} table={table} onCommitted={onCommitted} />
      {lineAfter && <TheLine table={table} />}
      {discardedZoneAfter !== null && (
        <Zone
          label="Écartées du jeu retenu — retrouvables par la recherche exhaustive"
          count={discardedZoneAfter}
        />
      )}
    </>
  );
}

/** **The line** — a cut BETWEEN two rows, drawn once, that states the tool's commitment in words
 *  and names its basis. Never drawn on a row; never a bare integer (FR-17). Read-only here: moving
 *  it is Story 4.9's surface. */
function TheLine({ table }: { table: TriageTable }) {
  const rank = table.line.last_retained_rank;
  // The line is named by the IDENTITY of the last retained pièce, not by a position: the contract
  // bars "Ligne à la position 180" and writes the identity as « Pièce n°142 "Contrat de cession" ».
  // So the sentence carries the pièce's NAME beside its number — the number alone would be the bare
  // integer the contract forbids, and an import that adds pièces must not appear to move the line.
  const last = table.rows.find((r) => r.piece_id === table.line.last_retained_piece_id);
  return (
    <tr className="apx-the-line" role="separator" aria-orientation="horizontal"
      aria-label={
        `La ligne — dernière pièce retenue : ${last?.name ?? ""} (rang ${rank ?? "?"})`}>
      <td colSpan={5}>
        <div className="rule" />
        <div className="say">
          <span className="s">
            À mon sens, tout ce qui précède — jusqu'à la pièce n°{rank ?? "?"}
            {last ? <> «&nbsp;{last.name}&nbsp;»</> : null}.
          </span>
          <span className="e">Fondé sur {table.line.basis}</span>
        </div>
      </td>
    </tr>
  );
}

function Row({ row, table, onCommitted }: {
  row: TriageRow; table: TriageTable;
  onCommitted: (e: ChangeLogEntry[], row: TriageRow) => void;
}) {
  const [entry, setEntry] = useState<ChangeLogEntry | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const live = useRef<HTMLSpanElement>(null);

  async function commit(next: string) {
    if (next === row.label) return;
    const previous = row.label;
    setBusy(true);
    setFailure(null);
    try {
      // `?? 0` is load-bearing, not a default: a never-labelled row reads back `label_seq: null`,
      // and the server treats a null `expected_seq` as "no opinion" and skips the conditional
      // commit entirely. Sending null would therefore DISARM the concurrency guard for exactly the
      // first edit of every row — the state every row starts in — and a second writer would
      // silently overwrite the first with no 409 and no message. Zero is this codebase's way of
      // saying "I observed no entries", which is precisely what a null seq means.
      const written = await setPieceLabel(table.matter, row.piece_id, next, row.label_seq ?? 0);
      setEntry(written.entries[written.entries.length - 1]);
      onCommitted(written.entries, row);
    } catch (e) {
      // The cell reverts and the reason is stated — never a silent loss (FR-20 extends to failure).
      // The revert needs no work: the <select> is CONTROLLED by `row.label`, which only a confirmed
      // write changes, so re-rendering puts the committed value back. And nothing is appended to
      // the change log: a refused edit produced no entry, and a log that showed one would be
      // lying about an act that never happened.
      setFailure(
        e instanceof ApiError && e.status === 409
          ? `Cette cellule a été modifiée entre-temps — elle reste sur « ${labelWord(previous)} ». `
            + "Rechargez pour voir la valeur retenue."
          : e instanceof Error ? e.message : String(e));
      setEntry(null);
    } finally {
      setBusy(false);
    }
  }

  const options = useMemo(() => {
    const base = [UNLABELLED, ...table.taxonomy];
    // a value the taxonomy no longer holds is SHOWN, never silently remapped (FR-40)
    return row.in_current_taxonomy || base.includes(row.label) ? base : [...base, row.label];
  }, [table.taxonomy, row.in_current_taxonomy, row.label]);

  return (
    <tr>
      <td className="apx-rank-cell">{row.rank ?? "—"}</td>
      <td className="apx-piece-cell">
        <Link className="n" to={`/piece/${encodeURIComponent(row.piece_id)}`}>{row.name}</Link>
        <span className="id">{row.piece_id}</span>
      </td>
      <td className="apx-confidence-cell">
        {row.confidence_derived ? (
          <>
            <span className="b">{band(row.confidence)}</span>
            <span className="d">dérivée</span>
          </>
        ) : (
          <span className="none">non dérivée</span>
        )}
      </td>
      <td className="apx-label-cell">
        <select
          value={row.label}
          disabled={busy}
          aria-label={`Étiquette de ${row.name}`}
          onChange={(e) => void commit(e.target.value)}
        >
          {options.map((value) => (
            <option key={value} value={value}>{labelWord(value)}</option>
          ))}
        </select>
        {!row.in_current_taxonomy && (
          <span className="out">Valeur hors de la taxonomie actuelle — conservée telle quelle.</span>
        )}
        <span ref={live} aria-live="polite">
          {entry && (
            <span className="apx-change-log-entry">
              <span className="from">{labelWord(entry.previous)}</span>
              {" → "}
              <span className="to">{labelWord(entry.label)}</span>
              {" · "}{entry.set_by}{" · "}{when(entry.at)}
            </span>
          )}
          {failure && <span className="apx-error" role="alert">{failure}</span>}
        </span>
      </td>
      <td>
        {/* a DERIVED view chip: not a control, and its accessible name says so (AD-39) */}
        <span
          className={`apx-side-badge apx-side-badge--${row.side}`}
          aria-label={`${SIDE_WORDS[row.side] ?? row.side} — vue dérivée de la ligne`}
        >
          {row.pinned && <span className="apx-pin-marker" aria-hidden>❖</span>}
          {SIDE_WORDS[row.side] ?? row.side}
        </span>
      </td>
    </tr>
  );
}

/** The matter-level change log — append-only, newest first. Nothing here edits or erases an entry;
 *  a reversal is a new entry of its own (AD-7/FR-20). */
/** The staleness banner (Story 4.13, FR-58). It names **which input moved** — never a bare
 *  "périmé" — and it OFFERS the recomputation; it never starts one. Staleness is resolved only by
 *  an explicit user act producing a NEW artefact, so there is deliberately no automatic refresh
 *  here, and no button on this screen that recomputes behind the user's back. */
function StalenessBanner(
  { lines, version }: { lines: WorklistLine[] | null; version: number | null },
) {
  if (lines === null) {
    // The same rule as the change log: a failed read is not a verified absence. Saying nothing
    // here would read as "tout est à jour", which is the exact false reassurance FR-58 exists
    // to prevent.
    return (
      <p className="apx-error" role="alert">
        La fraîcheur du classement n'a pas pu être vérifiée — cet écran ne peut pas dire s'il est à
        jour. Rechargez pour réessayer.
      </p>
    );
  }
  if (lines.length === 0) return null;   // read, and nothing is stale
  return (
    <section className="apx-stale" role="status" aria-label="Fraîcheur des artefacts dérivés">
      {lines.map((line) => (
        <p key={`${line.kind}-${line.artefact_id}`} style={{ margin: ".25rem 0" }}>
          {/* AD-23 — the banner names the version it speaks of; the worklist carries only the
              artefacts IN FORCE, so "Le classement" is the one on screen and not a superseded one */}
          <strong>{STALE_SUBJECT[line.kind] ?? line.kind}</strong>
          {version !== null && line.kind !== "bound" && line.kind !== "sampling_run" && (
            <> v{version}</>
          )} — périmé depuis&nbsp;:{" "}
          {line.changed_fr.join(", ")}. <span className="apx-hint">{line.offer_fr}</span>
        </p>
      ))}
      <p className="apx-hint" style={{ margin: ".4rem 0 0" }}>
        Rien n'est recalculé automatiquement, et le temps qui passe ne remet rien à jour.
      </p>
    </section>
  );
}

const STALE_SUBJECT: Record<string, string> = {
  ranking: "Le classement",
  line: "La ligne",
  bound: "La borne de confiance",
  sampling_run: "Le tirage sur les écartées",
};

/** The confidence bound (FR-58/FR-23). A stale bound is visually distinct, cannot be exported as
 *  current, and the string the copy button puts on the clipboard is the SERVER's — so the number
 *  cannot travel without its staleness. */
function BoundPanel({ bound, matter }: { bound: Bound | null | undefined; matter: string }) {
  const [copied, setCopied] = useState(false);
  if (bound === undefined) return null;   // not read — the banner above already says what it can
  if (bound === null) {
    return (
      <section className="apx-card" aria-label="Borne de confiance">
        <strong>Borne de confiance</strong>
        <p className="apx-hint" style={{ margin: ".3rem 0 0" }}>
          Aucune borne n'a encore été établie pour ce dossier.
        </p>
      </section>
    );
  }
  const stale = !bound.exportable_as_current;
  const copy = () => {
    // the SERVER's sentence, never one composed here: every path through it carries the staleness
    void navigator.clipboard?.writeText(bound.copy_text).then(
      () => setCopied(true), () => setCopied(false));
  };
  return (
    <section
      className={`apx-card apx-bound${stale ? " apx-bound-stale" : ""}`}
      aria-label="Borne de confiance"
    >
      <strong>Borne de confiance</strong>
      {stale && (
        <span className="apx-chip apx-chip-review" style={{ marginLeft: ".5rem" }}>
          {bound.status_fr}
        </span>
      )}
      <p style={{ margin: ".4rem 0 .2rem" }}>{bound.copy_text}</p>
      {/* The unit comes from the SERVER (`unit_fr`) — a sampling run counts near-duplicate
          FAMILIES, and hard-coding "pièces écartées" here was the Story-5.1 defect repeated one
          file over. A census is not an "échantillon": it read everything. */}
      <p className="apx-hint" style={{ margin: 0 }}>
        {bound.kind === "census"
          ? <>Recensement : {bound.population} {bound.unit_fr}, toutes examinées</>
          : <>Échantillon de {bound.sample_size} sur {bound.population} {bound.unit_fr}</>}
        {bound.piece_count !== null && <> ({bound.piece_count} pièces)</>} ·{" "}
        {bound.relevant_found} pertinente(s) trouvée(s)
      </p>
      <p style={{ margin: ".5rem 0 0" }}>
        <button type="button" onClick={copy}>Copier la phrase</button>{" "}
        {stale ? (
          <span className="apx-hint">
            Export impossible tant que la borne est périmée — ré-échantillonnez pour en produire une
            nouvelle.
          </span>
        ) : (
          <a href={`/api/matters/${encodeURIComponent(matter)}/bound/export`}>Exporter</a>
        )}
        {copied && <span className="apx-hint"> · copiée</span>}
      </p>
    </section>
  );
}

function ChangeLogPanel({ entries }: { entries: ChangeLogEntry[] | null }) {
  return (
    <section className="apx-change-log" aria-label="Journal des modifications">
      <strong>Journal des modifications</strong>
      <span className="apx-hint"> — en ajout seul, du plus récent au plus ancien</span>
      {entries === null ? (
        // NOT an absence: the read failed, so the surface says it does not know rather than
        // asserting there is nothing — an unverified absence is the one claim this product bars.
        <p className="apx-error" role="alert" style={{ margin: ".4rem 0 0" }}>
          Le journal n'a pas pu être lu — cet écran ne peut pas dire s'il y a eu des modifications.
          Rechargez pour réessayer.
        </p>
      ) : entries.length === 0 ? (
        <p className="apx-hint" style={{ margin: ".4rem 0 0" }}>
          Aucune modification pour l'instant.
        </p>
      ) : (
        <ol>
          {entries.map((e) => (
            <li key={`${e.piece_id}-${e.seq}`}>
              <span className="apx-mono" style={{ fontSize: ".72rem" }}>{e.piece_id.slice(0, 12)}…</span>
              <span className="from">{labelWord(e.previous)}</span>
              {" → "}
              <span className="to">{labelWord(e.label)}</span>
              <span>· {e.set_by}</span>
              <span className="when">· {when(e.at)}</span>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
