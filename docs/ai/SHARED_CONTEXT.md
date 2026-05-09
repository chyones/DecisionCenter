# Shared AI Operating Context

## Current State

- Project name: DecisionCenter
- Current verified commit: `dd7e5b832b18be55e675f2424cc7a7863b9f6b58`
- Current status: `PHASE_1E_COMPLETE_NOT_LIVE`
- Production status: `NOT_LIVE`
- Last completed phase: Phase 1E
- Current allowed next phase: Phase 1F (requires explicit user approval)
- Latest report: `docs/execution/PHASE_1E_REPORT.md`

Phase 1E is complete. LLM nodes (02, 03, 04, 11, 12, 13) are implemented with cost guardrails, prompt-injection protection, and Langfuse tracing. Export remains blocked unless quality_gate == "passed".

## Required Validation Commands

Run these before claiming readiness or success for repo-level changes:

```bash
make smoke
make test
ruff check .
python3 -m compileall apps scripts
python3 scripts/check_doc_drift.py
python3 scripts/check_ai_context.py
```

For fast local sanity checks, `python3 -m pytest -q` is also acceptable as
supporting evidence, but it does not replace `make smoke` and `make test` when
the user requests the full gate.

## Current No-Go Rules

- Do not start Phase 1F without explicit user approval.
- Do not claim Phase 1E is complete until the new commit is pushed and CI passes.
- Do not implement persistence changes, publish logic, approval flows, or UI work as part of Phase 1E.
- Do not deploy.
- Do not claim production is live.
- Do not commit `.env`, `.env.*`, credentials, tokens, local session files, or generated caches.
- Do not rely on previous chat memory over current repo files.
- Do not claim a check passed unless it was run and produced passing output.

## Production Deployment Requirements

Production is `NOT_LIVE`. A push to `origin/main` does not deploy the service.
Production requires an operator to run:

```bash
ssh <user>@<your-hetzner-host>
cd DecisionCenter
git pull origin main
make up
make smoke
```

Before `make up`, the server `.env` must provide:

- `PUBLIC_HOSTNAME`
- `OWNCLOUD_USERNAME`
- `OWNCLOUD_PASSWORD`
- `N8N_WEBHOOK_TOKEN`
- Existing Odoo settings
- Existing Qdrant settings
- Existing Redis settings
- Existing Postgres settings
- Existing Entra settings

## n8n Credential Requirement

n8n must have a Webhook Header Auth credential configured as:

```text
Authorization: Bearer <N8N_WEBHOOK_TOKEN>
```

The ownCloud and Odoo service-account credentials are read from n8n container
environment variables and must not be sent in webhook bodies.

## Protected And Ignored Files

Protected source-of-truth files:

- `docs/workflows/EDR-AGENTIC-RAG-v2.1.md`
- `docs/execution/IMPLEMENTATION_PHASES.md`
- `docs/execution/CURRENT_PROJECT_STATE.md`
- `docs/execution/PHASE_1D_FIXUP_REPORT.md`
- `docs/execution/PHASE_1E_REPORT.md`
- `docs/admin/CONTROL_PLANE_LOCK.md`
- `docs/admin/FEATURE_MATRIX.md`
- `docs/ai/SHARED_CONTEXT.md`
- `docs/ai/AGENT_HANDOFF.md`
- `docs/ai/agent-state.json`

Ignored or local-only files must not be committed:

- `.env`
- `.env.*` except `.env.example`
- `.claude/`
- `.venv/`
- `.pytest_cache/`
- `.ruff_cache/`
- `__pycache__/`'
- `staging/`
- `final/`
- `logs/`
- Docker volume data directories

## Agent Coordination Rules

- Read `AGENTS.md` and this shared context before editing.
- Verify branch, commit, status, and phase before work.
- Treat `docs/ai/agent-state.json` as the machine-readable checkpoint.
- Update `docs/ai/AGENT_HANDOFF.md` before ending a repo-changing session.
- Keep each commit scoped and explain what was verified.
- If checks fail, leave the status as not ready or document the exact blocker.
- If a future user explicitly authorizes Phase 1F, update the shared context
  and handoff as part of that Phase 1F session.
