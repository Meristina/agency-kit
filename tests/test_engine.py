"""Tests for the CLI-engine mission path (`agency_cli/engines/cli_engine.py`).

The engine shells out to a local agent CLI (claude/codex/gemini). Tests stub the
`_call` subprocess wrapper so they run offline with no CLI installed.
"""

import signal
import threading

import pytest

from agency_cli.engines import cli_engine


def test_engines_registry_has_three_web_search_engines():
    assert {"claude-code", "codex", "gemini"} <= set(cli_engine.ENGINES)
    assert {"claude-code", "codex", "gemini"} <= set(cli_engine._ROUTE_CMD)


def test_route_via_cli_parses_json_array(monkeypatch):
    monkeypatch.setattr(cli_engine, "_call", lambda cmd, prompt, timeout=900, should_cancel=None: '["solve", "product"]')
    assert cli_engine._route_via_cli("claude-code", "fix our broken funnel") == ["solve", "product"]


def test_route_via_cli_falls_back_to_keyword(monkeypatch):
    # Unparseable CLI output → keyword_classify fallback.
    monkeypatch.setattr(cli_engine, "_call", lambda cmd, prompt, timeout=900, should_cancel=None: "not json at all")
    route = cli_engine._route_via_cli("claude-code", "write a marketing campaign")
    assert route == ["marketing"]


def test_route_prompt_loads_doctrine_and_forces_json_array(monkeypatch):
    seen = {}

    def _capture(cmd, prompt, timeout=900, should_cancel=None):
        seen["prompt"] = prompt
        return '["product"]'

    monkeypatch.setattr(cli_engine, "_call", _capture)
    cli_engine._route_via_cli("claude-code", "build an app")
    p = seen["prompt"].lower()
    # Doctrine (router-agency.md) is loaded — carries the problem-led guardrail.
    assert "problem-led" in p, "routing prompt must load router-agency.md (problem-led guardrail)"
    # Output format is forced to a JSON array for parsing.
    assert "json array" in p, "routing prompt must force JSON-array output"
    # The goal is injected.
    assert "build an app" in seen["prompt"], "routing prompt must include the goal"


def test_run_mission_cli_returns_dossier_shape(monkeypatch):
    # Mock only the boundaries: PATH lookup + the subprocess wrapper. The real
    # _route_via_cli runs and parses the JSON array the first _call returns.
    monkeypatch.setattr(cli_engine.shutil, "which", lambda b: "/usr/local/bin/" + b)
    calls = {"n": 0}

    def _fake_call(cmd, prompt, timeout=900, should_cancel=None):
        calls["n"] += 1
        if calls["n"] == 1:               # routing call → parsed by _route_via_cli
            return '["solve", "product"]'
        return f"OUTPUT {calls['n']}"      # dept / synthesis / inspect text

    monkeypatch.setattr(cli_engine, "_call", _fake_call)

    dossier = cli_engine.run_mission_cli("diagnose and rebuild our onboarding", engine="claude-code")

    assert dossier["route"] == ["solve", "product"]
    assert set(dossier["dept_outputs"]) == {"solve", "product"}
    assert dossier["delivered"]
    assert dossier["verdicts"][0]["engine"] == "claude-code"
    # At least one engine call per routed dept plus synthesis + inspect — exact
    # count is an implementation detail; the dossier shape above is the contract.
    assert calls["n"] >= len(dossier["route"]) + 2


def _scripted_engine(monkeypatch, inspector_verdicts):
    """Stub the _call boundary: route → JSON array, inspect → next scripted verdict,
    everything else → canned dept/synth text. Keys off the prompt's stable instructions
    so it never depends on call ordering."""
    monkeypatch.setattr(cli_engine.shutil, "which", lambda b: "/usr/local/bin/" + b)
    seq = iter(inspector_verdicts)

    def _call(cmd, prompt, timeout=900, should_cancel=None):
        low = prompt.lower()
        if "json array" in low:
            return '["product"]'
        if "issue a verdict" in low:
            return next(seq)
        return "DEPARTMENT / SYNTHESIS OUTPUT"

    monkeypatch.setattr(cli_engine, "_call", _call)


