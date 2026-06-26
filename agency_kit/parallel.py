"""Parallel mission runner — runs independent departments concurrently.

Dependency order:
  Stage 1 (parallel):   product, solve       — independent; run with ThreadPoolExecutor
  Stage 2 (sequential): marketing            — uses product output as context
  Stage 3 (sequential): finance              — uses all upstream output as context

The agency commander is used only for SYNTHESIS (combining dept outputs into one
cross-department deliverable) and the agency inspector for the final audit.
Department orchestration happens here in Python, not inside the LLM.

Usage:
  from agency_kit.parallel import run_parallel_mission
  dossier = run_parallel_mission("pitch investors and build a go-to-market plan")
"""

import json
from concurrent.futures import ThreadPoolExecutor, as_completed

from agents import Runner

from .mission import (
    new_dossier, parse_verdict, extract_required_fixes, auto_proceed, MAX_ITERS,
)
from .commander import agency_commander
from .inspector import agency_inspector
from .router import classify
from . import store

_PARALLEL_GROUP = frozenset({"product", "solve"})
_SEQUENTIAL_AFTER = ["marketing", "finance"]


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
    )
    return {
        "product":   (commander_product,   _HAS_PRODUCT),
        "marketing": (commander_marketing, _HAS_MARKETING),
        "solve":     (commander_solve,     _HAS_SOLVE),
        "finance":   (commander_finance,   _HAS_FINANCE),
    }


def _run_dept(commander, prompt: str) -> str:
    return Runner.run_sync(commander, prompt).final_output or ""


def _execute_departments(route: list, goal: str) -> dict:
    """Stage 1: parallel (product+solve); Stage 2+: sequential (marketing → finance)."""
    commanders = _get_commanders()
    dept_outputs = {}

    # Stage 1 — parallel group
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
                dept_outputs[dept] = fut.result()
                print(f"  [parallel] {dept} done ({len(dept_outputs[dept])} chars)")
    elif parallel:
        dept = parallel[0]
        dept_outputs[dept] = _run_dept(commanders[dept][0], _dept_brief(dept, goal, {}))
        print(f"  [sequential] {dept} done")

    # Stage 2+ — sequential
    for dept in _SEQUENTIAL_AFTER:
        if dept not in route:
            continue
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
    but runs product+solve concurrently before marketing/finance.
    """
    dossier = new_dossier(goal)
    dossier["mission_id"] = store.new_mission_id(goal)
    dossier["route"] = classify(goal)
    dossier["context"] = {
        "classified_departments": dossier["route"],
        "execution_mode": "parallel",
    }
    print(f"Route (parallel mode): {dossier['route']}")

    required_fixes: list = []
    deliverable = ""

    while dossier["iteration"] < MAX_ITERS:
        dossier["iteration"] += 1
        print(f"\n=== ITERATION {dossier['iteration']}/{MAX_ITERS} [parallel] ===")

        # Direction Check
        dc_pkg = "\n".join([
            "ROUTE:", json.dumps(dossier["route"], ensure_ascii=False),
            "\nGOAL:", goal,
        ])
        dc_choice, dc_note = dc_fn(dc_pkg)
        dossier["direction_check"] = {
            "iteration": dossier["iteration"],
            "choice": dc_choice,
            "note": dc_note,
        }
        print(f"Direction check: {dc_choice}" + (f" — {dc_note}" if dc_note else ""))

        if dc_choice == "STEER":
            steer_note = dc_note or "steer the route"
            required_fixes = [f"Direction steer: {steer_note}"]
            dossier["route"] = classify(f"{goal}\n\nUser steer: {steer_note}")
            dossier["context"]["classified_departments"] = dossier["route"]
            dossier["context"]["steered"] = True
            print(f"Re-classified route: {dossier['route']}")
            continue

        # Execute — parallel stage 1, sequential stage 2+
        dept_outputs = _execute_departments(dossier["route"], goal)
        dossier["dept_outputs"].update(dept_outputs)

        # Synthesis via agency commander (combining role only, not orchestration)
        synthesis_result = Runner.run_sync(
            agency_commander, _synthesis_brief(dossier, dept_outputs, required_fixes)
        )
        deliverable = synthesis_result.final_output
        dossier["previous_synthesis"] = deliverable
        dossier["decisions"].append({
            "iteration": dossier["iteration"],
            "route_executed": list(dossier["route"]),
            "departments_run": list(dept_outputs.keys()),
            "execution_mode": "parallel",
        })
        required_fixes = []
        store.save(dossier)

        # Inspect
        inspection = Runner.run_sync(
            agency_inspector,
            "MODE: FINAL. Run the cross-department audit on this synthesised deliverable "
            "(sources / ethics & compliance / cross-department consistency) and end with a clear "
            "verdict line — PASS, PASS WITH FIXES, or VETO — plus the required fixes as bullet "
            "lines, each naming the departments involved:\n\n" + deliverable,
        )
        verdict = parse_verdict(inspection.final_output)
        required_fixes = extract_required_fixes(inspection.final_output)
        if verdict != "PASS" and not required_fixes:
            feedback = inspection.final_output.strip()
            if len(feedback) > 2000:
                feedback = feedback[:2000] + "\n... [truncated]"
            required_fixes = [f"Inspector {verdict} — feedback:\n{feedback}"]
        dossier["verdicts"].append({
            "iteration": dossier["iteration"],
            "verdict": verdict,
            "required_fixes": required_fixes,
        })
        print(f"Inspector verdict: {verdict}  ({len(required_fixes)} fix(es))")

        if verdict == "PASS":
            dossier["delivered"] = deliverable
            store.save(dossier)
            return dossier

    dossier["delivered"] = deliverable
    dossier["residual_risk"] = (
        f"Iteration cap reached. Unresolved fixes: {required_fixes}; "
        f"open_to_verify: {dossier['open_to_verify']}."
    )
    store.save(dossier)
    return dossier
