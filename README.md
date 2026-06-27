# Agency-Kit

The **meta-orchestrator** of the AI Agency. Agency-Kit sits one level above nine optional departments — `product-kit`, `marketing-kit`, `solve-kit`, `finance-kit`, `comms-kit`, `data-kit`, `ops-kit`, `people-kit`, and `tech-kit` — reads a mission goal, and routes it to the right department(s). It runs single-department missions as well as cross-department pipelines (e.g. *product → marketing → finance*) behind a single CLI and a single Python entry point, so you describe the outcome once and the agency figures out who does what, in what order.

---

## Architecture

```
Agency Commander
 ├─ router_agency        🔵  classifies the goal → ordered department list
 ├─ commander_product    🎖️  product-kit    (optional extra)
 ├─ commander_marketing  🎖️  marketing-kit  (optional extra)
 ├─ commander_solve      🎖️  solve-kit      (optional extra)
 ├─ commander_finance    🎖️  finance-kit    (optional extra)
 ├─ commander_comms      🎖️  comms-kit      (optional extra)
 ├─ commander_data       🎖️  data-kit       (optional extra)
 ├─ commander_ops        🎖️  ops-kit        (optional extra)
 ├─ commander_people     🎖️  people-kit     (optional extra)
 ├─ commander_tech       🎖️  tech-kit       (optional extra)
 └─ inspector_agency     🎖️  cross-department consistency check (veto power)
```

🎖️ **elite** — `AK_ELITE_MODEL` (default `gpt-4o`) — meta-commander, inspector, and each department commander
🔵 **standard** — `AK_STANDARD_MODEL` (default `gpt-4o-mini`) — the routing agent

Departments are **optional extras**. If a department package is not installed, its commander is simply absent from the toolset — the agency commander routes around it and notes the gap, never fabricating its output.

---

## Routing

The router reads the goal and returns an **ordered** list of departments (earlier department runs first). It deploys the *minimum* set the goal actually requires — a pricing question is `["finance"]`, not all nine.

### Single-department

| Goal mentions… | → Department |
|---|---|
| `product` · `feature` · `roadmap` · `jtbd` · `pmf` · `discovery` · `prioritization` | **product** |
| `campaign` · `content` · `launch` · `positioning` · `seo` · `brand` | **marketing** |
| `debug` · `architect` · `algorithm` · `implement` · `solve` · `fix` | **solve** |
| `finance` · `pricing` · `budget` · `roi` · `p&l` · `pipeline` · `commercial` | **finance** |
| `pr` · `press release` · `crisis` · `esg` · `csrd` · `public affairs` · `events` | **comms** |
| `data` · `pipeline` · `analytics` · `bi` · `ml` · `llm` · `rag` · `warehouse` | **data** |
| `ops` · `process` · `pmo` · `nis2` · `ai act` · `compliance` · `procurement` | **ops** |
| `hr` · `talent` · `recruiting` · `org design` · `l&d` · `culture` · `compensation` | **people** |
| `architecture` · `devops` · `security` · `cloud` · `kubernetes` · `ci/cd` · `soc2` | **tech** |

### Cross-department pipelines

| Goal | → Route (in order) |
|---|---|
| "launch a product" | **product → marketing** |
| "build and market" | **product → marketing** |
| "solve and explain" | **solve → marketing** |
| "pitch investors" | **product → finance** |
| "launch with financial model" | **product → marketing → finance** |
| "end-to-end" / "full agency" | minimum set the goal needs (never all nine reflexively) |

The router outputs a small JSON object (`{"departments": [...], "rationale": "..."}`). If parsing fails it falls back to a keyword heuristic, and ultimately to `["product"]`.

---

## Installation

```bash
pip install openai-agents
pip install -e .
```

Install the departments you need as extras:

```bash
pip install -e ".[all]"          # all nine department kits
pip install -e ".[product]"      # product-kit only
pip install -e ".[marketing]"    # marketing-kit only
pip install -e ".[solve]"        # solve-kit only
pip install -e ".[finance]"      # finance-kit only
pip install -e ".[comms]"        # comms-kit only
pip install -e ".[data]"         # data-kit only
pip install -e ".[ops]"          # ops-kit only
pip install -e ".[people]"       # people-kit only
pip install -e ".[tech]"         # tech-kit only
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
export AK_ELITE_MODEL="gemini-2.5-pro"
export AK_STANDARD_MODEL="gemini-2.5-flash"
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
| `AK_ELITE_MODEL` | `gpt-4o` | Model for the meta-commander and inspector |
| `AK_STANDARD_MODEL` | `gpt-4o-mini` | Model for the routing agent |
| `AK_SEARCH` | auto | Search backend (`ddg` / `tavily` / `gemini` / `openai`). When unset, auto-detects from keys present: `TAVILY_API_KEY` → tavily; `GEMINI_API_KEY` → gemini; `OPENAI_BASE_URL` set → ddg; otherwise OpenAI hosted WebSearchTool. |
| `AK_JURISDICTION` | *(unset)* | Jurisdiction context injected into ops / tech / comms / data / people agents: `eu` (GDPR + NIS2 + AI Act + DORA + CSRD) · `us` (NIST CSF + SOC2 + state privacy + SEC) · `fr` (RGPD + ANSSI + Code du travail + CCP). When unset, agents infer from the goal. |
| `AK_HTTP_TIMEOUT` | `90` | HTTP timeout in seconds for the OpenAI client. Set to `0` to disable. |
| `OPENAI_API_KEY` | required | OpenAI key (or point at any OpenAI-compatible endpoint via `OPENAI_BASE_URL`) |

Secrets and overrides are also read from a local, gitignored `.env` (loaded before any model or key is resolved).

**Each kit keeps its own configuration.** When a department is deployed, *its* env vars still apply — agency-kit never overrides them:

| Department | Elite model | Standard model | Search |
|---|---|---|---|
| product | `PK_ELITE_MODEL` | `PK_STANDARD_MODEL` | `PK_SEARCH` |
| marketing | `MK_ELITE_MODEL` | `MK_STANDARD_MODEL` | `MK_SEARCH` |
| solve | `SK_ELITE_MODEL` | `SK_STANDARD_MODEL` | `SK_SEARCH` |
| finance | `FK_ELITE_MODEL` | `FK_STANDARD_MODEL` | `FK_SEARCH` |
| comms | `CK_ELITE_MODEL` | `CK_STANDARD_MODEL` | `CK_SEARCH` |
| data | `DK_ELITE_MODEL` | `DK_STANDARD_MODEL` | `DK_SEARCH` |
| ops | `OK_ELITE_MODEL` | `OK_STANDARD_MODEL` | `OK_SEARCH` |
| people | `PEK_ELITE_MODEL` | `PEK_STANDARD_MODEL` | `PEK_SEARCH` |
| tech | `TK_ELITE_MODEL` | `TK_STANDARD_MODEL` | `TK_SEARCH` |

---

## Usage

### CLI

```bash
# Scaffold .agency/ + slash commands for your harness
agency init
# installs: /agency.mission /agency.frame   /agency.inspect
#           /agency.product  /agency.marketing /agency.solve
#           /agency.finance  /agency.comms   /agency.data
#           /agency.ops      /agency.people  /agency.tech
#           (12 commands total)

# Run a headless mission (router decides the route, then auto-proceeds)
agency run "Launch our new B2B analytics product"

# Run with the interactive Direction Check (confirm or steer the route before execution)
agency run --steer "Take this feature end-to-end"

# Run departments concurrently where possible
agency run --parallel "Full go-to-market plan"

# Classify the goal and show the planned route — no API call
agency run --dry-run "Pitch investors for Series A"

# List saved missions
agency missions

# Resume a paused mission (e.g. after a rate-limit hit)
agency resume 20260627-123000-launch-b2b-analytics

# Add goals to the batch queue and run them sequentially
agency batch add "Build a data strategy"
agency batch run
agency batch run --resume-paused    # after a quota pause
agency batch status

# Export a mission deliverable to PDF (needs pip install -e ".[pdf]")
agency export 20260627-123000-launch-b2b-analytics

# Launch the terminal UI — Pipeline / Viewer / Analytics (needs pip install -e ".[tui]")
agency tui

# Prerequisite / health check
agency check

# Regenerate the bundled payload after editing .agency/ or agents/
agency sync
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

## The nine kits

| Department | Repo | Focus |
|---|---|---|
| Product | `product-kit` | Discovery · strategy · prioritisation · design · delivery · measurement |
| Marketing | `marketing-kit` | Research · positioning · content · campaigns · analytics |
| Solve | `solve-kit` | Problem-solving · root-cause · architecture · implementation |
| Finance | `finance-kit` | Business case · pricing · P&L · commercial pipeline · closing · reporting |
| Comms | `comms-kit` | Corporate comms · PR/media · crisis · public affairs · ESG/CSRD · events |
| Data | `data-kit` | Data strategy · engineering · analytics/BI · ML/LLMOps · data products |
| Ops | `ops-kit` | Process optimisation · PMO · EU compliance (NIS2, AI Act) · risk |
| People | `people-kit` | Org design · talent · L&D · performance · culture · people analytics |
| Tech | `tech-kit` | Architecture · DevOps · security · engineering excellence · build-vs-buy |

Each kit is a complete, standalone agent army (Commander → Officers → Soldiers → Inspector) with its own CLI and its own constitution.

---

## Why nine kits + one orchestrator (not a monorepo)

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

---

## More

**`GUIDE.md`** — full usage manual: pipeline walkthrough, slash-command catalogue, skills reference, and the repeatable pattern to wire a new department kit.
