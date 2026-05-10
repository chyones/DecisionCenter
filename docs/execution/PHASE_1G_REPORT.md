# Phase 1G Report — Human Review Gate

## Scope

- Branch: `main`
- Phase 1G commit (verified): `001d606ca4742c2d35983b2a2b7993fc7a3a0e8b`
- Ending commit on `main`: `d1f40a4040a99bbd242bccb0734ebc6e6aabb30d` (adjusts AI-context refs to point at `001d606`)
- Production status: `NOT_LIVE`
- Final readiness decision: `PHASE_1G_COMPLETE_NOT_LIVE`

## What Was Implemented

### Review Endpoints

Three new `POST` endpoints on `/reports/staging/{request_id}/`:

1. **`/approve`** — writes an approval record to PostgreSQL.
   - Normal reviewers (roles with `can_approve=True`) use action `approve`.
   - Admin uses action `admin_override` (metadata-only) and must provide a mandatory comment.
   - Auditor is blocked.
   - Self-approval is blocked for all roles.
   - Returns 409 if the report is already finalized or rejected.

2. **`/reject`** — writes a rejection record with a required reason.
   - Self-rejection is blocked.
   - Returns 409 if already finalized.

3. **`/request-revision`** — writes a revision-request record with required reason and optional comment.
   - Self-revision-request is blocked.
   - Returns 409 if already finalized.

### Final Download Endpoint

- `GET /reports/final/{request_id}/download/{fmt}` — serves artifacts from `/final/{request_id}/` in MinIO.
- Only works when `review_state == "final"`.
- Quality gate `failed` blocks all download paths (staging and final).

### Staging Download Blocking

- Approval-required reports block staging downloads before approval.
- Draft-only reports (e.g., `document_control` intent) bypass the approval block.
- Authorization is checked before approval blocking.

### Node 16 — Human Review

- Reads `review_state` and `review_decisions` from PostgreSQL.
- Exposes `human_review_status` mapped to: `pending`, `approved`, `rejected`, `revision_requested`.
- Gracefully degrades when PostgreSQL is unavailable.

### Node 17 — Publish

- Publishes only when `review_state` is `approved`.
- Hard-stops for `rejected` and `revision_requested` states.
- Copies artifacts from `/staging/` to `/final/` in MinIO.
- Final artifacts are write-once: `copy_to_final` raises `FileExistsError` if already present.
- Writes `approval-log.json` exactly once to `/final/{request_id}/`.
- Updates PostgreSQL `review_state` to `final` after successful publish.
- Returns `publish_status`: `published`, `rejected`, `revision_requested`, `blocked_until_approval`.

### Database Schema

- `audit_log` table extended with:
  - `review_state TEXT DEFAULT 'staging'`
  - `requires_approval BOOLEAN DEFAULT TRUE`
- New `review_decisions` table:
  - `request_id`, `reviewer_id_hash`, `action`, `reason`, `comment`, `created_at`

### RBAC Enforcement

- Reviewer RBAC uses canonical `RolePermissions.can_approve`.
- Admin override is a distinct action (`admin_override`) with mandatory comment.
- Auditor cannot approve, reject, or request revision.
- Admin cannot view report content (enforced by never serving content to admin in download endpoints).

### Approval-Required vs Draft-Only

- `_requires_approval()` in Node 15 uses intent classification:
  - Draft-only intents: `document_control`
  - All other intents require approval by default (financial, delay, contract risk, claims, etc.)

## What Was NOT Implemented

- Phase 1H (Evaluation & Hardening)
- Frontend UI
- Automatic re-generation after reject or request-revision
- Background polling/publish job (publish runs synchronously in Node 17 or on approve)

## Test Coverage

Added 22 integration tests in `apps/edr/tests/integration/test_phase1g.py`:

1. Approve writes approval record with hashed reviewer ID
2. Approve blocks self-approval
3. Approve blocks auditor
4. Admin override requires mandatory comment
5. Reject requires reason (Pydantic validation)
6. Reject writes rejection record
7. Request-revision writes decision
8. Node 16 reflects pending when no decisions
9. Node 16 reflects approved
10. Node 16 reflects rejected
11. Node 16 reflects revision_requested
12. Node 17 publishes when approved
13. Node 17 blocks when no approval
14. Node 17 rejects rejected reports
15. Node 17 rejects revision_requested reports
16. Node 17 final artifacts are write-once
17. Staging download blocked before approval
18. Final download succeeds after approval
19. Final download blocked before finalization
20. Quality gate failed blocks all downloads
21. Approval-log.json is written once
22. Unauthorized role blocked from review

Total test count: 108 passed locally, 118 passed in Docker container.

## Validation Proof

- `make smoke`: 2 passed
- `make test`: 118 passed
- `ruff check .`: clean
- `python3 -m compileall apps scripts`: clean
- `python3 scripts/check_doc_drift.py`: clean
- `python3 scripts/check_ai_context.py`: clean

## Next Phase

Phase 1H — Evaluation & Hardening (requires explicit user approval before starting).
