---
description: Fix a goal end-to-end — audit every bug/gap, plan the fix order, execute, verify, repeat until done. No skips, no half-fixes.
argument-hint: "<goal statement — e.g. 'fix all bugs and make agency-kit operational'>"
---

# /agency.goal — goal-driven end-to-end execution

**Input:** `$ARGUMENTS` = the goal to reach (e.g. "fix all bugs in agency-kit and make it operational")

---

## Phase 1 — Full audit

Read the codebase against the goal. Find **everything** that blocks it:
- Bugs (crashes, wrong output, broken logic)
- Gaps (missing files, unimplemented stubs, wrong imports)
- Inconsistencies (stale references, mismatched names, doc ↔ code drift)
- Test failures or untested paths

Produce a numbered **fix list**. Each entry:
```
[ID] Title — affected file(s) — severity (blocking | important | cleanup) — depends on [IDs]
```

State the total count explicitly: "Found N items to fix."

---

## Phase 2 — Order the work

Sort the fix list:
1. **Blocking** items first (anything that breaks imports, tests, or the CLI)
2. **Important** items next (wrong behaviour, incomplete features)
3. **Cleanup** last (inconsistencies, doc drift)

Resolve dependency chains: if item B needs item A, A goes first.
Print the execution order before starting.

---

## Phase 3 — Execute (one item at a time)

For each item in order:
1. **Fix** — make the change.
2. **Verify** — run the relevant test / command / lint check. Show the output.
3. **Record** — mark ✓ done with one line on what changed.
4. Move to the next item.

Rules:
- Never mark done without running a verification step.
- If a fix reveals a new bug, add it to the list (label it `[NEW]`) and continue.
- If stuck, flag `[BLOCKED: reason]` and move on — never skip silently.

---

## Phase 4 — Final sweep

After all items:
1. Run the full test suite (`pytest tests/ -v`). Show the result.
2. Do a final scan for anything missed.
3. Deliver the verdict:
   - ✅ **DONE** — goal achieved, all items fixed, tests pass.
   - ⚠️ **PARTIAL** — list what remains and why (blocked, out of scope, needs human decision).

Mirror the user's language throughout.
