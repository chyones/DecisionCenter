# DecisionCenter — Current Project State

> **Audited commit:** `9dde3c1cb807a0ab4e0ff2d3353893bfa2b7e92d`
> **Audit date:** 2026-05-07
> **Audit scope:** Documentation/truth alignment only. No Phase 1C implementation and no product behavior changes.

---

## Current Project Stage

DecisionCenter is a pre-Phase-1C backend foundation. The control documents, infrastructure
foundation, RBAC/identity gate, and async graph runtime are complete enough for Phase 1C to
start. The product is not usable as an evidence-backed report generator yet because connector
workflows, retrieval, LLM report generation, persistence, approval, evaluation hardening, and UI
are not implemented.

---

## Completed Phases

| Phase | Status | Evidence |
|---|---|---|
| Phase 0 — Control and documentation lock | Complete | Locked spec, control-plane docs, policies, contracts, schemas, operations docs, and phase plan exist under `docs/`. |
| Phase 1A — Infrastructure Foundation | Complete | `.env.example` has 36 keys; `apps/edr/config.py` maps 36 settings; `.github/workflows/ci.yml` runs ruff, compileall, config coverage, smoke tests, and integration tests; `pyproject.toml` uses pinned dependencies; `docker-compose.yml` defines app, PostgreSQL, Redis, Qdrant, MinIO, n8n, and Caddy; `scripts/init_qdrant.py` exists. |
| Phase 1B — RBAC and Identity | Complete | `apps/edr/auth/validator.py` validates Entra JWTs when configured; `apps/edr/graph/node_01_auth.py` enforces canonical roles, valid `project_code`, and project source mapping; `apps/edr/rbac/roles.py` defines 9 roles; `apps/edr/rbac/project_mapping.py` loads `docs/config/project_source_mapping.json`; `apps/edr/tests/integration/test_rbac.py` covers authorized, denied, unknown project, invalid role, and all-role cases. |
| Phase 1B.5 — Async Connector Runtime Readiness | Complete | `apps/edr/graph/runner.py` is async and awaits each node; every `apps/edr/graph/node_00_begin.py` through `node_17_publish.py` exposes `async def run`; smoke and RBAC tests use `asyncio.run()`. |

---

## Partial Or Scaffold-Only Areas

| Area | Current state | Remaining gap |
|---|---|---|
| Graph workflow shell | All 18 nodes exist and are visited by smoke tests. | Nodes 02-17 are mostly stubs and do not perform real retrieval, LLM, persistence, approval, or publish work. |
| Phase 1D retrieval helpers | Chunking, memory cache, and reciprocal rank fusion exist; embedding and rerank classes exist. | Chunking is character-based, not token-based; embeddings and reranking raise `NotImplementedError`; no Redis cache wiring or Qdrant round trip. |
| Phase 1E report/export shell | Node 14 can export a stub report through exporter helpers. | No LLM calls, no real JSON report generation, no deterministic claim checker over real evidence, and no Langfuse traces. |
| Phase 1H evaluation shell | Evaluation docs, metrics helpers, promptfoo placeholder, and one JSONL example exist. | Evaluation runner is stubbed, promptfoo has empty providers/tests, and the golden set is far below the 50-case go-live target. |

---

## Not-Started Functional Phases

| Phase | Evidence |
|---|---|
| Phase 1C — n8n Connector Workflows | `n8n/sharepoint_search.json`, `n8n/owncloud_list.json`, `n8n/email_search.json`, and `n8n/odoo_read.json` all have `"nodes": []`. |
| Phase 1F — Persistence and Audit | `apps/edr/graph/node_15_save_audit.py` returns `audit_status = "stubbed"`; `GET /reports/staging/{request_id}/download/{fmt}` always returns 404 in stub mode; no MinIO bucket initialization exists. |
| Phase 1G — Human Review Gate | `node_16_review.py` returns pending only; `node_17_publish.py` blocks until approval; no approve/reject API endpoints exist in `apps/edr/app.py`. |
| Phase 1I, 2A, 2B, 2C — UI phases | No `frontend/` directory exists and no `make test:ui` target exists. |

---

## Blockers

### Already Resolved

| Blocker | Resolution evidence |
|---|---|
| B6 — Async/sync connector bridge | `run_workflow()` and all 18 graph nodes are async. This removes the runtime mismatch that would have blocked future async n8n calls. |
| Phase 1B validation gate | RBAC tests cover authorized user, unauthorized roles, unknown project, missing/invalid role, populated allowed mailboxes, populated Odoo IDs, and 9-role enumeration. |

### Remaining

| Blocker | Blocks | Evidence |
|---|---|---|
| Empty n8n workflows | Phase 1D and all real retrieval | All four `n8n/*.json` files contain empty `nodes` arrays. |
| Missing MinIO bucket initialization | Phase 1F | `MINIO_BUCKET=decision-center` is configured, but no bucket init script or startup hook exists. |
| Stubbed evaluation runner message | Phase 1H polish | `apps/edr/evaluation/run.py` still says evaluation is stubbed until Phase 1G, while the plan places evaluation in Phase 1H. |

---

## Safe Next Phase

Phase 1C may start.

Allowed Phase 1C work is limited to the four read-only n8n workflows and their isolated validation:

- `n8n/sharepoint_search.json`
- `n8n/owncloud_list.json`
- `n8n/email_search.json`
- `n8n/odoo_read.json`
- curl tests and schema checks against `docs/schemas/evidence-object.schema.json`

## Forbidden Work In Phase 1C

Do not add Python graph node behavior, LLM calls, embeddings, vector retrieval, reranking,
report persistence, audit persistence, approval/reject APIs, publish logic, frontend/UI work,
or unrelated product behavior. Do not commit secrets into workflows, docs, code, logs, or tests.

---

## README And Truth Doc Freshness

Before this audit, README and feature/truth docs were stale: README still reported Phase 1B as
not started, and the feature matrix still treated RBAC as documented-only/partial. These docs now
reflect the live repo state at the audited commit.

---

## Readiness Ratings

| Rating | Score | Reason |
|---|---:|---|
| Architecture quality | 8/10 | Clear phase plan, fixed 18-node graph, separated docs/contracts/policies, and explicit service boundaries. |
| Code foundation | 7/10 | Good Python package shape, pinned dependencies, CI, smoke/RBAC tests, and async runtime; many business nodes remain stubs. |
| Pre-1C readiness | 9/10 | Phase 1C prerequisites are satisfied; the remaining B10 blocker is for Phase 1F, not Phase 1C. |
| Product readiness | 2/10 | No real connectors, no LLM, no persistence, no approval APIs, and no UI. |
| Overall maturity | 4/10 | Strong controlled foundation, but still early in functional implementation. |
