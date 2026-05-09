# Agent Handoff

## Last Agent / Session Summary

Created shared AI operating context before Phase 1E. This session added
repo-level coordination rules, human-readable shared context, a machine-readable
agent state file, and a checker to keep the context present and valid.

## Current Branch And Commit

- Branch: `main`
- Current verified commit: `368f086a665c9403dd27713fbfa17970863c2b9d`
- Status: `READY_FOR_PHASE_1E_NOT_LIVE`
- Production status: `NOT_LIVE`

## What Was Completed

- Phase 1D-fixup was previously completed and verified.
- `docs/execution/PHASE_1D_FIXUP_REPORT.md` exists and records
  `READY_FOR_PHASE_1E_NOT_LIVE`.
- Shared AI context files were prepared for all future coding agents.
- A context checker was added at `scripts/check_ai_context.py`.
- CI was prepared to run the AI context checker.

## What Was Not Done

- Phase 1E was not started.
- No LLM node implementation was changed.
- No application behavior was changed.
- No production deployment was performed.
- No secrets or `.env` files were committed.

## Must Read Before Next Work

1. `AGENTS.md`
2. `docs/ai/SHARED_CONTEXT.md`
3. `docs/ai/AGENT_HANDOFF.md`
4. `docs/ai/agent-state.json`
5. `docs/execution/PHASE_1D_FIXUP_REPORT.md`
6. `docs/execution/IMPLEMENTATION_PHASES.md`
7. `docs/workflows/EDR-AGENTIC-RAG-v2.1.md`

## Next Allowed Task

Phase 1E may be started only after explicit user approval in the current
session. Until that approval exists, the allowed work is verification,
documentation, context maintenance, and other non-implementation cleanup that
does not change application behavior.

## Blockers

- Production is not live.
- Production still requires operator SSH, `git pull origin main`, `make up`,
  and `make smoke`.
- Server `.env` must provide required production values before `make up`.
- n8n must have the Webhook Header Auth credential:
  `Authorization: Bearer <N8N_WEBHOOK_TOKEN>`.

## Tests Last Executed

Latest required validation executed for this context change:

- `git status --short --branch`: clean before editing; context files pending during authoring.
- `python3 scripts/check_ai_context.py`: clean.
- `python3 scripts/check_doc_drift.py`: clean.
- `ruff check .`: clean.
- `python3 -m compileall apps scripts`: clean.
- `make smoke`: 2 passed.
- `make test`: 62 passed.

Local Docker validation used an ignored `.env` copied from `.env.example` and a
temporary Compose override that binds DecisionCenter MinIO to localhost ports
`9002` and `9003`, because `vt360_minio` already owns `9000` and `9001` on this
shared host.

## Final Status

`READY_FOR_PHASE_1E_NOT_LIVE`
