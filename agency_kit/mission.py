"""
MISSION RUNNER — Agency — single-stage cross-department control loop + Mission Dossier

The agency's spine. Where commander.py *defines* the agency commander (the meta-orchestrator that
classifies the mission, deploys the right departments in order, carries each department's output
forward, and synthesises one cross-department deliverable), this runner *drives the mission*: it
holds the Mission Dossier (living state), classifies the route once up front, offers ONE optional
Direction Check (non-blocking), runs the commander, runs the FINAL agency inspector, parses the
verdict, and controls re-entry and the iteration cap.

This army is SIMPLER than an individual kit's runner: there are no per-stage briefs, because the
ROUTING and DEPARTMENT SEQUENCING happen INSIDE the agency commander. The mission runner just
drives the commander+inspector loop. One iteration is:
  CLASSIFY  -> ask the router which departments the mission needs (recorded in the dossier route).
  --- DC offered: present the route + goal, offer to confirm/steer (non-blocking) ---
  EXECUTE   -> run the agency commander on the goal + required_fixes. It internally routes,
               deploys the departments in order, carries output forward, and synthesises.
  INSPECT   -> run the agency inspector's FINAL cross-department check.
Then the inspector verdict gates delivery.

Inspector VETO or PASS_WITH_FIXES loops back with the required fixes for a full commander re-run.
Cap at MAX_ITERS = 3; if still failing, deliver the best result with residual_risk stated.

Run:  python -m agency_kit.mission "Describe the cross-department mission here"
(Requires `pip install openai-agents` and OPENAI_API_KEY.)
"""

import json
import re
import sys

from agents import Runner

from .commander import agency_commander
from .inspector import agency_inspector
from .router import classify

_QUOTA_PAT = re.compile(
    r"session\s*limit|usage\s*limit|resets?\s+\d+:\d+\s*[ap]m|quota\s*exceeded|rate\s*limit",
    re.IGNORECASE,
)


def _is_quota_error(exc: Exception) -> bool:
    return bool(_QUOTA_PAT.search(str(exc)))


MAX_ITERS = 3  # iteration cap — deliver-with-residual-risk rather than thrash forever


# ---------------------------------------------------------------------------
# Mission Dossier
# ---------------------------------------------------------------------------

def new_dossier(goal: str) -> dict:
    """The single living-state artifact carried across the whole cross-department mission."""
    return {
        "goal": goal,
        "route": [],                # ordered department list returned by the router
        "context": None,            # mission type / sector / stage detected in framing
        "dept_outputs": {},         # one entry per deployed department (the commander fills these)
        "decisions": [],            # cross-department decisions, versioned on re-entry
        "sources": [],
        "open_to_verify": [],
        "direction_check": None,    # optional steer recorded after CLASSIFY (if used)
        "verdicts": [],             # agency inspector verdicts + required fixes, per iteration
        "iteration": 0,
    }


