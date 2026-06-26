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
import sys

from agents import Runner

from .commander import agency_commander
from .inspector import agency_inspector
from .router import classify

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
    import re
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
# The mission loop
# ---------------------------------------------------------------------------

def run_mission(goal: str, dc_fn=auto_proceed) -> dict:
    """Drive the single-stage cross-department loop. Returns the dossier.

    Each outer iteration: CLASSIFY (router) once, offer ONE optional Direction Check (after
    classify, before execute), run the agency commander (which internally routes, deploys
    departments, and synthesises), then run the FINAL agency inspector.
      DC STEER → add steer note to required_fixes, re-run the iteration (re-classify + re-execute).
    Inspector VETO / PASS_WITH_FIXES → add required_fixes, loop the iteration.
    """
    dossier = new_dossier(goal)
    required_fixes: list = []
    deliverable = ""

    # Classify once up front — re-classify only when the user steers the route.
    dossier["route"] = classify(goal)
    print(f"Route: {dossier['route']}")

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
            required_fixes = [
                "Direction steer before execution: "
                + (dc_note or "steer the route / mission framing")
            ]
            dossier["route"] = classify(goal)  # re-classify after user steer
            print(f"Re-classified route: {dossier['route']}")
            continue

        # ── EXECUTE: the agency commander routes, deploys, and synthesises ─
        mission_result = Runner.run_sync(agency_commander, agency_brief(dossier, required_fixes))
        deliverable = mission_result.final_output
        # Carry the synthesis forward so the next iteration builds on it rather than
        # re-running all departments from scratch with an empty dossier.
        dossier["previous_synthesis"] = deliverable
        required_fixes = []

        # ── INSPECT: FINAL cross-department audit ──────────────────────────
        inspection = Runner.run_sync(
            agency_inspector,
            "MODE: FINAL. Run the cross-department audit on this synthesised deliverable "
            "(sources / ethics & compliance / cross-department consistency) and end with a clear "
            "verdict line — PASS, PASS WITH FIXES, or VETO — plus the required fixes as bullet "
            "lines, each naming the departments involved:\n\n" + deliverable,
        )
        verdict = parse_verdict(inspection.final_output)
        required_fixes = extract_required_fixes(inspection.final_output)
        # If the inspector vetoed/flagged but no structured fixes were extracted,
        # carry the inspector feedback so the commander has reasoning on re-entry.
        # Cap at 2000 chars to avoid context-window overflow on verbose VETO essays.
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
            return dossier
        # VETO, PASS_WITH_FIXES, or UNCLEAR → loop with required fixes; full re-run.

    # Iteration cap reached: deliver the best result with residual risk stated.
    dossier["delivered"] = deliverable
    dossier["residual_risk"] = (
        "Iteration cap reached without a clean PASS. Delivered the best cross-department result; "
        f"unresolved required fixes: {required_fixes}; "
        f"open_to_verify: {dossier['open_to_verify']}."
    )
    return dossier


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
