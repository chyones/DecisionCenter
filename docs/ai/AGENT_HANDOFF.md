# Agent Handoff — DecisionCenter

## Current State — Phase 2B Slice 6 (Project Source Mapping)

Timestamp: `2026-05-17`.

Status: `PHASE_2B_SLICE_6_COMPLETE_NOT_LIVE`.

Production remains `NOT_LIVE`. Phase 2B is in progress. Slice 6 (Project Source Mapping) is complete and CI-green. Subsequent Phase 2B slices require explicit per-slice user approval before any work begins.

## What Changed In This Session

Scope was Phase 2B Slice 6 only — Project Source Mapping:

- Extended `apps/edr/persistence/postgres_store.py` with the `source_mappings` table (idempotent schema init + JSON seeding from `docs/config/project_source_mapping.json`) and five CRUD helpers:
  - `list_source_mappings()` — ordered by `project_code ASC`
  - `get_source_mapping()` — single-row lookup
  - `upsert_source_mapping()` — full-field INSERT … ON CONFLICT DO UPDATE
  - `disable_source_mapping()` — soft-disable (`mapping_status = 'disabled'`)
  - `update_source_mapping_validation()` — validation result persistence
- Added five admin-only endpoints in `apps/edr/app.py`, all gated by `_require_admin`:
  - `GET /admin/source-mappings` — list all mappings with computed status
  - `GET /admin/source-mappings/{code}` — single mapping detail
  - `POST /admin/source-mappings/{code}/validate` — structural validation; no side effects
  - `PUT /admin/source-mappings/{code}` — upsert; `_compute_mapping_status()` validates enabled sources; A-21 audit event (`admin.source_mapping_changed`) emitted BEFORE save
  - `POST /admin/source-mappings/{code}/disable` — 404 if missing; 409 if already disabled; A-21 audit event emitted before status change; returns 204
- Added A-20 guard in `POST /reports/staging` (`stage_report()`): blocks report generation when `source_mappings` table is seeded and the requested `project_code` has no `complete` mapping. Degrades gracefully if PG is unavailable.
- Added Pydantic models: `SourceMappingSharePoint`, `SourceMappingOwnCloud`, `SourceMappingEmail`, `SourceMappingOdoo`, `RelatedPeople`, `SourceMappingSummary`, `SourceMappingDetail`, `SourceMappingListResponse`, `SourceMappingUpsertRequest`, `ValidationFieldError`, `SourceMappingValidateResponse`.
- Added `_compute_mapping_status()` pure validation function and `_row_to_source_mapping_detail()` row normaliser.
- Extended `frontend/src/api/types.ts` and `frontend/src/api/index.ts` with all source mapping types.
- Rewrote `AdminSourceMappingScreen.tsx` from static scaffold to live two-column editor:
  - Left column: project list with status pills and `[+ Add]` button
  - Right column: editor with 8 form sections (Project, Odoo, SharePoint, ownCloud, Email, Related People, Enabled Sources, Allowed Roles), `[Validate]`, `[Save]`, `[Disable]` buttons
  - `DiffPreviewModal` local component showing old→new diff before every save
  - Risky-change detection (source/role removal, critical path changes) triggers extra `ConfirmDialog`
  - `ConfirmDialog` with typed-confirmation for both risky saves and disable
- Wrote `apps/edr/tests/integration/test_phase2b_source_mapping.py` (53 cases) covering:
  - RBAC denial for all 8 non-admin roles on all 5 endpoints (parametrised)
  - Missing claims → 401
  - List happy path
  - Get detail happy path + 404
  - Validate complete vs incomplete mapping
  - Upsert happy path
  - A-21 audit-before-save call-order assertion
  - Disable happy path → 204
  - Disable not-found → 404
  - Disable already disabled → 409
  - C-1 regex sweep (no business content)
  - C-6 regex sweep (no credential leakage)
- Reconciled governance: `docs/ai/agent-state.json`, `docs/ai/SHARED_CONTEXT.md`, this handoff, `docs/admin/CONTROL_PLANE_LOCK.md`, `docs/admin/FEATURE_MATRIX.md`, and `docs/execution/CURRENT_PROJECT_STATE.md` were updated to reflect Slice 6 completion.

No deployment. The quality gate, RBAC, approval, and download gates were not weakened.

## Validation Evidence

- `ruff check apps scripts`: clean.
- `python3 -m compileall apps scripts`: clean.
- `python3 scripts/check_doc_drift.py`: clean (incl. anchor-currency invariant).
- `python3 scripts/check_ai_context.py`: clean (incl. extended Phase 2B whitelist).
- `python3 scripts/agent_preflight.py`: clean (post-commit).
- `python3 -m pytest -q apps/edr/tests/integration/test_phase2b_source_mapping.py`: 53 passed.
- `make smoke`: 2 passed.
- `make test`: full suite green (394 passed, 1 warning).
- `make eval`: 64/64 passed.
- `cd frontend && npm run lint`: clean.
- `cd frontend && npm run build`: success.

## Safe Next Work

Phase 2B Slice 7 — Approval Queue + admin override is the safe next work item per `docs/execution/PHASE_2B_PLAN.md` §E. It requires explicit per-slice user approval before implementation.

Do not deploy. Do not start Slice 7 by inference. Do not change production status from `NOT_LIVE` without an explicit deployment instruction and evidence. Do not weaken `_require_admin`.