def test_mission_passes_first_iteration(monkeypatch):
    _scripted_engine(monkeypatch, ["VERDICT: PASS"])
    d = cli_engine.run_mission_cli("ship a feature", engine="claude-code")
    assert d["iteration"] == 1
    assert d["verdicts"][-1]["verdict"] == "PASS"
    assert "residual_risk" not in d


def test_mission_veto_then_retries_to_pass(monkeypatch):
    # Art. IX: a VETO must trigger another iteration, not a skip.
    _scripted_engine(monkeypatch, ["VETO: invented stat", "VERDICT: PASS"])
    d = cli_engine.run_mission_cli("diagnose churn and relaunch", engine="claude-code")
    assert d["iteration"] == 2
    assert [v["verdict"] for v in d["verdicts"]] == ["VETO", "PASS"]
    assert "residual_risk" not in d


def test_mission_caps_with_residual_risk(monkeypatch):
    # Inspector never passes → stop at MAX_ITERS and flag residual risk.
    _scripted_engine(monkeypatch, ["VETO", "VETO", "VETO", "VETO"])
    d = cli_engine.run_mission_cli("hard mission", engine="claude-code")
    assert d["iteration"] == cli_engine.MAX_ITERS
    assert len(d["verdicts"]) == cli_engine.MAX_ITERS
    assert "residual_risk" in d and "did not PASS" in d["residual_risk"]


def test_run_mission_cli_rejects_unknown_engine():
    with pytest.raises(ValueError):
        cli_engine.run_mission_cli("goal", engine="nonsense")


class _FakePopen:
    """Stand-in for ``subprocess.Popen`` driving ``_call`` offline.

    ``communicate`` returns ``(out, err)`` once the process is considered finished:
    immediately when ``block`` is False, or only once ``unblock()`` is called when
    ``block`` is True (to simulate a long-running CLI that a cancel must interrupt).
    ``unblock`` is what a stubbed ``os.killpg`` calls — the real kill path goes
    through the process group, not ``proc.terminate``."""

    def __init__(self, out="", err="", returncode=0, block=False):
        self._out, self._err, self.returncode = out, err, returncode
        self.pid = 4321
        self._done = threading.Event()
        if not block:
            self._done.set()

    def communicate(self, timeout=None):
        self._done.wait()
        return self._out, self._err

    def unblock(self, returncode=-15):
        self.returncode = returncode
        self._done.set()


def _patch_groupkill(monkeypatch, fake):
    """Route _signal_tree's os.killpg at a blocking _FakePopen: record the signal and
    release communicate(), so the kill path is exercised without a real process."""
    sent = []
    monkeypatch.setattr(cli_engine.os, "getpgid", lambda pid: pid)
    monkeypatch.setattr(
        cli_engine.os, "killpg",
        lambda _pgid, sig: (sent.append(sig), fake.unblock()),
    )
    return sent


def test_call_returns_stripped_stdout_on_success(monkeypatch):
    fake = _FakePopen(out="  delivered text \n", returncode=0)
    monkeypatch.setattr(cli_engine.subprocess, "Popen", lambda *a, **k: fake)
    assert cli_engine._call(["claude", "-p"], "hi") == "delivered text"


def test_call_raises_on_empty_output(monkeypatch):
    # returncode 0 but empty stdout → clear error, not a silent empty deliverable.
    fake = _FakePopen(out="   ", returncode=0)
    monkeypatch.setattr(cli_engine.subprocess, "Popen", lambda *a, **k: fake)
    with pytest.raises(RuntimeError, match="empty output"):
        cli_engine._call(["claude", "-p"], "hi")


def test_call_raises_on_nonzero_exit_surfacing_detail(monkeypatch):
    fake = _FakePopen(out="", err="boom on stderr", returncode=2)
    monkeypatch.setattr(cli_engine.subprocess, "Popen", lambda *a, **k: fake)
    with pytest.raises(RuntimeError, match="exited 2: boom on stderr"):
        cli_engine._call(["claude", "-p"], "hi")


