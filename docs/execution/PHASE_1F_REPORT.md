# Phase 1F Report — Persistence & Audit

## Scope

- Branch: `main`
- Ending commit: `5bb6ed8d3fdec1f80a94aa0d89a65b644ff5a8ef`
- Production status: `NOT_LIVE`
- Final readiness decision: `PHASE_1F_COMPLETE_NOT_LIVE`

## What Was Implemented

### Node 15 — Save and Audit

Replaced the stub with real persistence logic (`apps/edr/graph/node_15_save_audit.py`):

1. **MinIO artifacts** (4 files per request under `/staging/{request_id}/`):
   - `executive-decision-report.{fmt}` — all generated export formats
   - `evidence-pack.json` — full evidence list from state
   - `quality-gate-result.json` — quality gate result
   - `audit-log.json` — metadata-only audit artifact (no confidential content)

2. **PostgreSQL audit row** (`audit_log` table):
   - `request_id` (unique)
   - `user_id_hash` (SHA-256, raw user_id never stored)
   - `project_code`, `query`
   - `quality_gate_status`
   - `token_counts` (JSONB)
   - `cost_total_usd` (NUMERIC)
   - `artifact_keys` (JSONB)
   - `created_at`, `updated_at`

3. **Graceful degradation**: connection errors are caught so the workflow completes in environments without MinIO/PostgreSQL.

### Download Endpoint

Updated `GET /reports/staging/{request_id}/download/{fmt}` (`apps/edr/app.py`):
- Validates format against `MIME_TYPES`
- Loads audit row from PostgreSQL
- Returns 404 for unknown request IDs
- Blocks download (403) when `quality_gate == "failed"`
- Authorizes by comparing hashed user_id or allowing admin/auditor roles
- Streams artifact bytes from MinIO with correct `Content-Type` and `Content-Disposition`

### Token & Cost Tracking

Updated `apps/edr/llm.py`:
- `_CostTracker` now accumulates token usage per `request_id`
- `get_token_usage(request_id)` returns `{"input": N, "output": N}`
- `reset_token_usage(request_id)` test helper added

### New Persistence Module

`apps/edr/persistence/`:
- `hash.py` — `hash_user_id()` using SHA-256
- `minio_store.py` — `MinioStore` with idempotent bucket creation, `put_json`, `put_bytes`, `get_object`, `object_exists`
- `postgres_store.py` — `PostgresStore` with `init_schema`, `insert_audit`, `get_audit`

### Schema Updates

`apps/edr/schemas/audit.py`:
- Added `AuditArtifact` Pydantic model matching spec Section 30 (with `user_id_hash` instead of raw `user_id`)

### Dependency

`pyproject.toml`:
- Added `asyncpg==0.29.0`

## What Was NOT Implemented

- Phase 1G (Human Review Gate)
- Approval/rejection endpoints
- Publish-to-final logic (Node 17)
- Production deployment

## Test Coverage

Added 12 integration tests in `apps/edr/tests/integration/test_phase1f.py`:

1. Node 15 writes all four artifacts
2. Bucket init is idempotent
3. Audit row is created and linked to request_id
4. Raw user_id is never stored (hashed only)
5. Token/cost totals persist
6. Audit artifacts omit full confidential content
7. Download md returns persisted Markdown
8. Failed quality gate blocks download
9. Invalid format rejected (400)
10. Unknown request ID rejected (404)
11. Unauthorized download blocked (403)
12. Admin/auditor roles allowed to download any report

Total test count: 86 passed (24 smoke/integration excluding pre-existing collection errors).

## Validation Proof

- `ruff check .`: clean
- `python3 -m compileall apps scripts`: clean
- `python3 scripts/check_doc_drift.py`: clean
- `python3 scripts/check_ai_context.py`: clean
- `pytest apps/edr/tests/smoke apps/edr/tests/integration/test_phase1e.py apps/edr/tests/integration/test_phase1f.py apps/edr/tests/integration/test_rbac.py apps/edr/tests/integration/test_connectors.py apps/edr/tests/integration/test_retrieval.py apps/edr/tests/integration/test_phase1d_security.py apps/edr/tests/integration/test_doc_drift.py`: 86 passed

## Next Phase

Phase 1G — Human Review Gate (requires explicit user approval before starting).
