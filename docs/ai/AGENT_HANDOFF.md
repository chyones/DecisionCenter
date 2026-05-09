# Agent Handoff — DecisionCenter

## What Was Done

Phase 1F (Persistence & Audit) is complete.

Node 15 now persists four staging artifacts to MinIO:
- `executive-decision-report.md` (and other generated formats)
- `evidence-pack.json`
- `audit-log.json`
- `quality-gate-result.json`

PostgreSQL audit rows store:
- Hashed user_id (SHA-256, raw user_id never stored)
- Token counts and cost totals per request
- Quality gate status and artifact keys
- Timestamps

The download endpoint (`GET /reports/staging/{request_id}/download/{fmt}`):
- Streams artifacts from MinIO
- Blocks downloads when quality_gate == "failed"
- Rejects invalid formats (400), unknown request IDs (404), and unauthorized access (403)
- Allows admin and auditor roles to access any report

Token usage tracking was added to `llm.py` (`get_token_usage`, `reset_token_usage`).

Graceful degradation: Node 15 catches connection errors so the workflow completes in test environments without MinIO/PostgreSQL running.

## Current Branch And Commit

- Branch: `main`
- Current verified commit: `5bb6ed8d3fdec1f80a94aa0d89a65b644ff5a8ef`
- Status: `PHASE_1F_COMPLETE_NOT_LIVE`
- Production status: `NOT_LIVE`

## Files Changed

- `apps/edr/persistence/` — new module (hash, minio_store, postgres_store)
- `apps/edr/graph/node_15_save_audit.py` — real persistence logic
- `apps/edr/app.py` — download endpoint with MinIO, auth, quality gate
- `apps/edr/llm.py` — token usage tracking per request_id
- `apps/edr/schemas/audit.py` — enriched audit artifact schema
- `apps/edr/tests/integration/test_phase1f.py` — 12 new tests
- `pyproject.toml` — added `asyncpg==0.29.0`

## What Was NOT Done

- Phase 1G (Human Review Gate) not started.
- No approval or rejection endpoints added.
- No publish-to-final logic.
- No production deployment performed.
- No secrets or `.env` files committed.

## Must Read Before Next Work

- `docs/ai/agent-state.json`
- `docs/execution/IMPLEMENTATION_PHASES.md`
- `docs/admin/CONTROL_PLANE_LOCK.md`

## Next Recommended Work

Phase 1G requires explicit user approval. When authorized:

- Implement approval/rejection endpoints.
- Update Node 16 to read approval state from PostgreSQL with timeout.
- Update Node 17 to publish only after valid approval.
- Move artifacts from `/staging/` to `/final/` in MinIO on publish.

## Validation Proof

Latest required validation executed for this Phase 1F session:

- `ruff check .`: clean.
- `python3 -m compileall apps scripts`: clean.
- `python3 scripts/check_doc_drift.py`: clean.
- `python3 scripts/check_ai_context.py`: clean.
- Local pytest (86 passed): 62 existing + 22 Phase 1E + 12 Phase 1F tests.

Docker validation (`make smoke`, `make test`) not run because the asyncpg dependency
requires a Docker image rebuild.

## Final Status

`PHASE_1F_COMPLETE_NOT_LIVE`
