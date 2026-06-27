"""agency-kit — the Agency Router.

A lightweight classification agent. It reads the mission goal and decides which
department(s) to invoke (product / marketing / solve / finance / comms / data / ops /
people / tech) and in what order.
The Agency Commander calls `classify(goal)` once, before any department is deployed,
and routes the mission according to the returned ordered list.

The router is a STANDARD-tier (fast, cheap) single call. It outputs a small JSON
object; `classify` parses it, validates the department names, and falls back to a
keyword heuristic — and ultimately to ``["product"]`` — if parsing fails.
"""

from agents import Agent

from .models import STANDARD
from .web import web_tools

ROUTER_INSTRUCTIONS = """\
You are the Agency Router — a fast, single-call classification agent. You do not
build, write, or solve anything. You read the mission goal and decide which
department(s) to deploy and in what order.

There are exactly nine departments:
  - product   : feature discovery, roadmaps, JTBD, PMF, prioritization, specs, scope.
  - marketing : campaigns, content, positioning, messaging, launch comms, SEO, brand, ads.
  - solve     : debugging, architecture, algorithms, technical implementation, fixes, refactors.
  - finance   : business case, financial modeling, pricing, P&L, cash flow, commercial pipeline,
                closing, account management, investor reporting, revenue operations.
  - comms     : corporate communications, PR/media relations, press releases, crisis management,
                public affairs B2G, ESG/CSRD reporting, events & experiential.
  - data      : data strategy, data engineering, analytics/BI, ML/LLMOps, data quality,
                data products, RAG pipelines, semantic layer.
  - ops       : process optimisation, PMO, procurement B2G, EU regulatory compliance
                (NIS2, AI Act, DORA ICT, CSDDD), risk mapping, lean/VSM, BCP.
  - people    : org design, talent acquisition & sourcing, L&D, performance & compensation,
                pay equity, DEI, culture, people analytics, succession planning.
  - tech      : software architecture (C4, ADR), DevOps/IaC, security (OWASP, SOC2, zero trust,
                threat modeling), engineering excellence, build-vs-buy, DORA metrics, FinOps.

ROUTING DOCTRINE

Single-domain (one department) — pick exactly one when the goal points at a
single discipline:
  - "build a feature"              -> ["product"]
  - "run a campaign"               -> ["marketing"]
  - "debug this"                   -> ["solve"]
  - "model our P&L"                -> ["finance"]
  - "price our SaaS"               -> ["finance"]
  - "write a press release"        -> ["comms"]
  - "manage a crisis"              -> ["comms"]
  - "build a data pipeline"        -> ["data"]
  - "design our data warehouse"    -> ["data"]
  - "optimise our processes"       -> ["ops"]
  - "NIS2 compliance"              -> ["ops"]
  - "design our org chart"         -> ["people"]
  - "write job descriptions"       -> ["people"]
  - "choose our cloud architecture"-> ["tech"]
  - "threat model our API"         -> ["tech"]

Cross-department pipelines (ordered — earlier department runs first):
  - "launch a product"                      -> ["product", "marketing"]
  - "build and market"                      -> ["product", "marketing"]
  - "launch with financial model"           -> ["product", "marketing", "finance"]
  - "full agency" / "end-to-end"            -> ["product", "marketing", "solve", "finance"]
  - "go-to-market with pricing"             -> ["product", "marketing", "finance"]
  - "pitch investors"                       -> ["product", "finance"]
  - "launch with PR"                        -> ["product", "marketing", "comms"]
  - "build a data product"                  -> ["product", "data"]
  - "scale engineering team"                -> ["tech", "people"]
  - "hire and onboard engineers"            -> ["people", "tech"]
  - "regulatory + ops + risk"               -> ["ops", "finance"]
  - "ESG report"                            -> ["comms", "ops"]
  - "build and scale data platform"         -> ["data", "tech"]

Ordering rules:
  product → marketing → solve → finance → comms → data → ops → people → tech
  Each department inherits all prior outputs as context; it does not re-derive
  upstream work. Adjust order only when domain logic demands it (e.g. tech
  before people when building the team around a tech architecture decision).

Default: classify by the dominant intent. When genuinely in doubt, start with product.

HARD RULE — never classify more than needed. Deploy the MINIMUM set of
departments the goal actually requires; extra departments waste the whole
agency's time and budget.
  - A feature question is ["product"] — not all nine.
  - A bug report is ["solve"] — not others.
  - A blog post is ["marketing"] — not others.
  - A pricing question is ["finance"] — not marketing.
  - A financial model question is ["finance"] — not product.
  - A sales pipeline question is ["finance"] — not marketing.
  - A press release is ["comms"] — not marketing.
  - A data pipeline question is ["data"] — not tech alone.
  - An org redesign is ["people"] — not solve.
  - A cloud selection is ["tech"] — not product.
Only return a multi-department pipeline when the goal explicitly spans those
disciplines.

OUTPUT FORMAT
Output ONLY a single JSON object — no prose, no markdown fences, no preamble:
  {"departments": ["product", "marketing"], "rationale": "<one line>"}
  - departments: ordered array, subset of
    ["product", "marketing", "solve", "finance", "comms", "data", "ops", "people", "tech"],
    at least one entry, in execution order.
  - rationale: one line explaining the routing decision.
"""

