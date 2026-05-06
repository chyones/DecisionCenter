# Phase 1C and 1F — Unresolved Blockers

> **Identified during:** Phase 1B audit (2026-05-06)
> **Status:** Documented. Must be resolved before respective phases begin.
> **Do NOT implement these items in Phase 1B or 1C without explicit phase approval.**

---

## Blocker B6 — Async/Sync Connector Bridge (required before Phase 1C)

**File:** `apps/edr/connectors/base.py`

**Problem:**
`N8NWebhookClient.post()` is declared `async def`. All 18 node `run()` functions are
synchronous. When Phase 1C wires n8n webhook calls into retrieval nodes, every call
will raise `RuntimeError: coroutine was never awaited` because synchronous code cannot
`await` a coroutine.

**Evidence:**
```python
# apps/edr/connectors/base.py
async def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    ...

# apps/edr/graph/node_05_sharepoint.py (and all retrieval nodes)
def run(state: DecisionState) -> DecisionState:
    ...
```

**Required resolution (choose one before Phase 1C begins):**
1. Convert all 18 node `run()` functions to `async def` and update `runner.py` to use
   `asyncio.run()` or a LangGraph async graph — this is the spec-correct approach
   since the locked spec mandates LangGraph orchestration.
2. OR: change `N8NWebhookClient.post()` to synchronous using `httpx` in sync mode
   (`httpx.Client` instead of `httpx.AsyncClient`).

**Recommendation:** Option 1. The spec mandates LangGraph, and LangGraph natively
supports async nodes. Converting now avoids a second rewrite in Phase 1E when LLM
calls (which are async) are added.

---

## Blocker B10 — MinIO Bucket Initialization (required before Phase 1F)

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