def test_call_terminates_inflight_subprocess_on_cancel(monkeypatch):
    # The real Stop (v2): a cancel that fires while a call is in flight must KILL the
    # child's process group immediately and raise MissionCancelled — not wait for the
    # timeout. SIGTERM is the first escalation step.
    monkeypatch.setattr(cli_engine, "_CANCEL_POLL_SECONDS", 0.01)
    fake = _FakePopen(out="never returned", block=True)
    monkeypatch.setattr(cli_engine.subprocess, "Popen", lambda *a, **k: fake)
    sent = _patch_groupkill(monkeypatch, fake)
    with pytest.raises(cli_engine.MissionCancelled):
        cli_engine._call(["claude", "-p"], "hi", should_cancel=lambda: True)
    assert signal.SIGTERM in sent, "an in-flight child group must be signalled on cancel"


def test_call_escalates_to_sigkill_when_sigterm_is_ignored(monkeypatch):
    # The second half of _terminate (cli_engine.py:102-104): a stubborn child that
    # ignores SIGTERM must be escalated to SIGKILL after the grace window. Here only
    # SIGKILL releases the blocked reader, so the SIGTERM grace must elapse and the
    # escalation fire — otherwise the test would hang. Shrink the grace so it's fast.
    monkeypatch.setattr(cli_engine, "_CANCEL_POLL_SECONDS", 0.01)
    monkeypatch.setattr(cli_engine, "_TERMINATE_GRACE", 0.05)
    fake = _FakePopen(out="ignores SIGTERM", block=True)
    monkeypatch.setattr(cli_engine.subprocess, "Popen", lambda *a, **k: fake)

    sent = []
    monkeypatch.setattr(cli_engine.os, "getpgid", lambda pid: pid)

    def _killpg(_pgid, sig):
        sent.append(sig)
        if sig == signal.SIGKILL:  # only the kill releases the stubborn child
            fake.unblock()

    monkeypatch.setattr(cli_engine.os, "killpg", _killpg)

    with pytest.raises(cli_engine.MissionCancelled):
        cli_engine._call(["claude", "-p"], "hi", should_cancel=lambda: True)
    assert sent == [signal.SIGTERM, signal.SIGKILL], "SIGTERM first, then SIGKILL escalation, in order"


def test_call_raises_runtime_on_timeout(monkeypatch):
    # A withheld child past its deadline is terminated (group kill) and reported as a
    # timeout.
    monkeypatch.setattr(cli_engine, "_CANCEL_POLL_SECONDS", 0.01)
    fake = _FakePopen(block=True)
    monkeypatch.setattr(cli_engine.subprocess, "Popen", lambda *a, **k: fake)
    sent = _patch_groupkill(monkeypatch, fake)
    with pytest.raises(RuntimeError, match="timed out after 0s"):
        cli_engine._call(["claude", "-p"], "hi", timeout=0)
    assert signal.SIGTERM in sent


def test_call_kills_tree_on_keyboard_interrupt(monkeypatch):
    # start_new_session detaches the child from our group, so a terminal Ctrl-C no
    # longer reaches it — _call must kill the tree itself and re-raise, never orphan
    # an in-flight engine process.
    monkeypatch.setattr(cli_engine, "_CANCEL_POLL_SECONDS", 0.01)
    fake = _FakePopen(block=True)
    monkeypatch.setattr(cli_engine.subprocess, "Popen", lambda *a, **k: fake)
    sent = _patch_groupkill(monkeypatch, fake)

    def _interrupt():
        raise KeyboardInterrupt()

    with pytest.raises(KeyboardInterrupt):
        cli_engine._call(["claude", "-p"], "hi", should_cancel=_interrupt)
    assert signal.SIGTERM in sent, "Ctrl-C must kill the in-flight tree, not orphan it"


def test_short_verdict_extracts_token():
    assert cli_engine._short_verdict("...everything checks out. VERDICT: PASS") == "PASS"
    assert cli_engine._short_verdict("found invented data — VETO") == "VETO"
    assert cli_engine._short_verdict("VERDICT: PASS-WITH-FIXES, see notes") == "PASS-WITH-FIXES"
    assert cli_engine._short_verdict("no verdict word here") == "DELIVERED"


