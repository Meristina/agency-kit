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


def _cmd_run(args) -> int:
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
        print(f"error: mission '{args.mission_id}' not found in {store.missions_dir()}",
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
        description="AI Agency — unified orchestrator for product-kit, marketing-kit, solve-kit, and finance-kit",
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
                    help="run product+solve concurrently, then marketing, then finance")
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
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
