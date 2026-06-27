"""End-to-end harness test for the agency mission loop — no SDK, no network, no API key.

conftest injects a fake `agents` module (and all nine department-kit stubs) into sys.modules
BEFORE importing agency_kit.mission — the package, its commander, router, and inspector all do
`from agents import ...` at import time and call `.as_tool()` while building the cross-department
graph. We then drive `run_mission` by scripting `Runner.run_sync` outputs and injecting a
direction-check callable, covering the agency-kit control-flow branches:
  PROCEED->PASS              — happy path (one commander call + PASS inspector)
  DC STEER->loop             — loops the OUTER iteration (re-runs the agency commander)
  VETO->iteration cap        — MAX_ITERS VETOs produce a residual_risk delivery
  PASS_WITH_FIXES->recheck   — loops with required fixes until PASS

NB: like the department kits, the agency has NO mandatory HITL gate — the single Direction Check
is optional and non-blocking (default auto_proceed), so there is no NO-GO branch.

The `agents` SDK and the department kits are stubbed in tests/conftest.py (shared, installed
before any test imports agency_kit).
"""

import pytest

from agency_kit import mission


class _Result:
    def __init__(self, final_output):
        self.final_output = final_output


class ScriptedRunner:
    """Returns scripted final_outputs in order; records the calls made."""

    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = []

    def run_sync(self, agent, inp):
        self.calls.append(getattr(agent, "name", None))
        return _Result(self.outputs.pop(0))


def _checker(sequence):
    """direction_check_fn returning (choice, note) from a scripted sequence."""
    seq = iter(sequence)

    def fn(_package):
        return (next(seq), "test")

    return fn


def _stub_classify(monkeypatch, route=("product", "marketing", "solve")):
    """Pin the router so the loop stays offline.

    classify(goal) is called once before the while-loop and again only after a DC STEER.
    It runs the router through its own Runner (not mission.Runner), so we stub it out.
    The scripted outputs then map one-to-one onto the commander + inspector calls.
    """
    monkeypatch.setattr(mission, "classify", lambda goal: list(route))


# ---- pure helpers ------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("all good, PASS but also VETO on cross-department conflict", "VETO"),
    ("verdict: PASS WITH FIXES", "PASS_WITH_FIXES"),
    ("PASS-WITH-FIXES", "PASS_WITH_FIXES"),
    ("PASS", "PASS"),
    ("", "UNCLEAR"),
])
def test_parse_verdict_priority(text, expected):
    assert mission.parse_verdict(text) == expected


def test_required_fixes_extracted():
    # Section-header pattern: a "Required Fixes (Blocking):" heading whose items are bullets on the
    # following lines (the agency inspector's cross-department reconciliation list).
    txt = (
        "Agency audit complete.\n\n"
        "Required Fixes (Blocking):\n"
        "- product cites a $4B market but marketing cites $7B; reconcile to one source of truth\n"
        "- North Star is weekly active teams but campaign KPI rewards raw signups; align the metric\n"
        "- spec feature 'audit log' is missing from the delivery plan; close the handoff\n"
    )
    fixes = mission.extract_required_fixes(txt)
    assert len(fixes) == 3
    assert any("$4B" in f and "$7B" in f for f in fixes), "market-size conflict fix not extracted"
    assert any("North Star" in f for f in fixes), "metric-mismatch fix not extracted"
    assert any("audit log" in f for f in fixes), "handoff-gap fix not extracted"


def test_required_fixes_bullet_line_with_keyword_not_eaten_as_heading():
    # Regression: a bullet line whose content contains "Required Fix" was misclassified as a
    # section heading, causing the heading-detection guard to set in_fixes_section=True and
    # `continue` — the fix item was silently dropped. Observed: inspector output like
    # "- Required Fix: reconcile the $4B vs $7B discrepancy" returned [] from extract.
    txt = (
        "Agency audit complete.\n\n"
        "VERDICT: PASS WITH FIXES\n\n"
        "- Required Fix: reconcile the $4B vs $7B market-size discrepancy\n"
        "- Required Fix: align North Star metric with campaign KPI\n"
    )
    fixes = mission.extract_required_fixes(txt)
    assert len(fixes) == 2, (
        "bullet lines containing 'Required Fix' keyword must be captured as fix items, not headings"
    )
    assert any("$4B" in f for f in fixes)
    assert any("North Star" in f for f in fixes)