def test_extract_sources_pulls_urls_deduped_in_order():
    text = (
        "## Sources cited\n"
        "| # | Source | URL |\n"
        "| 1 | Scrum Alliance | https://example.com/a |\n"
        "| 2 | Mountain Goat | https://example.com/b |\n"
        "See also the inline [study](https://example.com/a) again, and bare "
        "https://example.com/c."
    )
    # First-seen order, de-duplicated, trailing sentence punctuation stripped.
    assert cli_engine._extract_sources(text) == [
        "https://example.com/a",
        "https://example.com/b",
        "https://example.com/c",
    ]


def test_extract_sources_empty_when_no_urls():
    assert cli_engine._extract_sources("no links here") == []
    assert cli_engine._extract_sources("") == []


def test_run_mission_cli_populates_sources_from_deliverable(monkeypatch):
    # Sources are extracted from the final synthesis text into the structured field.
    monkeypatch.setattr(cli_engine.shutil, "which", lambda b: "/usr/local/bin/" + b)

    def _call(cmd, prompt, timeout=900, should_cancel=None):
        low = prompt.lower()
        if "json array" in low:
            return '["solve"]'
        if "issue a verdict" in low:
            return "VERDICT: PASS"
        return "Findings. Source: https://example.com/x and https://example.com/y"

    monkeypatch.setattr(cli_engine, "_call", _call)
    d = cli_engine.run_mission_cli("diagnose", engine="claude-code")
    assert d["sources"] == ["https://example.com/x", "https://example.com/y"]


def test_run_mission_cli_raises_clear_error_when_binary_missing(monkeypatch):
    # Engine known but its CLI is not on PATH → fail fast with a clear RuntimeError.
    monkeypatch.setattr(cli_engine.shutil, "which", lambda b: None)
    with pytest.raises(RuntimeError, match="not found on PATH|needs the"):
        cli_engine.run_mission_cli("goal", engine="gemini")


def test_call_reports_missing_binary(monkeypatch):
    # Popen raising FileNotFoundError becomes a clear RuntimeError.
    def _boom(*a, **k):
        raise FileNotFoundError(2, "No such file or directory")

    monkeypatch.setattr(cli_engine.subprocess, "Popen", _boom)
    with pytest.raises(RuntimeError, match="not found on PATH"):
        cli_engine._call(["claude", "-p"], "hello")


# ── cooperative cancellation (the real Stop) ────────────────────────────────

def _counting_engine(monkeypatch):
    """Stub the _call boundary and return the shared call counter. Routing is the
    first call (→ two depts); every later call is dept/synth/inspect text."""
    monkeypatch.setattr(cli_engine.shutil, "which", lambda b: "/usr/local/bin/" + b)
    calls = {"n": 0}

    def _call(cmd, prompt, timeout=900, should_cancel=None):
        calls["n"] += 1
        if calls["n"] == 1:
            return '["solve", "product"]'
        return f"OUTPUT {calls['n']}"

    monkeypatch.setattr(cli_engine, "_call", _call)
    return calls


def test_cancel_at_route_boundary_raises_before_any_department(monkeypatch):
    # CP1: a cancel requested before departments start must stop the mission with
    # only the routing call spent — no department is ever invoked.
    calls = _counting_engine(monkeypatch)
    with pytest.raises(cli_engine.MissionCancelled):
        cli_engine.run_mission_cli("rebuild onboarding", should_cancel=lambda: True)
    assert calls["n"] == 1, "no department _call may run once cancel fires at CP1"


def test_cancel_after_departments_raises_before_synthesis(monkeypatch):
    # CP3: cancel fires only after both departments have run (3 calls: route + 2
    # depts). The synthesise→inspect loop must never start — no further _call.
    calls = _counting_engine(monkeypatch)
    with pytest.raises(cli_engine.MissionCancelled):
        cli_engine.run_mission_cli("rebuild onboarding", should_cancel=lambda: calls["n"] >= 3)
    assert calls["n"] == 3, "synthesis/inspect must not run once cancel fires at CP3"


