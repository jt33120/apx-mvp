---
date: 2026-04-28
type: architecture
status: décidé · à valider avec Maxime en hebdo
impact: structurel · concerne RMT et P&P
---

# ADR · Noyau technique commun pour RMT et P&P

## Contexte

APX a deux deals actifs en parallèle : RMT (triage de masse documentaire pour 145 CPC / pénal / commercial) et Philippe & Partners Luxembourg (LexCore IA + Veille). Côté commercial, Maxime peut chiffrer en deux forfaits. Côté technique, la question est : un codebase ou deux ?

L'analyse des deux briefs (deck P&P + synthèse RMT du 27/04) montre une convergence à ~80% sur la plomberie :
- Ingestion multi-format hétérogène
- Indexation vectorielle avec provenance
- LLM zero-retention EU
- Audit log immuable
- Édition de tables/documents avec préservation de l'historique
- RBAC, conformité RGPD/AI Act

Ce qui change entre les deux clients :
- Connecteurs (CSIP + Outlook Graph pour P&P ; .msg + DVD/USB pour RMT)
- Vocabulaire métier (cotes, rebut, syllogisme pour RMT ; templates bilingues, style avocat pour P&P)
- Emphase UI (chat + drafting pour P&P ; table-first pour RMT)
- Modèle de données (cote/date/thématique pour RMT, document/clause/template pour P&P)

## Options envisagées

**A — Deux codebases séparés**
- Pour : indépendance totale, pas de risque de couplage parasite, vélocité par projet.
- Contre : duplication massive, double maintenance, double dette technique. Toute amélioration archi (nouveau format ingéré, nouveau LLM, nouveau modèle d'audit) doit être faite deux fois.

**B — Un codebase mutualisé sans modularité**
- Pour : zéro duplication.
- Contre : intrication des spécificités client, risque de "feature flag spaghetti", couplage commercial dangereux (un bug sur un client peut affecter l'autre).

**C — Noyau commun + composition par client (option retenue)**
- Pour : mutualisation des fondations, isolation des spécificités, scalable à un Nème client. Architecture "library + apps" classique et éprouvée.
- Contre : exige une discipline de séparation. Le noyau ne doit jamais "savoir" qui est le client.

## Décision

**Option C.** Trois repos :

```
legal-rag-core/        ← bibliothèque, semver, testée, sans logique client
apx-rmt/              ← compose le core, ajoute connecteurs + vocab + UI RMT
apx-pp/               ← compose le core, ajoute connecteurs + vocab + UI P&P
```

Le core gère :
1. Ingestion (parsers .msg, .pdf OCR, .docx, .xlsx, .pptx, images)
2. Chunking sémantique adaptatif
3. Indexation Qdrant + embeddings BGE-M3 (option Mistral-embed)
4. Pipeline RAG avec provenance et top-k re-ranking
5. Couche LLM (adaptateurs Mistral/Claude/OpenAI/Vertex en API zero-retention, ou Mistral 7B air-gapped)
6. Audit log append-only chiffré
7. Génération `.docx`/`.pdf` avec respect templates
8. Schéma RBAC + scopes par avocat/équipe/cabinet

Chaque app client définit :
- Connecteurs spécifiques (Microsoft Graph pour P&P, scan dossier + parser USB pour RMT)
- Schéma métier (Pièce/Cote/Thématique pour RMT, Document/Clause/Template pour P&P)
- Vocabulaire des prompts (français juridique, expressions cabinet)
- UI sur-mesure (table-first vs chat-first)
- Configuration commerciale (utilisateurs, scopes, hébergement)

## Conséquences

**Positives**
- Toute amélioration sur le core (perf, conformité, nouveau LLM) bénéficie aux deux clients sans double dev.
- Le 3e client deviendra une 3e app, pas un 3e codebase.
- Les tests sont concentrés sur le core, ce qui maximise leur ROI.
- Argumentaire commercial : "nous capitalisons sur 5 cabinets déjà déployés" devient vrai au sens technique.

**Négatives**
- Discipline d'API stable requise sur le core. Toute breaking change implique synchroniser les deux apps.
- Versioning sémantique du core obligatoire. Les apps épinglent une version, mise à jour explicite.
- Le coût de mise en place initial est légèrement supérieur (S1 du core seul, pas direct sur le client).

## Mitigation des risques

- Le core démarre vraiment léger. On ne fait pas d'over-engineering en S1 ; on extrait dans le core ce qui est dupliqué entre les deux apps après les avoir construites.
- Tests d'intégration sur des fixtures représentatives des deux scénarios.
- CI/CD : tag du core déclenche un PR automatique de bump de version dans les apps.

## Validation

- [x] Arbitrage Julian — fait le 28/04
- [ ] Confirmation Maxime — au prochain hebdo
- [ ] Première PR du core — semaine S1
