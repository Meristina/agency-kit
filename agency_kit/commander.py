"""
COMMANDER — Agency  🎖️ elite

Meta-orchestrator for the AI Agency. Sits one level above the department
commanders. It does not do product, marketing, or problem-solving work itself —
it classifies the mission, deploys the right department commanders in sequence,
carries each department's output forward as context into the next, synthesises a
single cross-department deliverable, and submits it to the agency inspector.

Chain of command (Constitution Art. IV, VI, IX):
  CLASSIFY    → router_agency       (🔵 standard) — which departments to invoke
  EXECUTE     → commander_product   (🎖️ elite, product-kit   — if installed)
              → commander_marketing (🎖️ elite, marketing-kit  — if installed)
              → commander_solve     (🎖️ elite, solve-kit      — if installed)
              → commander_finance   (🎖️ elite, finance-kit    — if installed)
              → commander_comms     (🎖️ elite, comms-kit      — if installed)
              → commander_data      (🎖️ elite, data-kit       — if installed)
              → commander_ops       (🎖️ elite, ops-kit        — if installed)
              → commander_people    (🎖️ elite, people-kit     — if installed)
              → commander_tech      (🎖️ elite, tech-kit       — if installed)
  SYNTHESIZE  → combine into one cross-department deliverable
  AUDIT       → inspector_agency    (🎖️ elite) — mandatory cross-department gate

Departments are optional extras. If a department package is not installed, its
commander tool is absent from the toolset — the commander routes around it and
notes the gap, never fabricating its output.
"""

from agents import Agent

from .departments import DEPT_NAMES, dept_list_text
from .models import ELITE
from .web import web_tools
from .inspector import agency_inspector
from .router import router_agent

# ---------------------------------------------------------------------------
# Optional department commanders — present only when their kit is installed.
# Each is wired into the toolset conditionally so an absent department simply
# disappears from the route rather than breaking import (Constitution Art. IV).
# ---------------------------------------------------------------------------
try:
    from product_kit.commander import commander_product
    _HAS_PRODUCT = True
except ImportError:
    commander_product = None
    _HAS_PRODUCT = False

try:
    try:
        from marketing_kit.commander import commander_marketing
    except ImportError:
        from marketing_kit.commander import commander as commander_marketing
    _HAS_MARKETING = True
except ImportError:
    commander_marketing = None
    _HAS_MARKETING = False

try:
    try:
        from solve_kit.commander import commander_solve
    except ImportError:
        from solve_kit.commander import commander as commander_solve
    _HAS_SOLVE = True
except ImportError:
    commander_solve = None
    _HAS_SOLVE = False

try:
    from finance_kit.commander import commander_finance
    _HAS_FINANCE = True
except ImportError:
    commander_finance = None
    _HAS_FINANCE = False

try:
    from comms_kit.commander import commander_comms
    _HAS_COMMS = True
except ImportError:
    commander_comms = None
    _HAS_COMMS = False

try:
    from data_kit.commander import commander_data
    _HAS_DATA = True
except ImportError:
    commander_data = None
    _HAS_DATA = False

try:
    from ops_kit.commander import commander_ops
    _HAS_OPS = True
except ImportError:
    commander_ops = None
    _HAS_OPS = False

try:
    from people_kit.commander import commander_people
    _HAS_PEOPLE = True
except ImportError:
    commander_people = None
    _HAS_PEOPLE = False

try:
    from tech_kit.commander import commander_tech
    _HAS_TECH = True
except ImportError:
    commander_tech = None
    _HAS_TECH = False


# ===========================================================================
# COMMANDER INSTRUCTIONS
# ===========================================================================

# Department list generated from departments.py — single source of truth.
_COMMANDER_DEPT_BLOCK = dept_list_text()

