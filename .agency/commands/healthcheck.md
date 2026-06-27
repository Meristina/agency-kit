---
description: Audit every key file in the repo for 9-department architecture consistency — no mission required
argument-hint: "(no argument needed)"
---

# /agency.healthcheck — arborescence audit (9-department)

**Scope:** verify that every key file in the repo correctly reflects the
9-department architecture (product · marketing · solve · finance · comms ·
data · ops · people · tech). Run after any structural change to the kit.

**No API key, no mission, no network.** This is a static audit of the repo's
own files.

## Do

1. **Read each file in the checklist below.** For every item, check the listed
   invariants. Emit ✅ clean or ❌ stale with the exact line(s) to fix.

2. **Fix every ❌ in-place.** After each fix, verify the file before moving to
   the next item.

3. **Run the test suite** when all files are clean:
   ```bash
   pytest tests/ -v
   ```
   All tests must pass. If `test_payload_router_matches_source` fails, run
   `agency sync` and re-test.

4. **Emit a final verdict:**
   - ✅ **CLEAN** — all files consistent, all tests pass.
   - ❌ **ISSUES** — list every remaining stale item with file + line + fix.

---

## Checklist

### Python engine

| File | Invariant |
|---|---|
| `agency_kit/commander.py` | 9 try/except import guards; 9 `_HAS_*` flags; `classify` tool description lists all 9; docstring EXECUTE chain has all 9 branches |
| `agency_kit/inspector.py` | Docstring and instructions list 9 kits and 9 domains |
| `agency_kit/mission.py` | No hardcoded department list — fully generic |
| `agency_kit/models.py` | No department refs — purely model config |
| `agency_kit/parallel.py` | `_get_commanders()` imports and returns all 9 pairs; docstring covers all 9 departments |
| `agency_kit/router.py` | `ROUTER_INSTRUCTIONS` lists all 9 departments; docstring correct |
| `agency_kit/departments.py` | `DEPT_NAMES` has exactly 9 entries; `VALID_DEPTS` matches; `dept_list_text()` covers all 9 |

### CLI

| File | Invariant |
|---|---|
| `agency_cli/cli.py` | No hardcoded 4-dept list |
| `agency_cli/integrations.py` | Comment lists all 9 dept slash commands |
| `agency_cli/sync_payload.py` | No hardcoded dept list; all 9 kits present |

### Agent docs (`agents/` — root source)

| File | Invariant |
|---|---|
| `agents/commander-agency.md` | Frontmatter, table, chain-of-command, EXECUTE steps — all 9 departments |
| `agents/inspector-agency.md` | 9 kits, 9 domains listed |
| `agents/router-agency.md` | "nine departments", dept list (9), single-dept examples (9), valid dept array (9) |
| **Sync invariant** | `agents/router-agency.md` must be byte-for-byte identical to `agency_cli/payload/agents/router-agency.md` |

### Commands (`.agency/commands/`)

14 commands must exist: `mission.md` `frame.md` `inspect.md` `goal.md`
`healthcheck.md` + one per department: `product.md` `marketing.md` `solve.md`
`finance.md` `comms.md` `data.md` `ops.md` `people.md` `tech.md`.

### Skills (`skills/`)

| File | Invariant |
|---|---|
| `skills/cross-dept-synthesis/SKILL.md` | Frontmatter lists 9 departments |
| `skills/mission-dossier/SKILL.md` | `dept_outputs` schema has 9 entries |
| `skills/routing/SKILL.md` | "nine departments", 9-row table, 9-step pipeline |
| `skills/routing/agents/openai.yaml` | `default_prompt` lists all 9 departments |

### Config & docs

| File | Invariant |
|---|---|
| `pyproject.toml` | 9 optional-dependency extras + `[all]` with 9 kits |
| `README.md` | Architecture diagram, routing table, config table — all 9 departments |
| `GUIDE.md` | §2 diagram (9 commanders), §5 dossier schema (9 dept_outputs), §8 catalogue (dept commands) |
| `CLAUDE.md` | Test architecture note mentions nine department kits |
| `.env.example` | Department overrides section: 9 kits with env var prefixes |
| `.gitignore` | `missions/`, `.env`, `*.egg-info/` present |
| `requirements.txt` | Core dep only, no dept refs |
| `MANIFEST.in` | No dept refs |

### Tests

| File | Invariant |
|---|---|
| `tests/conftest.py` | Stub loop covers all 9 departments |
| `tests/test_structure.py` | `_HAS_*` flags check: all 9 flags listed |
| `tests/test_mission_harness.py` | Docstring mentions nine department-kit stubs |
| `tests/test_cli.py` | No hardcoded 4-dept list |

---

## Fail protocol

For each ❌: state the file, the line number, the stale text, and the correct
replacement. Fix in-place, verify, move on. Mirror the user's language.
