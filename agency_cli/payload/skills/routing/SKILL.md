---
name: routing
description: >-
  Classify a mission goal into the minimal ordered set of departments to deploy
  (product / marketing / solve / finance / comms / data / ops / people / tech). Used by the agency commander in Phase 0 (Frame)
  via the router_agent, and again whenever the commander must reclassify mid-mission
  after a REDIRECT or a direction-check correction. Not a problem-solving method —
  it is the classification logic the whole agency pipeline depends on.
---

# Routing — Field Manual

The routing decision is the first and most consequential call the agency makes. Deploy
the wrong department and the mission either fails or wastes budget. Deploy too many and
focus dissolves. This skill documents the classification logic so the commander can
apply it confidently — both on the first call via `router_agency` and when reclassifying
mid-mission after a REDIRECT.

## The nine departments

| Department | Domain | Canonical keywords |
|---|---|---|
| **product** | Discovery, strategy, prioritisation, JTBD, PMF, spec, roadmap, delivery, measurement | feature, roadmap, JTBD, PMF, spec, user story, scope, build, discovery |
| **marketing** | Research, positioning, content, campaigns, SEO, brand, launch comms, analytics | campaign, content, copy, positioning, messaging, SEO, brand, launch, go-to-market, ads |
| **solve** | Problem-solving, root-cause, decision intelligence, architecture, debugging, implementation | debug, fix, bug, root cause, architect, algorithm, implement, refactor, optimise, decide |
| **finance** | Business case, financial modelling, pricing, P&L, commercial pipeline, closing, reporting | finance, pricing, budget, ROI, P&L, cash flow, pipeline, deal, commercial, investor, business case |
| **comms** | Corporate narrative, PR/media, crisis management, public affairs, ESG, events communications | PR, press, media, crisis, narrative, communications, ESG, stakeholders, event, launch comms |
| **data** | Data strategy, analytics, ML/LLMOps, data pipelines, governance | data, analytics, ML, LLM, pipeline, governance, warehouse, BI, reporting, AI |
| **ops** | Process design, PMO, compliance (NIS2, AI Act), risk management, operational excellence | process, PMO, compliance, NIS2, AI Act, risk, operations, workflow, audit |
| **people** | Org design, talent acquisition, L&D, performance & comp, culture, people analytics | HR, hiring, talent, org design, culture, compensation, onboarding, L&D, engagement |
| **tech** | Architecture, DevOps/IaC, security engineering, engineering excellence, build-vs-buy, DORA | architecture, DevOps, security, infrastructure, CI/CD, DORA, engineering, cloud, IaC |

## Classification rules

### Rule 1 — Single domain first
If the goal points at one discipline, deploy one department. Most missions are
single-domain. Do not inflate the pipeline to look thorough — it wastes budget and
violates Art. VI.

- "Add an export-to-CSV button" → `["product"]`
- "Write a launch email sequence" → `["marketing"]`
- "Our checkout throws a 500 on Safari" → `["solve"]`
- "Define the North Star metric" → `["product"]`
- "Run an SEO audit" → `["marketing"]`
- "Choose between two architectures" → `["solve"]`

### Rule 2 — Multi-domain pipeline (ordered)
Deploy more than one department only when the goal **explicitly spans** those domains.
The order is the execution sequence — each department's output feeds the next.

Default pipeline order when multiple departments are needed:

1. **product** first — establishes what is being built, for whom, and why. Its strategy
   and outcome targets become ground truth for downstream departments.
2. **marketing** second — takes the product output as the positioning input. It does not
   re-derive the product strategy; it builds on it.
3. **solve** third — applies decision intelligence to the blockers, trade-offs, or open
   decisions the upstream departments surfaced. Or runs standalone if it is the only
   routed department.
4. **finance** — evaluates economic viability, pricing, and commercial strategy. Takes upstream outputs; does not re-derive upstream strategy — it evaluates it financially.
5. **comms** — corporate narrative, PR, crisis, ESG, event strategy. Runs after product/marketing to wrap the right message around the right offer.
6. **data** — data strategy, pipelines, analytics, ML/LLMOps. Runs after product/solve when data infrastructure or intelligence is a primary deliverable.
7. **ops** — process design, PMO, compliance. Runs after solve to operationalise the chosen solution.
8. **people** — org design, talent, comp, culture. Runs after product/solve when workforce or org change is a primary deliverable.
9. **tech** — architecture, DevOps, security, build-vs-buy. Runs after product/solve for any technical implementation decisions.

Common multi-domain patterns:
- "Launch a new product" → `["product", "marketing"]`
- "Build a feature and write the launch copy" → `["product", "marketing"]`
- "Debug a problem and explain it to stakeholders" → `["solve", "marketing"]`
- "Launch with a financial model" → `["product", "marketing", "finance"]`
- "Pitch investors" → `["product", "finance"]`
- "Full agency / end-to-end engagement" → all nine (rarely justified — apply Rule 1 first)

### Rule 3 — Classify by dominant intent
When a goal mixes signals, pick the **dominant intent** — the discipline that owns the
primary outcome. Secondary concerns handled inside the primary department do not justify
adding another department to the route.

- "Pricing question with a bit of copy" → `["product"]` (pricing is product; copy is
  secondary, product can note it)
- "Campaign brief that needs a spec" → `["marketing"]` (the campaign is the deliverable;
  the spec is an input)
- "Architecture decision + a blog post about it" → `["solve", "marketing"]` (both are
  primary deliverables — justified multi-domain)

### Rule 4 — Never classify more than needed (Art. VI)
A pure positioning question is not `["product", "marketing", "solve"]`. A root-cause
investigation may need only `["solve"]`. Extra departments that are not needed:
- Waste the user's time and token budget.
- Dilute accountability (who owns the answer?).
- Violate Art. VI and the HARD RULE of the router doctrine.

## Output format

Every routing decision must record, in the dossier:

```
route     : ["department", ...]  ← ordered execution list
rationale : one line per department — why it is IN (or OUT)
```

Example:
```
route     : ["product", "marketing"]
rationale :
  product  → IN: goal requires scoping the feature and defining the pricing model
  marketing → IN: launch copy and channel plan are explicit deliverables
  solve    → OUT: no debugging, architecture, or decision-intelligence task present
  finance  → OUT: no financial modelling, pricing, or commercial pipeline task present
```

Rationale for **out** departments is as important as rationale for in — it makes the
classification auditable and revisable.

## Reclassification (REDIRECT / mid-mission)

The route is a decision, not a fixed rail. Reclassify when:
- The user sends a **REDIRECT** at the direction-check gate.
- A department's deliverable reveals that an upstream assumption was wrong.
- A new constraint surfaces that changes the dominant intent.

When reclassifying:
1. Read the updated dossier — include any `dept_outputs` already produced.
2. Run `router_agency` / `classify` again with the revised brief.
3. Do not discard completed `dept_outputs` from departments that remain in the new route.
4. Record the reclassification decision in the dossier → Decisions (with why).
5. **Do not restart from scratch** unless the mission goal itself has fundamentally
   changed; carry forward what was produced.

## Guardrails

- **Classify before you deploy.** No department runs until the route is set and recorded
  in the dossier (Art. VI).
- **The route is a recorded decision.** Always write `route` + `rationale` to the dossier
  before execution — the Inspector will check it.
- **Single-department missions are correct.** Not a shortfall; not a sign of insufficient
  analysis. The agency's quality bar is precision, not coverage.
- **REDIRECT ≠ restart.** A corrected route reuses all prior `dept_outputs` that still
  apply; only re-runs the departments affected by the change.
- Mirror the user's language (Art. III).
