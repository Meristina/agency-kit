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


# ---- optional department imports are guarded by try/except ------------------

def test_optional_kit_imports_guarded():
    from agency_kit import commander
    assert hasattr(commander, "_HAS_PRODUCT"), "optional department imports are not guarded (no _HAS_PRODUCT flag)"
    assert isinstance(commander._HAS_PRODUCT, bool), "_HAS_PRODUCT should be a bool set by the try/except guard"
