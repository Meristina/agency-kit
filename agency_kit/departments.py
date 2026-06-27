"""Single source of truth for the 9-department roster.

Imported by commander, router, inspector, and CLI so the department names,
roles, grades, and kit names are defined once and can't drift across modules.

Adding a new department: add one row to _ROSTER and that's it — every
instruction string, validator, and CLI help text updates automatically.
"""

# Canonical ordered list — execution order matters for the pipeline.
DEPT_NAMES: tuple = (
    "product", "marketing", "solve", "finance",
    "comms", "data", "ops", "people", "tech",
)

# Fast membership test used by router.classify() and --dry-run.
VALID_DEPTS: frozenset = frozenset(DEPT_NAMES)

# (name, one-line role, grade, optional-kit)
_ROSTER: tuple = (
    ("product",   "Full product lifecycle — discovery, roadmaps, JTBD, PMF, prioritisation, specs, scope",                     "elite",    "product-kit"),
    ("marketing", "Campaigns, content, positioning, brand, launch comms, SEO, growth, analytics",                             "elite",    "marketing-kit"),
    ("solve",     "Problem-solving, root-cause analysis, decision intelligence, architecture, algorithms",                    "elite",    "solve-kit"),
    ("finance",   "Business case, pricing, P&L, cash flow, commercial pipeline, closing, investor reporting, RevOps",         "elite",    "finance-kit"),
    ("comms",     "Corporate comms, PR/media, crisis management, public affairs B2G, ESG/CSRD, events",                       "elite",    "comms-kit"),
    ("data",      "Data strategy, engineering pipelines, analytics/BI, ML/LLMOps, data quality, data products",              "elite",    "data-kit"),
    ("ops",       "Process optimisation, PMO, procurement B2G, EU compliance (NIS2, AI Act, DORA ICT), risk mapping",         "elite",    "ops-kit"),
    ("people",    "Org design, talent acquisition, L&D, performance, compensation, DEI, culture, people analytics",           "elite",    "people-kit"),
    ("tech",      "Architecture, DevOps/IaC, security (OWASP, SOC2, zero trust), engineering excellence, DORA metrics",      "elite",    "tech-kit"),
)


def dept_list_text(indent: str = "  ") -> str:
    """Render the roster as a text block for inclusion in agent instruction strings."""
    return "\n".join(
        f"{indent}- {name:<12} : {role}  ({kit})"
        for name, role, _grade, kit in _ROSTER
    )


def dept_table_md() -> str:
    """Render the roster as a markdown table for documentation files."""
    rows = ["| # | Department | Role | Grade | Kit |", "|---|---|---|---|---|"]
    for i, (name, role, grade, kit) in enumerate(_ROSTER, 1):
        rows.append(f"| {i} | **{name}** | {role} | 🎖️ {grade} | `{kit}` |")
    return "\n".join(rows)
