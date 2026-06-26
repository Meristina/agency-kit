"""Structural invariants for agency-kit — the meta-orchestrator wiring.

Confirms the agency's spine is present and importable under the offline stub (conftest installs
the `agents` SDK stub and the three department-kit stubs), and that the commander wires the router
and the inspector and guards its optional department imports.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "agency_kit"


# ---- the Constitution is present --------------------------------------------

def test_constitution_present():
    assert (ROOT / ".agency" / "memory" / "constitution.md").exists()


# ---- the spine imports under the offline stub -------------------------------

def test_commander_importable():
    from agency_kit.commander import agency_commander

    assert agency_commander is not None


def test_router_importable():
    from agency_kit.router import classify, router_agent

    assert router_agent is not None
    assert callable(classify)


def test_inspector_importable():
    from agency_kit.inspector import agency_inspector

    assert agency_inspector is not None


def test_mission_importable():
    from agency_kit.mission import run_mission

    assert callable(run_mission)


def test_cli_importable():
    from agency_cli.cli import main

    assert callable(main)


# ---- wiring: commander invokes the router and the inspector -----------------

def test_commander_wires_router_and_inspector():
    from agency_kit.commander import agency_commander
    tool_names = {t.get("tool_name") for t in agency_commander.tools if isinstance(t, dict)}
    assert "classify" in tool_names, "router not wired into the agency commander tools"
    assert "inspect" in tool_names, "inspector not wired into the agency commander tools"


# ---- sync_payload pre-flight guard ------------------------------------------
# Bug: sync() wiped payload/agents/ before checking sibling repos; missing repos
# caused permanent loss of 100+ committed files with exit 0.

def test_sync_preflight_raises_when_kits_missing(tmp_path):
    from agency_cli import sync_payload

    # Point repo_root() and payload_dir() at a temp tree that has .agency/ but no sibling kits
    fake_root = tmp_path / "agency-kit"
    (fake_root / ".agency" / "memory").mkdir(parents=True)
    (fake_root / ".agency" / "memory" / "constitution.md").write_text("# Constitution\n")
    (fake_root / "agents").mkdir()
    payload = fake_root / "agency_cli" / "payload"
    payload.mkdir(parents=True)

    import importlib, sys
    orig_root = sync_payload.repo_root
    orig_payload = sync_payload.payload_dir
    sync_payload.repo_root = lambda: fake_root
    sync_payload.payload_dir = lambda: payload
    try:
        import pytest
        with pytest.raises(RuntimeError, match="Missing sibling repos"):
            sync_payload.sync(allow_missing=False)
        # allow_missing=True must not raise (may skip silently)
        sync_payload.sync(allow_missing=True)
    finally:
        sync_payload.repo_root = orig_root
        sync_payload.payload_dir = orig_payload


# ---- optional department imports are guarded by try/except ------------------

def test_optional_kit_imports_guarded():
    from agency_kit import commander
    for flag in ("_HAS_PRODUCT", "_HAS_MARKETING", "_HAS_SOLVE", "_HAS_FINANCE"):
        assert hasattr(commander, flag), f"optional department import not guarded (no {flag} flag)"
        assert isinstance(getattr(commander, flag), bool), f"{flag} should be a bool set by the try/except guard"


def test_store_importable():
    from agency_kit.store import save, load, list_missions, new_mission_id
    assert callable(save)
    assert callable(load)
    assert callable(list_missions)
    assert callable(new_mission_id)


def test_parallel_importable():
    from agency_kit.parallel import run_parallel_mission
    assert callable(run_parallel_mission)


def test_resume_mission_importable():
    from agency_kit.mission import resume_mission
    assert callable(resume_mission)
