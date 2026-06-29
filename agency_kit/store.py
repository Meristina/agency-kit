"""Mission store — persist dossiers to disk; list and resume missions.

Saves each dossier to ~/.agency/missions/<YYYYMMDD-HHMMSS-ffffff>-<slug>/dossier.json
so missions survive across CLI runs and can be resumed or audited offline.
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path


def slug(text: str, max_words: int = 5) -> str:
    """URL-safe slug from text. Public so callers can pass their preferred max_words."""
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return "-".join(s.split("-")[:max_words]) or "mission"


def missions_path() -> Path:
    """Return the missions directory path without creating it."""
    return Path.home() / ".agency" / "missions"


def missions_dir() -> Path:
    d = missions_path()
    d.mkdir(parents=True, exist_ok=True)
    return d


def agency_dir() -> Path:
    """Return ~/.agency, creating it if absent. Public so batch_runner and other
    callers don't need to duplicate this one-liner."""
    d = Path.home() / ".agency"
    d.mkdir(parents=True, exist_ok=True)
    return d


def split_frontmatter(content: str) -> tuple:
    """Canonical YAML front-matter splitter. Returns ``(frontmatter, body)``.

    The closing delimiter is matched as a line of its own (``\\n---``), so a
    ``---`` that appears inside the body is not mistaken for the end of the
    front-matter. If no well-formed front-matter is present, returns
    ``("", content)`` (the whole input is the body). This is the single
    implementation used by ``strip_frontmatter`` (here), ``cli_engine``, and
    ``integrations`` so the three never diverge.
    """
    if not content.startswith("---"):
        return "", content
    end = content.find("\n---", 3)
    if end == -1:
        return "", content
    return content[3:end], content[end + 4:]


def strip_frontmatter(content: str) -> str:
    """Strip YAML front-matter (---...---) written by store.save().

    Returns the body text with leading/trailing whitespace removed.
    If no front-matter is present, returns the original string unchanged.
    """
    fm, body = split_frontmatter(content)
    return body.strip() if fm else content


def new_mission_id(goal: str) -> str:
    """Generate a mission ID of the form ``<YYYYMMDD-HHMMSS-ffffff>-<slug>``.

    The microsecond field (``%f``) is the uniqueness guarantee: two workers that
    start in the same second still get distinct IDs. No filesystem lock is used —
    a lock would only serialise the call, not inject entropy, so two same-second
    same-goal workers would have collided whether it was held or not.
    """
    ts = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    return f"{ts}-{slug(goal)}"


def save(dossier: dict) -> "Path | None":
    """Persist the dossier as JSON. Creates/overwrites <missions_dir>/<mission_id>/dossier.json.

    Returns the dossier.json path on success, or ``None`` when there is nothing to
    persist — i.e. the dossier carries no ``mission_id`` (call ``new_mission_id``
    first), or a disk write failed. Never raises: a disk failure must not abort a
    live mission. Callers must handle the ``None`` case before using the result.
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
            verdicts = dossier.get("verdicts") or []
            last_verdict = verdicts[-1].get("verdict", "—") if verdicts else "in-progress"
            meta = "\n".join([
                "---",
                f"mission_id: {dossier.get('mission_id', '')}",
                f"route: {json.dumps(dossier.get('route', []))}",
                f"departments: {', '.join(dossier.get('route', []))}",
                f"iteration: {dossier.get('iteration', 0)}",
                f"verdict: {last_verdict}",
                "delivered: true",
                "---",
            ])
            (d / "deliverable.md").write_text(meta + "\n\n" + dossier["delivered"], encoding="utf-8")
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
        except (OSError, json.JSONDecodeError, KeyError):
            # Recoverable: a corrupt/unreadable JSON file or a missing key — skip
            # that one mission. Programming errors (other exceptions) propagate.
            continue
    return result
