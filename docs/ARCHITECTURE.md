# agency-kit — Architecture

## Overview

agency-kit is a thin routing and orchestration layer. It does not reimplement
product, marketing, or solve logic — it imports the department commanders as
tools and sequences them. The departments are optional extras; agency-kit is
useful even with only one kit installed (it degrades gracefully).

## Chain of command

```
agency_commander (ELITE)
  ├─ classify          → router_agency      (STANDARD) — which depts, in what order
  ├─ product           → commander_product  (ELITE)    — product-kit [optional]
  ├─ marketing         → commander_marketing (ELITE)   — marketing-kit [optional]
  ├─ solve             → commander_solve    (ELITE)    — solve-kit [optional]
  ├─ finance           → commander_finance  (ELITE)    — finance-kit [optional]
  ├─ inspect           → agency_inspector   (ELITE)    — cross-dept consistency gate
  └─ web search tools  → AK_SEARCH backend
```

## Mission loop

```
run_mission(goal)
  │
  ├── CLASSIFY: classify(goal) → dept list        # classify() from agency_kit.router
  │   └── [optional DC: confirm route or steer]
  │
  ├── ITERATE (max 3):
  │   ├── EXECUTE: Runner.run_sync(agency_commander, agency_brief(dossier, fixes))
  │   │     └─ commander internally: classify → execute depts → synthesise
  │   └── INSPECT: Runner.run_sync(agency_inspector, deliverable)
  │         ├── PASS       → return dossier
  │         ├── PASS_WITH_FIXES → extract fixes, loop
  │         └── VETO       → extract fixes, loop
  │
  └── [cap] deliver with residual_risk if MAX_ITERS reached
```

## Routing table

| Goal keywords | Departments invoked | Order |
|---|---|---|
| product / feature / roadmap / jtbd / pmf / discovery / prioriti | product | 1 |
| market / campaign / content / launch / position / seo / brand | marketing | 1 |
| solve / debug / fix / architect / algorithm / technical / implement | solve | 1 |
| finance / pricing / budget / roi / p&l / pipeline / commercial / deal | finance | 1 |
| "launch a product" / "go to market" | product → marketing | 1 → 2 |
| "build and market" / "product launch" | product → marketing | 1 → 2 |
| "launch with financial model" / "pitch investors" | product → marketing → finance | 1 → 2 → 3 |
| "solve and communicate" / "fix and explain" | solve → marketing | 1 → 2 |
| "end-to-end" / "full agency" | product → marketing → solve → finance | 1 → 2 → 3 → 4 |

Finance runs AFTER product, marketing, and solve when co-deployed — it evaluates their upstream outputs; it does not re-derive product or marketing strategy.

The router outputs JSON `{"departments": [...], "rationale": "..."}`.
Keyword fallback in `classify()` handles parse errors gracefully.

## Cross-department dossier

Carried across the whole mission (passed as JSON block in every brief):

```python
{
  "goal": str,
  "route": list,            # ["product", "marketing"]
  "context": str | None,    # detected audience / stage / constraints
  "dept_outputs": dict,     # {"product": "...", "marketing": "..."}
  "decisions": list,
  "sources": list,
  "open_to_verify": list,
  "direction_check": dict | None,  # DC result: {"iteration", "choice", "note"}
  "verdicts": list,         # Inspector verdicts per iteration
  "iteration": int,
}
```

## Department sovereignty (Art. IV)

The agency commander delegates fully to each department's internal logic. It does
not short-circuit, summarise, or rewrite a department's output before passing it
to the next — it carries the full output forward as context. The inspector checks
CROSS-DEPARTMENT consistency, not the individual kit's internal quality (each kit's
own inspector handles that).

## Inspector — 3 cross-department checks

1. **SOURCES** — same never-cite list as individual kits; cross-referenced facts must
   be consistent across departments (e.g., market size cited in product ≠ marketing).
2. **ETHICS & COMPLIANCE** — no dark patterns; coherent compliance posture
   (e.g., product says privacy-first but marketing recommends tracking → VETO).
3. **CROSS-DEPARTMENT CONSISTENCY** — strategy ↔ positioning ↔ delivery alignment:
   - Product North Star ↔ Marketing KPIs
   - Product spec ↔ Solve deliverables (builds what was designed)
   - No orphaned handoffs (discover → position → deliver, no gaps)

## Optional department wiring

`commander.py` uses try/except ImportError for each department kit:

```python
try:
    from product_kit.commander import commander_product
    _HAS_PRODUCT = True
except ImportError:
    commander_product = None
    _HAS_PRODUCT = False
```

The commander tool list is built conditionally — missing kits are silently absent.
The commander notes the gap in its output rather than fabricating dept output.

## Parse verdict — smart strategy

1. Look for explicit verdict lines (`OVERALL: X`, `VERDICT: X`, `FINAL VERDICT: X`) first.
2. Fall back to the LAST occurrence of VETO / PASS WITH FIXES / PASS in the text.

This prevents misfires on "resolving the previous VETO..." references in later iterations.
