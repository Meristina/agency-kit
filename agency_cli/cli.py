"""agency — Agency-Kit CLI. Subcommands: init, run, check, version."""

import argparse
import sys

# Flush stdout immediately so `agency run` output is visible in real time when
# stdout is redirected (e.g. piped to a file or captured by a test runner).
sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]

from . import __version__, scaffolder


def _cmd_init(args) -> int:
    summary = scaffolder.init(args.path, agent=args.agent)
    print(f"Initialized Agency-Kit in {summary['target']} (harness: {summary['agent']})")
    print(f"  payload source : {summary['payload_mode']}")
    if "commands" in summary:
        print(f"  commands       : {summary['commands']} → /agency.<name>")
    for k in ("agents", "skills", "note"):
        if k in summary:
            print(f"  {k:<14} : {summary[k]}")
    print('Next:  agency run "<your mission goal>"   (or use /agency.mission in your harness)')
    return 0


def _cmd_dry_run(args) -> int:
    try:
        from agency_kit.router import keyword_classify
        from agency_kit.commander import DEPT_INSTALLED
    except ModuleNotFoundError as e:
        print(f"error: {e}. Install the engine SDK: pip install openai-agents", file=sys.stderr)
        return 2
    _installed = DEPT_INSTALLED
    route = keyword_classify(args.goal)
    print(f"\n[dry-run] Goal: {args.goal}")
    print(f"[dry-run] Planned route ({len(route)} dept(s), keyword classifier — no API call):")
    for i, dept in enumerate(route, 1):
        flag = "✓ installed" if _installed.get(dept) else "✗ not installed (will be skipped)"
        print(f"  {i}. {dept:<12}  {flag}")
    missing = [d for d in route if not _installed.get(d)]
    if missing:
        print(f"\n[dry-run] Install missing:  pip install -e \".[{','.join(missing)}]\"")
    print(f"\n[dry-run] No API call made. Remove --dry-run to execute.")
    return 0


def _cmd_run(args) -> int:
    if getattr(args, "dry_run", False):
        return _cmd_dry_run(args)
    from . import runner_bridge
    try:
        out = runner_bridge.run(
            args.goal, project_root=args.path, steer=args.steer,
            parallel=getattr(args, "parallel", False),
        )
    except ModuleNotFoundError as e:
        print(f"error: {e}. `agency run` needs the engine SDK: pip install openai-agents",
              file=sys.stderr)
        return 2
    print(f"Mission written to: {out}")
    return 0


def _cmd_missions(args) -> int:
    from agency_kit import store
    missions = store.list_missions()
    if not missions:
        print("No missions saved yet. Run:  agency run \"<your goal>\"")
        return 0
    print(f"{'MISSION ID':<38}  {'VERDICT':<15}  GOAL")
    print("-" * 90)
    for m in missions:
        tick = "✓" if m["delivered"] else "○"
        goal_preview = m["goal"][:42] + "…" if len(m["goal"]) > 42 else m["goal"]
        print(f"{m['mission_id']:<38}  {m['verdict']:<15}  {tick} {goal_preview}")
    return 0


def _cmd_resume(args) -> int:
    from agency_kit import store
    from . import runner_bridge
    try:
        out = runner_bridge.resume(args.mission_id, project_root=args.path, steer=args.steer)
    except FileNotFoundError:
        print(f"error: mission '{args.mission_id}' not found in {store.missions_path()}",
              file=sys.stderr)
        return 2
    except ModuleNotFoundError as e:
        print(f"error: {e}. `agency resume` needs the engine SDK: pip install openai-agents",
              file=sys.stderr)
        return 2
    print(f"Mission resumed and written to: {out}")
    return 0


def _cmd_sync(args) -> int:
    from . import sync_payload
    try:
        return sync_payload.main(allow_missing=getattr(args, "allow_missing", False))
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


def _cmd_export(args) -> int:
    try:
        from . import exporter
        path = exporter.export_pdf(args.mission_id)
    except (FileNotFoundError, ImportError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"error: PDF export failed — {e}", file=sys.stderr)
        return 2
    print(f"PDF exported to: {path}")
    return 0


def _cmd_tui(args) -> int:
    try:
        from . import tui
        tui.launch()
    except ImportError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    return 0


def _cmd_batch(args) -> int:
    from . import batch_runner
    cmd = getattr(args, "batch_cmd", None)
    if cmd == "add":
        return batch_runner.add(args.goal, priority=args.priority, notes=args.notes)
    if cmd == "run":
        return batch_runner.run(
            resume_paused=getattr(args, "resume_paused", False),
            retry_failed=getattr(args, "retry_failed", False),
            limit=getattr(args, "limit", 0),
        )
    if cmd == "status":
        return batch_runner.status()
    if cmd == "clear":
        return batch_runner.clear(status_filter=getattr(args, "status_filter", "done"))
    return 1


