# `eval/` — the corpus and gold-set evaluation substrate (Story 2.12, FR-54)

This tree is the APX **evaluation substrate**: the labelled gold corpus, the mechanical degradation
pipeline, the gold-set relevance mapping, and the harness that runs recall against the gold set in
CI. Its reason to exist is one sentence from the v1 retrospective: **v1 had a gold set and never
once ran it.** AD-34 makes that impossible here — no ranking or triage code merges before recall
executes against this gold set.

## Not a fixture (FR-33)

`eval/` is a top-level tree, **outside `apx/`** (so it is not product runtime) and **outside
`tests/`** (so the corpus is not a test fixture). The corpus is a *configured data source*, ingested
through the **real** ingestion path exactly as client material is. `eval` imports `apx`; `apx` never
imports `eval` — the product does not depend on the evaluation corpus.

## `corpus/` — the lifted gold corpus

Lifted as-is from the APX v1 build (the retrospective's rank-1 salvage): a **fully synthetic**,
anonymised, deterministic (seed 42) ~6-month dump for a 2-lawyer French employment-law firm — 139
items across 105 emails, 21 documents, 13 notes — with **two-axis ground truth** per item in
`corpus/manifest.json`:

- `gold_dossier` — routing: which of the 8 matters the item belongs to (or `null`).
- `gold_pertinence` — a 5-value relevance grade: `pertinent` · `référence` · `edge` · `borderline` · `rebut`.

Because it is self-authored and synthetic, it carries **no third-party licence** and **no real
client data** (EU-only, zero-retention). The recorded licence-verification step (FR-54) is
[`provenance.json`](provenance.json), which pins the specific distribution by a `distribution_sha256`
digest (see `eval.corpus_source.corpus_digest`).

## The gold mapping is the hard part

The v1 labels are **mapped**, not used verbatim: [`gold_mapping.py`](gold_mapping.py) translates the
5-value pertinence + routing onto **this product's notion of relevance** — *the line* (retained vs
discarded) and the uncertain band — as a written, versioned, reviewable table. *The line* is Epic 4,
so this mapping is the contract the future ranker's recall is measured against.

## The recall number is deferred (SM-2)

Recall at *the line* needs a ranker (Epic 3/4), which does not exist yet. So 2.12 ships the harness
and the **merge gate** (`apx/checks/gold_gate.py`); the recall **figure** is produced the moment
ranking lands. Per PRD §7 SM-2, **no absolute recall target is set** — inventing one would be the
unaudited number the PRD forbids; the metric that matters is that it *runs at all*.
