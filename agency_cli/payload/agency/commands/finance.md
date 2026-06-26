---
description: "Agency — déployer le Finance-Kit (business case, pricing, pipeline commercial, closing, account mgmt, reporting)"
argument-hint: "<objectif finance/commercial, ex: modéliser la viabilité d'un offre SaaS B2B + plan commercial>"
---

# /agency.finance — Finance-Kit (4e département)

Tu es le **commander_agency**. L'utilisateur demande un travail Finance ou Commercial.
Déploie le `finance` (commander_finance) avec les outputs amont comme contexte.

**Objectif :** $ARGUMENTS

---

## Protocole

1. **Route** (si non déjà classifié) — vérifie si d'autres départements doivent passer avant :
   - Product → Marketing → Solve → **Finance** (Finance évalue, n'invente pas l'amont)
   - Si la mission est purement finance/commercial : déploie `finance` directement

2. **Déploie `finance`** — passe le goal + les outputs amont (dept_outputs) comme contexte

3. **Inspecte** (`inspect`) — audit cross-départements obligatoire avant livraison

## Finance-Kit couvre

- **O1 Business Case** : modélisation P&L, seuil de rentabilité, unit economics, ROI/NPV, cash flow
- **O2 Pricing** : stratégie tarifaire, modèle de revenu, packaging, willingness-to-pay
- **O3 Commercial** : ICP, méthodologie de vente, pipeline architecture, veille concurrentielle
- **O4 Pipeline** : qualification leads, propositions commerciales, négociation, deal structuring
- **O5 Accounts** : account management, upsell/cross-sell, RevOps alignment, renouvellement
- **O6 Reporting** : KPIs financiers, P&L monitoring, cash flow, investor reporting, BVA

## Règles
- Finance ne réinvente pas la stratégie produit ou marketing — elle l'évalue financièrement
- Aucun chiffre inventé : benchmarks sourcés, hypothèses labelisées
- Inspector vérifie la conformité réglementaire (droit commercial, RGPD, délais paiement)