COMMANDER_INSTRUCTIONS = (
    """
You are the agency commander, the meta-orchestrator of the AI Agency. You sit
one level above the department commanders. You do NOT do product work, marketing
work, or problem-solving work yourself. You classify the mission, deploy the
right departments in the right order, carry each department's output forward as
context into the next, synthesise one cross-department deliverable, and submit
it to the agency inspector before anything ships.

You command nine optional departments and one cross-department auditor:
  - classify  (router_agency)    -> which departments the mission needs
"""
    + _COMMANDER_DEPT_BLOCK
    + """
  - inspect   (inspector_agency) -> cross-department quality gate (mandatory)

A department tool is present ONLY when its kit is installed. If a routed
department's tool is absent, route around it and record the gap in the dossier.
Never fabricate a department's output.

CONSTITUTION CONSTRAINTS (non-negotiable):
- Art. IV  (department sovereignty): Each department commander is the final
           authority on its own discipline's method, sequencing, and internal
           quality bar. You orchestrate BETWEEN departments; you never reach
           inside a department to rewrite its deliverable. Deficient output is
           fixed by re-entering THAT department with a sharpened brief, not by
           patching it yourself.
- Art. VI  (don't over-route): Deploy the fewest departments the mission
           genuinely needs. A pure positioning question does not need product.
           A root-cause investigation may need only solve. Single-department
           missions are normal and correct. Justify the route in one line per
           department; never fire every department reflexively.
- Art. IX  (the inspector is mandatory): Call inspect on the synthesised
           deliverable at the end of every loop. Veto power — a failing check
           blocks delivery until the responsible department fixes. The inspector
           audits only; it never authors the fix.

PHASE 0 — CLASSIFY (call: classify):
Call the router with the mission goal. It returns:
  - route: the ordered subset of {product, marketing, solve, finance, comms, data, ops, people, tech} to invoke.
  - rationale: one line per department on why it is in or out.
Record both in the dossier (route field). Do not deploy a department the router
excluded, and do not silently add one it omitted. If you believe the route is
wrong, state the disagreement in the dossier and re-run classify with a
sharpened goal rather than overriding by fiat (Art. VI).
If the brief is thin, ask at most 2-3 genuinely-unanswered clarifying questions
(mission type, stage/context, constraints) BEFORE classifying. If it is already
rich, classify immediately.

PHASE 1 — EXECUTE (calls: routed departments in order, per route):
Run each routed department in order. Each department's output is fed forward as
context into the next — a department never starts from the raw goal alone once
an upstream department has run.
Default order when multiple departments are routed:
  1. product   — establishes what is built, for whom, and why. Its strategy and
                 outcome targets become context for marketing.
  2. marketing — takes the product output as ground truth for positioning,
                 messaging, content, and campaigns. It does not re-derive
                 product strategy; it builds on it.
  3. solve     — applies problem-solving / decision intelligence to whatever
                 blocker, trade-off, or open decision upstream surfaced (or runs
                 standalone if it is the only routed department).
  4. finance   — evaluates economic viability, pricing, and commercial strategy.
                 Takes product, marketing, and solve outputs as inputs.
  5. comms     — corporate communications, PR/media, crisis management, public
                 affairs, ESG/CSRD, and events. Runs after product/marketing
                 when messaging and narrative are needed externally.
  6. data      — data strategy, engineering pipelines, analytics/BI, ML/LLMOps,
                 data quality, and data products. Runs when the mission involves
                 building or scaling data infrastructure or intelligence.
  7. ops       — process optimisation, PMO, procurement B2G, legal-EU compliance
                 (NIS2, AI Act, DORA ICT), risk mapping. Runs when the mission
                 involves operational delivery, regulatory fit, or scaling ops.
  8. people    — org design, talent acquisition, L&D, performance, compensation,
                 culture, and people analytics. Runs when the mission involves
                 the organisation's human capital.
  9. tech      — software architecture, DevOps/IaC, security (OWASP, SOC2, zero
                 trust), engineering excellence, build-vs-buy, DORA metrics.
                 Runs when the mission involves technology decisions or delivery.
For each department call: pass the goal PLUS the accumulated upstream
dept_outputs as context; capture the full deliverable into dept_outputs[<dept>];
carry it forward — never reset or drop an upstream output.
If a routed department's tool is absent (kit not installed), skip it and record
the gap; do not invent its work (Art. IV).

PHASE 2 — SYNTHESIZE:
Combine the department outputs into ONE coherent cross-department deliverable —
not a stapled stack of reports.
  - Reconcile overlaps: when two departments speak to the same point, resolve
    them into a single consistent narrative; name the source department for each
    load-bearing claim.
  - Surface contradictions: if departments disagree, state the tension and
    either resolve it with reasoning or escalate it as an open decision.
  - Produce the joined-up answer: the agency speaks with one voice, traceable
    to each department's contribution.
Record the combined artefact in the dossier (synthesis field).

PHASE 3 — AUDIT (call: inspect, mandatory every loop):
Call the agency inspector on the synthesised deliverable. It is a
CROSS-DEPARTMENT gate checking what no single-department inspector can:
  - Coherence: do the departments actually agree, or were contradictions papered
    over?
  - Hand-off integrity: was each department's output genuinely carried forward,
    or did context get dropped between stages?
  - Sources: every cross-department claim cited or tagged [assumption — verify];
    no invented figures bridging departments.
  - No gaps: routed scope fully covered; any uninstalled department's absence
    disclosed, not silently ignored.
Veto power: a failing check blocks delivery. Re-enter the responsible department
(or re-run synthesis) to fix, then re-audit. Record each verdict in the dossier
(verdicts field).

CROSS-DEPARTMENT DOSSIER (carry forward, never reset):
- goal:         original mission goal + any FRAME clarifications.
- route:        router's ordered department list + per-department rationale.
- dept_outputs: one entry per deployed department, full deliverable, versioned
                on re-entry.
- synthesis:    the combined cross-department deliverable.
- verdicts:     inspector pass/fail per check + revision history.

CONTROL LOOP:
  CLASSIFY -> EXECUTE depts in route order (each output -> next dept's context)
           -> SYNTHESIZE -> AUDIT -> DONE (or re-enter responsible department /
           re-synthesise).
Cap at MAX_ITERS = 3. If the inspector still fails after 3 loops, deliver the
best available cross-department result with residual risk explicitly stated —
never loop silently. On a fix, re-enter only the responsible department or
re-run synthesis; do not restart classification unless the goal fundamentally
changed.

PRINCIPLES:
- Classify before you deploy. The route is a recorded decision, not a reflex.
- Don't over-route (Art. VI). Fewer departments, correctly chosen, wins.
- Department sovereignty (Art. IV). Orchestrate between departments; never
  rewrite their work. Fix deficiencies by re-entering the department.
- Output feeds forward. Marketing inherits product's truth; solve inherits the
  surfaced decision. Context is never dropped between stages.
- Synthesise, don't staple. One agency voice, contradictions surfaced.
- The inspector is mandatory (Art. IX). Nothing ships without the
  cross-department audit.
- Truth over flattery. Surface cross-department tension, uncertainty, and any
  uninstalled-department gaps explicitly.
- Mirror the user's language.
"""
)


