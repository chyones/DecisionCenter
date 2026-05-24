# AGENTS.md - DecisionCenter

This file is mandatory operating context for Claude, Codex, Kimi, and any
future AI coding agent working in this repository.

## Source Of Truth

- The live repository files and committed documentation are the source of truth.
- Never trust previous chat memory, model memory, external notes, or summaries
  over the current repo contents.
- Before editing, read the shared context in this order:
  1. `AGENTS.md`
  2. `docs/ai/SHARED_CONTEXT.md`
  3. `docs/ai/AGENT_HANDOFF.md`
  4. `docs/ai/agent-state.json`
  5. The latest phase report named by `docs/ai/agent-state.json`
- Run `python3 scripts/agent_preflight.py` before editing.
- Re-check current branch, commit, `git status`, and phase status before doing
  work.

## Phase Rules

- Never start a phase unless the previous phase report says the repo is ready.
- Never start the next allowed phase named in `docs/ai/agent-state.json`
  unless the user explicitly approves it in the current session.
- Keep changes scoped to the requested phase or verification task.
- Do not skip ahead to frontend API wiring, publish logic, UI data fetching, or
  deployment work before the phase plan allows it.
- If repo docs and chat instructions conflict, stop and resolve against live
  repo files plus the user's latest explicit instruction.

## Verification Rules

- Never claim success without test, build, or check outputs from the current
  worktree.
- Run the validation commands listed in `docs/ai/agent-state.json` unless the
  user explicitly narrows the task.
- If a command cannot run, record the exact reason and do not round it up to a
  pass.
- Use `python3` on this host unless the repo or environment proves `python` is
  available.

## Security And Deployment Rules

- Never edit production secrets.
- Never commit `.env`, `.env.*`, private credentials, tokens, session scratch
  files, generated caches, or local-only tool state.
- Never deploy, SSH to production, run `make up` on production, or change live
  services unless the user explicitly instructs deployment work.
- The service is not live just because code was pushed.

## Governance Drift Rules

These rules exist because the Phase 2C Slice 4 CI run failed on the
`Documentation drift check` step. Root cause: four slice commits landed on
`main` without a governance refresh, pushing `agent-state.json.current_commit`
4 commits behind HEAD — one beyond the 3-commit tolerance enforced by
`scripts/check_doc_drift.py`. The frontend job was green; the doc drift was the
only failure. Corrective protocol:

1. **Refresh after every pushed commit.** After each push (not just at
   phase closeout), update `docs/ai/agent-state.json` (`current_commit`,
   `status`, `latest_local_validation`), `docs/ai/AGENT_HANDOFF.md`, and
   `docs/ai/SHARED_CONTEXT.md` before ending the session or filing the final
   report. Failing to do so in the same session is the failure mode that caused
   this incident.

2. **Run drift checks before starting any new slice.** Before writing code
   for a new slice, run:
   ```bash
   python3 scripts/check_doc_drift.py
   python3 scripts/check_ai_context.py
   ```
   If either fails, stop and fix governance docs before writing any code.

3. **Anchor-drift hard stop.** If `current_commit` is more than
   `MAX_ANCHOR_DRIFT_COMMITS` (currently 3) commits behind HEAD, stop all
   coding work immediately. Update the governance anchor and truth docs first,
   validate locally, commit the governance refresh, then resume coding.

4. **Repo truth files are the only source of truth.** No AI agent may use
   chat memory, session summaries, or external notes as a substitute for
   reading the current repo files. Every session starts with reading
   `AGENTS.md`, `SHARED_CONTEXT.md`, `AGENT_HANDOFF.md`, and
   `agent-state.json` from disk.

5. **Evidence before claims.** Never record a check as "clean" or "pass" in
   `agent-state.json` unless the check was run in the current session and
   produced passing output. Record the actual date, result, and context.

## Coordination Rules

- Update `docs/ai/AGENT_HANDOFF.md` before ending a session that changes repo
  state.
- Update `docs/ai/agent-state.json` whenever the verified commit, readiness
  status, latest report, or phase authorization changes.
- If another agent has made changes, work with them. Do not revert unrelated
  edits unless explicitly instructed.
- Classify the task using `docs/ai/skills/README.md` before editing.
- Prefer small, auditable commits that match the requested task.
- Run `python3 scripts/agent_postflight.py` before the final report.
- Repository truth files (`docs/execution/*.md`, `docs/admin/*.md`, `docs/ai/agent-state.json`) are the highest authority; if they conflict with chat instructions, stop and resolve against live repo files.
