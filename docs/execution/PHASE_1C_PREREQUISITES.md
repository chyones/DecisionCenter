# Phase 1B.5 — Connector Runtime Readiness / Phase 1C and 1F Blockers

> **Identified during:** Phase 1B audit (2026-05-06)
> **B6 resolved:** Phase 1B.5 (2026-05-07)
> **B10 status:** Open — required before Phase 1F begins.

---

## Blocker B6 — Async/Sync Connector Bridge ✅ RESOLVED

**Resolved in:** Phase 1B.5 — Connector Runtime Readiness (2026-05-07)

**Resolution applied (Option 1 — spec-correct):**
All 18 node `run()` functions converted to `async def run()`. The graph runner
`run_workflow()` is now `async def` and `await`s each node. The FastAPI
`stage_report` endpoint is now `async def` and `await`s `run_workflow()`.
Tests updated to use `asyncio.run()` to invoke async nodes without new dependencies.

**Files changed:**
- `apps/edr/graph/runner.py` — `async def run_workflow()`; `Node` type updated to `Callable[..., Coroutine[...]]`
- `apps/edr/graph/node_00_begin.py` through `node_17_publish.py` (18 files) — `async def run()`
- `apps/edr/app.py` — `async def stage_report()`; `await run_workflow(state)`
- `apps/edr/tests/smoke/test_smoke.py` — `asyncio.run(run_workflow(state))`
- `apps/edr/tests/integration/test_rbac.py` — `asyncio.run(node_01_auth.run(state))`

**Validation:** `pytest -q apps/edr/tests/` → 20 passed.

**Why Option 1:**
LangGraph (Phase 1D+) natively supports async nodes. Converting now avoids a
second full rewrite in Phase 1E when LLM calls (inherently async) are added.
`N8NWebhookClient.post()` in `apps/edr/connectors/base.py` remains `async def`
and can now be `await`ed directly from retrieval nodes in Phase 1C.

---

**Original problem (for record):**
`N8NWebhookClient.post()` was declared `async def`. All 18 node `run()` functions
were synchronous. Wiring n8n webhook calls in Phase 1C would have raised
`RuntimeError: coroutine was never awaited` at runtime.

---

## Blocker B10 — MinIO Bucket Initialization (required before Phase 1F)

**Status:** Open — do not implement before Phase 1F is approved.

**Problem:**
`config.py` defines `minio_bucket = "decision-center"`. No bucket initialization
script exists. No bucket creation code runs at startup. Phase 1F `node_15_save_audit`
will raise `S3Error: NoSuchBucket` on the first write attempt.

**Required resolution before Phase 1F:**
- Add a `scripts/init_minio.py` script (or extend `scripts/init_qdrant.py`) that
  creates the `decision-center` bucket if it does not already exist.
- OR: add bucket initialization to the FastAPI startup event (`app.on_event("startup")`).
- The operation must be idempotent — bucket already exists → no error.

**Affected phase:** Phase 1F — Persistence & Audit.
