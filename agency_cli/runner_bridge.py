"""runner_bridge — headless mission path.

Calls the UNCHANGED engine `agency_kit.mission.run_mission(...)` and serializes the returned
Mission Dossier dict into `missions/<NNN-slug>/` as Markdown (`dossier.md` + `deliverable.md`), so
the headless path writes the same on-disk contract as the interactive harness commands. The rich
per-phase artifacts are produced by the interactive command path; the headless path captures the
carried Dossier + the final delivered text.
"""

import json
import re
from pathlib import Path


def _slug(text: str, max_words: int = 6) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return "-".join(s.split("-")[:max_words]) or "mission"


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
    mission_id = f"{_next_id(missions)}-{_slug(dossier.get('goal', ''))}"
    out = missions / mission_id
    out.mkdir()
    (out / "dossier.md").write_text(_dossier_md(mission_id, dossier), encoding="utf-8")
    delivered = dossier.get("delivered") or "(no deliverable)"
    (out / "deliverable.md").write_text(
        f"# Deliverable — {mission_id}\n\n{delivered}\n", encoding="utf-8"
    )
    return out


def run(goal: str, project_root: str = ".", steer: bool = False, parallel: bool = False) -> Path:
    """Headless run: drive the engine, then serialize. Needs openai-agents + a configured provider.

    parallel=True runs routed departments concurrently where possible (ThreadPoolExecutor).
    steer=True opens the interactive Direction Check gate before execution.
    """
    from agency_kit.mission import auto_proceed, console_direction_check
    dc_fn = console_direction_check if steer else auto_proceed
    if parallel:
        from agency_kit.parallel import run_parallel_mission
        dossier = run_parallel_mission(goal, dc_fn=dc_fn)
    else:
        from agency_kit.mission import run_mission
        dossier = run_mission(goal, dc_fn=dc_fn)
    return serialize_dossier(dossier, Path(project_root))


def resume(mission_id: str, project_root: str = ".", steer: bool = False) -> Path:
    """Resume a saved mission by ID. Loads the dossier and re-enters the loop."""
    from agency_kit.mission import resume_mission, auto_proceed, console_direction_check
    dc_fn = console_direction_check if steer else auto_proceed
    dossier = resume_mission(mission_id, dc_fn=dc_fn)
    return serialize_dossier(dossier, Path(project_root))
