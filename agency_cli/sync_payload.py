"""sync_payload — regenerate the bundled payload from all source repos.

Pulls from agency-kit (the meta-orchestrator) AND all three department kit repos
(product-kit, marketing-kit, solve-kit) so that `agency init` installs a complete,
standalone agency without requiring separate `product init` / `marketing init` /
`solve init` calls.

Source layout (all repos are expected as siblings of agency-kit):
  agency-kit/     → .agency/, agents/, skills/
  product-kit/    → agents/, skills/
  marketing-kit/  → agents/, skills/
  solve-kit/      → agents/, skills/

Bundle layout (agency_cli/payload/):
  payload/agency/    ← .agency/ (constitution, commands, templates, scripts)
  payload/agents/    ← merged agents from agency-kit + all dept kits
  payload/skills/    ← merged skills from agency-kit + all dept kits

Naming conflict: every dept kit has its own inspector.md — renamed on copy:
  product-kit/agents/inspector.md  → payload/agents/inspector-product.md
  marketing-kit/agents/inspector.md → payload/agents/inspector-marketing.md
  solve-kit/agents/inspector.md    → payload/agents/inspector-solve.md

Run:  agency sync   (or: python -m agency_cli.sync_payload)
"""

import shutil
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def payload_dir() -> Path:
    return Path(__file__).resolve().parent / "payload"


def _dept_root(name: str) -> Path:
    """Sibling repo directory for a department kit (e.g. 'product-kit')."""
    return repo_root().parent / name


# Department kits to pull from — (repo-dir-name, dept-label)
DEPT_KITS = [
    ("product-kit",   "product"),
    ("marketing-kit", "marketing"),
    ("solve-kit",     "solve"),
]


def _copy_agents(src: Path, dst: Path, dept: str) -> int:
    """Copy all .md files from src into dst, renaming inspector.md → inspector-<dept>.md."""
    dst.mkdir(parents=True, exist_ok=True)
    count = 0
    for f in src.glob("*.md"):
        target_name = f"inspector-{dept}.md" if f.name == "inspector.md" else f.name
        shutil.copy2(f, dst / target_name)
        count += 1
    return count


def _copy_skills(src: Path, dst: Path) -> int:
    """Merge skill directories from src into dst (copytree each skill folder)."""
    dst.mkdir(parents=True, exist_ok=True)
    count = 0
    for skill_dir in src.iterdir():
        if skill_dir.is_dir():
            shutil.copytree(skill_dir, dst / skill_dir.name, dirs_exist_ok=True)
            count += sum(1 for _ in (dst / skill_dir.name).rglob("*") if _.is_file())
    return count


def sync() -> dict:
    root, dest = repo_root(), payload_dir()
    summary = {}

    # 1) .agency/ → payload/agency/
    agency_src = root / ".agency"
    if not agency_src.exists():
        raise RuntimeError(f"Required source dir not found: {agency_src}")
    agency_dst = dest / "agency"
    if agency_dst.exists():
        shutil.rmtree(agency_dst)
    shutil.copytree(agency_src, agency_dst)
    summary["agency"] = sum(1 for _ in agency_dst.rglob("*") if _.is_file())

    # 2) agents/ — agency-kit first, then all dept kits (with inspector renaming)
    agents_dst = dest / "agents"
    if agents_dst.exists():
        shutil.rmtree(agents_dst)
    agents_dst.mkdir(parents=True)

    n_agents = _copy_agents(root / "agents", agents_dst, "agency")

    for repo_name, dept in DEPT_KITS:
        dept_root = _dept_root(repo_name)
        dept_agents = dept_root / "agents"
        if not dept_agents.exists():
            print(f"  [skip] {repo_name}/agents not found — dept kit not present")
            continue
        n_agents += _copy_agents(dept_agents, agents_dst, dept)

    summary["agents"] = n_agents

    # 3) skills/ — agency-kit first, then all dept kits (merged, no conflicts)
    skills_dst = dest / "skills"
    if skills_dst.exists():
        shutil.rmtree(skills_dst)
    skills_dst.mkdir(parents=True)

    n_skills = 0
    agency_skills = root / "skills"
    if agency_skills.exists():
        n_skills += _copy_skills(agency_skills, skills_dst)

    for repo_name, dept in DEPT_KITS:
        dept_root = _dept_root(repo_name)
        dept_skills = dept_root / "skills"
        if not dept_skills.exists():
            print(f"  [skip] {repo_name}/skills not found — dept kit not present")
            continue
        n_skills += _copy_skills(dept_skills, skills_dst)

    summary["skills"] = n_skills

    return summary


def main() -> int:
    s = sync()
    print(f"Synced payload → {payload_dir()}")
    for k, n in s.items():
        print(f"  {k:<8} {n} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
