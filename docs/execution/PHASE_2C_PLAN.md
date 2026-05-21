# Phase 2C Plan — UI Hardening & Acceptance Validation

> **Date:** 2026-05-21
> **Status:** `PHASE_2C_IN_PROGRESS_NOT_LIVE`
> **Prepared against:** HEAD `14c3154` with CI run `26207850379` successful.
> **Previous phase:** Phase 2B — Admin Visual Control Plane Implementation
> **Production:** `NOT_LIVE`

---

## Authorization

Phase 2C was explicitly authorized by the user on 2026-05-21 after the
pre-2C cleanup was pushed and GitHub Actions completed successfully. This
authorization is limited to UI hardening and acceptance validation. It does not
authorize deployment, new admin endpoints, new business-report behavior, or
locked spec changes.

## Scope

Phase 2C proves the existing UI against the locked UI contract before go-live:

| Track | Validation intent |
|---|---|
| Accessibility | Keyboard navigation, visible focus, ARIA labels, dialog focus management |
| Responsive behavior | Minimum 768px support, sidebar collapse/expand, detail-panel behavior |
| Security DOM | No credential values in DOM, no failed-QG export panel, admin blocked from workspace report content |
| Performance | Bundle-size budget and targeted render/progress checks |
| Cross-browser | Chromium first, then Firefox/WebKit/Edge-compatible coverage where feasible in CI |
| Golden path automation | Browser-driven Query Composer -> Processing -> Report View -> Review/Final -> Download path |

## Slices

| Slice | Status | Deliverable |
|---|---|---|
| Slice 1 — Browser test harness and first hardening checks | ✅ Done | Playwright config, `frontend/e2e/*`, `frontend` `test:ui`, root `make test-ui`, CI headless browser step |
| Slice 2 — Performance and bundle-budget validation | ✅ Done | `scripts/check-bundle-size.mjs`, `frontend/e2e/performance.spec.ts`, CI bundle-size gate |
| Slice 3 — Golden-path acceptance automation | Planned | Browser test for submit -> processing -> report -> approve -> download with mocked or deterministic backend fixtures |
| Slice 2 — Performance and bundle-budget validation | Planned | Automated bundle-size check plus targeted Report View/Processing View performance assertions |
| Slice 3 — Golden-path acceptance automation | Planned | Browser test for submit -> processing -> report -> approve/final -> download with mocked or deterministic backend fixtures |
| Slice 4 — Cross-browser expansion and closeout | Planned | Broaden Playwright project matrix, record U-01..U-16 and A-01..A-23 automated/manual evidence, produce Phase 2C closeout report |

## Guardrails

- Keep Phase 2C frontend-focused unless a test exposes a real UI defect that
  requires a small frontend fix.
- Do not add admin endpoints or broaden admin response data.
- Do not weaken RBAC, route guards, quality-gate export gating, typed
  confirmations, or audit-before-action rules.
- Do not expose query text, report content, evidence excerpts, credential
  values, raw user IDs, or secrets in admin DOM assertions.
- Do not deploy. Production remains `NOT_LIVE`.

## Validation

Minimum validation for Slice 1:

- `cd frontend && npm run test:ui`
- `cd frontend && npm run lint`
- `cd frontend && npm run build`
- `python3 scripts/check_doc_drift.py`
- `python3 scripts/check_ai_context.py`
- `python3 scripts/agent_postflight.py --allow-no-evidence`

Full closeout validation before production readiness remains:

- `make phase2a-e2e`
- `make smoke`
- `make test`
- `make test-ui`
- `make eval`
- `docker compose exec -T app ruff check apps scripts`
- `docker compose exec -T app python -m compileall -q apps scripts`
- `cd frontend && npm run lint`
- `cd frontend && npm run build`
- `python3 scripts/check_doc_drift.py`
- `python3 scripts/check_ai_context.py`
- `python3 scripts/agent_postflight.py --allow-no-evidence`