def _cmd_check(args) -> int:
    ok_all = True
    for label, ok, detail in scaffolder.check(args.path):
        mark = "✓" if ok else "✗"
        ok_all = ok_all and ok
        print(f"  {mark} {label}" + (f"  ({detail})" if detail and not ok else ""))
    return 0 if ok_all else 1


def _harness_choices():
    from .integrations import SUPPORTED
    return list(SUPPORTED)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="agency",
        description="AI Agency — unified orchestrator for nine optional department kits (product, marketing, solve, finance, comms, data, ops, people, tech)",
    )
    p.add_argument("--version", action="version", version=f"agency-kit {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("init", help="scaffold .agency/ + harness commands into a project")
    pi.add_argument("path", nargs="?", default=".", help="target project dir (default: .)")
    pi.add_argument("--agent", default="claude", choices=_harness_choices(),
                    help="agent harness: claude | codex | cursor | copilot | gemini | opencode")
    pi.set_defaults(func=_cmd_init)

    pr = sub.add_parser("run", help="headless mission via the engine (needs openai-agents)")
    pr.add_argument("goal", help="the mission goal, one line")
    pr.add_argument("path", nargs="?", default=".", help="project dir for missions/ output")
    pr.add_argument("--steer", action="store_true",
                    help="open the interactive Direction Check (otherwise auto-proceeds)")
    pr.add_argument("--parallel", action="store_true",
                    help="run routed departments concurrently where possible (experimental)")
    pr.add_argument("--dry-run", dest="dry_run", action="store_true",
                    help="classify goal with keyword heuristic and show planned route — no API call")
    pr.set_defaults(func=_cmd_run)

    pm = sub.add_parser("missions", help="list saved missions from ~/.agency/missions/")
    pm.set_defaults(func=_cmd_missions)

    pre = sub.add_parser("resume", help="resume a previously saved mission by ID")
    pre.add_argument("mission_id", help="mission ID shown by `agency missions`")
    pre.add_argument("path", nargs="?", default=".", help="project dir for missions/ output")
    pre.add_argument("--steer", action="store_true")
    pre.set_defaults(func=_cmd_resume)

    pc = sub.add_parser("check", help="prerequisite / health check")
    pc.add_argument("path", nargs="?", default=".")
    pc.set_defaults(func=_cmd_check)

    ps = sub.add_parser("sync", help="regenerate the bundled payload from the repo source")
    ps.add_argument("--allow-missing", action="store_true",
                    help="run even if sibling dept-kit repos are absent (keeps their committed files)")
    ps.set_defaults(func=_cmd_sync)

    pt = sub.add_parser("tui", help="launch terminal UI — Pipeline / Viewer / Analytics (needs pip install -e \".[tui]\")")
    pt.set_defaults(func=_cmd_tui)

    pe = sub.add_parser("export", help="export a mission deliverable to PDF (needs pip install -e \".[pdf]\")")
    pe.add_argument("mission_id", help="mission ID (from `agency missions`)")
    pe.set_defaults(func=_cmd_export)

    pb = sub.add_parser("batch", help="batch mission queue: add / run / status / clear")
    bsub = pb.add_subparsers(dest="batch_cmd", required=True)

    pba = bsub.add_parser("add", help="add a goal to the queue")
    pba.add_argument("goal", help="mission goal")
    pba.add_argument("--priority", type=int, default=5, metavar="N",
                     help="execution priority — lower = higher priority (default: 5)")
    pba.add_argument("--notes", default="", help="optional notes attached to the queue entry")
    pba.set_defaults(func=_cmd_batch)

    pbr = bsub.add_parser("run", help="execute pending goals sequentially")
    pbr.add_argument("--limit", type=int, default=0, metavar="N",
                     help="max goals to run this session (default: 0 = all pending)")
    pbr.add_argument("--resume-paused", dest="resume_paused", action="store_true",
                     help="also run goals paused by a previous rate-limit hit")
    pbr.add_argument("--retry-failed", dest="retry_failed", action="store_true",
                     help="also retry goals that errored")
    pbr.set_defaults(func=_cmd_batch)

    pbs = bsub.add_parser("status", help="show queue and run state")
    pbs.set_defaults(func=_cmd_batch)

    pbc = bsub.add_parser("clear", help="remove entries from the queue by status")
    pbc.add_argument("--status", dest="status_filter", default="done",
                     help="status to remove (default: done)")
    pbc.set_defaults(func=_cmd_batch)

    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
