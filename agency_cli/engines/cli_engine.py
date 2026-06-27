"""cli_engine — run missions via Claude Code CLI or Codex CLI.

Uses subprocess instead of the OpenAI Agents SDK.
No API key needed: the CLI tool uses its own authenticated session.

Supported engines:
  claude-code   claude --allowedTools WebSearch -p "<prompt>"   (live web search)
  codex         codex --search exec "<prompt>"                  (live web search)
"""

import json
import re
import subprocess
from pathlib import Path

# Execution commands — WebSearch enabled for live research
ENGINES: dict = {
    "claude-code": ["claude", "--allowedTools", "WebSearch", "-p"],
    "codex": ["codex", "--search", "exec", "--color", "never", "--sandbox", "read-only", "--"],
}

# Routing commands — no web search needed, just classification
_ROUTE_CMD: dict = {
    "claude-code": ["claude", "-p"],
    "codex": ["codex", "--color", "never", "--sandbox", "read-only", "--"],
}

_VALID_DEPTS = ("product", "marketing", "solve", "finance", "comms", "data", "ops", "people", "tech")


# ── helpers ───────────────────────────────────────────────────────────────────

def _agents_dir() -> Path:
    here = Path(__file__).resolve()
    candidate = here.parents[2] / "agents"
    if candidate.is_dir():
        return candidate
    candidate = here.parents[1] / "payload" / "agents"
    if candidate.is_dir():
        return candidate
    raise RuntimeError("agents/ directory not found — run `agency sync` first.")


def _strip_frontmatter(text: str) -> str:
    """Remove YAML frontmatter (--- ... ---) so it isn't parsed as CLI flags."""
    if not text.startswith("---"):
        return text
    end = text.find("\n---", 3)
    return text[end + 4:].lstrip() if end != -1 else text


def _load(name: str) -> str:
    try:
        raw = (_agents_dir() / f"{name}.md").read_text(encoding="utf-8")
        return _strip_frontmatter(raw)
    except FileNotFoundError:
        return ""


