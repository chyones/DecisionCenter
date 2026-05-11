# AI Agent Failure Modes

> This file is read-only guidance for agents. It does not change product behavior.

Each failure mode includes symptom, prevention, detection, and required response.
Agents must stop and report when a failure mode is detected.

---

## 1. False Success

**Symptom**
- Agent claims a task is complete but no command output is shown.
- Tests are described as passing without exact counts or command lines.
- Validation is skipped with excuses like "it should work" or "local environment issue".

**Prevention**
- Run every validation command listed in `docs/ai/agent-state.json`.
- Capture and include exact stdout/stderr in the final report.
- If a command cannot run, record the exact error and do not round up to a pass.

**Detection**
- Final report lacks command outputs.
- Commit message claims success but no test/evidence is quoted.
- `scripts/agent_preflight.py` or `scripts/agent_postflight.py` was skipped.

**Required Response**
- Stop. Do not commit.
- Re-run the missing validation.
- If the failure is genuine, fix the direct cause and re-validate.

---

## 2. Stale Phase Context

**Symptom**
- Agent references a phase that is already complete as if it were current.
- `docs/ai/agent-state.json` shows `last_completed_phase` older than the work being done.
- Agent edits files based on chat memory instead of reading live repo files.

**Prevention**
- Always run `scripts/agent_preflight.py` before editing.
- Re-read `docs/ai/agent-state.json` after any long pause.
- Re-read the latest phase report named in `agent-state.json`.

**Detection**
- `scripts/check_ai_context.py` reports stale status.
- Edits reference outdated phase numbers or missing files.
- `git log --oneline -5` does not match the claimed commit anchor.

**Required Response**
- Stop. Re-read `agent-state.json` and the latest phase report.
- If the task conflicts with the current phase, ask the user for clarification.
- Do not proceed until the phase context is verified.

---

## 3. Skipped Validation

**Symptom**
- Agent claims `ruff check .` passed but only ran `ruff check apps`.
- Agent skips `make eval` because "it's slow" or "it passed last time".
- Agent runs tests in a subset and generalizes to the full suite.

**Prevention**
- Run the exact commands listed in `agent-state.json`.
- Do not substitute commands unless the user explicitly narrows the task.
- Run `make smoke`, `make test`, and `make eval` inside Docker when they are listed.

**Detection**
- Final report omits a required command.
- Test counts do not match the known baseline.
- `scripts/agent_postflight.py` shows files changed that belong to a skill type whose validation was skipped.

**Required Response**
- Stop. Run the missing validation.
- Update the final report with exact command outputs.
- If validation fails, fix the direct cause and rerun.

---

## 4. Architecture Drift

**Symptom**
- New code bypasses the 18-node graph and calls connectors or LLMs directly.
- New modules duplicate logic already in `apps/edr/graph/` or `apps/edr/retrieval/`.
- A node starts calling services it is not spec'd to call.

**Prevention**
- Map every change to a spec section in `docs/workflows/EDR-AGENTIC-RAG-v2.1.md`.
- Keep graph nodes single-purpose and linear.
- Reuse existing utilities rather than inventing parallel implementations.

**Detection**
- New imports appear from `apps/edr/graph/node_XX.py` into unrelated modules.
- `scripts/check_doc_drift.py` flags spec-reference mismatches.
- Code review shows a node doing work that belongs to another node.

**Required Response**
- Stop. Revert the drift.
- Refactor the change into the correct node or module.
- Update the spec if the change is intentional and approved.

---

## 5. Unauthorized Scope Expansion

**Symptom**
- A "docs fix" task starts adding new API endpoints.
- A bug fix task starts refactoring unrelated modules.
- An agent claims a phase is complete and begins the next phase without user approval.

**Prevention**
- Classify the task using `docs/ai/skills/README.md` before editing.
- Keep commits small and scoped.
- Do not start a new phase unless `agent-state.json` says it is allowed **and** the user explicitly approves.

**Detection**
- Changed files include modules outside the declared skill type.
- Commit diff is larger than the task description justifies.
- `scripts/agent_postflight.py` flags unexpected file categories.

**Required Response**
- Stop. Revert out-of-scope changes.
- Ask the user for explicit approval before expanding scope.
- If the extra work is valuable, create a separate task for it.

---

## 6. Undocumented Behavior Change

**Symptom**
- Logic changes but no spec, policy, or truth file is updated.
- A node changes its output shape but the schema file is untouched.
- CI passes because tests were updated to match the new behavior, but docs still describe the old behavior.

**Prevention**
- Update the spec (`docs/workflows/EDR-AGENTIC-RAG-v2.1.md`) for any behavior change.
- Update schemas (`docs/schemas/*.json`) for any data-shape change.
- Update truth files for any phase-state change.

**Detection**
- `scripts/check_doc_drift.py` fails after a code change.
- Schema files disagree with runtime output.
- Phase reports describe behavior that no longer exists.

**Required Response**
- Stop. Document the change before committing.
- Update the spec, schemas, and truth files.
- Re-run `scripts/check_doc_drift.py` until it passes.

---

## 7. Secret Leakage

**Symptom**
- `.env`, `.env.*`, or private key files appear in `git status`.
- API keys, tokens, or passwords are committed in code, tests, or logs.
- `scripts/agent_postflight.py` flags blocked file patterns.

**Prevention**
- Never edit `.env` or `.env.*` files.
- Never hard-code credentials in source files.
- Use `settings.*` for config values; use mocks for test credentials.

**Detection**
- `scripts/agent_postflight.py` reports `.env` or key files.
- `git diff` shows credentials in plain text.
- `grep -r "api_key\|token\|password" apps/` finds literals in non-test code.

**Required Response**
- Stop. Do not commit.
- Rotate the leaked credential immediately.
- Replace the literal with a `settings.*` reference or mock.
- Scrub the credential from git history if it was already pushed.

---

## 8. CI / Local Mismatch

**Symptom**
- All tests pass locally but CI fails.
- CI passes on a previous commit but fails on the current one.
- Agent assumes local environment matches CI environment.

**Prevention**
- Run tests inside the Docker container (`make smoke`, `make test`, `make eval`) whenever possible.
- Keep CI env overrides explicit in `.github/workflows/ci.yml`.
- Do not rely on local `.env` values that CI does not have.

**Detection**
- CI fails while local tests pass.
- `scripts/agent_preflight.py` shows env differences.
- GitHub Actions logs show missing env vars or different timeout behavior.

**Required Response**
- Stop. Read the CI failure log.
- Reproduce the failure locally by matching CI env vars.
- Fix the root cause (usually missing env override, service dependency, or timeout).
- Re-push and verify CI passes before declaring success.
