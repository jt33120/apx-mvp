# APX MVP — Context Pack

Everything the BMAD agents need to plan this product **without asking you to re-explain
the last six months**. Read this file first; it tells you what else to load and when.

This is a **rebuild**. A prior implementation exists at `../../../apx-platform/` and is
kept as reference only — see `02-existing-build-retrospective.md` for what to salvage.

## Files

| File | What it is | Load it when |
|---|---|---|
| `01-client-and-commercial-context.md` | Who the clients are (RMT, Philippe & Partners), what each stakeholder demands, commercial model, locked decisions, non-negotiables | Analysis, product brief, PRD, trigger mapping |
| `02-existing-build-retrospective.md` | Module-by-module inventory of the previous build: what works, what is stubbed, ranked salvage verdicts, traps | Architecture, solutioning, any "can we reuse X" question |
| `03-design-and-ux-inventory.md` | Existing mockups + shipped UI: screens, real colour/type values, interaction patterns, client feedback, UX gaps | UX design, WDS phases, front-end stories |
| `00-sources/` | Verbatim originals. Nothing here is summarised — go here to check a claim | Whenever a summary above is ambiguous or you need exact wording |

## `00-sources/` contents

- `legacy-PLAN-2026-05-31.md` — the previous build spec. Its **§5 Guardrails** and
  **§7 Definition of Done** are still valid product thinking; its build sequence is not.
- `adr/` — 4 architecture decision records (shared-core architecture, LLM/hosting stack,
  billing model, multi-agent bridge).
- `state-snapshot.json` — project state as of the last agent session: clients, contacts,
  pipeline, next actions.
- `distilled/` — dated notes on commercial blockers and demo status.
- `legacy-syllogisme-pipeline.md` — spec of the 5-block Syllogisme pipeline, the most
  developed piece of the old build.
- `legacy-apx-platform-CLAUDE.md` — the old project's operating notes, incl. the
  production secrets checklist.
- `mockups/` — 4 standalone HTML mockups shown to clients.

## The three products (unchanged scope)

| Product | Corpus | Core task | Client |
|---|---|---|---|
| **Documentation** | Ephemeral per-matter dump (1700+ docs, mostly `.msg`) | Triage → chat over the kept set | RMT |
| **Syllogisme** | Persistent firm-wide knowledge | Cited cross-matter Q&A → firm-style drafting | P&P UC01 |
| **Veille IA** | Public sources (Légifrance, EUR-Lex, Legilux) | Crawl → filter by practice area → digest | P&P UC02 |

## Non-negotiables — treat as blocking constraints, not preferences

- **EU-only · zero-retention · no fine-tuning on client data.**
- **Strict RAG**: every claim cited, or an honest "not in the corpus". A fabricated
  citation gets a lawyer sanctioned — this is the failure mode that kills the product.
- **Human-in-the-loop everywhere**: no auto-delete, no auto-send, no auto-sign.
- **Triage never destroys.** "Rebut" is a label and a recommendation, always reversible.
- **Recall over precision in triage**: losing a relevant document ≫ keeping junk.
- **Auditability is the trust mechanism** — random-sampling audit, every classification
  traceable. This is a named client requirement, not a nice-to-have.
- **RBAC by matter/team** — conflicts and Chinese walls are a legal obligation.

## Conventions

- Agents converse in **French**; all documents are written in **English**.
- French legal terms of art stay in French (*ordonnance 145 CPC*, *conclusions*,
  *veille*) — glossed in parentheses on first use, never translated away.