def _call(cmd_prefix: list, prompt: str, timeout: int = 900) -> str:
    """Invoke the CLI with a prompt; return stdout. Raises RuntimeError on failure."""
    proc = subprocess.run(
        cmd_prefix + [prompt],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if proc.returncode != 0:
        stderr = proc.stderr.strip()
        raise RuntimeError(
            f"CLI engine exited {proc.returncode}"
            + (f": {stderr}" if stderr else "")
        )
    return proc.stdout.strip()


def _route_via_cli(engine: str, goal: str) -> list:
    """AI-powered routing via CLI — asks the model which departments to invoke.

    Falls back to keyword_classify() if the model returns unparseable output.
    """
    route_cmd = _ROUTE_CMD.get(engine, _ROUTE_CMD["claude-code"])
    prompt = (
        "You are an agency mission router. Given the mission goal below, decide which "
        "departments are needed and in what order.\n\n"
        f"Available departments: {', '.join(_VALID_DEPTS)}\n\n"
        "Rules:\n"
        "- Only include departments genuinely needed for this goal\n"
        "- Typical order: product → marketing → solve → finance → data → ops → people → tech → comms\n"
        "- For a market study: product + marketing + solve + finance\n"
        "- For a tech product: product + tech + marketing\n"
        "- For a business plan: product + marketing + finance + ops\n"
        "- Art. VI: do NOT over-route; deploy the minimum set the goal requires\n\n"
        "Return ONLY a valid JSON array of department names, nothing else.\n"
        "Example: [\"product\", \"marketing\", \"finance\"]\n\n"
        f"Mission goal: {goal}"
    )

    try:
        response = _call(route_cmd, prompt, timeout=60)
        match = re.search(r'\[.*?\]', response, re.DOTALL)
        if match:
            depts = json.loads(match.group())
            valid = [d for d in depts if d in _VALID_DEPTS]
            if valid:
                return valid
    except Exception:
        pass

    # Fallback: keyword heuristic (no API call)
    from agency_kit.router import keyword_classify
    return keyword_classify(goal)


_MAX_DEPT_CHARS = 4000  # per department, to keep prompts manageable


def _fmt_dept_outputs(dept_outputs: dict) -> str:
    if not dept_outputs:
        return "(no prior department output)"
    parts = []
    for dept, output in dept_outputs.items():
        truncated = output[:_MAX_DEPT_CHARS]
        suffix = f"\n... [truncated — {len(output) - _MAX_DEPT_CHARS} chars omitted]" if len(output) > _MAX_DEPT_CHARS else ""
        parts.append(f"### {dept.upper()}\n{truncated}{suffix}")
    return "\n\n".join(parts)


# ── main entry point ──────────────────────────────────────────────────────────

def run_mission_cli(goal: str, engine: str = "claude-code") -> dict:
    """Run a full mission via a local CLI tool.

    Returns the same dossier dict shape as agency_kit.mission.run_mission().
    Web search is live — the CLI tool fetches real pages at execution time.
    """
    cmd = ENGINES.get(engine)
    if cmd is None:
        raise ValueError(f"Unknown engine '{engine}'. Available: {', '.join(ENGINES)}")

    # 1. Route — via the CLI model (AI, not keyword heuristic)
    print(f"[{engine}] routing...", end=" ", flush=True)
    route = _route_via_cli(engine, goal)
    print(f"{' → '.join(route)}", flush=True)

    # 2. Run each department sequentially (with live web search)
    dept_outputs: dict = {}
    for dept in route:
        print(f"[{engine}] {dept}...", end=" ", flush=True)
        shared = _load(f"_shared-{dept}")
        prompt = (
            f"You are the {dept} department commander for an AI agency.\n\n"
            f"MISSION GOAL:\n{goal}\n\n"
            f"PRIOR DEPARTMENT OUTPUTS:\n{_fmt_dept_outputs(dept_outputs)}\n\n"
            + (f"DEPARTMENT DOCTRINE:\n{shared}\n\n" if shared else "")
            + "Produce a complete, detailed deliverable for this department.\n"
            "CRITICAL: Use WebSearch to find current, real data (today's date, live sources). "
            "Never invent statistics, market sizes, or citations. "
            "Every factual claim must come from a real source you have searched and verified."
        )
        dept_outputs[dept] = _call(cmd, prompt)
        print("done", flush=True)

    # 3. Synthesise (with live web search)
    print(f"[{engine}] synthesising...", end=" ", flush=True)
    commander_doc = _load("commander-agency")
    synth_prompt = (
        (f"{commander_doc}\n\n" if commander_doc else "")
        + f"MISSION GOAL:\n{goal}\n\n"
        f"ROUTE: {route}\n\n"
        f"DEPARTMENT OUTPUTS:\n{_fmt_dept_outputs(dept_outputs)}\n\n"
        "Synthesise all department outputs into a final cross-department mission dossier. "
        "List decisions taken, open items to verify, and all sources cited with URLs and dates."
    )
    delivered = _call(cmd, synth_prompt)
    print("done", flush=True)

    # 4. Inspect (verify sources are real and live)
    print(f"[{engine}] inspecting...", end=" ", flush=True)
    inspector_doc = _load("inspector-agency")
    inspect_prompt = (
        (f"{inspector_doc}\n\n" if inspector_doc else "")
        + f"MISSION GOAL:\n{goal}\n\n"
        f"DELIVERABLE:\n{delivered}\n\n"
        "Use WebSearch to spot-check at least 3 sources cited. "
        "Issue a verdict: PASS, PASS-WITH-FIXES, or VETO. "
        "Flag any invented data, outdated figures, or unverifiable claims."
    )
    verdict_text = _call(cmd, inspect_prompt)
    print("done", flush=True)

    return {
        "goal": goal,
        "route": route,
        "context": None,
        "dept_outputs": dept_outputs,
        "decisions": [],
        "sources": [],
        "open_to_verify": [],
        "direction_check": None,
        "verdicts": [{"engine": engine, "verdict": verdict_text}],
        "iteration": 1,
        "delivered": delivered,
    }