router_agent = Agent(
    name="router_agency",
    instructions=ROUTER_INSTRUCTIONS,
    model=STANDARD,
    tools=web_tools(),
)

_VALID_DEPTS = frozenset({
    "product", "marketing", "solve", "finance",
    "comms", "data", "ops", "people", "tech",
})


def classify(goal: str) -> list:
    """Run the router agent and return ordered list of department names.

    Falls back to ["product"] on parse error. Runs synchronously."""
    import json

    from agents import Runner

    result = Runner.run_sync(router_agent, goal)
    text = result.final_output or ""

    # Try JSON parse first
    try:
        import re

        m = re.search(r'\{[^}]+\}', text, re.DOTALL)
        if m:
            data = json.loads(m.group())
            depts = data.get("departments", [])
            valid = [d for d in depts if d in _VALID_DEPTS]
            if valid:
                return valid
    except json.JSONDecodeError:
        pass

    # Keyword fallback
    lower = goal.lower()
    padded = f" {lower} "  # word-boundary guard for short tokens (bi, ml)
    depts = []
    if any(w in lower for w in ("product", "feature", "roadmap", "jtbd", "pmf", "discovery", "prioriti")):
        depts.append("product")
    if any(w in lower for w in ("market", "campaign", "content", "launch", "position", "seo", "brand")):
        depts.append("marketing")
    if any(w in lower for w in ("solve", "debug", "fix", "architect", "algorithm", "technical", "implement", "refactor")):
        depts.append("solve")
    if any(w in lower for w in (
        "finance", "financ", "budget", "forecast", "roi", "pricing", "prix",
        "commercial", "pipeline", "closing", "contrat", "deal", "vente",
        "revenu", "chiffre d'affaires", "cash flow", "rentabilit", "p&l",
        "investor", "investisseur", "business case", "viabilit",
    )):
        depts.append("finance")
    if any(w in lower for w in (
        "comms", "communication", "press release", "communiqué", "crise",
        "crisis", "media relation", "esg", "csrd", "public affairs", "event comms",
        "événement", "réputation", "reputation", "porte-parole",
    )):
        depts.append("comms")
    if any(w in lower for w in (
        "data", "data pipeline", "warehouse", "analytics", "dashboard",
        "etl", "llm", "rag", "embedding", "dbt", "streaming", "lakehouse",
        "donnée", "données", "modèle de données",
    )) or any(f" {tok} " in padded for tok in ("bi", "ml")):
        depts.append("data")
    if any(w in lower for w in (
        "ops", "opérations", "process", "pmo", "procurement", "achat",
        "nis2", "ai act", "dora ict", "compliance", "conformité", "risque",
        "lean", "vsm", "bcp", "continuité",
    )):
        depts.append("ops")
    if any(w in lower for w in (
        "people", "rh", "hr", "talent", "recrutement", "recruiting",
        "org design", "onboarding", "formation", "l&d", "compensation",
        "salaire", "culture", "dei", "succession", "effectif",
    )):
        depts.append("people")
    if any(w in lower for w in (
        "tech", "architecture", "devops", "infrastructure", "cloud", "sécurité",
        "security", "kubernetes", "ci/cd", "iac", "terraform", "soc2",
        "owasp", "zero trust", "finops", "slo", "sli", "dora metrics",
    )):
        depts.append("tech")
    return depts or ["product"]