def test_required_fixes_blank_line_between_heading_and_bullets():
    # Regression: blank line between "Required Fixes:" and the first bullet
    # used to close the section before any bullet was captured → [] returned.
    txt = (
        "Required Fixes (Blocking):\n"
        "\n"
        "- reconcile the $4B vs $7B market-size discrepancy\n"
        "- align North Star with campaign KPI\n"
    )
    fixes = mission.extract_required_fixes(txt)
    assert len(fixes) == 2, "blank line between heading and bullets must not close the section"


def test_veto_without_structured_fixes_falls_back_to_inspector_text(monkeypatch):
    # Regression: when the inspector VETOs with prose (no structured "Required Fixes:" section),
    # extract_required_fixes returns [] and the next commander pass ran blind — same output,
    # same VETO, cap hit without progress. Observed in production: missions/001.
    # Fix: fall back to the full inspector output as a single required fix.
    _stub_classify(monkeypatch)
    inspector_prose = (
        "VERDICT: VETO\n"
        "The deliverable is an 'Orphaned Input' stage — no actual NSM was produced, "
        "only clarifying questions. The agency must proceed with reasonable assumptions."
    )
    runner = ScriptedRunner(["OUTPUT", inspector_prose, "OUTPUT2", "VERDICT: PASS"])
    monkeypatch.setattr(mission, "Runner", runner)
    d = mission.run_mission("goal")
    # Iteration 1: VETO with no structured fixes → fallback to inspector text
    iter1_fixes = d["verdicts"][0]["required_fixes"]
    assert len(iter1_fixes) == 1, "fallback required fix must be set when inspector VETO has no structured fixes"
    assert "VETO" in iter1_fixes[0], "fallback must include the verdict type"
    assert "Orphaned Input" in iter1_fixes[0], "fallback must carry the inspector reasoning"
    # Iteration 2: commander received the feedback and produced a passing result
    assert d["verdicts"][1]["verdict"] == "PASS"


# ---- the agency-kit control-flow branches -----------------------------------

def test_happy_path_pass(monkeypatch):
    # single iteration: classify → DC PROCEED → one agency-commander call → PASS inspector → delivered
    _stub_classify(monkeypatch)
    runner = ScriptedRunner(["AGENCY OUTPUT", "VERDICT: PASS"])
    monkeypatch.setattr(mission, "Runner", runner)
    d = mission.run_mission("goal")
    assert "delivered" in d and "residual_risk" not in d
    assert d["iteration"] == 1
    assert d["verdicts"][-1]["verdict"] == "PASS"
    # the agency commander was invoked for the cross-department run, then the inspector
    assert runner.calls == ["commander_agency", "inspector_agency"]


def test_direction_check_steer_loops(monkeypatch):
    # The DC fires AFTER classify but BEFORE the commander, so a STEER re-runs the whole iteration
    # without ever invoking the commander or inspector:
    #   iter 1: classify → DC STEER (loops back, increments the outer iteration; no Runner calls)
    #   iter 2: classify → DC PROCEED → commander → inspector PASS
    _stub_classify(monkeypatch)
    runner = ScriptedRunner(["AGENCY OUTPUT", "VERDICT: PASS"])
    monkeypatch.setattr(mission, "Runner", runner)
    d = mission.run_mission("goal", dc_fn=_checker(["STEER", "PROCEED"]))
    assert d["iteration"] == 2
    assert "delivered" in d
    assert d["direction_check"]["choice"] == "PROCEED"
    # iter 1 steered before any execution, so only one commander+inspector pass ran
    assert runner.calls == ["commander_agency", "inspector_agency"]
    assert len(d["verdicts"]) == 1


