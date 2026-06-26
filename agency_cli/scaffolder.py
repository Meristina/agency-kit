"""scaffolder — `agency init`: copy the command pack into a target project and write the
chosen harness's command files (via integrations).

Resolves the payload from the **repo root** when running from a source checkout (dev). A bundled
mode (shipping the pack inside the wheel) is the optional next step; for now `agency init`
requires a source checkout / editable install.
"""

import importlib.util
import shutil
import sys
from pathlib import Path

from . import integrations


def _spec_present(name: str) -> bool:
    """True if `name` is importable. Handles stub modules whose __spec__ is None."""
    try:
        return importlib.util.find_spec(name) is not None
    except ValueError:
        return name in sys.modules

# The downstream kits the agency orchestrates; at least one must be installed.
KITS = ("product_kit", "marketing_kit", "solve_kit", "finance_kit")
KIT_LABELS = {"product_kit": "product-kit", "marketing_kit": "marketing-kit", "solve_kit": "solve-kit", "finance_kit": "finance-kit"}


def sources() -> dict:
    """Locate the payload source. Keys: agency, commands, agents, skills, mode.

    In a source checkout .agency/ is served live from root (so edits take effect without
    re-running sync), but agents/ and skills/ always come from the bundled payload so the
    full 100+ agent bundle is installed regardless of which sibling repos are present.
    """
    here = Path(__file__).resolve()
    root = here.parents[1]
    payload = here.parent / "payload"
    if (root / ".agency").is_dir() and (payload / "agents").is_dir():
        return {"agency": root / ".agency", "commands": root / ".agency" / "commands",
                "agents": payload / "agents", "skills": payload / "skills", "mode": "source"}
    if (payload / "agency").is_dir():
        return {"agency": payload / "agency", "commands": payload / "agency" / "commands",
                "agents": payload / "agents", "skills": payload / "skills", "mode": "bundled"}
    raise RuntimeError("Agency-Kit payload not found — run `agency sync` first, or re-install.")


def init(target: str, agent: str = "claude") -> dict:
    """Scaffold .agency/ + missions/ into `target` and install the harness command pack."""
    src = sources()
    target = Path(target).resolve()
    target.mkdir(parents=True, exist_ok=True)

    # 1) the .agency/ payload (the command pack)
    shutil.copytree(src["agency"], target / ".agency", dirs_exist_ok=True)

    # 2) memory/constitution.md
    constitution = target / ".agency" / "memory" / "constitution.md"
    constitution.parent.mkdir(parents=True, exist_ok=True)
    if not constitution.is_file():
        constitution.write_text(
            "# Agency Constitution\n\n"
            "The agency is the unified orchestrator for product-kit, marketing-kit, solve-kit, and finance-kit.\n",
            encoding="utf-8",
        )

    # 3) missions/ output dir
    (target / "missions").mkdir(exist_ok=True)

    # 4) harness integration (commands + engine for claude)
    summary = integrations.install(agent, src, target)
    summary["target"] = str(target)
    summary["payload_mode"] = src["mode"]
    return summary


def _installed_kits():
    """Return (installed, missing) lists of human-readable kit labels."""
    installed, missing = [], []
    for mod in KITS:
        label = KIT_LABELS[mod]
        (installed if _spec_present(mod) else missing).append(label)
    return installed, missing


def check(target: str = ".") -> list:
    """Lightweight prerequisite/health check. Returns (label, ok, detail) tuples."""
    checks = []

    # .agency/memory/constitution.md exists (prefer target, fall back to payload source)
    constitution = Path(target).resolve() / ".agency" / "memory" / "constitution.md"
    if not constitution.is_file():
        try:
            constitution = sources()["agency"] / "memory" / "constitution.md"
        except RuntimeError:
            pass
    checks.append(("constitution present", constitution.is_file(), str(constitution)))

    # agency_commander importable
    checks.append((
        "agency_commander importable",
        _spec_present("agency_kit.commander"),
        "pip install -e . (editable) or pip install agency-kit",
    ))

    # at least one downstream kit installed
    installed, missing = _installed_kits()
    detail = f"installed: {', '.join(installed) or 'none'}; missing: {', '.join(missing) or 'none'}"
    checks.append(("at least one kit installed (product-kit | marketing-kit | solve-kit | finance-kit)",
                   bool(installed), detail))

    # Agents SDK installed
    checks.append((
        "Agents SDK installed (needed for `agency run`)",
        _spec_present("agents"),
        "pip install openai-agents",
    ))
    return checks
