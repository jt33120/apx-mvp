# APX Platform — notes projet

Monorepo : `apps/apx-demo/web` (Next.js/Tailwind/TS, front), `apps/apx-demo/backend`
(FastAPI), `packages/legal-rag-core` (cœur RAG/LLM). Backend déployé sur **Railway**
(mis à jour à chaque merge) ; front sur **Vercel**.

## ⚠️ À ajouter en PROD (secrets / variables d'environnement Railway)

Le code fonctionne aujourd'hui en **mode dégradé** sans ces clés (rien ne casse).
À configurer pour activer les capacités complètes :

| Variable | Sert à | Statut | Coût |
|---|---|---|---|
| `PISTE_API_KEY` | **Jurisprudence FR** : Légifrance + Judilibre (Cass., Conseil d'État) — Bloc 02 « passe B » + veille officielle | **à créer en prod** (laissé en dégradé pour le moment, à la demande) | inscription **gratuite** (piste.gouv.fr) |
| `MISTRAL_API_KEY` ou `ANTHROPIC_API_KEY` | Génération en direct (LLM) | normalement déjà configuré | payant à l'usage (faible) |
| `COHERE_API_KEY` | Reranker Bloc 02 (optionnel) | non requis | payant — optionnel |
| `SYLLOGISME_MIN_SCORE` | Seuil hors-corpus du retriever (échelle dépend de l'embedder) | désactivé (0) par défaut | — |
| `EMBEDDER` | Qualité du RAG. `mistral` (réutilise `MISTRAL_API_KEY`, recommandé) / `bge_m3` (local, souverain, ~2 Go) / `auto` / `local` | **`local`** par défaut (hash non sémantique) | mistral = peu cher ; bge_m3 = gratuit |

> **RAG — point clé** : par défaut l'embedder est `LocalHashEmbedder` (gratuit
> mais **non sémantique** → pertinence limitée en live). Pour un vrai RAG, poser
> `EMBEDDER=mistral` (réutilise la clé LLM Mistral) ou `EMBEDDER=bge_m3`.
> ⚠️ Changer d'embedder change la dimension des vecteurs : **réindexer le corpus**
> (le store Qdrant recrée la collection sur changement de taille → repartir d'un
> stockage vide / relancer l'ingestion).

> **Rappel** : créer le compte **PISTE** (gratuit) et poser `PISTE_API_KEY` sur
> Railway avant la mise en prod, pour brancher la jurisprudence publique. Tant
> qu'elle est absente, le pipeline tourne sur le corpus cabinet seul.

Gratuit, sans clé : EUR-Lex, CEDH/HUDOC, Conseil constitutionnel, flux RSS
(CNIL, AMF, Autorité de la concurrence…). Veille : flux publics EU déjà branchés
en live (`domain/veille/feeds.py`, repli échantillon hors-ligne).

## Conventions
- Tests : `python -m pytest tests -q` (+ `packages/legal-rag-core/tests`). Lint : `ruff`.
- Front : `npm run build` dans `apps/apx-demo/web`. Pas d'ESLint configuré.
- Démo sans backend : couche `lib/demo.ts` (fixtures), repli automatique via `lib/api.ts`.
- i18n : FR source + `lib/translations.ts` (clé = texte FR), repli gracieux.

## Pipeline Syllogisme
Voir `docs/syllogisme-pipeline.md` (5 blocs, dégradation gracieuse, reste d'infra).
