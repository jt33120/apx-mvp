---
date: 2026-04-28
type: technique
status: pré-décidé · à confirmer avec chaque client
impact: stack production
---

# ADR · Choix LLM, embeddings, vector DB, hébergement

## Contexte

Contraintes non-négociables (issues du brief Maxime du 28/04) :
- Données ne sortent pas de l'UE
- Zero-retention sur tous les LLM tiers
- Pas de fine-tuning sur les données client
- RAG strict, fragments seulement transmis aux LLM
- Option air-gapped pour clients paranoïaques

Choix techniques à arbitrer : LLM par défaut, embeddings, vector DB, hébergeur.

## Décisions

### LLM par défaut

**Mistral Large** via API EU zero-retention (Mistral entreprise française, endpoints EU natifs, pas de gymnastique juridique de transfert). Fallback possible Claude Sonnet 4.6 via endpoints EU si performance Mistral insuffisante sur des tâches précises.

**Option air-gapped** : Mistral 7B Instruct ou Llama 3 8B auto-hébergé sur GPU local (Scaleway L4 ou H100 selon volume). Plus complexe à provisionner (CAPEX GPU, OPEX surveillance), performances un cran en-dessous, mais isolation absolue.

### Embeddings

**BGE-M3** par défaut (open-source, multilingue FR/NL/EN, autohébergeable, gratuit après installation). Pour clients qui veulent tout-Mistral pour cohérence : `mistral-embed` en API. BGE-M3 par défaut car :
- Tourne sur CPU pour les volumes envisagés
- Zéro coût récurrent (vs $0.10/M tokens Mistral-embed)
- Multilingue out-of-the-box (essentiel pour P&P bilingue FR/NL)

### Vector DB

**Qdrant** auto-hébergé sur l'infra client (open source, Apache 2.0, scalable au million de docs sans douleur, supporte filtres complexes, payload riche pour RBAC). Alternative envisagée Weaviate (rejeté car plus lourd à déployer pour notre besoin), Chroma (rejeté car moins mature en prod).

Pour les très gros corpus type instruction pénale 10k+ docs, ajouter une couche **GraphRAG** par-dessus Qdrant pour relier entités/dates/événements. Référence : déjà utilisé en veille réglementaire bancaire.

### Hébergement

Trois options par défaut, à décider par client :

1. **Scaleway sovereign cloud** (FR, certifié SecNumCloud) — défaut recommandé
2. **OVH** — équivalent EU, parfois préféré pour raisons culturelles
3. **Infra cabinet** — si capacité serveur disponible (P&P potentiellement)

Pour la phase POC/MVP de Julian : dev box Scaleway 30€/mois. Pour la prod client : machine dédiée 8-16 vCPU + 32-64 GB RAM (mode standard) ou GPU L4 + 24 GB VRAM (mode air-gapped).

### Tech stack applicative

- Backend : **Python** (FastAPI) — écosystème mature pour parsers, LangChain compatible, équipes juridiques savent dépanner si besoin.
- Frontend : **Next.js + Tailwind + TipTap** pour les tables éditables. Pas Vite/SPA pure car SSR + auth serveur cohérent avec besoin RBAC.
- Templating doc : **python-docx** pour Word, **WeasyPrint** ou **ReportLab** pour PDF.
- OCR : **Tesseract** local par défaut, **Mistral OCR** ou **Azure Document Intelligence** EU pour précision élevée.

## Conséquences

- Stack 100% EU même en mode cloud.
- Coût LLM API maîtrisé (Mistral Large ~3x moins cher que Claude Sonnet 4.6 sur input).
- Argument commercial fort : "moteur d'IA français, hébergement français, équipe française".
- Trade-off : Mistral Large encore légèrement derrière Claude/GPT-5 sur certains benchmarks de raisonnement complexe — à mitiger via prompt engineering et possibilité de basculer en Claude EU pour tâches sensibles.

## Validation

- [x] Arbitrage Julian — 28/04
- [ ] Confirmation Maxime — hebdo
- [ ] Validation client RMT — phase cadrage
- [ ] Validation client P&P — phase cadrage (Maître Gouden + Jérôme IT)
