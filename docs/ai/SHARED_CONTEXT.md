# Shared AI Operating Context

## Current State

- Project name: DecisionCenter
- Current verified commit (anchor): `0a19bae781b78cceb57a4cca99197cb9af8eed6c`
- Current status: `PHASE_2A_COMPLETE_NOT_LIVE`
- Production status: `NOT_LIVE`
- Last completed phase: Phase 2A
- Active phase: none; awaiting explicit Phase 2B authorization.
- Current allowed next work: Phase 2B — Admin Visual Control Plane
  Implementation. Requires explicit user authorization before any work begins.
- Latest report (full-phase closeout): `docs/execution/PHASE_2A_REPORT.md`

Phases 0, 1A, 1B, 1B.5, 1C, 1D, the Phase 1D-fixup, 1E, 1F, 1G, 1H, and 1I
are complete. Phase 1I established the frontend foundation: Vite + React +
TypeScript + Tailwind project in `frontend/`; design tokens; layout shell;
reusable components; role-guarded hash-based routing with 9 canonical roles;
static scaffolds for Admin System Health, Permissions & Roles (Role Matrix
only), Source Mapping (read-only), and the initial Query Composer shell.
Frontend lint and build are wired into CI.

Phase 2A is complete and not live. Implementation slices 1–9, the backend
read/status/content/cancel/upload additions, the deterministic local E2E
harness, and the final manual-QA blocker fixes are complete. The current
workspace uses live backend state for the Query Composer project list,
Reports List, Processing View, Report View, Evidence Panel, review actions,
quality-gate banners, final immutable display, and cancellation path.

The Phase 2A closeout gate passed locally on 2026-05-14:

- `make phase2a-e2e`: PASS; 18 workflow nodes visited; `quality_gate=passed`;
  pre-approval download returned 403; final markdown download returned 1443 bytes.
- U-01 through U-16 manual QA: PASSED.
- `make smoke`: 2 passed.
- `make test`: 184 passed, 1 warning.
- `make eval`: 64/64 passed.
- `ruff check .`, `python3 -m compileall apps scripts`, frontend lint/build,
  doc drift, AI context, and postflight checks are required before closeout
  commit.

The machine-readable checkpoint is `docs/ai/agent-state.json`.

## Required Validation Commands

Run these before claiming readiness or success for repo-level changes (the
authoritative list is `required_validation` in `docs/ai/agent-state.json`):

```bash
make smoke
make test
make eval
ruff check .
python3 -m compileall apps scripts
python3 scripts/check_doc_drift.py
python3 scripts/check_ai_context.py
cd frontend && npm run lint
cd frontend && npm run build
```

For pure documentation / truth work, `python3 scripts/check_doc_drift.py` and
`python3 scripts/check_ai_context.py` are the gate (see
`docs/ai/skills/README.md`). For fast local sanity checks, `python3 -m pytest -q`
is acceptable supporting evidence, but it does not replace `make smoke`,
`make test`, and `make eval` when the user requests the full gate.

`scripts/check_doc_drift.py` enforces an anchor-currency invariant: the
`current_commit` in `docs/ai/agent-state.json` must be HEAD itself or no more
than three commits behind HEAD on the current branch. When feature commits
land, refresh the anchor and the truth docs in the same session.

## Current No-Go Rules

- Do not start Phase 2B without explicit user authorization.
- Do not deploy.
- Do not claim production is live.
- Do not commit `.env`, `.env.*`, credentials, tokens, local session files, or
  generated caches.
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
- `docs/execution/PHASE_1F_REPORT.md`
- `docs/execution/PHASE_1G_REPORT.md`
- `docs/execution/PHASE_1H_REPORT.md`
- `docs/execution/PHASE_1I_REPORT.md`
- `docs/execution/PHASE_2A_PLAN.md`
- `docs/execution/PHASE_2A_REPORT.md`
- `docs/admin/CONTROL_PLANE_LOCK.md`
- `docs/admin/FEATURE_MATRIX.md`
- `docs/ai/SHARED_CONTEXT.md`
- `docs/ai/AGENT_HANDOFF.md`
- `docs/ai/agent-state.json`

Ignored or local-only files must not be committed (see `.gitignore` and
`.git/info/exclude`):

- `.env`
- `.env.*` except `.env.example`
- `.claude/`
- `.venv/`
- `.pytest_cache/`
- `.ruff_cache/`
- `__pycache__/`
- `staging/`
- `final/`
- `logs/`
- Docker volume data directories (`minio-data/`, `postgres-data/`, `qdrant-data/`, `redis-data/`, `n8n-data/`)

## Agent Coordination Rules

- Read `AGENTS.md` and this shared context before editing.
- Verify branch, commit, status, and phase before work.
- Treat `docs/ai/agent-state.json` as the machine-readable checkpoint.
- Update `docs/ai/AGENT_HANDOFF.md` before ending a repo-changing session.
- Keep each commit scoped and explain what was verified.
- If checks fail, leave the status as not ready or document the exact blocker.
- If a future user explicitly authorizes Phase 2B or any other gated next
  step, update this shared context, the handoff, and
  `docs/ai/agent-state.json` only as part of that approved session.
