# AI Task Template

> Copy this template into the conversation or a temporary planning file before starting work.
> Do not commit this template itself unless it is being added to the repo as governance.

---

## Objective

One sentence describing the exact outcome expected.

## Phase

- Current phase per `docs/ai/agent-state.json`: __________
- Phase authorization: __________ (user-approved / verification-only / maintenance)
- This task is part of phase: __________

## Allowed Scope

- Modules/files that may be edited:
- Validation commands that must run:
- Maximum commit count:

## Forbidden Scope

- Modules/files that must not be touched:
- Phases that must not be started:
- Behaviors that must not change:

## Files Expected

| File | Action | Reason |
|---|---|---|
| | create / edit / delete / inspect | |

## Validation Commands

Run these in order. Do not skip. Capture output.

```bash
# 1. Pre-flight
python3 scripts/agent_preflight.py

# 2. Lint and syntax
ruff check .
python3 -m compileall -q apps scripts

# 3. Doc and AI context
python3 scripts/check_doc_drift.py
python3 scripts/check_ai_context.py

# 4. Tests (run inside Docker when available)
make smoke
make test
make eval

# 5. Post-flight
python3 scripts/agent_postflight.py
```

## Rollback Condition

Stop and revert if any of the following occur:
- [ ] CI fails on the pushed commit.
- [ ] `scripts/check_doc_drift.py` or `scripts/check_ai_context.py` fails.
- [ ] A validation command fails and the fix would expand scope beyond this task.
- [ ] The user explicitly cancels or redirects the task.
- [ ] `agent-state.json` status changes unexpectedly.

## Final Report Format

```
A. Objective
- What was requested and why.

B. Changes Made
- File: action (create/edit/delete) + one-line reason.

C. Validation Results
- Command: exact output (pass/fail + counts).

D. Behavior Impact
- Backend changed: yes/no
- Frontend changed: yes/no
- Product behavior changed: yes/no
- Phase started/advanced: yes/no

E. Remaining Risks
- Any accepted risks or follow-up tasks.

F. Verdict
- One of: COMPLETE / PARTIAL / ROLLED_BACK / BLOCKED
```
