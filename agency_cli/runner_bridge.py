"""runner_bridge — headless mission path.

Drives the local agent CLI engine (`cli_engine.run_mission_cli`), saves the returned
Mission Dossier to the `~/.agency` store (so `agency missions/resume/export` see it),
and serializes it into `missions/<NNN-slug>/` as Markdown (`dossier.md` +
`deliverable.md`) for a project-local human-readable copy.
"""

import json
import re
from pathlib import Path
from typing import Callable, NamedTuple, Optional

from agency_kit.store import slug as _store_slug


class MissionResult(NamedTuple):
    """Result of a headless run: the project-local mission folder + the dossier.

    `dossier` carries `verdicts` so callers (e.g. batch_runner) can record the
    real Inspector verdict instead of assuming success.
    """
    path: Path
    dossier: dict


def _last_verdict(dossier: dict) -> str:
    """The Inspector's final verdict token, or 'DELIVERED' if none was recorded.
    Tolerant of a malformed (non-dict) verdict entry so it can't raise."""
    verdicts = dossier.get("verdicts") or []
    last = verdicts[-1] if verdicts else None
    return last.get("verdict", "DELIVERED") if isinstance(last, dict) else "DELIVERED"


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
    slug = _store_slug(dossier.get("goal", ""), max_words=6)
    # _next_id() then mkdir() is a TOCTOU race: two concurrent missions can read the
    # same highest number and collide. mkdir() (no exist_ok) is the atomic claim —
    # on FileExistsError, recompute the next id and retry rather than aborting.
    for _ in range(100):
        mission_id = f"{_next_id(missions)}-{slug}"
        out = missions / mission_id
        try:
            out.mkdir()
            break
        except FileExistsError:
            continue
    else:
        raise RuntimeError(f"could not allocate a mission folder under {missions}")
    (out / "dossier.md").write_text(_dossier_md(mission_id, dossier), encoding="utf-8")
    delivered = dossier.get("delivered") or "(no deliverable)"
    (out / "deliverable.md").write_text(
        f"# Deliverable — {mission_id}\n\n{delivered}\n", encoding="utf-8"
    )
    return out


def _run_and_persist(
    goal: str,
    project_root: str,
    engine: str,
    on_event: Optional[Callable[[dict], None]] = None,
    should_cancel: Optional[Callable[[], bool]] = None,
) -> MissionResult:
    """Drive the engine for `goal`, persist to the ~/.agency store (so
    `agency missions/resume/export` see it) AND serialize the project-local
    missions/<id>/ copy. Shared by run() and resume() so both persist identically.

    `on_event` is an optional observational progress callback threaded straight
    through to `run_mission_cli` (used by the Studio server to stream SSE). Default
    None ⇒ unchanged behaviour.

    `should_cancel` is an optional cooperative-cancel predicate. When it fires,
    `run_mission_cli` raises `MissionCancelled` BEFORE returning — so the store.save
    and serialize_dossier below never run, and a cancelled mission leaves no trace.
    """
    from agency_kit import store
    from .engines.cli_engine import run_mission_cli
    dossier = run_mission_cli(goal, engine=engine, on_event=on_event, should_cancel=should_cancel)
    dossier["mission_id"] = store.new_mission_id(goal)
    # Stamp the canonical project root so store.list_missions can scope history to
    # this project (the Studio GUI launched with --path), not the global store.
    dossier["project_root"] = store.canonical_project_root(project_root)
    store.save(dossier)
    path = serialize_dossier(dossier, Path(project_root))
    return MissionResult(path=path, dossier=dossier)


def run(
    goal: str,
    project_root: str = ".",
    engine: str = "claude-code",
    on_event: Optional[Callable[[dict], None]] = None,
    should_cancel: Optional[Callable[[], bool]] = None,
) -> MissionResult:
    """Headless run: drive a local agent CLI engine, then serialize the dossier.

    engine="claude-code" — `claude -p "..." --allowedTools WebSearch`  (default)
    engine="codex"       — `codex --search exec ... -- "..."`
    engine="gemini"      — `gemini -p "..."`
    No API key required: each CLI uses its own authenticated session + web search.

    `on_event` is an optional observational progress callback (route/dept/synth/
    inspect events) used by the Studio server to stream live SSE progress.

    `should_cancel` is an optional cooperative-cancel predicate polled at phase
    boundaries; if it fires the mission stops and nothing is persisted.

    Returns a MissionResult (path + dossier) so callers can read the real verdict.
    """
    return _run_and_persist(goal, project_root, engine, on_event=on_event, should_cancel=should_cancel)


def resume(
    mission_id: str,
    project_root: str = ".",
    engine: str = "claude-code",
    on_event: Optional[Callable[[dict], None]] = None,
    should_cancel: Optional[Callable[[], bool]] = None,
) -> MissionResult:
    """Re-run a saved mission's goal through the engine.

    The engine is single-shot (no quota checkpoint), so 'resume' loads the saved
    dossier, takes its goal, and re-runs it — producing a fresh result that is
    persisted to the store and serialized identically to run().
    """
    from agency_kit import store
    saved = store.load(mission_id)
    goal = saved.get("goal", "")
    return _run_and_persist(goal, project_root, engine, on_event=on_event, should_cancel=should_cancel)
