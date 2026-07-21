# Bloc Syllogisme — pipeline (spec technique v1.0)

Mise en œuvre de la spécification *Syllogisme AI — Bloc Syllogisme Juridique* :
un pipeline en **5 blocs séquentiels**, chacun avec une responsabilité unique
et une sortie structurée consommée par le bloc suivant.

> **Principe fondamental.** Le LLM n'a pas d'opinion juridique propre : il
> organise/structure/formule ce que le corpus lui donne. Toute assertion est
> ancrée dans un document réel indexé. **Zéro inférence non sourcée.**

## Les 5 blocs

| Bloc | Rôle | Entrée → Sortie | Statut |
|---|---|---|---|
| **01 Case Parser** | NL → JSON cas normalisé | texte avocat → `CaseModel` | ✅ implémenté (`parser.py`) |
| **02 Majeure Retriever** | recherche vectorielle 2 collections + rerank + boost cabinet + seuil | `CaseModel` → sources rerankées | ⚙️ logique implémentée (`retriever.py`), **infra partielle** |
| **03 Syllogisme Builder** | triplet M/m/C **structuré**, ancré | cas + sources → `SyllogismBuild` | ✅ implémenté (`builder.py`) |
| **04 Confidence Scorer** | score M/m/C, revue humaine si < 0,70, questions auto | build + sources → `ConfidenceScore` | ✅ implémenté (`scorer.py`, déterministe) |
| **05 Draft Generator** | acte `.docx` au style cabinet | build validé → `.docx` | ✅ existant (`domain/conclusions`) |

Orchestration : `domain/syllogisme/service.py` → `draft_syllogism()`.
Règle de séquencement : un bloc ne s'exécute que si le précédent a produit une
sortie valide ; si `requires_human_review`, le pipeline s'arrête côté UI avant le
Draft Generator.

## Dégradation gracieuse (ce qui « s'allume » avec l'infra)

Le pipeline tourne aujourd'hui en **corpus-cabinet seul** ; les briques externes
s'activent quand elles sont configurées, sans changement de code :

| Capacité | Activation | Sans elle |
|---|---|---|
| **Collection jurisprudence publique** (Bloc 02 passe B) | créer la collection Qdrant `jurisprudence_publique` + ingestion | passe B ignorée, corpus cabinet seul |
| **Reranker** (Bloc 02 §4.3) | `COHERE_API_KEY` | tri par score vectoriel + boost cabinet |
| **Seuil de retrieval** (Bloc 02 §4.4) | `SYLLOGISME_MIN_SCORE` (échelle dépend de l'embedder) | garde-fou hors-corpus piloté par le LLM |
| **LLM** (Blocs 01/03) | `MISTRAL_API_KEY` / `ANTHROPIC_API_KEY` | scaffold démo (fixtures) |

Boost cabinet : les sources internes (`corpus_{firm_id}`) sont multipliées par
**1,4** avant tri — elles priment sur la jurisprudence générale.

## Reste à faire (infra — chantier dédié)

1. **Ingestion jurisprudence publique** → collection partagée `jurisprudence_publique` :
   Légifrance + Judilibre (clé **PISTE**), EUR-Lex, CNIL, Bodacc. Pipeline
   PDF/JSON → chunking → embeddings → upsert. (Recoupe la veille officielle.)
2. **Extraction du syllogisme à l'indexation** du corpus cabinet : chaque doc
   passé par un LLM qui en extrait le triplet M/m/C (`syllogisme_extrait`), pour
   un retrieval « par logique » et non seulement lexical.
3. **Reranker** Cohere v3 (ou cross-encoder fine-tuné) — clé + intégration.
4. **Isolation par cabinet** : `corpus_{firm_id}` (cf. multi-tenant #15).

## Critères de succès du POC (spec §9)

- 75–80 % du draft directement exploitable sans réécriture majeure.
- Zéro citation inventée ou non sourcée dans le syllogisme.
- Génération < 45 s de la requête au `.docx`.
- Score de confiance moyen > 0,80 sur les cas testés.
