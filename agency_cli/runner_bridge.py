"""runner_bridge — headless mission path.

Drives the local agent CLI engine (`cli_engine.run_mission_cli`), saves the returned
Mission Dossier to the `~/.agency` store (so `agency missions/resume/export` see it),
and serializes it into `missions/<NNN-slug>/` as Markdown (`dossier.md` +
`deliverable.md`) for a project-local human-readable copy.
"""

import json
import re
from pathlib import Path
from typing import NamedTuple

from agency_kit.store import slug as _store_slug


class MissionResult(NamedTuple):
    """Result of a headless run: the project-local mission folder + the dossier.

    `dossier` carries `verdicts` so callers (e.g. batch_runner) can record the
    real Inspector verdict instead of assuming success.
    """
    path: Path
    dossier: dict


def _last_verdict(dossier: dict) -> str:
    """The Inspector's final verdict token, or 'DELIVERED' if none was recorded."""
    verdicts = dossier.get("verdicts") or []
    return verdicts[-1].get("verdict", "DELIVERED") if verdicts else "DELIVERED"


def _next_id(missions: Path) -> str:
    nums = []
    if missions.exists():
        for p in missions.iterdir():
            m = re.match(r"(\d{3})-", p.name)
            if m:
                nums.append(int(m.group(1)))
    return f"{(max(nums) + 1) if nums else 1:03d}"


def _dossier_md(mission_id: str, d: dict) -> str:
    """Render the dossier dict as Markdown."""
    lines = [f"# Mission Dossier — {mission_id}", ""]
    for key in ("goal", "route", "context", "iteration", "direction_check"):
        lines.append(f"- **{key}**: {d.get(key)}")
    dept_keys = list((d.get("dept_outputs") or {}).keys())
    if dept_keys:
        lines.append(f"- **departments run**: {', '.join(dept_keys)}")
    lines.append("\n## Decisions")
    for dec in d.get("decisions", []) or []:
        lines.append(f"- {dec}")
    lines.append("\n## Sources")
    for i, s in enumerate(d.get("sources", []) or [], 1):
        lines.append(f"{i}. {s}")
    lines.append("\n## Open to verify")
    for o in d.get("open_to_verify", []) or []:
        lines.append(f"- {o}")
    lines.append("\n## Verdicts")
    for v in d.get("verdicts", []) or []:
        lines.append(f"- {json.dumps(v, ensure_ascii=False)}")
    if d.get("residual_risk"):
        lines.append(f"\n## Residual risk\n{d['residual_risk']}")
    return "\n".join(lines) + "\n"


def serialize_dossier(dossier: dict, project_root) -> Path:
    """Write the dossier + deliverable into a fresh missions/<NNN-slug>/ folder."""
    project_root = Path(project_root)
    missions = project_root / "missions"
    missions.mkdir(parents=True, exist_ok=True)
    mission_id = f"{_next_id(missions)}-{_store_slug(dossier.get('goal', ''), max_words=6)}"
    out = missions / mission_id
    out.mkdir()
    (out / "dossier.md").write_text(_dossier_md(mission_id, dossier), encoding="utf-8")
    delivered = dossier.get("delivered") or "(no deliverable)"
    (out / "deliverable.md").write_text(
        f"# Deliverable — {mission_id}\n\n{delivered}\n", encoding="utf-8"
    )
    return out


def _run_and_persist(goal: str, project_root: str, engine: str) -> MissionResult:
    """Drive the engine for `goal`, persist to the ~/.agency store (so
    `agency missions/resume/export` see it) AND serialize the project-local
    missions/<id>/ copy. Shared by run() and resume() so both persist identically.
    """
    from agency_kit import store
    from .engines.cli_engine import run_mission_cli
    dossier = run_mission_cli(goal, engine=engine)
    dossier["mission_id"] = store.new_mission_id(goal)
    store.save(dossier)
    path = serialize_dossier(dossier, Path(project_root))
    return MissionResult(path=path, dossier=dossier)


def run(goal: str, project_root: str = ".", engine: str = "claude-code") -> MissionResult:
    """Headless run: drive a local agent CLI engine, then serialize the dossier.

    engine="claude-code" — `claude -p "..." --allowedTools WebSearch`  (default)
    engine="codex"       — `codex --search exec ... -- "..."`
    engine="gemini"      — `gemini -p "..."`
    No API key required: each CLI uses its own authenticated session + web search.

    Returns a MissionResult (path + dossier) so callers can read the real verdict.
    """
    return _run_and_persist(goal, project_root, engine)


def resume(mission_id: str, project_root: str = ".", engine: str = "claude-code") -> MissionResult:
    """Re-run a saved mission's goal through the engine.

    The engine is single-shot (no quota checkpoint), so 'resume' loads the saved
    dossier, takes its goal, and re-runs it — producing a fresh result that is
    persisted to the store and serialized identically to run().
    """
    from agency_kit import store
    saved = store.load(mission_id)
    goal = saved.get("goal", "")
    return _run_and_persist(goal, project_root, engine)