# ===========================================================================
# Commander — Agency
# ===========================================================================

agency_commander = Agent(
    name="commander_agency",
    instructions=COMMANDER_INSTRUCTIONS,
    model=ELITE,
    tools=[
        router_agent.as_tool(
            tool_name="classify",
            tool_description=(
                "Classify the mission goal: return the ordered subset of "
                "departments {product, marketing, solve, finance, comms, data, ops, people, tech} "
                "to invoke, with a one-line rationale per department. Call this FIRST, "
                "before deploying any department."
            ),
        ),
        *(
            [
                commander_product.as_tool(
                    tool_name="product",
                    tool_description=(
                        "Deploy product-kit: the full product lifecycle "
                        "(discovery, strategy, prioritisation, design, delivery, "
                        "measurement). Pass the goal plus upstream department "
                        "outputs as context. Establishes what is built, for whom, "
                        "and why. (🎖️ elite)"
                    ),
                )
            ]
            if _HAS_PRODUCT
            else []
        ),
        *(
            [
                commander_marketing.as_tool(
                    tool_name="marketing",
                    tool_description=(
                        "Deploy marketing-kit: research, positioning, content, "
                        "campaigns, and analytics. Pass the goal plus the product "
                        "output as context — build on the product strategy, do not "
                        "re-derive it. (🎖️ elite)"
                    ),
                )
            ]
            if _HAS_MARKETING
            else []
        ),
        *(
            [
                commander_solve.as_tool(
                    tool_name="solve",
                    tool_description=(
                        "Deploy solve-kit: problem-solving, root-cause analysis, "
                        "and decision intelligence. Pass the goal plus upstream "
                        "outputs as context — applies to the blocker, trade-off, "
                        "or open decision surfaced upstream, or runs standalone. "
                        "(🎖️ elite)"
                    ),
                )
            ]
            if _HAS_SOLVE
            else []
        ),
        *(
            [
                commander_finance.as_tool(
                    tool_name="finance",
                    tool_description=(
                        "Deploy finance-kit: business case, financial modeling, "
                        "pricing strategy, commercial pipeline, account management, "
                        "and investor reporting. Pass the goal plus upstream "
                        "department outputs as context — evaluates viability and "
                        "commercial strategy built on upstream work. (🎖️ elite)"
                    ),
                )
            ]
            if _HAS_FINANCE
            else []
        ),
        *(
            [
                commander_comms.as_tool(
                    tool_name="comms",
                    tool_description=(
                        "Deploy comms-kit: corporate communications, PR/media "
                        "relations, crisis management, public affairs B2G, "
                        "ESG/CSRD reporting, and events. Pass the goal plus "
                        "upstream department outputs as context. (🎖️ elite)"
                    ),
                )
            ]
            if _HAS_COMMS
            else []
        ),
        *(
            [
                commander_data.as_tool(
                    tool_name="data",
                    tool_description=(
                        "Deploy data-kit: data strategy, engineering pipelines, "
                        "analytics/BI, ML/LLMOps, data quality, and data products. "
                        "Pass the goal plus upstream outputs as context. (🎖️ elite)"
                    ),
                )
            ]
            if _HAS_DATA
            else []
        ),
        *(
            [
                commander_ops.as_tool(
                    tool_name="ops",
                    tool_description=(
                        "Deploy ops-kit: process optimisation, PMO, procurement "
                        "B2G, EU regulatory compliance (NIS2, AI Act, DORA ICT), "
                        "and risk mapping. Pass the goal plus upstream outputs as "
                        "context. (🎖️ elite)"
                    ),
                )
            ]
            if _HAS_OPS
            else []
        ),
        *(
            [
                commander_people.as_tool(
                    tool_name="people",
                    tool_description=(
                        "Deploy people-kit: org design, talent acquisition, L&D, "
                        "performance & compensation, culture, and people analytics. "
                        "Pass the goal plus upstream outputs as context. (🎖️ elite)"
                    ),
                )
            ]
            if _HAS_PEOPLE
            else []
        ),
        *(
            [
                commander_tech.as_tool(
                    tool_name="tech",
                    tool_description=(
                        "Deploy tech-kit: software architecture, DevOps/IaC, "
                        "security (OWASP, SOC2, zero trust), engineering excellence, "
                        "build-vs-buy decisions, and DORA metrics. Pass the goal "
                        "plus upstream outputs as context. (🎖️ elite)"
                    ),
                )
            ]
            if _HAS_TECH
            else []
        ),
        agency_inspector.as_tool(
            tool_name="inspect",
            tool_description=(
                "Agency inspector: mandatory cross-department audit of the "
                "synthesised deliverable. Checks coherence, hand-off integrity, "
                "sources, and scope gaps across departments. Veto power — a "
                "failing check blocks delivery until the responsible department "
                "fixes. Audits only; never authors the fix."
            ),
        ),
        *web_tools(),
    ],
)


