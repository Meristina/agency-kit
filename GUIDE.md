# GUIDE — Agency-Kit, the meta-orchestrator

> Full usage manual: pipeline walkthrough, slash-command catalogue, skills reference,
> and the repeatable pattern to wire a new department kit.

---

## 1. What it is

**Agency-Kit** sits one level above the three department kits. It reads a mission goal,
classifies which departments to mobilise, runs them in order, combines their outputs
into a single coherent deliverable, and submits it to a cross-department Inspector with
veto power.

Two non-negotiable guarantees:

- **No invented information.** Every fact is sourced or explicitly flagged
  `[ASSUMPTION]` / `to verify`. The Inspector enforces this before anything ships.
- **Mirror the user's language.** Files are written in English, but every unit
  **responds in the user's language** (EN / FR / AR …).

---

## 2. Architecture

```
🔴 AGENCY COMMANDER  (meta-orchestrator — classifies, executes, synthesises, delivers)
   │
   ├─ 🔵 router_agency         classifies the goal → ordered department list
   │
   ├─ 🎖️ commander_product     product-kit    (optional extra)
   ├─ 🎖️ commander_marketing   marketing-kit  (optional extra)
   ├─ 🎖️ commander_solve       solve-kit      (optional extra)
   │
   └─ 🎖️ inspector_agency      cross-department quality gate (VETO power)
```

🎖️ **elite** — `AK_ELITE_MODEL` — meta-commander, inspector, department commanders
🔵 **standard** — `AK_STANDARD_MODEL` — router (fast, single classification call)

Departments are **optional extras**. A missing department drops out of the route
silently — its absence is recorded in the dossier, never fabricated.

---

## 3. File tree

```
agency-kit/
├─ README.md                    ← overview + quickstart
├─ GUIDE.md                     ← this file
├─ pyproject.toml               ← pip packaging (package `agency-kit`)
├─ MANIFEST.in                  ← ships payload in sdist
├─ requirements.txt             ← core dep (openai-agents)
├─ .env.example                 ← env vars template (copy to .env)
│
├─ agents/                      ← Claude units (3 .md)
│   ├─ commander-agency.md
│   ├─ inspector-agency.md
│   └─ router-agency.md
│
├─ skills/                      ← Claude procedures (3 SKILL.md)
│   ├─ mission-dossier/         ← cross-department dossier protocol
│   ├─ cross-dept-synthesis/    ← combining N outputs into one voice
│   └─ routing/                 ← classification logic + reclassification
│
├─ .agency/                     ← toolkit: constitution + commands + templates + scripts
│   ├─ memory/constitution.md   ← 10 articles, immutable rules
│   ├─ commands/                ← 6 slash commands (single source of truth)
│   │   ├─ mission.md           → /agency.mission
│   │   ├─ frame.md             → /agency.frame
│   │   ├─ product.md           → /agency.product
│   │   ├─ marketing.md         → /agency.marketing
│   │   ├─ solve.md             → /agency.solve
│   │   └─ inspect.md           → /agency.inspect
│   ├─ templates/
│   │   ├─ dossier-template.md
│   │   └─ deliverable-template.md
│   └─ scripts/sh/
│       ├─ new-mission.sh       ← scaffold missions/<NNN-slug>/
│       └─ install-claude.sh    ← global ~/.claude install
│
├─ agency_kit/                  ← Python engine
│   ├─ mission.py               ← control loop + direction check
│   ├─ commander.py
│   ├─ inspector.py
│   ├─ router.py
│   ├─ models.py                ← grade→model mapping (env-configurable)
│   └─ web.py                   ← search backends
│
├─ agency_cli/                  ← `agency` CLI (init/run/check/sync)
│   ├─ cli.py  scaffolder.py  integrations.py  runner_bridge.py  sync_payload.py
│   └─ payload/                 ← bundled mirror (.agency + agents + skills) for the wheel
│
└─ tests/                       ← structural audit + e2e harness (SDK stub, no network)
```

---

## 4. The pipeline in detail

### Phase 0 — FRAME (classify before deploying)

```
/agency.frame $MISSION
```

1. The Commander reads the dossier and **restates the goal in one sentence**.
2. It asks **2–3 questions that change the plan** (constraint, expected outcome, data
   available) — each with a recommended default. It waits for answers.
3. It calls **`router_agency`** (STANDARD grade) — one fast call:
   ```json
   {"departments": ["product", "marketing"], "rationale": "..."}
   ```