def test_iteration_cap_residual_risk(monkeypatch):
    # every iteration: classify → DC PROCEED → commander → VETO; after MAX_ITERS → residual_risk
    _stub_classify(monkeypatch)
    outputs = []
    for _ in range(mission.MAX_ITERS):
        outputs += ["OUTPUT", "VERDICT: VETO"]
    runner = ScriptedRunner(outputs)
    monkeypatch.setattr(mission, "Runner", runner)
    d = mission.run_mission("goal")
    assert d["iteration"] == mission.MAX_ITERS
    assert "residual_risk" in d
    assert d["verdicts"][-1]["verdict"] == "VETO"


def test_pass_with_fixes_loops(monkeypatch):
    # iter 1: classify → DC PROCEED → commander → PASS_WITH_FIXES (loops with required fixes)
    # iter 2: classify → DC PROCEED → commander → PASS (delivered)
    _stub_classify(monkeypatch)
    runner = ScriptedRunner(["OUTPUT1", "VERDICT: PASS WITH FIXES", "OUTPUT2", "VERDICT: PASS"])
    monkeypatch.setattr(mission, "Runner", runner)
    d = mission.run_mission("goal")
    assert d["iteration"] == 2
    assert "delivered" in d and "residual_risk" not in d
    assert d["verdicts"][0]["verdict"] == "PASS_WITH_FIXES"
    assert d["verdicts"][1]["verdict"] == "PASS"


def test_resume_mission(monkeypatch):
    """resume_mission loads a saved dossier and continues from the last VETO checkpoint."""
    import agency_kit.store as st

    saved = {
        "goal": "resume goal",
        "mission_id": "20260101-000000-resume-goal",
        "route": ["product"],
        "context": {"classified_departments": ["product"]},
        "dept_outputs": {},
        "decisions": [],
        "sources": [],
        "open_to_verify": [],
        "direction_check": None,
        "verdicts": [{"iteration": 1, "verdict": "VETO", "required_fixes": ["Fix X"]}],
        "iteration": 1,
        "previous_synthesis": "PREV OUTPUT",
    }
    monkeypatch.setattr(st, "load", lambda mid: dict(saved))
    monkeypatch.setattr(st, "save", lambda d: None)
    _stub_classify(monkeypatch)
    runner = ScriptedRunner(["OUTPUT2", "VERDICT: PASS"])
    monkeypatch.setattr(mission, "Runner", runner)

    d = mission.resume_mission("20260101-000000-resume-goal")
    assert "delivered" in d
    assert d["verdicts"][-1]["verdict"] == "PASS"
    assert runner.calls == ["commander_agency", "inspector_agency"]


def test_parallel_happy_path(monkeypatch):
    """Parallel runner: single-dept route (product) → synthesis → inspect → PASS."""
    from agency_kit import parallel
    import agency_kit.store as st

    monkeypatch.setattr(st, "save", lambda d: None)
    monkeypatch.setattr(parallel, "classify", lambda g: ["product"])

    # Calls in order: commander_product (dept), commander_agency (synthesis), inspector_agency
    runner = ScriptedRunner(["PRODUCT OUT", "SYNTHESIS OUT", "VERDICT: PASS"])
    monkeypatch.setattr(parallel, "Runner", runner)

    d = parallel.run_parallel_mission("goal")
    assert "delivered" in d
    assert d["verdicts"][-1]["verdict"] == "PASS"
    assert d["dept_outputs"].get("product") == "PRODUCT OUT"
    assert d["decisions"][0]["execution_mode"] == "parallel"


# ---- quota / rate-limit handling -------------------------------------------
# Bug surface: Runner.run_sync in mission.py (commander + inspector) and in
# parallel.py (dept execution, synthesis, inspect) were not wrapped; a quota
# error crashed the mission instead of saving state and printing resume instructions.

class _QuotaRunner:
    """Returns scripted outputs for the first N calls, then raises a quota error."""

    def __init__(self, ok_outputs, fail_on):
        self.outputs = list(ok_outputs)
        self.fail_on = fail_on
        self.calls = 0

    def run_sync(self, agent, inp):
        n = self.calls
        self.calls += 1
        if n >= self.fail_on:
            raise RuntimeError("session limit reached — resets 5:00 am")
        return _Result(self.outputs[n])


