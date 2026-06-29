"""Tests for the CLI-engine mission path (`agency_cli/engines/cli_engine.py`).

The engine shells out to a local agent CLI (claude/codex/gemini). Tests stub the
`_call` subprocess wrapper so they run offline with no CLI installed.
"""

import pytest

from agency_cli.engines import cli_engine


def test_engines_registry_has_three_web_search_engines():
    assert {"claude-code", "codex", "gemini"} <= set(cli_engine.ENGINES)
    assert {"claude-code", "codex", "gemini"} <= set(cli_engine._ROUTE_CMD)


def test_route_via_cli_parses_json_array(monkeypatch):
    monkeypatch.setattr(cli_engine, "_call", lambda cmd, prompt, timeout=900: '["solve", "product"]')
    assert cli_engine._route_via_cli("claude-code", "fix our broken funnel") == ["solve", "product"]


def test_route_via_cli_falls_back_to_keyword(monkeypatch):
    # Unparseable CLI output → keyword_classify fallback.
    monkeypatch.setattr(cli_engine, "_call", lambda cmd, prompt, timeout=900: "not json at all")
    route = cli_engine._route_via_cli("claude-code", "write a marketing campaign")
    assert route == ["marketing"]


def test_route_prompt_loads_doctrine_and_forces_json_array(monkeypatch):
    seen = {}

    def _capture(cmd, prompt, timeout=900):
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

    def _fake_call(cmd, prompt, timeout=900):
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

    def _call(cmd, prompt, timeout=900):
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


def test_call_raises_on_empty_output(monkeypatch):
    # returncode 0 but empty stdout → clear error, not a silent empty deliverable.
    class _Proc:
        returncode = 0
        stdout = "   "
        stderr = ""
    monkeypatch.setattr(cli_engine.subprocess, "run", lambda *a, **k: _Proc())
    with pytest.raises(RuntimeError, match="empty output"):
        cli_engine._call(["claude", "-p"], "hi")


def test_short_verdict_extracts_token():
    assert cli_engine._short_verdict("...everything checks out. VERDICT: PASS") == "PASS"
    assert cli_engine._short_verdict("found invented data — VETO") == "VETO"
    assert cli_engine._short_verdict("VERDICT: PASS-WITH-FIXES, see notes") == "PASS-WITH-FIXES"
    assert cli_engine._short_verdict("no verdict word here") == "DELIVERED"


def test_run_mission_cli_raises_clear_error_when_binary_missing(monkeypatch):
    # Engine known but its CLI is not on PATH → fail fast with a clear RuntimeError.
    monkeypatch.setattr(cli_engine.shutil, "which", lambda b: None)
    with pytest.raises(RuntimeError, match="not found on PATH|needs the"):
        cli_engine.run_mission_cli("goal", engine="gemini")


def test_call_reports_missing_binary(monkeypatch):
    # subprocess raising FileNotFoundError becomes a clear RuntimeError.
    def _boom(*a, **k):
        raise FileNotFoundError(2, "No such file or directory")

    monkeypatch.setattr(cli_engine.subprocess, "run", _boom)
    with pytest.raises(RuntimeError, match="not found on PATH"):
        cli_engine._call(["claude", "-p"], "hello")
