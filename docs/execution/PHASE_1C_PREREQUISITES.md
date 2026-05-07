# Phase 1C Prerequisites — Live Repo Audit

> **Audited commit:** `9dde3c1cb807a0ab4e0ff2d3353893bfa2b7e92d`
> **Audit date:** 2026-05-07
> **Phase 1C decision:** May start.
> **B6 status:** Resolved in Phase 1B.5.
> **B10 status:** Open, but required before Phase 1F, not before Phase 1C.

---

## Phase 1C Readiness Decision

Phase 1C may start because the live repository proves:

- Phase 1A infrastructure foundation is present: 36-key config coverage, pinned Python dependencies,
  Docker Compose service stack, CI lint/syntax/config/smoke/integration gates, and Qdrant init script.
- Phase 1B RBAC/identity foundation is present: `node_01_auth.py` validates role and project scope,
  loads `docs/config/project_source_mapping.json`, populates allowed project/mailbox/Odoo IDs, and
  denies admin, auditor, invalid role, missing project, and unknown project cases.
- Phase 1B.5 async runtime readiness is present: `run_workflow()` is async, all 18 node `run()`
  functions are async, and tests invoke async graph code with `asyncio.run()`.

Phase 1C is still not implemented. All four workflow files in `n8n/*.json` still have empty
`nodes` arrays and must be treated as placeholders.

---

## Forbidden During Phase 1C

Phase 1C must stay limited to n8n connector workflow implementation and isolated curl/schema
validation. Do not add:

- Python graph node behavior beyond what is needed to keep existing tests passing.
- LLM calls, prompt execution, embeddings, vector retrieval, reranking, or retrieval persistence.
- PostgreSQL/MinIO report persistence, audit trail writes, approval APIs, publish logic, or frontend.
- New product behavior outside the four read-only connector workflows.
- Secret values in workflow JSON, docs, code, logs, or tests.

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
