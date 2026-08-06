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
  type ChangeLogEntry,
  type TriageRow,
  type TriageTable,
  UNLABELLED,
  readMatterChangeLog,
  readTriageTable,
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
      const [t, l] = await Promise.all([
        readTriageTable(matter),
        readMatterChangeLog(matter).then(
          (entries) => entries as ChangeLogEntry[] | null,
          () => null),
      ]);
      setTable(t);
      setLog(l);
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
          <Denominator table={table} />
          <p className="apx-honesty">
            Ordre proposé par l'outil, révisable — ce n'est pas une preuve. Rien n'est
            supprimé&nbsp;: une pièce écartée reste retrouvable par la recherche exhaustive.
          </p>
          <Table table={table} onCommitted={onCommitted} />
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
  const rows: [number, string][] = table.line.placed
    ? [
        [table.retained_count, "retenues"],
        [table.discarded_count, "écartées du jeu retenu — retrouvables par la recherche exhaustive"],
        [table.unscored_count, "non scorées — la cascade n'a pas pu les départager"],
      ]
    : [
        [table.unsplit_count, "classées, en attente de la ligne"],
        [table.unscored_count, "non scorées — la cascade n'a pas pu les départager"],
      ];
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
