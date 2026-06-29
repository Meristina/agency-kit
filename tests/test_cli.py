"""Regression tests for the CLI layer — runner_bridge, integrations, scaffolder.

Each test documents a specific bug that was found and fixed; the test name names
the scenario so a future reader knows why the guard exists.
"""

from pathlib import Path

import pytest


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
# Engine-only health check: agency_kit importable + at least one engine on PATH.

def test_check_reports_agency_kit_importable(tmp_path):
    from agency_cli.scaffolder import check

    results = check(str(tmp_path))
    by_label = {label: ok for label, ok, _ in results}

    assert "agency_kit importable" in by_label, "health check missing 'agency_kit importable' entry"
    assert by_label["agency_kit importable"], "agency_kit core not importable"
    # The engine-availability check is always present (value depends on PATH).
    assert any("engine CLI available" in label for label in by_label), (
        "health check missing the engine-on-PATH entry"
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
    rc = _cmd_resume(Namespace(mission_id="nonexistent-id", path=".", engine="claude-code"))
    assert rc == 2
    err = capsys.readouterr().err
    assert "nonexistent-id" in err


# ---- agency export ----------------------------------------------------------
# Bug surface: _cmd_export must catch BOTH error paths and yield rc==2 with an
# 'error' message — FileNotFoundError (mission/deliverable absent) and ImportError
# (WeasyPrint not installed). One parametrize over the raised exception covers both.

@pytest.mark.parametrize("exc", [
    FileNotFoundError("deliverable.md not found for mission: x"),
    ImportError('WeasyPrint not installed. Run:  pip install -e ".[pdf]"'),
])
def test_cmd_export_error_paths_return_rc2(monkeypatch, capsys, exc):
    from agency_cli import exporter
    from agency_cli.cli import _cmd_export
    from argparse import Namespace

    def _raise(mid):
        raise exc

    monkeypatch.setattr(exporter, "export_pdf", _raise)
    rc = _cmd_export(Namespace(mission_id="any-mission"))
    assert rc == 2
    assert "error" in capsys.readouterr().err.lower()


# ---- agency tui -------------------------------------------------------------
# Bug surface: _cmd_tui must catch ImportError from tui.launch() (textual absent)
# and return exit code 2. The tui module itself is importable without textual
# because all textual imports are deferred inside launch().

def test_cmd_tui_missing_textual(monkeypatch, capsys):
    from agency_cli import tui
    from agency_cli.cli import _cmd_tui
    from argparse import Namespace

    def _raise():
        raise ImportError('Textual not installed. Run:  pip install -e ".[tui]"')

    monkeypatch.setattr(tui, "launch", _raise)
    rc = _cmd_tui(Namespace())
    assert rc == 2
    assert "error" in capsys.readouterr().err.lower()


def test_cmd_tui_success(monkeypatch):
    from agency_cli import tui
    from agency_cli.cli import _cmd_tui
    from argparse import Namespace

    launched = []

    def _noop():
        launched.append(True)

    monkeypatch.setattr(tui, "launch", _noop)
    rc = _cmd_tui(Namespace())
    assert rc == 0
    assert launched


# ---- agency run forwards the engine -----------------------------------------
# Bug surface: the --engine flag must reach runner_bridge.run; a typo in the
# kwarg name would silently default the engine.

def test_cmd_run_forwards_engine(monkeypatch, tmp_path):
    from agency_cli.cli import _cmd_run
    from argparse import Namespace

    from agency_cli.runner_bridge import MissionResult

    calls = {}

    def _fake_run(goal, project_root, engine="claude-code"):
        calls["engine"] = engine
        calls["goal"] = goal
        return MissionResult(path=tmp_path / "001-result", dossier={})

    monkeypatch.setattr("agency_cli.runner_bridge.run", _fake_run)
    rc = _cmd_run(Namespace(goal="ship it", path=str(tmp_path), engine="gemini", dry_run=False))
    assert rc == 0
    assert calls.get("engine") == "gemini", "--engine not forwarded to runner_bridge.run"


# ---- agency run --dry-run ---------------------------------------------------
# Bug surface: _cmd_dry_run prints the planned keyword route without any engine call.

def test_cmd_dry_run_shows_route(capsys, monkeypatch):
    from agency_cli.cli import _cmd_run
    from argparse import Namespace

    monkeypatch.setattr("agency_kit.router.keyword_classify", lambda goal: ["product", "marketing"])

    rc = _cmd_run(Namespace(goal="launch our product", path=".", engine="claude-code", dry_run=True))
    assert rc == 0
    out = capsys.readouterr().out
    assert "product" in out
    assert "marketing" in out
    assert "dry-run" in out.lower()
    assert "no engine call" in out.lower()


# ---- agency batch -----------------------------------------------------------
# Bug surface: _cmd_batch dispatches to batch_runner functions via the batch_cmd
# attribute — verify each subcommand hits the right function and returns its code.

def test_cmd_batch_add(monkeypatch):
    from agency_cli.cli import _cmd_batch
    from argparse import Namespace
    from agency_cli import batch_runner

    calls = {}

    def _fake_add(goal, priority, notes):
        calls["goal"] = goal
        calls["priority"] = priority
        calls["notes"] = notes
        return 0

    monkeypatch.setattr(batch_runner, "add", _fake_add)
    rc = _cmd_batch(Namespace(batch_cmd="add", goal="launch widget", priority=3, notes="urgent"))
    assert rc == 0
    assert calls["goal"] == "launch widget"
    assert calls["priority"] == 3


def test_cmd_batch_status(monkeypatch):
    from agency_cli.cli import _cmd_batch
    from argparse import Namespace
    from agency_cli import batch_runner

    called = []
    monkeypatch.setattr(batch_runner, "status", lambda: called.append(True) or 0)
    rc = _cmd_batch(Namespace(batch_cmd="status"))
    assert rc == 0
    assert called


def test_cmd_batch_clear(monkeypatch):
    from agency_cli.cli import _cmd_batch
    from argparse import Namespace
    from agency_cli import batch_runner

    calls = {}
    monkeypatch.setattr(batch_runner, "clear", lambda status_filter: calls.update({"sf": status_filter}) or 0)
    rc = _cmd_batch(Namespace(batch_cmd="clear", status_filter="failed"))
    assert rc == 0
    assert calls["sf"] == "failed"


def test_cmd_batch_run_flags(monkeypatch):
    from agency_cli.cli import _cmd_batch
    from argparse import Namespace
    from agency_cli import batch_runner

    calls = {}

    def _fake_run(retry_failed, limit, engine):
        calls.update({"rf": retry_failed, "lim": limit, "engine": engine})
        return 0

    monkeypatch.setattr(batch_runner, "run", _fake_run)
    rc = _cmd_batch(Namespace(batch_cmd="run", retry_failed=True, limit=5, engine="codex"))
    assert rc == 0
    assert calls["rf"] is True
    assert calls["lim"] == 5
    assert calls["engine"] == "codex"


# ---- batch_runner file I/O --------------------------------------------------
# Unit tests for the TSV queue helpers — verify add/status/clear mutate
# the queue file correctly without touching the real ~/.agency directory.

def test_batch_runner_add_creates_queue(tmp_path, monkeypatch):
    from agency_cli import batch_runner

    monkeypatch.setattr(batch_runner, "_agency_dir", lambda: tmp_path)

    rc = batch_runner.add("first goal", priority=3, notes="note1")
    assert rc == 0
    rows = batch_runner._read_tsv(tmp_path / "batch-queue.tsv")
    assert len(rows) == 1
    assert rows[0]["goal"] == "first goal"
    assert rows[0]["priority"] == "3"
    assert rows[0]["status"] == "pending"


def test_batch_runner_add_increments_ids(tmp_path, monkeypatch):
    from agency_cli import batch_runner

    monkeypatch.setattr(batch_runner, "_agency_dir", lambda: tmp_path)

    batch_runner.add("goal A")
    batch_runner.add("goal B")
    rows = batch_runner._read_tsv(tmp_path / "batch-queue.tsv")
    ids = [int(r["id"]) for r in rows]
    assert ids == sorted(set(ids))
    assert len(set(ids)) == 2


def test_batch_runner_status_empty(tmp_path, monkeypatch, capsys):
    from agency_cli import batch_runner

    monkeypatch.setattr(batch_runner, "_agency_dir", lambda: tmp_path)

    rc = batch_runner.status()
    assert rc == 0
    assert "empty" in capsys.readouterr().out.lower()


def test_batch_runner_clear_removes_done(tmp_path, monkeypatch):
    from agency_cli import batch_runner

    monkeypatch.setattr(batch_runner, "_agency_dir", lambda: tmp_path)

    batch_runner.add("keep this")
    batch_runner.add("remove this")
    # Manually write state marking second entry as done
    rows = batch_runner._read_tsv(tmp_path / "batch-queue.tsv")
    done_id = rows[1]["id"]
    batch_runner._write_tsv(
        tmp_path / "batch-state.tsv",
        batch_runner._STATE_COLS,
        [{"id": done_id, "status": "done", "started_at": "", "finished_at": "",
          "last_verdict": "PASS", "retries": "1", "mission_id": ""}],
    )
    rc = batch_runner.clear(status_filter="done")
    assert rc == 0
    remaining = batch_runner._read_tsv(tmp_path / "batch-queue.tsv")
    goals = [r["goal"] for r in remaining]
    assert "keep this" in goals
    assert "remove this" not in goals