def _dossier_block(dossier: dict) -> str:
    return json.dumps(dossier, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Mission brief
# ---------------------------------------------------------------------------

def agency_brief(dossier: dict, required_fixes: list) -> str:
    """Single combined brief for the agency commander.

    The commander handles routing and department sequencing internally, so there are no per-stage
    briefs — one prompt drives the whole CLASSIFY -> EXECUTE -> SYNTHESIZE -> AUDIT chain. The
    route classified up front is passed as a recommendation; the commander remains free to
    re-classify with a sharpened goal if it disagrees (Constitution Art. VI).
    """
    parts = [
        "MISSION DOSSIER (read in; do not re-ask what is already here):",
        _dossier_block(dossier),
        "\nRun the complete cross-department agency mission:",
        "  CLASSIFY  — confirm the route (the dossier's `route` is the router's recommendation; "
        "re-classify with a sharpened goal only if it is genuinely wrong).",
        "  EXECUTE   — deploy each routed department in order; feed each department's output "
        "forward as context into the next; never reset or drop an upstream output.",
        "  SYNTHESIZE — combine the department outputs into ONE coherent cross-department "
        "deliverable; reconcile overlaps and surface contradictions; speak with one agency voice.",
        "\nReturn the synthesised cross-department deliverable in the user's language. Name the "
        "source department for each load-bearing claim. Make sources and open-to-verify items "
        "explicit, and disclose any routed-but-uninstalled department as a gap (never fabricate "
        "its output).",
    ]
    if required_fixes:
        prev = dossier.get("previous_synthesis", "")
        if prev:
            parts.append(
                "\nPREVIOUS SYNTHESIS (the inspector rejected this — build on it, do NOT discard "
                "the department work already done; re-enter only the responsible department(s) or "
                "re-run synthesis to resolve the required fixes below):\n" + prev
            )
        parts.append(
            "\nREQUIRED FIXES (resolve every item before re-presenting; do not restart "
            "classification unless the goal fundamentally changed):\n- "
            + "\n- ".join(required_fixes)
        )
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Verdict parsing  (SMART version — copied from product_kit, battle-tested)
# ---------------------------------------------------------------------------

def parse_verdict(text: str) -> str:
    """Map the Inspector's free text to a machine verdict.

    Strategy: prefer an explicit verdict announcement line (OVERALL / VERDICT / FINAL VERDICT)
    so we don't misfire on references like "resolving the previous VETO..." in later iterations.
    Fall back to the LAST occurrence of a verdict keyword in the text (the Inspector's conclusion
    is always at the end, not the top). Order of severity: VETO > PASS_WITH_FIXES > PASS.
    """
    upper = (text or "").upper()

    # 1. Explicit verdict lines — highest priority
    _explicit = re.search(
        r"(?:OVERALL|VERDICT|FINAL\s+VERDICT)\s*[:\-–]\s*(VETO|PASS[\s\-]WITH[\s\-]FIXES|PASS)",
        upper,
    )
    if _explicit:
        token = _explicit.group(1)
        if "VETO" in token:
            return "VETO"
        if "FIX" in token:
            return "PASS_WITH_FIXES"
        return "PASS"

    # 2. Fall back to the LAST occurrence of any verdict keyword
    last_veto = upper.rfind("VETO")
    last_pwf = max(upper.rfind("PASS WITH FIXES"), upper.rfind("PASS-WITH-FIXES"))
    last_pass = upper.rfind("PASS")

    candidates = {k: v for k, v in {"VETO": last_veto, "PWF": last_pwf, "PASS": last_pass}.items() if v >= 0}
    if not candidates:
        return "UNCLEAR"
    winner = max(candidates, key=lambda k: candidates[k])
    if winner == "VETO":
        return "VETO"
    if winner == "PWF":
        return "PASS_WITH_FIXES"
    return "PASS"


def extract_required_fixes(text: str) -> list:
    """Best-effort pull of the required-fix bullet lines from the Inspector output.

    Captures two patterns:
      1. Lines that start with FIX: / REQUIRED: / BLOCK: etc. (keyword-prefixed items).
      2. Bullet lines (- / * / •) immediately following a heading that contains
         REQUIRED or BLOCK — handles "Required Fixes (Blocking):" section headers
         whose items are indented bullets on the next lines.

    Key invariant: heading detection must NOT fire on bullet lines whose content happens
    to contain a keyword (e.g. "- Required Fix: reconcile..." is a fix item, not a heading).
    """
    fixes = []
    lines = (text or "").splitlines()
    in_fixes_section = False
    for line in lines:
        stripped = line.strip()
        is_bullet = stripped.startswith(("-", "*", "•"))
        content = stripped.lstrip("-*•").strip()
        content_upper = content.upper()

        if not is_bullet and any(p in content_upper for p in ("REQUIRED FIX", "BLOCKING FIX", "MUST FIX", "REQUIRED CHANGE")):
            in_fixes_section = True
            continue

        if in_fixes_section:
            if not stripped:
                continue  # blank line between heading and first bullet must not close the section
            if stripped.startswith("#") or (stripped.startswith("**") and stripped.endswith("**")):
                in_fixes_section = False
                continue
            if is_bullet and content:
                fixes.append(content)
                continue

        if content and any(content_upper.startswith(p) for p in ("FIX:", "REQUIRED:", "BLOCKING:", "BLOCK:")):
            fixes.append(content)
        # Bullet lines that directly name a fix keyword (guards the bullet-as-heading misfire).
        elif is_bullet and content and any(p in content_upper for p in ("REQUIRED FIX", "BLOCKING FIX", "MUST FIX")):
            fixes.append(content)
    return fixes


# ---------------------------------------------------------------------------
# Direction Check functions (injectable; OPTIONAL and NON-BLOCKING by default)
# ---------------------------------------------------------------------------

def auto_proceed(pkg: str) -> tuple:
    """Default: no human gate. This agency produces deliverables, so it proceeds without approval."""
    return ("PROCEED", "auto-proceed (no mandatory direction check)")


def console_direction_check(pkg: str) -> tuple:
    """Optional interactive light check: show the package, offer to confirm or steer.

    Recommended for high-stakes / non-obvious routing; still NON-BLOCKING — the default is to
    proceed. Returns ("PROCEED", note) or ("STEER", note); a STEER re-enters with the steer note.
    """
    print("\n=== DIRECTION CHECK (optional) — confirm the route or steer before execution ===")
    print(pkg)
    raw = input("\nProceed to execute, or steer the route? [PROCEED / STEER] (default PROCEED): ").strip().lower()
    note = input("Steer/note (optional): ").strip()
    if raw in ("steer", "s", "revise", "r"):
        return ("STEER", note)
    return ("PROCEED", note)  # default: proceed (non-blocking)


# ---------------------------------------------------------------------------
# Inspection prompt — shared constant used by _mission_loop and (via import)
# by any alternate runner (e.g. parallel.py) so the text stays in sync.
# ---------------------------------------------------------------------------

_FINAL_INSPECT_PREFIX = (
    "MODE: FINAL. Run the cross-department audit on this synthesised deliverable "
    "(sources / ethics & compliance / cross-department consistency) and end with a clear "
    "verdict line — PASS, PASS WITH FIXES, or VETO — plus the required fixes as bullet "
    "lines, each naming the departments involved:\n\n"
)


# ---------------------------------------------------------------------------
# The mission loop
# ---------------------------------------------------------------------------

def _mission_loop(
    dossier: dict,
    required_fixes: list,
    deliverable: str,
    dc_fn,
    execute_fn=None,
    _runner=None,
) -> dict:
    """The core iteration loop — shared by run_mission, resume_mission, and run_parallel_mission.

    Drives DIRECTION CHECK → EXECUTE → INSPECT until PASS, VETO cap, or PASS_WITH_FIXES.
    Auto-saves the dossier to disk after each execute run.

    execute_fn: Callable[[dict, list], str]
        Takes (dossier, required_fixes) and returns the deliverable string.
        Must also update dossier['previous_synthesis'] and dossier['decisions'] in-place.
        When None, defaults to a single agency-commander call (the standard mission path).

    _runner: the Runner object to use for the inspect call.
        Defaults to the module-level Runner.  Pass the caller's module-level Runner
        so that monkeypatching in tests (`monkeypatch.setattr(module, 'Runner', stub)`)
        correctly intercepts both the execute and inspect calls.
    """
    from . import store
    goal = dossier["goal"]

    if _runner is None:
        _runner = Runner

    if execute_fn is None:
        def execute_fn(dos, req_fixes):
            result = _runner.run_sync(agency_commander, agency_brief(dos, req_fixes))
            del_text = result.final_output
            dos["previous_synthesis"] = del_text
            dos["decisions"].append({
                "iteration": dos["iteration"],
                "route_executed": list(dos["route"]),
                "direction_check": dos.get("direction_check", {}).get("choice"),
            })
            return del_text

    while dossier["iteration"] < MAX_ITERS:
        dossier["iteration"] += 1
        print(f"\n=== ITERATION {dossier['iteration']}/{MAX_ITERS} ===")

        # ── Direction Check (non-blocking; default auto-proceed) ──────────
        dc_pkg = "\n".join([
            "ROUTE (departments to deploy, in order):",
            json.dumps(dossier["route"], ensure_ascii=False),
            "\nGOAL:",
            goal,
        ])
        dc_choice, dc_note = dc_fn(dc_pkg)
        dossier["direction_check"] = {
            "iteration": dossier["iteration"],
            "choice": dc_choice,
            "note": dc_note,
        }
        print(f"Direction check: {dc_choice}" + (f" — {dc_note}" if dc_note else ""))

        if dc_choice == "STEER":
            steer_note = dc_note or "steer the route / mission framing"
            required_fixes = [f"Direction steer before execution: {steer_note}"]
            classify_input = f"{goal}\n\nUser steer: {steer_note}"
            dossier["route"] = classify(classify_input)
            dossier["context"] = {"classified_departments": dossier["route"], "steered": True}
            print(f"Re-classified route: {dossier['route']}")
            continue

        # ── EXECUTE ───────────────────────────────────────────────────────
        try:
            deliverable = execute_fn(dossier, required_fixes)
        except Exception as exc:
            if _is_quota_error(exc):
                dossier["status"] = "paused_rate_limit"
                dossier["paused_reason"] = str(exc)
                store.save(dossier)
                print(f"\n[quota] Session limit reached — mission paused and saved.")
                print(f"  Resume with:  agency resume {dossier.get('mission_id', '<id>')}")
                return dossier
            raise
        required_fixes = []
        store.save(dossier)  # checkpoint after each execute run

        # ── INSPECT: FINAL cross-department audit ──────────────────────────
        try:
            inspection = _runner.run_sync(
                agency_inspector,
                _FINAL_INSPECT_PREFIX + deliverable,
            )
        except Exception as exc:
            if _is_quota_error(exc):
                dossier["status"] = "paused_rate_limit"
                dossier["paused_reason"] = str(exc)
                store.save(dossier)
                print(f"\n[quota] Session limit reached during inspect — mission saved.")
                print(f"  Resume with:  agency resume {dossier.get('mission_id', '<id>')}")
                return dossier
            raise
        verdict = parse_verdict(inspection.final_output)
        required_fixes = extract_required_fixes(inspection.final_output)
        if verdict != "PASS" and not required_fixes:
            feedback = inspection.final_output.strip()
            if len(feedback) > 2000:
                feedback = feedback[:2000] + "\n... [truncated — full output in dossier verdicts]"
            required_fixes = [f"Inspector {verdict} — feedback:\n{feedback}"]
        dossier["verdicts"].append({
            "iteration": dossier["iteration"],
            "verdict": verdict,
            "required_fixes": required_fixes,
        })
        print(f"Agency inspector verdict: {verdict}  ({len(required_fixes)} required fix(es))")

        if verdict == "PASS":
            dossier["delivered"] = deliverable
            store.save(dossier)
            return dossier

    # Iteration cap reached: deliver with residual risk.
    dossier["delivered"] = deliverable
    dossier["residual_risk"] = (
        "Iteration cap reached without a clean PASS. Delivered the best cross-department result; "
        f"unresolved required fixes: {required_fixes}; "
        f"open_to_verify: {dossier['open_to_verify']}."
    )
    store.save(dossier)
    return dossier


def run_mission(goal: str, dc_fn=auto_proceed) -> dict:
    """Drive the single-stage cross-department loop. Returns the dossier."""
    from . import store
    dossier = new_dossier(goal)
    dossier["mission_id"] = store.new_mission_id(goal)
    dossier["route"] = classify(goal)
    dossier["context"] = {"classified_departments": dossier["route"]}
    print(f"Route: {dossier['route']}")
    return _mission_loop(dossier, [], "", dc_fn)


def resume_mission(mission_id: str, dc_fn=auto_proceed) -> dict:
    """Resume a previously saved mission from its last checkpoint.

    Loads the dossier from ~/.agency/missions/<mission_id>/dossier.json, restores
    the required_fixes from the last verdict, resets the iteration counter so up to
    MAX_ITERS additional attempts are made, and re-enters the loop.
    """
    from . import store
    dossier = store.load(mission_id)
    if dossier.get("delivered"):
        print(f"Mission {mission_id} already delivered — returning saved dossier.")
        return dossier
    verdicts = dossier.get("verdicts") or []
    required_fixes = verdicts[-1].get("required_fixes", []) if verdicts else []
    deliverable = dossier.get("previous_synthesis", "")
    dossier["iteration"] = 0  # fresh cap for the resume attempt
    print(f"Resuming {mission_id} (route: {dossier.get('route')}, {len(required_fixes)} fix(es))")
    return _mission_loop(dossier, required_fixes, deliverable, dc_fn)


# ---------------------------------------------------------------------------
# Console entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Console-script entry point (`agency-kit-mission "<goal>"`)."""
    goal = sys.argv[1] if len(sys.argv) > 1 else "We have a cross-department mission: ... (describe it)"
    # Non-blocking auto-proceed by default; inject console_direction_check (or a custom callable)
    # as dc_fn to enable interactive steering of the route before execution.
    final = run_mission(goal)
    print("\n=== DELIVERED ===")
    print(final.get("delivered", "(nothing)"))
    if final.get("residual_risk"):
        print("\n=== RESIDUAL RISK ===")
        print(final["residual_risk"])


if __name__ == "__main__":
    main()
