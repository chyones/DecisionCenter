# DecisionCenter — Current Project State

> **Audited commit:** `1c5d62806b2339fa972b7a9c8ea884f79971ffe2`
> **Audit date:** 2026-05-07
> **Audit scope:** Post-Phase 1C documentation alignment. No Phase 1D implementation.

---

## Current Project Stage

DecisionCenter has completed Phase 1C. The four n8n connector workflows are implemented,
Python-side connector validation is wired, and isolated integration tests pass in CI.
The product is not yet an evidence-backed report generator because retrieval, embedding,
LLM report generation, persistence, approval, evaluation hardening, and UI remain
unimplemented.

---

## Completed Phases

| Phase | Status | Evidence |
|---|---|---|
| Phase 0 — Control and documentation lock | Complete | Locked spec, control-plane docs, policies, contracts, schemas, operations docs, and phase plan exist under `docs/`. |
| Phase 1A — Infrastructure Foundation | Complete | `.env.example` has 36 keys; `apps/edr/config.py` maps 36 settings; `.github/workflows/ci.yml` runs ruff, compileall, config coverage, smoke tests, and integration tests; `pyproject.toml` uses pinned dependencies; `docker-compose.yml` defines app, PostgreSQL, Redis, Qdrant, MinIO, n8n, and Caddy; `scripts/init_qdrant.py` exists. |
| Phase 1B — RBAC and Identity | Complete | `apps/edr/auth/validator.py` validates Entra JWTs when configured; `apps/edr/graph/node_01_auth.py` enforces canonical roles, valid `project_code`, and project source mapping; `apps/edr/rbac/roles.py` defines 9 roles; `apps/edr/rbac/project_mapping.py` loads `docs/config/project_source_mapping.json`; `apps/edr/tests/integration/test_rbac.py` covers authorized, denied, unknown project, invalid role, and all-role cases. |
| Phase 1B.5 — Async Connector Runtime Readiness | Complete | `apps/edr/graph/runner.py` is async and awaits each node; every `apps/edr/graph/node_00_begin.py` through `node_17_publish.py` exposes `async def run`; smoke and RBAC tests use `asyncio.run()`. |
| Phase 1C — n8n Connector Workflows | Complete | All four `n8n/*.json` workflows contain real 4-node pipelines (Webhook → HTTP Request → Code normalization → Respond to Webhook). `apps/edr/connectors/validation.py` enforces `EvidenceObject` schema. All four connector wrappers validate responses. `apps/edr/tests/integration/test_connectors.py` has 10 isolated mock-based tests passing in CI. |

---

## Partial Or Scaffold-Only Areas

| Area | Current state | Remaining gap |
|---|---|---|
| Graph workflow shell | All 18 nodes exist and are visited by smoke tests. | Nodes 02–17 are mostly stubs. Nodes 05–08 return `*_status = "stubbed"`; Nodes 12, 13, 14, 15, 16 are stubbed. |
| Phase 1D retrieval helpers | Chunking, memory cache, and reciprocal rank fusion exist; embedding and rerank classes exist. | `embeddings.py` and `rerank.py` raise `NotImplementedError`; chunking is character-based, not token-based; no Redis cache wiring or Qdrant round trip. |
| Phase 1E report/export shell | Node 14 can export a stub report through exporter helpers. | No LLM calls, no real JSON report generation, no deterministic claim checker over real evidence, and no Langfuse traces. |
| Phase 1H evaluation shell | Evaluation docs, metrics helpers, promptfoo placeholder, and one JSONL example exist. | Evaluation runner is stubbed until Phase 1G/1H; promptfoo has empty providers/tests; golden set is far below the 50-case go-live target. |

---

## Not-Started Functional Phases

| Phase | Evidence |
|---|---|
| Phase 1D — Embedding & Vector Retrieval | Nodes 05–08 return `"stubbed"`. `embeddings.py` and `rerank.py` raise `NotImplementedError`. No Redis-backed cache. No Qdrant round-trip test. |
| Phase 1F — Persistence and Audit | `node_15_save_audit.py` returns `audit_status = "stubbed"`. `GET /reports/staging/{request_id}/download/{fmt}` does not exist. No MinIO bucket initialization script. |
| Phase 1G — Human Review Gate | `node_16_review.py` returns pending only; `node_17_publish.py` blocks until approval; no approve/reject API endpoints exist in `apps/edr/app.py`. |
| Phase 1I, 2A, 2B, 2C — UI phases | No `frontend/` directory exists and no `make test:ui` target exists. |

---

## Blockers

### Already Resolved

| Blocker | Resolution evidence |
|---|---|
| B6 — Async/sync connector bridge | `run_workflow()` and all 18 graph nodes are async. |
| Phase 1B validation gate | RBAC tests cover authorized user, unauthorized roles, unknown project, missing/invalid role, populated allowed mailboxes, populated Odoo IDs, and 9-role enumeration. |
| Empty n8n workflows | All four `n8n/*.json` files contain real node definitions with 4 nodes each. Isolated connector validation tests pass in CI. |

### Remaining

| Blocker | Blocks | Evidence |
|---|---|---|
| Missing MinIO bucket initialization | Phase 1F | `MINIO_BUCKET=decision-center` is configured, but no bucket init script or startup hook exists. |
| Stubbed evaluation runner message | Phase 1H polish | `apps/edr/evaluation/run.py` still says evaluation is stubbed until Phase 1G, while the plan places evaluation in Phase 1H. |

---

## Safe Next Phase

Phase 1D may start.

Allowed Phase 1D work is limited to the retrieval pipeline and vector store wiring:

- Wire `apps/edr/retrieval/embeddings.py` → Voyage-3-large API
- Fix `apps/edr/retrieval/chunking.py` to token-based 500–800 tokens with 100–150 overlap
- Wire `apps/edr/retrieval/rerank.py` → Cohere Rerank 3.5
- Wire RBAC-aware `MemoryCache` to Redis
- Real Node 05–08: call n8n webhooks → embed results → insert into Qdrant
- Node 09: real normalization and dedup
- Node 10: real sufficiency check

## Forbidden Work In Phase 1D

Do not add LLM calls, report generation, persistence, audit writes, approval/reject APIs,
publish logic, frontend/UI work, or unrelated product behavior. Do not commit secrets into
workflows, docs, code, logs, or tests.

---

## README And Truth Doc Freshness

This audit refreshed `CURRENT_PROJECT_STATE.md` and `IMPLEMENTATION_PHASES.md` to reflect
the live repo state at commit `1c5d628`. Phase 1C is now recorded as complete.

---

## Readiness Ratings

| Rating | Score | Reason |
|---|---:|---|
| Architecture quality | 8/10 | Clear phase plan, fixed 18-node graph, separated docs/contracts/policies, and explicit service boundaries. |
| Code foundation | 7/10 | Good Python package shape, pinned dependencies, CI, smoke/RBAC/connector tests, and async runtime; many business nodes remain stubs. |
| Pre-1D readiness | 9/10 | Phase 1D prerequisites are satisfied; connector workflows and validation exist. B10 blocker is for Phase 1F, not 1D. |
| Product readiness | 2/10 | No embeddings, no vector retrieval, no LLM, no persistence, no approval APIs, and no UI. |
| Overall maturity | 4/10 | Strong controlled foundation, but still early in functional implementation. |