4. It records `route` + rationale in the dossier — why each department is IN or OUT
   (both are required).
5. **Direction check (Art. VIII)** — it surfaces the proposed route and waits for
   **GO / REDIRECT / ADJUST**. On REDIRECT, reclassifies and re-proposes.

### Phase 1 — EXECUTE (ordered pipeline, context carried forward)

```
/agency.product $MISSION  →  /agency.marketing $MISSION  →  /agency.solve $MISSION
```

Each department receives the goal **and all upstream `dept_outputs`**. Marketing
inherits the product strategy; solve receives the full combined picture. No department
starts from the raw brief once an upstream department has run.

- Department not installed → `dept_outputs.<dept>: not_installed` — never fabricated (Art. I + Art. IV).
- Department not routed → `not_routed`, skipped.

### Phase 2 — SYNTHESIZE (one voice, not a stack of reports)

The Commander combines `dept_outputs` into a single deliverable (`deliverable.md`):

| Task | Skill used |
|---|---|
| Inventory outputs | — |
| Overlaps → merge, cite both departments | `cross-dept-synthesis` |
| Contradictions → surface, name both sides | `cross-dept-synthesis` |
| Orphaned handoffs → flag | `cross-dept-synthesis` |
| Open decisions → escalate to the human | `cross-dept-synthesis` |

The result is written to `dossier.md → synthesis` and to `deliverable.md`.

### Phase 3 — AUDIT (Inspector, FINAL mode, veto power)

```
/agency.inspect $MISSION
```

`inspector_agency` (ELITE grade) runs **3 checks**:

1. **SOURCES** — every cross-department fact is cited and identical where shared.
   Hallucinated or uncited fact → **automatic VETO**.
2. **ETHICS & COMPLIANCE** — no dark patterns; sector-relevant regulations flagged; no
   compliance risk laundered across departments.
3. **CROSS-DEPARTMENT CONSISTENCY** — same customer, same value prop, consistent
   metrics, no conflicting constraints, no orphaned handoffs.

Verdict → **PASS / PASS WITH FIXES / VETO**. On VETO, re-enter only the responsible
department, re-synthesise, re-audit. Cap `MAX_ITERS = 3`.

---

## 5. The Dossier — the thread through every phase

```
missions/001-<slug>/
├─ dossier.md       ← living cross-department state (read-in / write-out each phase)
└─ deliverable.md   ← final synthesis deliverable (Phase 2 output)
```

Dossier schema:

```
goal           → original goal + Frame clarifications
context        → sector · stage · constraints
route          → ordered dept list + per-department rationale
direction_check→ GO | REDIRECT | ADJUST + note
dept_outputs
  .product     → full product-kit deliverable (or not_installed / not_routed)
  .marketing   → full marketing-kit deliverable
  .solve       → full solve-kit deliverable
synthesis      → deliverable.md summary (one voice)
assumptions    → [ASSUMPTION] / confirmed / to verify
decisions      → per phase — choice + one-line why
sources        → numbered; every fact points here (Art. I)
open_to_verify → unresolved items (live debt)
verdicts       → PASS / PASS WITH FIXES / VETO + required fixes
iteration      → control-loop counter
```

**Key rule:** the dossier is **carried, never reset** between iterations. On VETO, the
re-entered department reads the updated dossier — the next loop builds on the last.

---

## 6. Running a mission — Claude side

### Quick install

```bash
# Global (all projects)
bash .agency/scripts/sh/install-claude.sh

# Per project (scaffold .agency/ + commands into the target project)
agency init <my-project> --agent claude
```

`agency init` writes the 6 slash commands in the target harness's native format:

| Harness | Directory | Format |
|---|---|---|
| claude | `.claude/commands/agency.*.md` | MD + frontmatter |
| codex | `.codex/prompts/agency-*.md` | MD + frontmatter |
| cursor | `.cursor/commands/agency-*.md` | MD, no frontmatter |
| copilot | `.github/prompts/agency-*.prompt.md` | YAML + body |
| gemini | `.gemini/commands/agency/*.toml` | TOML |
| opencode | `.opencode/commands/agency-*.md` | MD + frontmatter |

### Usage

In Claude Code, address the **commander** with the goal:

```
/agency.mission Launch our new B2B analytics product in the French market
```

Or step by step for more control:

```
/agency.frame    missions/001-...   ← clarify, classify, direction check
/agency.product  missions/001-...   ← product department
/agency.marketing missions/001-...  ← marketing department (inherits product output)
/agency.inspect  missions/001-...   ← final cross-department audit
```

---

## 7. Running a mission — OpenAI / CLI side

### Install

```bash
pip install -e ".[all]"     # agency + product-kit + marketing-kit + solve-kit
export OPENAI_API_KEY=sk-...
```

### Run

```bash
# Headless (router auto-decides, no interruption)
agency run "Launch our new B2B analytics product"

# With interactive direction check (confirm route before execution)
agency run --steer "Launch our new B2B analytics product"
```

### Python API

```python
from agency_kit.mission import run_mission

dossier = run_mission("Launch our new B2B analytics product")
print(dossier["route"])      # e.g. ["product", "marketing"]
print(dossier["delivered"])  # synthesised cross-department deliverable
```

With the optional direction check:

```python
from agency_kit.mission import run_mission, console_direction_check

dossier = run_mission(
    "Launch our new B2B analytics product",
    dc_fn=console_direction_check,   # pause after CLASSIFY, before EXECUTE
)
```

### Other CLI commands

```bash
agency check                          # prerequisites / health check
agency sync                           # regenerate agency_cli/payload/ after editing .agency/ or agents/
agency init <project> --agent claude  # scaffold into a project
```

---

## 8. Slash-command catalogue

| Command | Phase | Role |
|---|---|---|
| `/agency.mission` | Orchestrator | Full loop: frame → execute → synthesize → audit |
| `/agency.frame` | 0 | Clarify goal, classify departments, direction check |
| `/agency.product` | 1a | Delegate to `commander_product`; carry upstream outputs |
| `/agency.marketing` | 1b | Delegate to `commander_marketing`; inherit product output |
| `/agency.solve` | 1c | Delegate to `commander_solve`; receive full combined picture |
| `/agency.inspect` | 3 | Cross-dept FINAL audit: sources · ethics · consistency; veto |

---

## 9. Skills catalogue

| Skill | Used by | Role |
|---|---|---|
| `mission-dossier` | Commander (all phases) | Read-in/write-out protocol, dossier schema, carry rules |
| `cross-dept-synthesis` | Commander (Phase 2) | Inventory, overlaps, contradictions, handoffs, one voice |
| `routing` | Commander (Phase 0 + reclassification) | Single/multi-domain rules, pipeline order, REDIRECT doctrine |

---

## 10. Cross-cutting guardrails (Constitution)

| Article | Rule |
|---|---|
| Art. I | No invented information — every fact sourced or `[ASSUMPTION]` |
| Art. II | No dark patterns; no compliance risk laundered across departments |
| Art. III | Mirror the user's language throughout |
| Art. IV | Department sovereignty — the agency orchestrates, never short-circuits |
| Art. VI | Minimum routing — deploy the fewest departments the goal actually needs |
| Art. VII | Ordered pipeline — each department's output is the next one's input |
| Art. VIII | Optional direction check — the only sanctioned interruption |
| Art. IX | Inspector is mandatory — veto power, nothing ships without the audit |
| Art. X | The agency produces artefacts — it does not act on the world |

---

## 11. Adding a department kit (repeatable pattern)

1. Build the department kit (`product-kit`, `marketing-kit`, `solve-kit`, or a new one).
2. Expose a `commander_<dept>` importable from the kit.
3. In `agency_kit/commander.py`, add the guard:
   ```python
   try:
       from <dept>_kit.commander import commander_<dept>
       _HAS_<DEPT> = True
   except ImportError:
       _HAS_<DEPT> = False
   ```
4. Add `commander_<dept>.as_tool()` to the commander's tools list (conditional on
   `_HAS_<DEPT>`).
5. In `agency_kit/router.py`, add `<dept>` to the known departments set.
6. Create `.agency/commands/<dept>.md` (slash command `/agency.<dept>`).
7. Add the extra in `pyproject.toml`: `<dept> = ["<dept>-kit"]`.
8. Run `agency sync` to regenerate the bundled payload.
9. Run `pytest` — all tests must pass.

**Quality check after each addition:**

```bash
find agency_kit -name '*.py' -print0 | xargs -0 python3 -m py_compile
find agency_cli -name '*.py' -print0 | xargs -0 python3 -m py_compile
python3 -m pytest tests/ -q
```
