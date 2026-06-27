# agency-kit — Architecture

## Overview

agency-kit is a thin routing and orchestration layer. It does not reimplement
department logic — it imports up to nine department commanders as tools and
sequences them (product, marketing, solve, finance, comms, data, ops, people,
tech). The departments are optional extras; agency-kit is useful even with only
one kit installed (it degrades gracefully).

## Chain of command

```
agency_commander (ELITE)
  ├─ classify          → router_agency       (STANDARD) — which depts, in what order
  ├─ product           → commander_product   (ELITE)    — product-kit  [optional]
  ├─ marketing         → commander_marketing (ELITE)    — marketing-kit [optional]
  ├─ solve             → commander_solve     (ELITE)    — solve-kit    [optional]
  ├─ finance           → commander_finance   (ELITE)    — finance-kit  [optional]
  ├─ comms             → commander_comms     (ELITE)    — comms-kit    [optional]
  ├─ data              → commander_data      (ELITE)    — data-kit     [optional]
  ├─ ops               → commander_ops       (ELITE)    — ops-kit      [optional]
  ├─ people            → commander_people    (ELITE)    — people-kit   [optional]
  ├─ tech              → commander_tech      (ELITE)    — tech-kit     [optional]
  ├─ inspect           → agency_inspector    (ELITE)    — cross-dept consistency gate
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
| comms / pr / press release / crisis / esg / event / réputation | comms | 1 |
| data / pipeline / analytics / bi / ml / llm / rag / warehouse | data | 1 |
| ops / process / pmo / nis2 / ai act / compliance / procurement | ops | 1 |
| people / hr / talent / recruiting / org design / l&d / culture | people | 1 |
| tech / architecture / devops / security / cloud / kubernetes / soc2 | tech | 1 |
| "launch a product" / "go to market" | product → marketing | 1 → 2 |
| "build and market" / "product launch" | product → marketing | 1 → 2 |
| "launch with financial model" / "pitch investors" | product → marketing → finance | 1 → 2 → 3 |
| "launch with PR" | product → marketing → comms | 1 → 2 → 3 |
| "build a data product" | product → data | 1 → 2 |
| "scale engineering team" | tech → people | 1 → 2 |
| "solve and communicate" / "fix and explain" | solve → marketing | 1 → 2 |
| "end-to-end" / "full agency" | minimum set the goal needs (never all nine reflexively) | router decides |

Default ordering when multiple departments are co-deployed:
product → marketing → solve → finance → comms → data → ops → people → tech.
Each department evaluates upstream outputs; it does not re-derive upstream strategy.

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

## CLI subcommands

| Command | Description |
|---|---|
| `agency init [path] [--agent claude\|codex\|cursor\|copilot\|gemini\|opencode]` | Scaffold `.agency/` + harness slash commands |
| `agency run "goal" [--steer] [--parallel] [--dry-run]` | Headless mission — routes, executes, inspects |
| `agency missions` | List all saved missions from `~/.agency/missions/` |
| `agency resume <mission_id>` | Resume a paused/VETO'd mission from its checkpoint |
| `agency check [path]` | Health check — constitution, SDK, at least one kit |
| `agency sync [--allow-missing]` | Regenerate bundled payload from all repo sources |
| `agency batch add "goal"` | Add a goal to the sequential batch queue |
| `agency batch run [--resume-paused] [--retry-failed] [--limit N]` | Execute pending queue goals |
| `agency batch status` | Show queue + run state |
| `agency batch clear [--status done]` | Remove entries from the queue by status |
| `agency export <mission_id>` | Export deliverable to PDF (optional: `pip install -e ".[pdf]"`) |
| `agency tui` | Terminal UI — Pipeline / Viewer / Analytics (optional: `pip install -e ".[tui]"`) |

## Slash commands (installed by `agency init`)

| Command | Description |
|---|---|
| `/agency.goal` | End-to-end goal execution — audit → fix-list → execute → verify (loop until done) |
| `/agency.mission` | Full cross-department mission with Direction Check |
| `/agency.frame` | Frame a goal before running: clarify constraints, audience, context |
| `/agency.inspect` | Inspect a deliverable: 3-check cross-department audit |
| `/agency.product` | Deploy the product department directly |
| `/agency.marketing` | Deploy the marketing department directly |
| `/agency.solve` | Deploy the solve department directly |
| `/agency.finance` | Deploy the finance department directly |
| `/agency.comms` | Deploy the comms department directly |
| `/agency.data` | Deploy the data department directly |
| `/agency.ops` | Deploy the ops department directly |
| `/agency.people` | Deploy the people department directly |
| `/agency.tech` | Deploy the tech department directly |

## Optional department wiring

`commander.py` uses try/except ImportError for each department kit. Kits that export
`commander` (not `commander_<dept>`) are handled with an import alias:

```python
try:
    from product_kit.commander import commander_product
    _HAS_PRODUCT = True
except ImportError:
    commander_product = None
    _HAS_PRODUCT = False

# Kits that export `commander` get an alias (e.g. solve-kit, marketing-kit)
try:
    try:
        from solve_kit.commander import commander_solve
    except ImportError:
        from solve_kit.commander import commander as commander_solve
    _HAS_SOLVE = True
except ImportError:
    commander_solve = None
    _HAS_SOLVE = False
```

The commander tool list is built conditionally — missing kits are silently absent.
The commander notes the gap in its output rather than fabricating dept output.

## Parse verdict — smart strategy

1. Look for explicit verdict lines (`OVERALL: X`, `VERDICT: X`, `FINAL VERDICT: X`) first.
2. Fall back to the LAST occurrence of VETO / PASS WITH FIXES / PASS in the text.

This prevents misfires on "resolving the previous VETO..." references in later iterations.
