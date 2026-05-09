# DecisionCenter — Current Project State

> **Audited commit:** post `c9ed521` Phase 1D + Phase 1D-fixup
> **Audit date:** 2026-05-09
> **Audit scope:** Phase 1D retrieval pipeline plus the closure of all
> Phase 1D-fixup items (audit findings C-1..C-8, S-1, L-2, L-5, O-1..O-4).

---

## Current Project Stage

DecisionCenter has completed Phase 1D and applied the post-1D fixup. The four
n8n connector workflows are real, header-authenticated, and read service-account
credentials from the n8n container environment. Voyage embeddings, Cohere
reranking, tiktoken-based chunking, the per-project Qdrant store, and the
Redis-backed evidence cache are wired. RBAC is enforced in Node 01 and the
mailbox allowlist is enforced twice in the Node 07 / email path. The product
is not yet an evidence-backed report generator because Phase 1E (LLM nodes),
Phase 1F (persistence), and Phase 1G (human review) are still ahead.

---

## Completed Phases

| Phase | Status | Evidence |
|---|---|---|
| Phase 0 — Control and documentation lock | Complete | Locked spec, control-plane docs, policies, contracts, schemas, operations docs, and phase plan exist under `docs/`. |
| Phase 1A — Infrastructure Foundation | Complete | `.env.example` has 39 keys; `apps/edr/config.py` maps 39 settings; `.github/workflows/ci.yml` runs ruff, compileall, config coverage, smoke tests, integration tests, and `pip-audit`; `pyproject.toml` uses pinned dependencies (PyJWT 2.10.1, cryptography 44.0.0); `docker-compose.yml` defines app, PostgreSQL, Redis, Qdrant, MinIO, n8n, Caddy with healthchecks; internal services bind only to localhost or the compose network; `scripts/init_qdrant.py` agrees with the runtime collection naming. |
| Phase 1B — RBAC and Identity | Complete | `apps/edr/auth/validator.py` validates Entra JWTs with a cached `PyJWKClient` and surfaces all roles; `apps/edr/graph/node_01_auth.py` enforces canonical roles and known `project_code`; `apps/edr/rbac/roles.py` defines 9 roles; `apps/edr/rbac/project_mapping.py` loads `docs/config/project_source_mapping.json`; `apps/edr/tests/integration/test_rbac.py` covers authorized, denied, unknown project, invalid role, and all-role cases. |
| Phase 1B.5 — Async Connector Runtime Readiness | Complete | `apps/edr/graph/runner.py` is async and awaits each node; every `apps/edr/graph/node_00_begin.py` through `node_17_publish.py` exposes `async def run`; smoke and RBAC tests use `asyncio.run()`. |
| Phase 1C — n8n Connector Workflows | Complete | All four `n8n/*.json` workflows contain real 4-node pipelines, declare `authentication=headerAuth`, and read service-account credentials from `$env.*`. The email workflow gates on the mailbox allowlist before any Graph call. `apps/edr/connectors/validation.py` enforces `EvidenceObject` schema. `apps/edr/tests/integration/test_connectors.py` covers all four sources with mocked responses. |
| Phase 1D — Embedding & Vector Retrieval | Complete | `apps/edr/retrieval/embeddings.py` calls Voyage-3-large; `apps/edr/retrieval/rerank.py` calls Cohere Rerank 3.5; `apps/edr/retrieval/chunking.py` uses tiktoken (500–800 tokens, 100–150 overlap, char fallback); `apps/edr/retrieval/qdrant_store.py` manages per-project collections with `edr_*` naming; `apps/edr/retrieval/cache.py` is Redis-backed with in-memory fallback; reciprocal rank fusion in `hybrid_search.py`; nodes 05–08 run real connector calls and embed/insert results into Qdrant; node 09 dedups by `(source_uri, hash_sha256)` with priority preservation; node 10 runs the sufficiency check. |
| Phase 1D-Fixup — Audit closure | Complete | All audit findings (C-1..C-8, S-1, L-2, L-5, O-1..O-4) closed; see `docs/admin/CONTROL_PLANE_LOCK.md` for the table. Regression tests in `apps/edr/tests/integration/test_phase1d_fixes.py` and `apps/edr/tests/integration/test_phase1d_security.py` lock the invariants. |

---

## Partial Or Scaffold-Only Areas

