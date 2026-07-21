---
date: 2026-04-28
type: agentique
status: implémenté
impact: méthodologie de travail Julian
---

# ADR · Architecture du pont multi-agent (Cowork ↔ APX agent ↔ Telegram)

## Contexte

Julian travaille avec plusieurs agents en parallèle :
- **Cowork** (sessions interactives Claude, c'est moi) — pour les phases d'architecture, de build, et de drafts complexes
- **APX agent Kimi-2** (OpenClaw, Telegram bot `APX_JTA_bot`) — pour le quotidien asynchrone du projet APX
- **James Kimi-2** — admin perso (mails, calendar)
- **Luke Codex GPT-5.4**, **Sofia DeepSeek**, **UTI Claude Sonnet** — autres rôles

Problème : aucune mémoire partagée entre eux. Quand je termine une session Cowork, l'APX agent ne sait rien de ce qui s'est dit. Julian sert de relais manuel — pas tenable.

## Options envisagées

1. **Notion comme source unique** — tous les agents lisent/écrivent dans une page Notion partagée.
2. **Markdown files + git** — convention de fichiers dans `/APX-Advisory/Agents/`, lus par tous.
3. **state.json unique** — un fichier JSON central, lu/écrit par tous.
4. **Combinaison** — 1 + 2 + 3.

## Décision

**Option 4 (combinaison).** Architecture en couches :

- **Couche "vérité courante"** : `state.json` — lu/écrit par tous, single point of truth pour l'état projet.
- **Couche "mémoire chronologique"** : `recaps/*.md` — append-only, un fichier par session significative.
- **Couche "décisions structurelles"** : `decisions/*.md` — append-only, ADR-light.
- **Couche "queue async"** : `inbox/inbox.md` — Telegram → Cowork (ce que Julian balance entre les sessions).
- **Mirror Notion** : les recaps et décisions sont aussi pushés sur Notion pour visualisation web (et pour Maxime/Lucia si on veut leur partager).

### Flux

```
[Cowork session]
    ├─ lit state.json + 3 derniers recaps + inbox.md au début
    ├─ travaille
    └─ écrit nouveau recap + décisions + état → state.json + push Notion à la fin

[APX Telegram tour]
    ├─ Kimi-2 lit state.json + dernier recap + inbox.md au démarrage
    ├─ répond à Julian
    └─ si décision/changement durable → écrit décision + update state.json

[Bridge cron quotidien · 18h]
    ├─ relit la journée (recaps, commits git, mails APX, modifs Notion)
    ├─ produit un brief court
    └─ pousse sur Telegram + audio à 7h le lendemain via TTS

[Telegram inbox]
    Julian → bot : message libre
    bot → écrit ligne timestamp dans inbox.md
    prochaine session Cowork ingère et archive
```

### Implémentation immédiate

Scripts Python dans `bridge/` :
- `daily_recap.py` — cron principal
- `telegram_send.py` — Cowork/cron → Telegram (Bot API)
- `telegram_inbox.py` — webhook Telegram → inbox.md
- `morning_brief.py` — TTS via OpenAI API ou ElevenLabs → audio Telegram
- `github_webhook.py` — push commits → Telegram

Stockés en clair dans le dossier `Agents/`. Versionnés en git privé.

## Conséquences

**Positives**
- Plus de relais manuel humain entre agents.
- Mémoire institutionnelle du projet APX visible et auditable.
- Cours de la journée tracé naturellement (recap quotidien, commits, mails, Notion).
- L'APX agent devient utile dès la prochaine session Telegram (a déjà du contexte).
- Scalable au-delà d'APX (même pattern pour Groupama, MIP, xSOM).

**Négatives**
- Discipline d'écriture requise. Si je ne tiens pas le recap à la fin de session, le système se dégrade vite.
- Risque de bruit (trop de fichiers, structure trop dense). À surveiller.
- `state.json` peut devenir source de conflit si deux agents écrivent en même temps. Mitigation : git versionning + convention "qui écrit timestamp + nom dans `_meta`".

## Validation

- [x] Architecture posée — 28/04
- [x] Implémentation files + scripts — 28/04
- [ ] Token Telegram à wirer dans `.env` — Julian
- [ ] Premier cycle complet (cron 18h → recap auto → Telegram) — à observer cette semaine
- [ ] Itération si besoin
