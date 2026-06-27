# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo does

agency-kit is a thin routing and orchestration layer that sits above nine optional department kits (product, marketing, solve, finance, comms, data, ops, people, tech). It reads a mission goal, classifies which departments are needed and in what order, runs them sequentially (each reads the previous dept's output), and passes the whole result through a cross-department inspector.

## Commands

```bash
# Install (dev)
pip install -e ".[dev]"         # core + pytest stubs
pip install -e ".[all]"         # all nine department kits
pip install -e ".[product,tech]" # individual kits

# Test
pytest tests/ -v                # full offline suite (SDK + 9 kits are stubbed)
pytest tests/test_structure.py -v  # structural invariants only
pytest tests/ -k "test_router"  # single test by name

# Health check (needs API key + at least one kit installed)
agency check

# CLI
agency init [path] [--agent claude|codex|cursor|copilot|gemini|opencode]
agency run "goal" [--dry-run] [--steer] [--parallel]
agency missions
agency resume <mission_id>
agency sync [--allow-missing]
agency batch add "goal" / run / status / clear
agency export <mission_id>      # requires pip install -e ".[pdf]"
agency tui                      # requires pip install -e ".[tui]"
```

## Architecture

### Mission loop (`agency_kit/mission.py`)

```
run_mission(goal)
  CLASSIFY → classify(goal) returns ordered dept list  (router_agent, STANDARD model)
  ITERATE up to 3×:
    EXECUTE → Runner.run_sync(agency_commander, brief)
                commander calls: classify → depts in order → synthesise
    INSPECT → Runner.run_sync(agency_inspector, deliverable)
                PASS          → return dossier
                PASS_WITH_FIXES → extract fixes, loop back
                VETO          → extract fixes, loop back  (saved to disk)
  CAP → deliver with residual_risk note if MAX_ITERS reached
```

Quota / rate-limit detection wraps every `Runner.run_sync` call — on detection the mission saves state (`status: paused_rate_limit`) and exits cleanly; `agency resume` replays from the checkpoint.

### Cross-department dossier

Carried as a JSON block through every brief:
```python
{
  "goal": str,
  "route": list,            # ["product", "marketing"]
  "context": str | None,
  "dept_outputs": dict,     # {"product": "<full text>", ...}
  "decisions": list,
  "sources": list,
  "open_to_verify": list,
  "direction_check": dict | None,
  "verdicts": list,
  "iteration": int,
}
```

Departments are sovereign (Art. IV): the commander passes the full previous output forward unchanged — never summarises or rewrites a kit's deliverable.

### Department wiring (`agency_kit/commander.py`)

Each of the 9 kits is imported inside `try/except ImportError` guarded by a `_HAS_<DEPT>` boolean. Two kits (`marketing-kit`, `solve-kit`) export `commander` rather than `commander_<dept>` — handle with a nested alias:

```python
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

`DEPT_INSTALLED` (exported from `commander.py`) is the live dict `{dept: bool}` used by `--dry-run` and tests.

### Single source of truth for department names

`agency_kit/departments.py` exports `DEPT_NAMES` (ordered list), `VALID_DEPTS` (frozenset), and `dept_list_text()`. The router, commander, inspector, and CLI all import from here. Adding a department means updating only this file + the try/except block in `commander.py`.

### Payload (`agency_cli/payload/`)

`agency init` installs from the bundled payload — no internet required:
- `payload/agency/` ← `.agency/` (commands, constitution, templates; `plans/` excluded)
- `payload/agents/` ← merged from agency-kit `agents/` + all 9 dept kit `agents/` dirs
- `payload/skills/` ← merged skill dirs

`agency sync` regenerates from sibling repos. A pre-flight check verifies all sibling repos exist before wiping anything (silent wipe + missing repo = permanent loss of committed agent files).

### Shared doctrine files (`agents/`)

| Pattern | Files |
|---|---|
| Agency-level doctrine | `commander-agency.md`, `router-agency.md`, `inspector-agency.md`, `_shared-agency.md` |
| Per-department doctrine | `_shared-product.md` … `_shared-tech.md` (× 9) |
| Jurisdiction context | `_shared-eu.md` · `_shared-us.md` · `_shared-fr.md` |

All source files under `agents/` are mirrored to `payload/agents/`. The drift guard test (`test_payload_agent_matches_source`) catches divergence — run `agency sync` to fix.

### Jurisdiction injection (`AK_JURISDICTION`)

When set (`eu` / `us` / `fr`), the five compliance-heavy department commands (ops, tech, comms, people, data) load `agents/_shared-{jurisdiction}.md` in step 1 and pass it as regulatory context to the commander in step 3.

## Key files

| File | Role |
|---|---|
| `agency_kit/router.py` | `router_agent` + `classify(goal)` — dept routing + keyword fallback |
| `agency_kit/commander.py` | `agency_commander` — meta-orchestrator; all dept wiring + `DEPT_INSTALLED` |
| `agency_kit/inspector.py` | `agency_inspector` — cross-dept consistency gate (PASS / PASS-WITH-FIXES / VETO) |
| `agency_kit/mission.py` | `run_mission()` / `resume_mission()` — mission loop, quota handling |
| `agency_kit/store.py` | `save()`, `load()`, `list_missions()`, atomic `new_mission_id()` |
| `agency_kit/parallel.py` | `run_parallel_mission()` — concurrent dept execution variant |
| `agency_kit/models.py` | `ELITE` / `STANDARD` / `JURISDICTION` from env; `.env` auto-load |
| `agency_kit/departments.py` | Single source of truth for 9 dept names |
| `agency_kit/web.py` | `web_tools()` — search backend selected by `AK_SEARCH` |
| `agency_cli/cli.py` | All CLI subcommands |
| `agency_cli/sync_payload.py` | Payload regeneration logic + pre-flight safety guard |
| `.agency/memory/constitution.md` | 10 articles — every command re-reads this before acting |
| `docs/ARCHITECTURE.md` | Full routing table, pipeline diagram, design decisions |

## Environment variables

```bash
AK_ELITE_MODEL=gpt-4o          # commander, inspector, dept commanders (default: gpt-4o)
AK_STANDARD_MODEL=gpt-4o-mini  # routing agent (default: gpt-4o-mini)
AK_SEARCH=ddg                  # ddg | tavily | gemini | openai (auto-detects from keys when unset)
AK_JURISDICTION=eu             # eu | us | fr — injects regulatory context into compliance depts
AK_HTTP_TIMEOUT=90             # HTTP timeout in seconds; 0 = disable
OPENAI_API_KEY=...
# Each kit reads its own vars: PK_ELITE_MODEL, MK_ELITE_MODEL, SK_ELITE_MODEL, etc.
```

Anthropic or Gemini models work via `OPENAI_BASE_URL` — no extra dependency needed.

## Test architecture

`tests/conftest.py` stubs two layers before any test imports `agency_kit`:
1. The openai-agents SDK (`agents` module — `Agent`, `Runner`, `function_tool`, `WebSearchTool`)
2. All nine department kits and their `.commander` submodules

This lets the full suite run offline (no API key, no installed kits) and tests the fully-wired path (all 9 `_HAS_*` flags `True`) rather than the degraded/missing-kit path.

Tests drive `Runner.run_sync` via monkeypatching on `mission.Runner`.

## Constitution

`.agency/memory/constitution.md` — 10 articles. Critical ones:
- **Art. I** — Never invent data, citations, or outputs
- **Art. II** — No dark patterns, no misleading outputs
- **Art. IV** — Department sovereignty: don't override a kit's internal logic
- **Art. VI** — Don't over-route: deploy the minimum set the goal requires
- **Art. IX** — Inspector always runs; VETO triggers another iteration, not a skip
