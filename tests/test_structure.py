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
    txt = (PKG / "commander.py").read_text(encoding="utf-8")
    assert "router_agent.as_tool" in txt, "router not wired into the agency commander"
    assert "agency_inspector.as_tool" in txt, "inspector not wired into the agency commander"


# ---- optional department imports are guarded by try/except ------------------

def test_optional_kit_imports_guarded():
    txt = (PKG / "commander.py").read_text(encoding="utf-8")
    assert "_HAS_PRODUCT" in txt, "optional department imports are not guarded (no _HAS_PRODUCT flag)"
    assert "try:" in txt and "except ImportError" in txt, "department imports lack try/except guards"