# Exported for CLI --dry-run: maps dept name → True if the kit is installed.
# Explicit dict so adding a department to DEPT_NAMES without updating this dict
# raises a KeyError rather than silently truncating via zip().
DEPT_INSTALLED: dict = {
    "product":   _HAS_PRODUCT,
    "marketing": _HAS_MARKETING,
    "solve":     _HAS_SOLVE,
    "finance":   _HAS_FINANCE,
    "comms":     _HAS_COMMS,
    "data":      _HAS_DATA,
    "ops":       _HAS_OPS,
    "people":    _HAS_PEOPLE,
    "tech":      _HAS_TECH,
}


# ===========================================================================
# __main__ — demo entry point
# ===========================================================================

if __name__ == "__main__":
    import asyncio

    from agents import Runner

    async def _demo() -> None:
        installed = [
            name
            for name, present in (
                ("product", _HAS_PRODUCT),
                ("marketing", _HAS_MARKETING),
                ("solve", _HAS_SOLVE),
                ("finance", _HAS_FINANCE),
                ("comms", _HAS_COMMS),
                ("data", _HAS_DATA),
                ("ops", _HAS_OPS),
                ("people", _HAS_PEOPLE),
                ("tech", _HAS_TECH),
            )
            if present
        ]
        goal = (
            "We're launching a developer-focused observability SaaS next quarter. "
            "We need to decide what to build first, how to position it against "
            "incumbents, and resolve whether to lead go-to-market with a free tier "
            "or a design-partner program."
        )
        print("=== Agency Commander — Demo ===")
        print(f"Departments installed: {installed or 'none'}")
        print(f"Goal: {goal}\n")
        result = await Runner.run(agency_commander, goal)
        print(result.final_output)

    asyncio.run(_demo())
