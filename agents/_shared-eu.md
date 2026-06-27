---
role: jurisdiction-context
scope: ops · tech · comms · data · people agents operating in EU/EEA markets
trigger: AK_JURISDICTION=eu  (or detected from goal/dossier context)
---

# EU Jurisdiction — Compliance Context

Load this file when the mission targets EU/EEA operations, customers, or data subjects. Inject into: ops (compliance), tech (security architecture), comms (ESG/disclosure), data (privacy engineering), people (employment law).

---

## Data Protection — GDPR (Regulation 2016/679)

| Requirement | Key articles | Implication |
|---|---|---|
| Lawful basis for processing | Art. 6 | Must document basis per processing activity (Art. 30 register) |
| Data subject rights | Art. 15–22 | Erasure, portability, restriction — pipelines must support |
| DPA / DPO appointment | Art. 37 | Mandatory if large-scale special-category processing |
| Data breach notification | Art. 33 | 72h to supervisory authority; Art. 34 to subjects if high risk |
| Cross-border transfer | Art. 44–49 | SCCs (Commission Decision 2021/914) or adequacy decision |
| Records of processing | Art. 30 | Mandatory for all controllers and processors |

**Sourcing:** cite GDPR article number + OJ L 119/1, 04.05.2016. For supervisory authority guidance, cite the relevant SA opinion (CNIL, BfDI, ICO, etc.) and date.

---

## Cybersecurity — NIS2 Directive (Directive 2022/2555)

**In force:** 17 October 2024 (transposition deadline). Applies to medium and large essential and important entities in 18 sectors.

| Obligation | Scope | Detail |
|---|---|---|
| Risk management measures | Art. 21 | Policies, incident handling, supply chain security, cryptography, MFA, access control |
| Incident reporting | Art. 23 | 24h early warning → 72h notification → 1 month final report to CSIRT/authority |
| Management accountability | Art. 20 | Board-level responsibility; training mandatory |
| Supply chain security | Art. 21(2)(d) | Evaluate ICT suppliers; include security clauses in contracts |
| Sanctions | Art. 34 | Up to €10M or 2% of global turnover (essential entities); €7M / 1.4% (important) |

**Sourcing:** cite Directive 2022/2555, OJ L 333/80, 27.12.2022. For national transposition, cite implementing law per member state.

---

## AI Systems — AI Act (Regulation 2024/1689)

**Application dates:** GPAI rules → August 2025; high-risk systems → August 2026; other → August 2027.

| Risk level | Examples | Obligations |
|---|---|---|
| Unacceptable | Social scoring, real-time biometric surveillance | **Prohibited** |
| High-risk | CV screening, credit scoring, critical infrastructure AI | Conformity assessment, human oversight, transparency, Art. 10 data governance |
| Limited risk | Chatbots, deepfake generation | Transparency disclosure (Art. 50) |
| Minimal | Spam filters, basic recommendation | No specific obligations |

**GPAI models** (Art. 51–53): systemic-risk models (>10^25 FLOPS) → adversarial testing, cybersecurity, incident reporting.

**Sourcing:** cite Regulation (EU) 2024/1689, OJ L 2024/1689, 12.07.2024.

---

## Financial Sector Resilience — DORA ICT (Regulation 2022/2554)

Applies to: banks, insurers, investment firms, payment institutions, crypto-asset service providers, and their critical ICT third-party providers.

| Pillar | Requirement |
|---|---|
| ICT risk management | Board-approved framework, asset inventory, classification |
| Incident reporting | Classify → report to competent authority (major incidents: within 4h initial, 72h intermediate, 1 month final) |
| Digital operational resilience testing | TLPT (threat-led penetration testing) every 3 years for significant entities |
| Third-party risk | Register of ICT contracts; concentration risk; oversight of critical providers |
| Information sharing | Voluntary (Art. 45) but encouraged |

**In force:** 17 January 2025.  
**Sourcing:** cite Regulation (EU) 2022/2554, OJ L 333/1, 27.12.2022.

---

## ESG Reporting — CSRD (Directive 2022/2464)

**Scope:** large public-interest entities FY2024 → large companies FY2025 → listed SMEs FY2026 (opt-out until 2028).

| Standard | Content |
|---|---|
| ESRS E1 | Climate (GHG Scope 1/2/3, TCFD-aligned) |
| ESRS S1 | Own workforce |
| ESRS S2 | Workers in the value chain |
| ESRS G1 | Business conduct |

Double materiality: report on both **financial** impact on the company AND the company's **impact on** environment/society.

**Sourcing:** cite Directive 2022/2464 + delegated acts (ESRS set 1, Commission Regulation (EU) 2023/2772).

---

## Public Procurement — Directive 2014/24/EU

| Threshold (2024–2025) | Scope |
|---|---|
| €143,000 | Central government works/supplies/services |
| €221,000 | Sub-central contracting authorities |
| €5,538,000 | Works contracts |

**Key principles:** transparency, equal treatment, proportionality, mutual recognition.  
**Sourcing:** cite current Commission Regulation setting thresholds (check OJ for biennial update).

---

## Employment — EU Directives (key)

| Directive | Topic |
|---|---|
| 2019/1152 | Transparent and predictable working conditions |
| 2022/2041 | Adequate minimum wages |
| 2023/970 | Pay transparency and equal pay enforcement |
| 2002/14/EC | Employee information and consultation (works councils) |
| 2001/23/EC | Transfer of undertakings (TUPE-equivalent) |

**Sourcing:** cite directive number + OJ reference. For national implementation, cite domestic statute.

---

## Verification Checklist (EU)
- [ ] GDPR Art. 30 processing register updated
- [ ] NIS2 sector classification confirmed (essential / important / not in scope)
- [ ] AI Act risk classification documented for each AI system in scope
- [ ] DORA applicability check (financial sector entity?)
- [ ] CSRD reporting scope and first reporting year confirmed
- [ ] Procurement thresholds verified against current OJ regulation
- [ ] Cross-border data transfer mechanism documented (SCC / adequacy)