| Area | Current state | Remaining gap |
|---|---|---|
| Graph workflow shell | All 18 nodes exist; nodes 00–10 are functional. | Nodes 11–17 are stubs awaiting Phase 1E (11–14) and Phase 1F–1G (15–17). |
| Phase 1E LLM nodes | Prompt templates and exporters exist; node 14 exports only when the quality gate is `passed`. | No LLM calls, no real JSON report, no deterministic claim checker, no Langfuse traces. |
| Phase 1F persistence | MinIO container runs; `MINIO_BUCKET=decision-center` is configured. | No bucket initialization script; `node_15_save_audit.py` returns `audit_status = "stubbed"`; `GET /reports/staging/{id}/download/{fmt}` returns 404 by design. |
| Phase 1H evaluation | One JSONL example, metrics docs, and a promptfoo placeholder. | Evaluation runner prints a stubbed message; promptfoo has empty providers/tests; golden set far below 50 cases. |

---

## Not-Started Functional Phases

| Phase | Evidence |
|---|---|
| Phase 1E — LLM Nodes | Nodes 02, 03, 04, 11, 12, 13 have no LLM calls. Node 14 exports only when `quality_gate == "passed"`. |
| Phase 1F — Persistence and Audit | `node_15_save_audit.py` returns `audit_status = "stubbed"`. `GET /reports/staging/{request_id}/download/{fmt}` returns 404 deliberately until Phase 1F. No MinIO bucket initialization script. |
| Phase 1G — Human Review Gate | `node_16_review.py` returns pending only; `node_17_publish.py` blocks until approval; no approve/reject API endpoints. |
| Phase 1I, 2A, 2B, 2C — UI phases | No `frontend/` directory; no `make test:ui` target. |

---

## Blockers

### Already Resolved

| Blocker | Resolution evidence |
|---|---|
| B6 — Async/sync connector bridge | `run_workflow()` and all 18 graph nodes are async. |
| Phase 1B validation gate | RBAC tests cover authorized user, unauthorized roles, unknown project, missing/invalid role, populated allowed mailboxes, populated Odoo IDs, and 9-role enumeration. |
| Empty n8n workflows | All four `n8n/*.json` files contain real node definitions. |
| n8n unauthenticated webhooks | All four workflows declare `authentication=headerAuth`. |
| Plaintext service-account credentials in webhook body | ownCloud and Odoo workflows read credentials from `$env.*`. |
| Qdrant naming mismatch between init and runtime | Init script delegates to `EvidenceStore._collection_name`. |
| Odoo domain f-string injection vector | Node 08 builds the domain via `json.dumps`. |
| Quality gate accepted `needs_review` for export | Node 14 requires `quality_gate == "passed"` and a populated `report_json`. |
| PyJWT and cryptography CVEs | Upgraded to PyJWT 2.10.1 and cryptography 44.0.0. |

### Remaining

| Blocker | Blocks | Evidence |
|---|---|---|
| Missing MinIO bucket initialization | Phase 1F | `MINIO_BUCKET=decision-center` is configured but no init script or startup hook exists. |
| Stubbed evaluation runner | Phase 1H polish | `apps/edr/evaluation/run.py` prints a stubbed message; runner has no behaviour. |

---

## Safe Next Phase

Phase 1E may start.

Allowed Phase 1E work is limited to:

- Node 02/03/04: Haiku 4.5 calls for intent classification, scope extraction, retrieval planning.
- Node 11: self-correct loop (max 3 iterations) — re-query targeted sources on gaps.
- Node 12: Sonnet 4.6 structured JSON output bound to `evidence_id`s.
- Node 13: deterministic claim checker over the evidence pack.
- Node 14: end-to-end export verified against the canonical JSON.
- Wire Langfuse tracing to every LLM call.

## Forbidden Work In Phase 1E

Do not add MinIO persistence, audit writes, approval/reject APIs, publish logic,
frontend/UI work, or unrelated product behavior. Do not commit secrets into
workflows, docs, code, logs, or tests.

---

## README And Truth Doc Freshness

This audit refreshed `CURRENT_PROJECT_STATE.md`, `IMPLEMENTATION_PHASES.md`,
`FEATURE_MATRIX.md`, `CONTROL_PLANE_LOCK.md`, and `README.md` to reflect the
live repo state after Phase 1D and the Phase 1D-fixup.

---

## Readiness Ratings

| Rating | Score | Reason |
|---|---:|---|
| Architecture quality | 8/10 | Clear phase plan, fixed 18-node graph, separated docs/contracts/policies, explicit service boundaries. |
| Code foundation | 8/10 | Pinned dependencies (CVE-current), CI with config coverage + integration tests + drift detector, async runtime, retrieval pipeline working. |
| Pre-1E readiness | 9/10 | Retrieval pipeline complete; n8n workflows authenticated; secrets out of webhook bodies; mailbox allowlist enforced twice. |
| Product readiness | 3/10 | Real retrieval lands, but no LLM analysis, no persistence, no approval, and no UI. |
| Overall maturity | 5/10 | Strong controlled foundation; first half of functional implementation done; second half ahead. |
