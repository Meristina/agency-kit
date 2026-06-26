"""Regression tests for the CLI layer — runner_bridge, integrations, scaffolder.

Each test documents a specific bug that was found and fixed; the test name names
the scenario so a future reader knows why the guard exists.
"""

from pathlib import Path


# ---- runner_bridge._dossier_md ----------------------------------------------
# Bug: field list was copied from product-kit and contained "baseline"/"assumptions"
# which do not exist in the agency dossier; "route" was absent entirely.

def test_dossier_md_renders_route_field_not_baseline():
    from agency_cli.runner_bridge import _dossier_md

    dossier = {
        "goal": "launch product",
        "route": ["product", "marketing"],
        "context": None,
        "iteration": 1,
        "direction_check": None,
        "dept_outputs": {"product": "p-out", "marketing": "m-out"},
        "decisions": [],
        "sources": [],
        "open_to_verify": [],
        "verdicts": [],
    }
    md = _dossier_md("001-test", dossier)
    assert "**route**" in md, "route field missing from dossier MD"
    assert "baseline" not in md, "product-kit 'baseline' field leaked into agency dossier MD"
    assert "assumptions" not in md, "product-kit 'assumptions' section leaked into agency dossier MD"


def test_dossier_md_lists_departments_run():
    from agency_cli.runner_bridge import _dossier_md

    dossier = {
        "goal": "build and market",
        "route": ["product", "marketing"],
        "context": None,
        "iteration": 2,
        "direction_check": None,
        "dept_outputs": {"product": "p-out", "marketing": "m-out"},
        "decisions": ["ship Q3"],
        "sources": ["internal doc"],
        "open_to_verify": [],
        "verdicts": [],
    }
    md = _dossier_md("002-test", dossier)
    assert "product" in md and "marketing" in md, "dept_outputs keys not rendered in dossier MD"


# ---- integrations._install_claude -------------------------------------------
# Bug: sources["skills"].iterdir() called unconditionally; agency-kit has no
# skills/ directory, so `agency init --agent claude` raised FileNotFoundError.

def test_install_claude_without_skills_dir_does_not_crash(tmp_path):
    from agency_cli.integrations import _install_claude

    commands_dir = tmp_path / "commands"
    commands_dir.mkdir()
    (commands_dir / "mission.md").write_text(
        "---\ndescription: run a mission\n---\n\n$ARGUMENTS\n", encoding="utf-8"
    )
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()

    sources = {
        "commands": commands_dir,
        "agents": agents_dir,
        "skills": tmp_path / "skills",  # intentionally absent
    }
    target = tmp_path / "target"
    target.mkdir()

    result = _install_claude(sources, target)
    assert result["skills"] == 0, "skills count should be 0 when skills/ dir is absent"
    assert result["commands"] == 1


def test_install_claude_with_skills_dir_copies_them(tmp_path):
    from agency_cli.integrations import _install_claude

    commands_dir = tmp_path / "commands"
    commands_dir.mkdir()
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    skills_dir = tmp_path / "skills"
    (skills_dir / "my-skill").mkdir(parents=True)
    (skills_dir / "my-skill" / "SKILL.md").write_text("# My Skill\n", encoding="utf-8")

    sources = {"commands": commands_dir, "agents": agents_dir, "skills": skills_dir}
    target = tmp_path / "target"
    target.mkdir()

    result = _install_claude(sources, target)
    assert result["skills"] == 1
    assert (target / ".claude" / "skills" / "my-skill" / "SKILL.md").exists()


# ---- scaffolder.check() -----------------------------------------------------
# Bug: find_spec("agency_commander") checked a non-existent top-level module;
# "agency_commander importable" check was always False even when installed.

def test_check_agency_commander_importable_when_installed(tmp_path):
    from agency_cli.scaffolder import check

    results = check(str(tmp_path))
    by_label = {label: ok for label, ok, _ in results}

    assert "agency_commander importable" in by_label, "health check missing 'agency_commander importable' entry"
    assert by_label["agency_commander importable"], (
        "agency_kit.commander not found — the find_spec target may have regressed "
        "to a wrong module name (was: 'agency_commander', correct: 'agency_kit.commander')"
    )


# ---- agency missions ---------------------------------------------------------
# Bug surface: _cmd_missions printed nothing when the missions dir was empty;
# no test existed to guard this code path.

def test_cmd_missions_empty(monkeypatch, capsys):
    from agency_cli.cli import _cmd_missions
    from argparse import Namespace

    monkeypatch.setattr("agency_kit.store.list_missions", lambda: [])
    rc = _cmd_missions(Namespace())
    assert rc == 0
    out = capsys.readouterr().out
    assert "No missions" in out


def test_cmd_missions_lists_rows(monkeypatch, capsys):
    from agency_cli.cli import _cmd_missions
    from argparse import Namespace

    fake = [
        {"mission_id": "20260101-000000-test-goal", "goal": "test goal", "route": ["product"],
         "iteration": 1, "verdict": "PASS", "delivered": True},
    ]
    monkeypatch.setattr("agency_kit.store.list_missions", lambda: fake)
    rc = _cmd_missions(Namespace())
    assert rc == 0
    out = capsys.readouterr().out
    assert "test-goal" in out
    assert "PASS" in out


# ---- agency resume ----------------------------------------------------------
# Bug surface: _cmd_resume called runner_bridge.resume but the error path for a
# missing mission_id was never tested.

def test_cmd_resume_missing_mission(monkeypatch, capsys):
    from agency_cli.cli import _cmd_resume
    from argparse import Namespace

    def _raise(*a, **kw):
        raise FileNotFoundError("not found")

    monkeypatch.setattr("agency_cli.runner_bridge.resume", _raise)
    # Stub missions_path (no mkdir) so the error message is pure display with no disk side-effect.
    monkeypatch.setattr("agency_kit.store.missions_path", lambda: Path("/stub/missions"))
    rc = _cmd_resume(Namespace(mission_id="nonexistent-id", path=".", steer=False))
    assert rc == 2
    err = capsys.readouterr().err
    assert "nonexistent-id" in err


# ---- agency run --parallel --------------------------------------------------
# Bug surface: --parallel flag was added to the CLI parser but runner_bridge.run
# was never tested with parallel=True; a typo in the kwarg name would be silent.

def test_cmd_run_parallel_flag(monkeypatch, tmp_path):
    from agency_cli.cli import _cmd_run
    from argparse import Namespace

    calls = {}

    def _fake_run(goal, project_root, steer, parallel):
        calls["parallel"] = parallel
        calls["goal"] = goal
        return tmp_path / "001-result"

    monkeypatch.setattr("agency_cli.runner_bridge.run", _fake_run)
    rc = _cmd_run(Namespace(goal="test parallel goal", path=str(tmp_path), steer=False, parallel=True))
    assert rc == 0
    assert calls.get("parallel") is True, "--parallel flag not forwarded to runner_bridge.run"
