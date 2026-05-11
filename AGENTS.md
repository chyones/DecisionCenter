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
- Never start Phase 1E unless the user explicitly approves it in the current
  session.
- Phase 1I must not start without explicit user approval.
- Keep changes scoped to the requested phase or verification task.
- Do not skip ahead to persistence, approval flows, publish logic, UI, or
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
