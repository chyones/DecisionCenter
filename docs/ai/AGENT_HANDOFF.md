# Agent Handoff — DecisionCenter

## Current State — Phase 2B Slice 5 (Permissions & Roles)

Timestamp: `2026-05-17`.

Status: `PHASE_2B_SLICE_5_COMPLETE_NOT_LIVE`.

Production remains `NOT_LIVE`. Phase 2B is in progress. Slice 5 (Permissions & Roles) is complete and CI-green. Subsequent Phase 2B slices require explicit per-slice user approval before any work begins.

## What Changed In This Session

Scope was Phase 2B Slice 5 only — Permissions & Roles (Entra Group Mapping):

- Extended `apps/edr/persistence/postgres_store.py` with the `entra_group_mappings` table (idempotent schema init) and four CRUD helpers:
  - `list_entra_mappings()` — ordered by `created_at ASC`
  - `upsert_entra_mapping()` — INSERT … ON CONFLICT DO UPDATE
  - `delete_entra_mapping()` — returns bool based on `"DELETE 1"` status
  - `get_entra_mapping()` — single-row lookup for existence checks
- Added three admin-only endpoints in `apps/edr/app.py`, all gated by `_require_admin`:
  - `GET /admin/entra-mappings` — list all mappings
  - `PUT /admin/entra-mappings/{group_id}` — upsert; `_validate_canonical_role()` rejects non-canonical roles with HTTP 400; A-17 audit event (`admin.role_mapping_changed`) emitted BEFORE save
  - `DELETE /admin/entra-mappings/{group_id}` — 404 if mapping absent; A-17 audit event emitted after existence check and before delete; returns 204
- Added `_validate_canonical_role()` helper and `VALID_ROLES` import from `apps/edr/rbac/roles.py`.
- Added `_ts_iso()` timestamp normaliser helper.
- Added `put()` method to `frontend/src/api/client.ts` (ApiClient).
- Extended `frontend/src/api/types.ts` and `frontend/src/api/index.ts` with `EntraGroupMapping`, `EntraGroupMappingUpsertRequest`, and `EntraGroupMappingListResponse`.
- Rewrote `AdminPermissionsScreen.tsx` from static scaffold to live three-tab screen:
  - Tab 1: Role Matrix (existing static table, unchanged)
  - Tab 2: Entra Group Mapping — live CRUD table with Add/Edit/Delete actions; `SlideInPanel` for add/edit; `ConfirmDialog` with typed-confirmation (`confirmationText={group_id}`) for delete
  - Tab 3: Project Role Assignments — active placeholder linking to Source Mapping screen
- Wrote `apps/edr/tests/integration/test_phase2b_permissions.py` (33 cases) covering:
  - RBAC denial for all 8 non-admin roles on all 3 endpoints (parametrised)
  - Missing claims → 401
  - List happy path
  - Upsert happy path
  - Invalid role → 400
  - A-17 audit-before-save call-order assertion
  - Delete happy path → 204
  - Delete not-found → 404 (no audit emitted)
  - C-1 regex sweep (no business content)
  - C-6 regex sweep (no credential leakage)
- Reconciled governance: `docs/ai/agent-state.json`, `docs/ai/SHARED_CONTEXT.md`, this handoff, `docs/admin/CONTROL_PLANE_LOCK.md`, `docs/admin/FEATURE_MATRIX.md`, and `docs/execution/CURRENT_PROJECT_STATE.md` were updated to reflect Slice 5 completion.

No deployment. The quality gate, RBAC, approval, and download gates were not weakened.

## Validation Evidence

- `ruff check apps scripts`: clean.
- `python3 -m compileall apps scripts`: clean.
- `python3 scripts/check_doc_drift.py`: clean (incl. anchor-currency invariant).
- `python3 scripts/check_ai_context.py`: clean (incl. extended Phase 2B whitelist).
- `python3 scripts/agent_preflight.py`: clean (post-commit).
- `python3 -m pytest -q apps/edr/tests/integration/test_phase2b_permissions.py`: 33 passed.
- `make smoke`: 2 passed.
- `make test`: full suite green (341 passed, 1 warning).
- `make eval`: 64/64 passed.
- `cd frontend && npm run lint`: clean.
- `cd frontend && npm run build`: success.

## Safe Next Work

Phase 2B Slice 6 — Project Source Mapping is the safe next work item per `docs/execution/PHASE_2B_PLAN.md` §E. It requires explicit per-slice user approval before implementation.

Do not deploy. Do not start Slice 6 by inference. Do not change production status from `NOT_LIVE` without an explicit deployment instruction and evidence. Do not weaken `_require_admin`.
