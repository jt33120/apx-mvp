# APX MVP

AI platform for law firms (France / Luxembourg), built by APX Advisory.
Rebuild — planned and executed with the **BMAD Method v6**.

## Start here

Read [`docs/context/00-README.md`](docs/context/00-README.md). It indexes the full
context pack: clients and their stated requirements, a retrospective of the previous
build with salvage verdicts, the design inventory, the competitive landscape, and the
verbatim source documents.

> **⚠️ Read the context pack with this correction in hand.** `docs/context/01-…` and the
> sources under `docs/context/00-sources/` (notably `state-snapshot.json`) describe the
> prospect relationships as live. **They are stale. No client engagement has been won,
> and no client corpus exists.** The product is built for the *use case*, not for a named
> firm; requirements gathered in discovery are kept on their merits, not their provenance.
> Established 20 July 2026 — see `_bmad-output/planning-artifacts/briefs/brief-apx-mvp-2026-07-20/addendum.md` §1.

**Current state of planning.** The first increment is **mass-document triage** (reversed
against Syllogisme on 20 July 2026, on commercial and competitive evidence). The
authoritative documents, in dependency order:
`_bmad-output/brainstorming/…/brainstorm-intent.md` → `…/briefs/brief-apx-mvp-2026-07-20/`
→ `…/prds/prd-apx-mvp-2026-07-20/` (60 FRs). Reviews and the revision log sit beside the PRD.

The previous implementation lives at `../apx-platform/` — **reference only, never an
edit target**. Ditto `../APX/`, `../legal-rag-core/`, `../maquettes/`,
`../../Resources/`, `../../Agents/`.

## Non-negotiables (blocking)

EU-only · zero-retention · no fine-tuning on client data · strict RAG with citations or
an honest "not in the corpus" · human-in-the-loop everywhere (no auto-delete, auto-send,
auto-sign) · triage is reversible labelling, never deletion · recall over precision in
triage · full audit trail · RBAC by matter (Chinese walls).

Rationale and provenance: `docs/context/00-README.md`.

## Language

Agents converse in **French**. Documents, code, comments and commits are **English**.
French legal terms of art (*ordonnance 145 CPC*, *conclusions*, *veille*) stay in French.

## BMAD

Installed under `_bmad/`, skills exposed in `.claude/skills/` (86 skills across bmm, cis,
wds, tea, bmb, core). Outputs land in `_bmad-output/` (planning + implementation
artifacts) and `design-artifacts/` (WDS).

Lost? Invoke the `bmad-help` skill and ask it what to do next.
