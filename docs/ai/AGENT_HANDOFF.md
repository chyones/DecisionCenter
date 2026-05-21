# Agent Handoff — DecisionCenter

## Current State

- **Status:** `PHASE_2C_IN_PROGRESS_NOT_LIVE`
- **Current anchor:** `14c3154`
- **Current plan:** `docs/execution/PHASE_2C_PLAN.md`
- **Latest full closeout report:** `docs/execution/PHASE_2B_REPORT.md`
- **Last completed phase:** Phase 2B — Admin Visual Control Plane Implementation
- **Production:** `NOT_LIVE`
- **Active phase:** Phase 2C — UI Hardening & Acceptance Validation

Phase 2B is closed. All ten slices (admin RBAC base, Connectors, Health, Audit
Log, Permissions, Source Mapping, Approval Queue, Dashboard, Routing + Nav,
Closeout) are complete and CI-green. The admin control plane has seven live
screens with backend integration.

Phase 2C was explicitly authorized on 2026-05-21 after pre-2C cleanup was
pushed and CI run `26207850379` passed at commit `14c3154`. Its scope is UI
hardening and acceptance validation: accessibility, responsive behavior,
security-DOM checks, performance, cross-browser coverage, Playwright/Cypress
automation, and adding `make test:ui` to CI. Phase 2C does not authorize
deployment, new admin endpoints, or spec changes.

## Current Guardrails

- Do not deploy; production remains `NOT_LIVE`.
- Do not weaken `_require_admin`; non-admin roles must continue to receive
  HTTP 403 from every `/admin/*` endpoint.
- Do not expose business report content, query text, evidence excerpts, or
  credential values in admin responses.
- Do not commit `.env`, `.env.*`, credentials, tokens, generated caches, local
  logs, or staging/final artifacts.
- Rebuild the Docker app image before using container tests as current-code
  evidence, because the image copies source files at build time.

## Latest Truth Cleanup

This handoff was refreshed after a stale-doc audit found old Phase 2B Slice 6
and Slice 7 language in live agent-facing files. The current truth is:

- `docs/ai/agent-state.json` reports `PHASE_2B_COMPLETE_NOT_LIVE`.
- `docs/execution/PHASE_2B_REPORT.md` is the latest full-phase report.
- Phase 2C is the active phase and remains limited to the approved hardening scope.

## Pre-2C Cleanup

The pre-2C cleanup kept Phase 2C unstarted until authorization. It removed
accidental Phase 2C UI-test implementation surface from the worktree:
Playwright config, `frontend/e2e/*`, `frontend`'s `test:ui`
script/dependency, the root `make test-ui` target, and CI browser-test steps.
Those surfaces may now be reintroduced only within the active Phase 2C scope.

The same cleanup tightens Node 15 persistence reporting: MinIO/PostgreSQL
write failures now leave `audit_status="degraded"` with sanitized operation
names in `audit_errors` instead of reporting `persisted`.

Validation run after rebuilding the app image: `make phase2a-e2e` PASS,
`make smoke` 2 passed, `make test` 461 passed with 1 warning, `make eval`
64/64 passed, ruff clean, compileall clean, frontend lint/build clean,
doc-drift clean, AI-context clean, and postflight clean.

## Required Validation

For repo-level changes, use the authoritative list in
`docs/ai/agent-state.json`. For pure truth-doc work, run at minimum:

- `python3 scripts/check_doc_drift.py`
- `python3 scripts/check_ai_context.py`
- `python3 scripts/agent_postflight.py --allow-no-evidence`

Run broader test/build gates when code or frontend behavior changes.

For Phase 2C UI hardening work, include `make test-ui` or
`cd frontend && npm run test:ui` in the validation evidence.
