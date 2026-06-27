# agency-kit — Claude Code context

Meta-orchestrator for the AI Agency. Classifies a mission goal and routes it to
the right department(s) — in sequence, feeding each department's output as context into the next.
One CLI (`agency`), one inspector (`inspector_agency`), one mission loop.

**9 departments available:** product · marketing · solve · finance · comms · data · ops · people · tech

## Key files

| File | Role |
|---|---|
| `agency_kit/router.py` | `router_agent` + `classify(goal)` — department routing |
| `agency_kit/commander.py` | `agency_commander` — meta-orchestrator (ELITE) |
| `agency_kit/inspector.py` | `agency_inspector` — cross-department quality gate |
| `agency_kit/mission.py` | `run_mission()` — control loop + direction check |
| `agency_kit/models.py` | `ELITE` / `STANDARD` via `AK_ELITE_MODEL` / `AK_STANDARD_MODEL` |
| `agency_kit/web.py` | `web_tools()` — search backend, selected by `AK_SEARCH` |
| `agency_cli/cli.py` | `agency init / run / check / missions / resume / sync / batch / tui / export` entry point |
| `agents/commander-agency.md` | Commander operating doctrine (prose) |
| `agents/router-agency.md` | Router doctrine + JSON output format |
| `agents/inspector-agency.md` | Inspector 3-check doctrine |
| `.agency/memory/constitution.md` | 10 articles — immutable rules for every command |
| `docs/ARCHITECTURE.md` | Routing table, pipeline diagram, design decisions |

## Run tests

```bash
pip install -e ".[dev]"
pytest tests/ -v          # offline (SDK stubbed in conftest.py)
```

## Environment variables

```bash
AK_ELITE_MODEL=gpt-5.5         # meta-commander, inspector
AK_STANDARD_MODEL=gpt-5.4-mini # routing agent
AK_SEARCH=ddg                  # search backend: ddg | tavily | gemini | openai (auto-detect when unset)
OPENAI_API_KEY=...
# Each installed kit also reads its own vars: PK_ELITE_MODEL, MK_ELITE_MODEL, etc.
```

## Add a department kit

```bash
pip install -e ".[product]"    # adds commander_product  — product lifecycle
pip install -e ".[marketing]"  # adds commander_marketing — positioning, campaigns
pip install -e ".[solve]"      # adds commander_solve    — problem-solving, decision intelligence
pip install -e ".[finance]"    # adds commander_finance  — business case, pricing, pipeline
pip install -e ".[comms]"      # adds commander_comms    — PR, crisis, ESG, events
pip install -e ".[data]"       # adds commander_data     — data strategy, ML/LLMOps, pipelines
pip install -e ".[ops]"        # adds commander_ops      — process, PMO, compliance (NIS2, AI Act)
pip install -e ".[people]"     # adds commander_people   — org design, talent, comp, culture
pip install -e ".[tech]"       # adds commander_tech     — architecture, DevOps, security
pip install -e ".[all]"        # all nine
```

Department imports in `commander.py` are guarded with `try/except ImportError`.
The agency routes around missing departments and notes the gap — never fabricates output.

## Constitution

`.agency/memory/constitution.md` — 10 articles. Articles I (sourcing), II (ethics),
IV (department sovereignty), VI (don't over-route), IX (inspector) are the critical ones.
The constitution is re-read at the start of every `agency.*` command.

## Test architecture

`tests/conftest.py` stubs both the OpenAI Agents SDK (`agents` module) AND all nine
department kits (`product_kit`, `marketing_kit`, `solve_kit`, `finance_kit`, `comms_kit`,
`data_kit`, `ops_kit`, `people_kit`, `tech_kit`) so the full suite runs
offline without any API key.
