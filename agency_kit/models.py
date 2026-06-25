"""agency-kit — grade → model mapping (provider-agnostic, env-configurable).

Defaults keep OpenAI (non-breaking):
  AK_ELITE_MODEL     elite tier  (🎖️)  default: "gpt-5.5"
  AK_STANDARD_MODEL  standard    (🔵)  default: "gpt-5.4-mini"

Non-OpenAI providers via the LiteLLM extra (`pip install "openai-agents[litellm]"`):
  export AK_ELITE_MODEL="litellm/anthropic/claude-opus-4-8"
  export AK_STANDARD_MODEL="litellm/anthropic/claude-sonnet-4-6"

The grade of each unit is fixed in its definition; only the concrete model is configurable.

Secrets & overrides are read from a local, gitignored `.env` (keys, OPENAI_BASE_URL, model
overrides) if present — loaded here, before any model/key is resolved, so every entry point
(`agency run`, the mission, a direct soldier import) picks it up. Dependency-free.
"""

import os
from pathlib import Path


def _load_dotenv() -> None:
    """Load the nearest `.env` (cwd upward). Variables in `.env` override the environment,
    so the project's secret file is authoritative for the keys it defines. No-op if absent."""
    for d in (Path.cwd(), *Path.cwd().parents):
        f = d / ".env"
        if f.is_file():
            for line in f.read_text(encoding="utf-8").splitlines():
                s = line.strip()
                if not s or s.startswith("#") or "=" not in s:
                    continue
                k, _, v = s.partition("=")
                k = k.strip()
                v = v.split(" #", 1)[0].strip().strip('"').strip("'")  # drop trailing ` # comment`
                if k and v and v != "REPLACE_ME":
                    os.environ[k] = v
            return


_load_dotenv()

ELITE = os.getenv("AK_ELITE_MODEL", "gpt-5.5")
STANDARD = os.getenv("AK_STANDARD_MODEL", "gpt-5.4-mini")
