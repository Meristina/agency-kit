"""Parallel mission runner — runs independent departments concurrently.

Dependency order (9 stages):
  Stage 1 (parallel):   product              — independent; entry point for product strategy
  Stage 2 (parallel):   solve                — independent; runs concurrently with product
  Stage 3 (sequential): marketing            — uses product output as context
  Stage 4 (sequential): finance              — uses all upstream output as context
  Stage 5 (sequential): comms               — uses product + marketing output as context
  Stage 6 (sequential): data                — uses all upstream output as context
  Stage 7 (sequential): ops                 — uses all upstream output as context
  Stage 8 (sequential): people              — uses all upstream output as context
  Stage 9 (sequential): tech                — uses all upstream output as context

Stages 1 and 2 (product + solve) form the _PARALLEL_GROUP and are submitted to a
ThreadPoolExecutor when both are in the route. All other stages are sequential.

The agency commander is used only for SYNTHESIS (combining dept outputs into one
cross-department deliverable) and the agency inspector for the final audit.
Department orchestration happens here in Python, not inside the LLM.

Usage:
  from agency_kit.parallel import run_parallel_mission
  dossier = run_parallel_mission("pitch investors and build a go-to-market plan")
"""

from concurrent.futures import ThreadPoolExecutor, as_completed

from agents import Runner

from .mission import (
    new_dossier, auto_proceed, _is_quota_error, _mission_loop,
)
from .commander import agency_commander
from .router import classify
from . import store

_PARALLEL_GROUP = frozenset({"product", "solve"})


def _dept_brief(dept: str, goal: str, upstream: dict) -> str:
    parts = [f"DEPARTMENT MISSION: {dept.upper()}", f"GOAL: {goal}"]
    if upstream:
        parts.append("UPSTREAM OUTPUTS (context — do not re-derive):")
        for d, out in upstream.items():
            parts.append(f"\n--- {d.upper()} ---\n{out}")
    return "\n\n".join(parts)


def _synthesis_brief(dossier: dict, dept_outputs: dict, required_fixes: list) -> str:
    parts = [
        "SYNTHESIZE: The departments below have already run. Combine their outputs into ONE "
        "coherent cross-department deliverable. Do NOT re-run or re-derive their work.\n"
    ]
    for dept, out in dept_outputs.items():
        parts.append(f"--- {dept.upper()} ---\n{out}")
    parts.append(f"\nGOAL: {dossier['goal']}")
    if required_fixes:
        prev = dossier.get("previous_synthesis", "")
        if prev:
            parts.append(f"\nPREVIOUS SYNTHESIS (build on it; fix the items below):\n{prev}")
        parts.append("\nREQUIRED FIXES:\n- " + "\n- ".join(required_fixes))
    return "\n\n".join(parts)


def _get_commanders():
    from .commander import (
        commander_product, _HAS_PRODUCT,
        commander_marketing, _HAS_MARKETING,
        commander_solve, _HAS_SOLVE,
        commander_finance, _HAS_FINANCE,
        commander_comms, _HAS_COMMS,
        commander_data, _HAS_DATA,
        commander_ops, _HAS_OPS,
        commander_people, _HAS_PEOPLE,
        commander_tech, _HAS_TECH,
    )
    return {
        "product":   (commander_product,   _HAS_PRODUCT),
        "marketing": (commander_marketing, _HAS_MARKETING),
        "solve":     (commander_solve,     _HAS_SOLVE),
        "finance":   (commander_finance,   _HAS_FINANCE),
        "comms":     (commander_comms,     _HAS_COMMS),
        "data":      (commander_data,      _HAS_DATA),
        "ops":       (commander_ops,       _HAS_OPS),
        "people":    (commander_people,    _HAS_PEOPLE),
        "tech":      (commander_tech,      _HAS_TECH),
    }


def _run_dept(commander, prompt: str) -> str:
    return Runner.run_sync(commander, prompt).final_output or ""


def _execute_departments(route: list, goal: str) -> dict:
    """Stages 1–2: parallel (product+solve); Stages 3–9: sequential in router's returned order."""
    commanders = _get_commanders()
    dept_outputs = {}

    # Stages 1–2 — parallel group
    parallel = [d for d in route if d in _PARALLEL_GROUP and commanders[d][1] and commanders[d][0]]
    if len(parallel) > 1:
        print(f"  [parallel] launching: {', '.join(parallel)}")
        with ThreadPoolExecutor(max_workers=len(parallel)) as ex:
            futures = {
                ex.submit(_run_dept, commanders[d][0], _dept_brief(d, goal, {})): d
                for d in parallel
            }
            for fut in as_completed(futures):
                dept = futures[fut]
                try:
                    dept_outputs[dept] = fut.result()
                except Exception:
                    raise  # quota errors caught by the execute_fn wrapper in _mission_loop
                print(f"  [parallel] {dept} done ({len(dept_outputs[dept])} chars)")
    elif parallel:
        dept = parallel[0]
        dept_outputs[dept] = _run_dept(commanders[dept][0], _dept_brief(dept, goal, {}))
        print(f"  [sequential] {dept} done")

    # Stages 3–9 — sequential, preserving the router's returned order
    for dept in route:
        if dept in _PARALLEL_GROUP:
            continue  # already ran in stages 1–2
        cmd, has = commanders[dept]
        if not has or not cmd:
            print(f"  [skip] {dept} not installed")
            continue
        out = _run_dept(cmd, _dept_brief(dept, goal, dept_outputs))
        dept_outputs[dept] = out
        print(f"  [sequential] {dept} done ({len(out)} chars)")

    return dept_outputs


def run_parallel_mission(goal: str, dc_fn=auto_proceed) -> dict:
    """Drive the parallel cross-department loop. Returns the dossier.

    Same control-flow as run_mission (Direction Check → Execute → Inspect → loop)
    but runs product+solve concurrently (stages 1–2) before the sequential tail
    (marketing → finance → comms → data → ops → people → tech, stages 3–9).

    The outer loop (DC, quota-pause, verdict dispatch, iteration cap) is provided by
    _mission_loop from mission.py; this function supplies the parallel execute_fn.
    """
    dossier = new_dossier(goal)
    dossier["mission_id"] = store.new_mission_id(goal)
    dossier["route"] = classify(goal)
    dossier["context"] = {
        "classified_departments": dossier["route"],
        "execution_mode": "parallel",
    }
    print(f"Route (parallel mode): {dossier['route']}")

    def execute_fn(dos, req_fixes):
        dept_outputs = _execute_departments(dos["route"], dos["goal"])
        dos["dept_outputs"].update(dept_outputs)
        synthesis_result = Runner.run_sync(
            agency_commander, _synthesis_brief(dos, dept_outputs, req_fixes)
        )
        deliverable = synthesis_result.final_output
        dos["previous_synthesis"] = deliverable
        dos["decisions"].append({
            "iteration": dos["iteration"],
            "route_executed": list(dos["route"]),
            "departments_run": list(dept_outputs.keys()),
            "execution_mode": "parallel",
        })
        return deliverable

    # Pass parallel.Runner explicitly so monkeypatching parallel.Runner in tests
    # correctly intercepts both the execute and the inspect call inside _mission_loop.
    return _mission_loop(dossier, [], "", dc_fn, execute_fn=execute_fn, _runner=Runner)