def test_mission_quota_during_commander(monkeypatch):
    _stub_classify(monkeypatch)
    import agency_kit.store as st
    saved = {}
    monkeypatch.setattr(st, "save", lambda d: saved.update(d))
    runner = _QuotaRunner(ok_outputs=[], fail_on=0)
    monkeypatch.setattr(mission, "Runner", runner)

    d = mission.run_mission("goal")
    assert d.get("status") == "paused_rate_limit", "quota during commander must set paused status"
    assert "paused_reason" in d
    assert saved.get("status") == "paused_rate_limit", "dossier must be saved on quota pause"


def test_mission_quota_during_inspector(monkeypatch):
    _stub_classify(monkeypatch)
    import agency_kit.store as st
    saved = {}
    monkeypatch.setattr(st, "save", lambda d: saved.update(d))
    runner = _QuotaRunner(ok_outputs=["COMMANDER OUTPUT"], fail_on=1)
    monkeypatch.setattr(mission, "Runner", runner)

    d = mission.run_mission("goal")
    assert d.get("status") == "paused_rate_limit", "quota during inspector must set paused status"
    assert saved.get("status") == "paused_rate_limit"


def test_parallel_quota_during_dept(monkeypatch):
    from agency_kit import parallel
    import agency_kit.store as st

    saved = {}
    monkeypatch.setattr(st, "save", lambda d: saved.update(d))
    monkeypatch.setattr(parallel, "classify", lambda g: ["product"])
    runner = _QuotaRunner(ok_outputs=[], fail_on=0)
    monkeypatch.setattr(parallel, "Runner", runner)

    d = parallel.run_parallel_mission("goal")
    assert d.get("status") == "paused_rate_limit", "quota during dept must pause the parallel mission"
    assert saved.get("status") == "paused_rate_limit"


def test_parallel_quota_during_synthesis(monkeypatch):
    from agency_kit import parallel
    import agency_kit.store as st

    saved = {}
    monkeypatch.setattr(st, "save", lambda d: saved.update(d))
    monkeypatch.setattr(parallel, "classify", lambda g: ["product"])
    # Call 0: dept (product) succeeds; call 1: synthesis raises quota
    runner = _QuotaRunner(ok_outputs=["PRODUCT OUT"], fail_on=1)
    monkeypatch.setattr(parallel, "Runner", runner)

    d = parallel.run_parallel_mission("goal")
    assert d.get("status") == "paused_rate_limit", "quota during synthesis must pause the parallel mission"
    assert d["dept_outputs"].get("product") == "PRODUCT OUT", "dept output should be preserved before pause"


def test_parallel_quota_during_inspect(monkeypatch):
    from agency_kit import parallel
    import agency_kit.store as st

    saved = {}
    monkeypatch.setattr(st, "save", lambda d: saved.update(d))
    monkeypatch.setattr(parallel, "classify", lambda g: ["product"])
    # Calls 0-1 succeed (dept + synthesis); call 2 (inspect) raises quota
    runner = _QuotaRunner(ok_outputs=["PRODUCT OUT", "SYNTHESIS OUT"], fail_on=2)
    monkeypatch.setattr(parallel, "Runner", runner)

    d = parallel.run_parallel_mission("goal")
    assert d.get("status") == "paused_rate_limit", "quota during inspect must pause the parallel mission"
    assert saved.get("status") == "paused_rate_limit"


# ---- store.new_mission_id atomic lock ---------------------------------------
# Bug surface: two parallel batch workers calling new_mission_id concurrently
# would not deadlock after the lock was added, but would the lock be released?

def test_new_mission_id_lock_not_leaked(tmp_path, monkeypatch):
    import agency_kit.store as st
    monkeypatch.setattr(st, "_agency_dir", lambda: tmp_path)

    id1 = st.new_mission_id("first goal")
    id2 = st.new_mission_id("first goal")  # must not deadlock

    assert id1.endswith("-first-goal"), f"unexpected ID format: {id1}"
    assert id2.endswith("-first-goal"), f"unexpected ID format: {id2}"
    assert not (tmp_path / ".mission-id.lock").exists(), "lock directory must be removed after use"