def test_should_cancel_false_runs_to_completion(monkeypatch):
    # An always-False predicate is byte-identical to no predicate: full dossier.
    _counting_engine(monkeypatch)
    dossier = cli_engine.run_mission_cli("rebuild onboarding", should_cancel=lambda: False)
    assert set(dossier["dept_outputs"]) == {"solve", "product"}
    assert dossier["delivered"]
    assert dossier["verdicts"]


# ── asset_clause (Wave 3 D1 — additive, default-None, byte-identical) ────────
#
# The studio may append a generic asset-capability clause to the department and
# synthesis prompts so a department/synthesis can emit fenced `asset` markers.
# The contract mirrors on_event/should_cancel: default None ⇒ byte-identical to
# standalone agency-kit, and the clause is NEVER shown to the router or inspector
# (those see the unmodified goal).

ASSET_CLAUSE = "ASSET CAPABILITY: you may embed one fenced ```asset JSON block."


def test_dept_prompt_byte_identical_without_clause():
    # The new param defaults to None → identical to the pre-Wave-3 no-arg prompt.
    base = cli_engine._dept_prompt("marketing", "launch a brand", {})
    assert base == cli_engine._dept_prompt("marketing", "launch a brand", {}, asset_clause=None)


def test_dept_prompt_appends_clause_verbatim_only_when_set():
    base = cli_engine._dept_prompt("marketing", "launch a brand", {})
    withc = cli_engine._dept_prompt("marketing", "launch a brand", {}, asset_clause=ASSET_CLAUSE)
    # Clause appended verbatim at the very end; the delta is exact, nothing else moves.
    assert withc == base + "\n\n" + ASSET_CLAUSE


def test_dept_prompt_empty_clause_is_noop():
    # A falsy clause ("") must not append a trailing separator → byte-identical.
    base = cli_engine._dept_prompt("solve", "fix it", {})
    assert cli_engine._dept_prompt("solve", "fix it", {}, asset_clause="") == base


def test_synth_prompt_byte_identical_without_clause():
    base = cli_engine._synth_prompt("g", ["marketing"], {})
    assert base == cli_engine._synth_prompt("g", ["marketing"], {}, asset_clause=None)


def test_synth_prompt_appends_clause_verbatim_only_when_set():
    base = cli_engine._synth_prompt("g", ["marketing"], {})
    withc = cli_engine._synth_prompt("g", ["marketing"], {}, asset_clause=ASSET_CLAUSE)
    assert withc == base + "\n\n" + ASSET_CLAUSE


def test_synth_prompt_clause_composes_with_fixes():
    # The fixes block (veto loop) and asset_clause are independent; clause stays last,
    # so the veto-loop logic the Inspector depends on is untouched (Art. IX).
    base = cli_engine._synth_prompt("g", ["marketing"], {}, fixes="resolve X")
    withc = cli_engine._synth_prompt(
        "g", ["marketing"], {}, fixes="resolve X", asset_clause=ASSET_CLAUSE
    )
    assert withc == base + "\n\n" + ASSET_CLAUSE
    assert "resolve X" in withc


def _capture_prompts_engine(monkeypatch):
    """Stub _call to record every prompt and return canned, marker-keyed output."""
    monkeypatch.setattr(cli_engine.shutil, "which", lambda b: "/usr/local/bin/" + b)
    prompts = []

    def _call(cmd, prompt, timeout=900, should_cancel=None):
        prompts.append(prompt)
        low = prompt.lower()
        if "json array" in low:
            return '["marketing"]'
        if "issue a verdict" in low:
            return "VERDICT: PASS"
        return "DELIVERED OUTPUT"

    monkeypatch.setattr(cli_engine, "_call", _call)
    return prompts


