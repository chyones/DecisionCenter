# Agent Handoff — DecisionCenter

## What Was Done

Phase 1G (Human Review Gate) is complete.

### Review Endpoints

- `POST /reports/staging/{request_id}/approve` — writes approval record.
  - Normal reviewers: action = `approve`.
  - Admin override: action = `admin_override`, mandatory comment required.
  - Auditor blocked. Self-approval blocked.
- `POST /reports/staging/{request_id}/reject` — writes rejection record with required reason.
- `POST /reports/staging/{request_id}/request-revision` — writes revision request with required reason.

### Download Endpoints

- `GET /reports/staging/{request_id}/download/{fmt}` — blocks approval-required reports before approval.
- `GET /reports/final/{request_id}/download/{fmt}` — serves immutable final artifacts only when `review_state == "final"`.
- Quality gate `failed` blocks all download paths.

### Node 16 — Human Review

- Reads `review_state` and `review_decisions` from PostgreSQL.
- Exposes `human_review_status` mapped to `pending`, `approved`, `rejected`, `revision_requested`.

### Node 17 — Publish

- Publishes only when `review_state == "approved"`.
- Copies artifacts from `/staging/{request_id}/` to `/final/{request_id}/` in MinIO.
- Final artifacts are write-once (`FileExistsError` on duplicate).
- Writes `approval-log.json` exactly once.
- Updates PostgreSQL `review_state` to `final`.
- Hard-stops for `rejected` and `revision_requested`.

### Database Schema

- `audit_log` extended with `review_state` and `requires_approval`.
- New `review_decisions` table tracks every approval, rejection, and revision request with hashed reviewer IDs.

### RBAC

- Reviewer roles determined by `RolePermissions.can_approve`.
- Admin override is metadata-only (no report content exposure) and creates a distinct `admin_override` audit event.
- Auditor cannot review.

## Current Branch And Commit

- Branch: `main`
- Current verified commit: `001d606ca4742c2d35983b2a2b7993fc7a3a0e8b`
- Status: `PHASE_1G_COMPLETE_NOT_LIVE`
- Production status: `NOT_LIVE`

## Files Changed

- `apps/edr/persistence/postgres_store.py` — review_decisions table, review state methods
- `apps/edr/persistence/minio_store.py` — `copy_to_final` with write-once protection
- `apps/edr/graph/node_15_save_audit.py` — `requires_approval` based on intent
- `apps/edr/graph/node_16_review.py` — reads review state from PostgreSQL
- `apps/edr/graph/node_17_publish.py` — publish to final on valid approval
- `apps/edr/app.py` — approve, reject, request-revision, final-download endpoints
- `apps/edr/tests/integration/test_phase1g.py` — 22 new tests
- `apps/edr/tests/integration/test_phase1f.py` — updated for new staging download behavior
- `docs/execution/PHASE_1G_REPORT.md` — new report

## What Was NOT Done

- Phase 1H (Evaluation & Hardening) not started.
- No frontend UI added.
- No automatic re-generation after reject or request-revision.
- No production deployment performed.
- No secrets or `.env` files committed.

## Must Read Before Next Work

- `docs/ai/agent-state.json`
- `docs/execution/IMPLEMENTATION_PHASES.md`
- `docs/admin/CONTROL_PLANE_LOCK.md`

## Next Recommended Work

Phase 1H requires explicit user approval. When authorized:

- Expand executable golden set.
- Wire evaluation runner and promptfoo config.
- Fix PDF Arabic RTL rendering.
- Add cost cap circuit breaker.
- Add `make eval` to CI.

## Validation Proof

Latest required validation executed for this Phase 1G session:

- `make smoke`: 2 passed.
- `make test`: 118 passed.
- `ruff check .`: clean.
- `python3 -m compileall apps scripts`: clean.
- `python3 scripts/check_doc_drift.py`: clean.
- `python3 scripts/check_ai_context.py`: clean.

## Final Status

`PHASE_1G_COMPLETE_NOT_LIVE`
