---
date: 2026-04-28
type: commercial
status: pré-décidé Julian · à négocier avec Maxime
impact: cadre contractuel Julian ↔ APX
---

# ADR · Modèle de facturation Julian → APX

## Contexte

APX vend en forfait par use case (modèle déjà validé commercialement) : 30-40k€ par use case, payé en 4 milestones, le client ne paie Mn qu'après validation de M(n-1). Pas de TJM, pas de licences, pas de subscription.

Question : comment Julian (freelance/exécutant) se positionne dans ce cadre ?

## Options envisagées

**A — TJM pur** (900-1100€/jour, défendable senior AI/freelance Paris)
- Pour : facture ce qui est fait, zéro risque de scope creep absorbé par moi.
- Contre : suivi heures exigé, négo permanente sur scope, mauvais signal commercial pour APX (incite à tirer le projet en longueur), désaligne avec le forfait que APX vend au client.

**B — Forfait pourcentage strict**
- Pour : aligné avec le modèle APX, simplicité.
- Contre : si APX sous-cote face au client, je porte le risque. Scope creep mange ma marge.

**C — Hybride : forfait dominant + backup TJM (option retenue)**
- Pour : protège contre les deux risques principaux. Scope défini = forfait, hors-scope explicitement validé = TJM.
- Contre : exige des bornes claires sur le scope.

## Décision

**Option C.** Modalités proposées à Maxime :

- **Forfait par use case = 50% de l'invoice client APX**, payé en 4 milestones (M1 25%, M2 35%, M3 25%, M4 15%). Versement à validation client de Mn-1, donc je suis payé en même temps que APX.
- **Cap TJM 900€/jour** pour tout dépassement de scope explicitement validé par moi par mail.
- **Maintenance corrective post-livraison incluse** dans le forfait (= je couvre les bugs critiques pendant 30 jours).
- **Évolutions / nouveaux features** = nouveau forfait ou TJM, à chiffrer au cas par cas.
- **Zero retention sur ma machine** : aucune donnée client sur mon poste sauf samples synthétiques/anonymisés. Je travaille en remote sur l'infra client en VPN/SSH.

## Calcul de référence (sur la base 30-40k€/use case côté APX)

3 use cases identifiés à date : P&P UC01 (LexCore IA), P&P UC02 (Veille), RMT (triage). À 50% :
- Plancher : 3 × 15k€ = **45k€** sur 8 semaines
- Plafond : 3 × 20k€ = **60k€** sur 8 semaines

À comparer à mon plancher de TJM théorique sur la même période : 35-40 jours × 900€ ≈ 31-36k€. Le forfait est plus rémunérateur car il valorise la responsabilité technique (architecte + dev + recette) et pas seulement les heures.

## Termes contractuels souhaités

- Convention freelance (ou contrat de prestation) signée avant démarrage M1.
- Mention claire du forfait et du backup TJM.
- Clause IP : le code produit appartient à APX/clients, mais je peux en réutiliser les patterns architecturaux génériques pour autres projets (sans contenu).
- Clause de non-concurrence : limitée aux deux clients du moment (RMT, P&P), pas un blocage généralisé du secteur juridique.
- Maintenance corrective 30 jours post-livraison incluse, étendue payante au-delà.

## À discuter en hebdo

- Maxime accepte-t-il la grille 50% ? Si non, à quel pourcentage tombe-t-on (40% ? 60% ?).
- Mécanique de validation client → versement Julian : qui notifie quand un milestone est validé ?
- Cas particulier UC02 (Veille P&P) — possiblement plus simple et plus court que les autres → forfait potentiellement plus bas (25%) à compenser sur les autres.

## Validation

- [x] Arbitrage Julian — 28/04
- [ ] Discussion Maxime — hebdo
- [ ] Convention signée avant M1
