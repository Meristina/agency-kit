"""agency-kit — the Agency Router.

A lightweight classification agent. It reads the mission goal and decides which
department(s) to invoke (product / marketing / solve) and in what order. The
Agency Commander calls `classify(goal)` once, before any department is deployed,
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

There are exactly four departments:
  - product   : feature discovery, roadmaps, JTBD, PMF, prioritization, specs, scope.
  - marketing : campaigns, content, positioning, messaging, launch comms, SEO, brand, ads.
  - solve     : debugging, architecture, algorithms, technical implementation, fixes, refactors.
  - finance   : business case, financial modeling, pricing, P&L, cash flow, commercial pipeline,
                closing, account management, investor reporting, revenue operations.

ROUTING DOCTRINE

Single-domain (one department) — pick exactly one when the goal points at a
single discipline:
  - "build a feature"         -> ["product"]
  - "run a campaign"          -> ["marketing"]
  - "debug this"              -> ["solve"]
  - "model our P&L"           -> ["finance"]
  - "price our SaaS"          -> ["finance"]
  - "build a sales pipeline"  -> ["finance"]

Cross-department pipelines (ordered — earlier department runs first):
  - "launch a product"                  -> ["product", "marketing"]
  - "build and market"                  -> ["product", "marketing"]
  - "solve and explain"                 -> ["solve", "marketing"]
  - "launch with financial model"       -> ["product", "marketing", "finance"]
  - "full agency" / "end-to-end"        -> ["product", "marketing", "solve", "finance"]
  - "go-to-market with pricing"         -> ["product", "marketing", "finance"]
  - "pitch investors"                   -> ["product", "finance"]

Finance runs AFTER product, marketing, and solve when they are co-deployed — it
evaluates their upstream outputs; it does not re-derive product or marketing strategy.

Default: classify by the dominant intent. When genuinely in doubt, start with product.

HARD RULE — never classify more than needed. Deploy the MINIMUM set of
departments the goal actually requires; extra departments waste the whole
agency's time and budget.
  - A feature discovery question is ["product"] — not all four.
  - A bug report is ["solve"] — not others.
  - A blog post is ["marketing"] — not others.
  - A financial model question is ["finance"] — not product.
  - A pricing strategy question is ["finance"] — not marketing.
Only return a multi-department pipeline when the goal explicitly spans those
disciplines (e.g. "launch", "build and market", "pitch investors", "end-to-end").

OUTPUT FORMAT
Output ONLY a single JSON object — no prose, no markdown fences, no preamble:
  {"departments": ["product", "marketing"], "rationale": "<one line>"}
  - departments: ordered array, subset of ["product", "marketing", "solve"],
    at least one entry, in execution order.
  - rationale: one line explaining the routing decision.
"""

router_agent = Agent(
    name="router_agency",
    instructions=ROUTER_INSTRUCTIONS,
    model=STANDARD,
    tools=web_tools(),
)


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
            valid = [d for d in depts if d in ("product", "marketing", "solve", "finance")]
            if valid:
                return valid
    except json.JSONDecodeError:
        pass

    # Keyword fallback
    lower = goal.lower()
    depts = []
    if any(w in lower for w in ("product", "feature", "roadmap", "jtbd", "pmf", "discovery", "prioriti")):
        depts.append("product")
    if any(w in lower for w in ("market", "campaign", "content", "launch", "position", "seo", "brand")):
        depts.append("marketing")
    if any(w in lower for w in ("solve", "debug", "fix", "architect", "algorithm", "technical", "implement")):
        depts.append("solve")
    if any(w in lower for w in (
        "finance", "financ", "budget", "forecast", "roi", "pricing", "prix",
        "commercial", "pipeline", "closing", "contrat", "deal", "vente",
        "revenu", "chiffre d'affaires", "cash flow", "rentabilit", "p&l",
        "investor", "investisseur", "business case", "viabilit",
    )):
        depts.append("finance")
    return depts or ["product"]