def test_run_mission_cli_threads_clause_to_dept_and_synth_only(monkeypatch):
    prompts = _capture_prompts_engine(monkeypatch)
    cli_engine.run_mission_cli("launch a brand", asset_clause=ASSET_CLAUSE)
    # Classify by the same stable prompt markers _scripted_engine keys off, so the
    # buckets are collapse-proof by construction (not value-exclusion of one another).
    route = [p for p in prompts if "json array" in p.lower()]
    inspect = [p for p in prompts if "issue a verdict" in p.lower()]
    dept_synth = [
        p for p in prompts
        if "json array" not in p.lower() and "issue a verdict" not in p.lower()
    ]
    assert route and inspect and dept_synth
    # Clause reaches the department + synthesis prompts...
    assert all(ASSET_CLAUSE in p for p in dept_synth)
    # ...but never the router or the inspector — they see the unmodified goal.
    assert all(ASSET_CLAUSE not in p for p in route)
    assert all(ASSET_CLAUSE not in p for p in inspect)


def test_run_mission_cli_default_none_appends_no_clause(monkeypatch):
    # Standalone path: no clause set ⇒ it appears in NO prompt (byte-identical run).
    prompts = _capture_prompts_engine(monkeypatch)
    cli_engine.run_mission_cli("launch a brand")
    assert all(ASSET_CLAUSE not in p for p in prompts)


# ── context_clause (Wave 4 D1 — additive, default-None, byte-identical) ──────
#
# The studio's RAG hook appends sourced excerpts from the user's uploaded documents
# to the department + synthesis prompts. Same contract as asset_clause: default None
# ⇒ byte-identical to standalone agency-kit, and the clause is NEVER shown to the
# router or inspector (those see the unmodified goal).

CONTEXT_CLAUSE = "REFERENCE DOCUMENTS:\n[1] Solar Basics\nPanels convert sunlight."


def test_dept_prompt_byte_identical_without_context_clause():
    base = cli_engine._dept_prompt("marketing", "launch a brand", {})
    assert base == cli_engine._dept_prompt("marketing", "launch a brand", {}, context_clause=None)


def test_dept_prompt_appends_context_clause_verbatim_only_when_set():
    base = cli_engine._dept_prompt("marketing", "launch a brand", {})
    withc = cli_engine._dept_prompt("marketing", "launch a brand", {}, context_clause=CONTEXT_CLAUSE)
    assert withc == base + "\n\n" + CONTEXT_CLAUSE


def test_dept_prompt_empty_context_clause_is_noop():
    base = cli_engine._dept_prompt("solve", "fix it", {})
    assert cli_engine._dept_prompt("solve", "fix it", {}, context_clause="") == base


def test_synth_prompt_byte_identical_without_context_clause():
    base = cli_engine._synth_prompt("g", ["marketing"], {})
    assert base == cli_engine._synth_prompt("g", ["marketing"], {}, context_clause=None)


def test_context_and_asset_clauses_compose_in_order():
    # Both hooks may be set at once. context_clause is appended first, then asset_clause,
    # so the two are independent and the deltas are exact (nothing else moves).
    base = cli_engine._dept_prompt("marketing", "launch a brand", {})
    both = cli_engine._dept_prompt(
        "marketing", "launch a brand", {},
        asset_clause=ASSET_CLAUSE, context_clause=CONTEXT_CLAUSE,
    )
    assert both == base + "\n\n" + CONTEXT_CLAUSE + "\n\n" + ASSET_CLAUSE


def test_synth_context_clause_composes_with_fixes():
    # The veto-loop fixes block and context_clause are independent (Art. IX untouched).
    base = cli_engine._synth_prompt("g", ["marketing"], {}, fixes="resolve X")
    withc = cli_engine._synth_prompt(
        "g", ["marketing"], {}, fixes="resolve X", context_clause=CONTEXT_CLAUSE
    )
    assert withc == base + "\n\n" + CONTEXT_CLAUSE
    assert "resolve X" in withc


def test_run_mission_cli_threads_context_clause_to_dept_and_synth_only(monkeypatch):
    prompts = _capture_prompts_engine(monkeypatch)
    cli_engine.run_mission_cli("launch a brand", context_clause=CONTEXT_CLAUSE)
    route = [p for p in prompts if "json array" in p.lower()]
    inspect = [p for p in prompts if "issue a verdict" in p.lower()]
    dept_synth = [
        p for p in prompts
        if "json array" not in p.lower() and "issue a verdict" not in p.lower()
    ]
    assert route and inspect and dept_synth
    assert all(CONTEXT_CLAUSE in p for p in dept_synth)   # reaches dept + synthesis...
    assert all(CONTEXT_CLAUSE not in p for p in route)    # ...never the router...
    assert all(CONTEXT_CLAUSE not in p for p in inspect)  # ...never the inspector


