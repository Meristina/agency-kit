"""Shared test setup: stub the openai-agents SDK *and* the optional department kits so the whole
suite runs OFFLINE — no SDK, no network, no API key, no department packages installed. pytest
imports this before any test module, so the stubs are in place when ``agency_kit`` (and its
commander, which does ``from product_kit.commander import commander_product`` etc.) is imported.

Two layers of stubbing happen here, both BEFORE any test imports agency_kit:
  1. ``agents`` — the openai-agents SDK (Agent, WebSearchTool, Runner, function_tool).
  2. The three department kits (product_kit / marketing_kit / solve_kit) and their ``.commander``
     submodules, each exposing ``commander_<dept>`` as an Agent instance. agency_kit's commander
     imports these inside try/except; stubbing them lets the wired (all-departments-present) path
     run under test instead of the degraded "kit absent" path.

Tests drive the loop script `Runner.run_sync` by monkeypatching `mission.Runner`.
"""

import sys
import types

# ---------------------------------------------------------------------------
# Layer 1 — the openai-agents SDK
# ---------------------------------------------------------------------------

_fake = types.ModuleType("agents")


class Agent:
    def __init__(self, *a, **k):
        self.name = k.get("name")
        self.model = k.get("model")
        self.tools = k.get("tools", [])

    def as_tool(self, *a, **k):
        return {"tool_name": k.get("tool_name")}


class WebSearchTool:
    def __init__(self, *a, **k):
        pass


class Runner:
    @staticmethod
    def run_sync(agent, inp):  # replaced per-test via a scripted runner
        raise RuntimeError("Runner.run_sync not scripted")


def function_tool(f=None, **k):
    """@function_tool and @function_tool(...) both return the function unchanged."""
    if f is None:
        return lambda g: g
    return f


_fake.Agent = Agent
_fake.WebSearchTool = WebSearchTool
_fake.Runner = Runner
_fake.function_tool = function_tool
# Force the stub regardless of whether a real `agents` SDK is installed — the suite is offline.
sys.modules["agents"] = _fake


# ---------------------------------------------------------------------------
# Layer 2 — the optional department kits (product / marketing / solve)
#
# agency_kit.commander does `from <dept>_kit.commander import commander_<dept>` inside try/except.
# We stub each kit + its .commander submodule so the all-departments-present wiring path runs under
# test (rather than the degraded "kit not installed" branch). Each stub only needs to expose its
# commander as an Agent instance.
# ---------------------------------------------------------------------------

def _stub_department(name: str) -> None:
    commander_attr = f"commander_{name}"
    commander_agent = Agent(name=commander_attr)

    pkg = types.ModuleType(f"{name}_kit")
    setattr(pkg, commander_attr, commander_agent)

    cmd = types.ModuleType(f"{name}_kit.commander")
    setattr(cmd, commander_attr, commander_agent)
    pkg.commander = cmd

    sys.modules[f"{name}_kit"] = pkg
    sys.modules[f"{name}_kit.commander"] = cmd


for _dept in ("product", "marketing", "solve"):
    _stub_department(_dept)
