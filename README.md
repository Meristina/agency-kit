# Agency-Kit

The **meta-orchestrator** of the AI Agency. Agency-Kit sits one level above the three autonomous departments — `product-kit`, `marketing-kit`, and `solve-kit` — reads a mission goal, and routes it to the right department(s). It runs single-department missions as well as cross-department pipelines (e.g. *product → marketing*) behind a single CLI and a single Python entry point, so you describe the outcome once and the agency figures out who does what, in what order.

---

## Architecture

```
Agency Commander
 ├─ router_agency        🔵  classifies the goal → ordered department list
 ├─ commander_product    🎖️  product-kit    (optional extra)
 ├─ commander_marketing  🎖️  marketing-kit  (optional extra)
 ├─ commander_solve      🎖️  solve-kit      (optional extra)
 └─ inspector_agency     🎖️  cross-department consistency check (veto power)
```

🎖️ **elite** — `AK_ELITE_MODEL` (default `gpt-5.5`) — meta-commander, inspector, and each department commander
🔵 **standard** — `AK_STANDARD_MODEL` (default `gpt-5.4-mini`) — the routing agent

Departments are **optional extras**. If a department package is not installed, its commander is simply absent from the toolset — the agency commander routes around it and notes the gap, never fabricating its output.

---

## Routing

The router reads the goal and returns an **ordered** list of departments (earlier department runs first). It deploys the *minimum* set the goal actually requires — a pricing question is `["product"]`, not all three.

### Single-department

| Goal mentions… | → Department |
|---|---|
| `product` · `feature` · `roadmap` · `jtbd` · `pmf` · `discovery` · `prioritization` | **product** |
| `campaign` · `content` · `launch` · `positioning` · `seo` · `brand` | **marketing** |
| `debug` · `architect` · `algorithm` · `implement` · `solve` · `fix` | **solve** |

### Cross-department pipelines

| Goal | → Route (in order) |
|---|---|
| "launch a product" | **product → marketing** |
| "build and market" | **product → marketing** |
| "solve and explain" | **solve → marketing** |
| "end-to-end" / "full agency" | **product → marketing → solve** |

The router outputs a small JSON object (`{"departments": [...], "rationale": "..."}`). If parsing fails it falls back to a keyword heuristic, and ultimately to `["product"]`.

---

## Installation

```bash
pip install openai-agents
pip install -e .
```

Install the departments you need as extras:

```bash
pip install -e ".[all]"          # product + marketing + solve
pip install -e ".[product]"      # product-kit only
pip install -e ".[marketing]"    # marketing-kit only
pip install -e ".[solve]"        # solve-kit only
pip install -e ".[dev]"          # pytest (offline tests)
```

Optional search backends:

```bash
pip install -e ".[ddg]"          # DuckDuckGo (free, no key)
pip install -e ".[tavily]"       # Tavily
pip install -e ".[gemini]"       # Gemini grounding
```

For Anthropic (direct — no extra dependency):

```bash
export OPENAI_BASE_URL="https://api.anthropic.com/v1/"
export OPENAI_API_KEY="sk-ant-..."
export AK_ELITE_MODEL="claude-opus-4-8"
export AK_STANDARD_MODEL="claude-sonnet-4-6"
```

For Gemini (direct):

```bash
export OPENAI_BASE_URL="https://generativelanguage.googleapis.com/v1beta/openai/"
export OPENAI_API_KEY="<google-ai-studio-key>"
export AK_ELITE_MODEL="gemini-3.5-flash"
export AK_STANDARD_MODEL="gemini-3.1-flash-lite"
```

LiteLLM is only needed for dynamic multi-provider routing within a single run:

```bash
pip install -e ".[litellm]"
export AK_ELITE_MODEL="litellm/anthropic/claude-opus-4-8"
export AK_STANDARD_MODEL="litellm/anthropic/claude-sonnet-4-6"
export ANTHROPIC_API_KEY="sk-ant-..."
```

---

## Configuration

| Variable | Default | Description |
|---|---|---|
| `AK_ELITE_MODEL` | `gpt-5.5` | Model for the meta-commander and inspector |
| `AK_STANDARD_MODEL` | `gpt-5.4-mini` | Model for the routing agent |
| `AK_SEARCH` | auto | Search backend (`ddg` / `tavily` / `gemini` / `openai`). When unset, auto-detects from keys present: `TAVILY_API_KEY` → tavily; `GEMINI_API_KEY` → gemini; `OPENAI_BASE_URL` set → ddg; otherwise OpenAI hosted WebSearchTool. |
| `OPENAI_API_KEY` | required | OpenAI key (or point at any OpenAI-compatible endpoint via `OPENAI_BASE_URL`) |

Secrets and overrides are also read from a local, gitignored `.env` (loaded before any model or key is resolved).

**Each kit keeps its own configuration.** When a department is deployed, *its* env vars still apply — agency-kit never overrides them:

| Department | Elite model | Standard model | Search |
|---|---|---|---|
| product | `PK_ELITE_MODEL` | `PK_STANDARD_MODEL` | `PK_SEARCH` |
| marketing | `MK_ELITE_MODEL` | `MK_STANDARD_MODEL` | `MK_SEARCH` |
| solve | `SK_ELITE_MODEL` | `SK_STANDARD_MODEL` | `SK_SEARCH` |

---

## Usage

### CLI

```bash
# Scaffold .agency/ + slash commands for your harness
agency init

# Run a headless mission (router decides the route, then auto-proceeds)
agency run "Launch our new B2B analytics product"

# Run with the interactive Direction Check (confirm or steer the route before execution)
agency run --steer "Take this feature end-to-end"

# Prerequisite / health check
agency check
```

### Python

```python
from agency_kit.mission import run_mission

dossier = run_mission("Launch our new B2B analytics product")
print(dossier["route"])       # e.g. ["product", "marketing"]
print(dossier["delivered"])   # the synthesised cross-department deliverable
```

With the optional, non-blocking Direction Check:

```python
from agency_kit.mission import run_mission, console_direction_check

dossier = run_mission(
    "Take this feature end-to-end",
    dc_fn=console_direction_check,   # pause after CLASSIFY, before EXECUTE
)
```

The mission loop is `CLASSIFY → (optional Direction Check) → EXECUTE → INSPECT`. The agency inspector gates delivery with veto power; a `VETO` or `PASS_WITH_FIXES` loops back with required fixes. Iterations are capped at `MAX_ITERS = 3`; if still failing, it delivers the best result with `residual_risk` stated.

---

## The three kits

| Department | Repo | Focus |
|---|---|---|
| Product | `product-kit` | Discovery · strategy · prioritisation · design · delivery · measurement |
| Marketing | `marketing-kit` | Research · positioning · content · campaigns · analytics |
| Solve | `solve-kit` | Problem-solving · root-cause · architecture · implementation |

Each kit is a complete, standalone agent army (Commander → Officers → Soldiers → Inspector) with its own CLI (`product`, `marketing`, `solve`) and its own constitution.

---

## Why three kits + one orchestrator (not a monorepo)

- **Each kit is standalone.** A client installs only the department(s) they need. `product-kit` runs perfectly well with no knowledge that agency-kit exists.
- **Agency-kit adds cross-department routing without coupling the kits.** Departments are optional extras wired in conditionally; an absent kit disappears from the route rather than breaking the import.
- **Department sovereignty (Art. IV).** The agency orchestrates *between* departments; it never reaches *inside* one to bypass that kit's own commander, inspector, or doctrine. Each department remains the sole authority over how its work is done.

---

## Tests

```bash
pip install -e ".[dev]"
pytest
# offline — SDK stub, no API key, no network
```