def test_run_mission_cli_default_none_appends_no_context_clause(monkeypatch):
    prompts = _capture_prompts_engine(monkeypatch)
    cli_engine.run_mission_cli("launch a brand")
    assert all(CONTEXT_CLAUSE not in p for p in prompts)


# ── Wave 6 — MCP tool-calling hook (_with_mcp + run_mission_cli threading) ───────

def test_with_mcp_none_is_unchanged():
    base = cli_engine.ENGINES["claude-code"]
    assert cli_engine._with_mcp(base, None, None) is base
    assert cli_engine._with_mcp(base, None, ["mcp__x"]) is base


def test_with_mcp_splices_config_and_tools_without_mutating_base():
    base = cli_engine.ENGINES["claude-code"]
    out = cli_engine._with_mcp(base, "/tmp/mcp.json", ["mcp__wiki", "mcp__db"])
    assert out == ["claude", "--allowedTools", "WebSearch", "mcp__wiki", "mcp__db",
                   "--mcp-config", "/tmp/mcp.json", "--strict-mcp-config", "-p"]
    assert cli_engine.ENGINES["claude-code"] == ["claude", "--allowedTools", "WebSearch", "-p"]


def test_with_mcp_config_without_tools_still_adds_config():
    base = cli_engine.ENGINES["claude-code"]
    out = cli_engine._with_mcp(base, "/tmp/m.json", None)
    assert out == ["claude", "--allowedTools", "WebSearch",
                   "--mcp-config", "/tmp/m.json", "--strict-mcp-config", "-p"]


def test_with_mcp_leaves_non_allowedtools_engine_untouched():
    codex = cli_engine.ENGINES["codex"]   # no --allowedTools flag
    assert cli_engine._with_mcp(codex, "/tmp/m.json", ["mcp__x"]) is codex


def _capture_cmds_engine(monkeypatch):
    """Stub _call to record the (marker, cmd) of every phase — so a test can assert which
    phases receive the MCP-augmented command. Classifies by the same stable prompt markers."""
    monkeypatch.setattr(cli_engine.shutil, "which", lambda b: "/usr/local/bin/" + b)
    seen = []

    def _call(cmd, prompt, timeout=900, should_cancel=None):
        low = prompt.lower()
        if "json array" in low:
            seen.append(("route", list(cmd)))
            return '["marketing"]'
        if "issue a verdict" in low:
            seen.append(("inspect", list(cmd)))
            return "VERDICT: PASS"
        seen.append(("exec", list(cmd)))   # dept or synthesis
        return "DELIVERED OUTPUT"

    monkeypatch.setattr(cli_engine, "_call", _call)
    return seen


def test_run_mission_cli_threads_mcp_into_dept_and_synth_not_router_or_inspector(monkeypatch):
    seen = _capture_cmds_engine(monkeypatch)
    cli_engine.run_mission_cli(
        "launch a brand", engine="claude-code",
        mcp_config_path="/tmp/mcp.json", mcp_allowed_tools=["mcp__wiki"],
    )
    exec_cmds = [c for k, c in seen if k == "exec"]
    other_cmds = [c for k, c in seen if k in ("route", "inspect")]
    assert exec_cmds and other_cmds
    # Departments + synthesis get the MCP flags…
    assert all("--mcp-config" in c and "mcp__wiki" in c for c in exec_cmds)
    # …the router and the inspector never do (Art. IX gate inputs unchanged).
    assert all("--mcp-config" not in c for c in other_cmds)


def test_run_mission_cli_without_mcp_leaves_every_command_clean(monkeypatch):
    seen = _capture_cmds_engine(monkeypatch)
    cli_engine.run_mission_cli("launch a brand", engine="claude-code")
    assert seen and all("--mcp-config" not in c for _k, c in seen)
