"""Mission store — persist dossiers to disk; list and resume missions.

Saves each dossier to ~/.agency/missions/<YYYYMMDD-HHMMSS>-<slug>/dossier.json
so missions survive across CLI runs and can be resumed or audited offline.
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path


def _slug(text: str, max_words: int = 5) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return "-".join(s.split("-")[:max_words]) or "mission"


def missions_dir() -> Path:
    d = Path.home() / ".agency" / "missions"
    d.mkdir(parents=True, exist_ok=True)
    return d


def new_mission_id(goal: str) -> str:
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{ts}-{_slug(goal)}"


def save(dossier: dict) -> Path:
    """Persist the dossier as JSON. Creates/overwrites <missions_dir>/<mission_id>/dossier.json.

    Never raises — a disk failure must not abort a live mission.
    """
    try:
        mid = dossier.get("mission_id")
        if not mid:
            return None
        d = missions_dir() / mid
        d.mkdir(exist_ok=True)
        path = d / "dossier.json"
        path.write_text(json.dumps(dossier, ensure_ascii=False, indent=2), encoding="utf-8")
        if dossier.get("delivered"):
            (d / "deliverable.md").write_text(dossier["delivered"], encoding="utf-8")
        return path
    except Exception as e:
        print(f"  [store] warning: could not save dossier — {e}", file=sys.stderr)
        return None


def load(mission_id: str) -> dict:
    """Load a dossier from disk. Raises FileNotFoundError if not found."""
    path = missions_dir() / mission_id / "dossier.json"
    return json.loads(path.read_text(encoding="utf-8"))


def list_missions() -> list:
    """Return a summary list of all saved missions, newest first."""
    result = []
    for d in sorted(missions_dir().iterdir(), reverse=True):
        if not d.is_dir():
            continue
        p = d / "dossier.json"
        if not p.exists():
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            verdicts = data.get("verdicts") or []
            last_verdict = verdicts[-1].get("verdict", "—") if verdicts else "in-progress"
            result.append({
                "mission_id": data.get("mission_id", d.name),
                "goal": (data.get("goal") or "")[:80],
                "route": data.get("route", []),
                "iteration": data.get("iteration", 0),
                "verdict": last_verdict,
                "delivered": bool(data.get("delivered")),
            })
        except Exception:
            continue
    return result
