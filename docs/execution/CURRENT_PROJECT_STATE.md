# DecisionCenter — Current Project State

> **Audited HEAD:** `50d8f87` (verified Phase 1H closeout commit).
> **Audit date:** 2026-05-10
> **Audit scope:** Phases 0, 1A, 1B, 1B.5, 1C, 1D, 1D-fixup, 1E, 1F, 1G, 1H — verified against
> live repo files, CI evidence, and local test execution.

---

## Current Project Stage

DecisionCenter has completed Phase 1H (Evaluation & Hardening); all prior
phases including the Phase 1D-fixup remain closed and locked. The full
execution pipeline runs end-to-end with evaluation coverage: authentication and
RBAC at Node 01; n8n connectors with Header Auth and `$env`-sourced
credentials; Voyage embeddings, Cohere reranking, tiktoken chunking, per-project
Qdrant collections, and a Redis-backed evidence cache; LLM nodes 02/03/04/11/12
(Haiku for Light, Sonnet for Heavy) with prompt-injection protection, per-tier
token caps, and a daily cost cap; deterministic claim checking at Node 13;
export gating at Node 14; MinIO + PostgreSQL persistence at Node 15 with hashed
user IDs and the four artifacts; human review at Node 16; write-once publish to
immutable final artifacts at Node 17; and a 65-case executable golden set with
pass-rate and precision thresholds enforced in CI.

Production is `NOT_LIVE`. Phase 1I (Frontend Foundation) is the next safe
phase and requires explicit user approval before it starts.

---

## Completed Phases

| Phase | Status | Evidence |
|---|---|---|
| Phase 0 — Control and documentation lock | Complete | Locked spec, control-plane docs, policies, contracts, schemas, operations docs, and phase plan exist under `docs/`. |
| Phase 1A — Infrastructure Foundation | Complete | `.env.example` has 40 keys; `apps/edr/config.py` maps 40 settings; `.github/workflows/ci.yml` runs ruff, compileall, config coverage, doc-drift, AI-context, smoke tests, integration tests, and `pip-audit`; `pyproject.toml` uses pinned dependencies (PyJWT 2.10.1, cryptography 44.0.0); `docker-compose.yml` defines app, PostgreSQL, Redis, Qdrant, MinIO, n8n, Caddy with healthchecks; internal services bind only to localhost or the compose network; `scripts/init_qdrant.py` agrees with the runtime collection naming; `scripts/init_minio.py` creates the configured bucket idempotently. |
| Phase 1B — RBAC and Identity | Complete | `apps/edr/auth/validator.py` validates Entra JWTs with a cached `PyJWKClient` and surfaces all roles; `apps/edr/graph/node_01_auth.py` enforces canonical roles and known `project_code`; `apps/edr/rbac/roles.py` defines 9 roles; `apps/edr/rbac/project_mapping.py` loads `docs/config/project_source_mapping.json`; `apps/edr/tests/integration/test_rbac.py` covers authorized, denied, unknown project, invalid role, and all-role cases. |
| Phase 1B.5 — Async Connector Runtime Readiness | Complete | `apps/edr/graph/runner.py` is async and awaits each node; every `apps/edr/graph/node_00_begin.py` through `node_17_publish.py` exposes `async def run`; smoke and RBAC tests use `asyncio.run()`. |
| Phase 1C — n8n Connector Workflows | Complete | All four `n8n/*.json` workflows contain real 4–5 node pipelines, declare `authentication=headerAuth`, and read service-account credentials from `$env.*`. The email workflow gates on the mailbox allowlist before any Graph call. `apps/edr/connectors/validation.py` enforces `EvidenceObject` schema. `apps/edr/tests/integration/test_connectors.py` covers all four sources with mocked responses. |
| Phase 1D — Embedding & Vector Retrieval | Complete | `apps/edr/retrieval/embeddings.py` calls Voyage-3-large; `apps/edr/retrieval/rerank.py` calls Cohere Rerank 3.5; `apps/edr/retrieval/chunking.py` uses tiktoken (500–800 tokens, 100–150 overlap, char fallback); `apps/edr/retrieval/qdrant_store.py` manages per-project collections with `edr_*` naming; `apps/edr/retrieval/cache.py` is Redis-backed with in-memory fallback; reciprocal rank fusion in `hybrid_search.py`; nodes 05–08 run real connector calls and embed/insert results into Qdrant; node 09 dedups by `(source_uri, hash_sha256)` with priority preservation; node 10 runs the sufficiency check. |
| Phase 1D-Fixup — Audit closure | Complete | All audit findings (C-1..C-8, S-1, L-2, L-5, O-1..O-4) closed; see `docs/admin/CONTROL_PLANE_LOCK.md` for the table. Regression tests in `apps/edr/tests/integration/test_phase1d_fixes.py` and `apps/edr/tests/integration/test_phase1d_security.py` lock the invariants. |
| Phase 1E — LLM Nodes | Complete | `apps/edr/llm.py` adds prompt-injection regex (11 patterns), per-tier token caps, daily cost tracking, and Langfuse tracing hooks. Nodes 02/03/04 run Haiku 4.5; node 11 implements the self-correct loop (max 3 iterations); node 12 runs Sonnet 4.6 with evidence-bound JSON; node 13 is the deterministic claim checker; node 14 only exports when `quality_gate == "passed"` and `report_json` is non-empty. Tests: `apps/edr/tests/integration/test_phase1e.py` (22 cases). |
| Phase 1F — Persistence and Audit | Complete | `apps/edr/persistence/postgres_store.py` defines `audit_log` and `review_decisions` schemas idempotently; `apps/edr/persistence/minio_store.py` lazily ensures the bucket via `_ensure_bucket()` and exposes `put_json`, `put_bytes`, `get_object`, `copy_to_final`. `scripts/init_minio.py` performs an explicit idempotent bucket create. Node 15 hashes user IDs and persists the four staging artifacts plus an audit row. Download endpoint enforces RBAC + quality gate. Tests: `apps/edr/tests/integration/test_phase1f.py` (12 cases). |
| Phase 1G — Human Review Gate | Complete | `POST /reports/staging/{request_id}/{approve,reject,request-revision}` enforce reviewer RBAC via `_check_reviewer_rbac` (auditor blocked, admin override is metadata-only with mandatory comment), self-approval blocking by hashed reviewer ID, and 409 on already-finalized reports. Node 16 reads `review_state` from PostgreSQL. Node 17 publishes only when `review_state == "approved"`, copies staging→final via write-once `MinioStore.copy_to_final` (raises `FileExistsError`), writes `approval-log.json` exactly once, and updates `review_state` to `final`. `GET /reports/final/{request_id}/download/{fmt}` only serves once finalized; quality-gate `failed` blocks all download paths. Tests: `apps/edr/tests/integration/test_phase1g.py` (22 cases). |
| Phase 1H — Evaluation and Hardening | Complete | Real evaluation runner (`apps/edr/evaluation/run.py`) with JSONL loader, per-case metrics, aggregate report, and non-zero exit on regression. 65 executable golden-set cases covering all 12 baseline categories. Arabic PDF hardening with bundled Amiri font and RTL limitation disclaimer. Local-only load test with deterministic fallback. pip-audit triage completed: safe pins upgraded (`cryptography` 44.0.1, `python-dotenv` 1.2.2, `PyJWT` 2.12.0); remaining 19 advisories on 9 packages accepted as deferred. CI integration: `make eval` runs with `--min-pass-rate 0.95 --min-precision 0.90`. `N8N_TIMEOUT` setting prevents connector hangs in CI. Tests: `test_evaluation.py` (15), `test_load_test.py` (5), `test_pdf_arabic.py` (7). |

---

## Not-Started Functional Phases

| Phase | Evidence |
|---|---|
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
| PyJWT and cryptography CVEs (initial set) | Upgraded to PyJWT 2.10.1 and cryptography 44.0.0. Newer advisories on these and other pinned packages are tracked under Phase 1H triage. |
| Missing MinIO bucket initialization | `scripts/init_minio.py` performs an explicit idempotent create; runtime `_ensure_bucket()` covers any missed init. |

### Remaining

| Blocker | Blocks | Evidence |
|---|---|---|
| Pip-audit advisories | Promotion of `pip-audit` to a hard CI gate | `pip-audit --progress-spinner off` reports 19 advisories on 9 packages; CI keeps `continue-on-error: true`. Triage list captured in `docs/admin/CONTROL_PLANE_LOCK.md`. |

---

## Safe Next Phase

Phase 1I may start (requires explicit user approval).

Allowed Phase 1I work is limited to:

- Initialize frontend project (Vite + React + TypeScript + Tailwind) in `frontend/`.
- Implement design tokens, layout shell, and reusable components per `UI_CONTRACT_v1.md`.
- Build static scaffolds (no API wiring): Admin System Health, Permissions & Roles,
  Source Mapping, Query Composer shell.
- Add `frontend/` lint and build steps to CI.

## Forbidden Work In Phase 1I

Do not deploy. Do not wire API calls or data fetching. Do not render real report
content. Do not change the locked spec unless an explicit spec-change ticket is
approved. Do not commit secrets in workflows, docs, code, logs, or tests.

---

## README And Truth Doc Freshness

This audit refreshed `CURRENT_PROJECT_STATE.md`, `IMPLEMENTATION_PHASES.md`,
`FEATURE_MATRIX.md`, `CONTROL_PLANE_LOCK.md`, `README.md`, the runbook, the
connectors connection guide, the AI context, and `scripts/check_doc_drift.py`
to reflect the live repo state at HEAD `50d8f87`.

---

## Readiness Ratings

| Rating | Score | Reason |
|---|---:|---|
| Architecture quality | 8/10 | Clear phase plan, fixed 18-node graph, separated docs/contracts/policies, explicit service boundaries. |
| Code foundation | 8/10 | Pinned dependencies, CI with config coverage + doc/AI checks + integration tests + drift detector, async runtime, retrieval pipeline + LLM + persistence + review gate working. |
| Pre-1I readiness | 8/10 | End-to-end pipeline implemented and tested; 65-case golden set with CI enforcement; Arabic PDF hardened; 19 pip-audit advisories accepted as deferred; no frontend exists yet. |
| Product readiness | 7/10 | Pipeline produces structured, evidence-bound reports with human approval; golden-set coverage (65 cases) and Arabic PDF hardening validated in CI; frontend does not exist yet. |
| Overall maturity | 7/10 | Strong controlled foundation; functional implementation complete through review/publish; evaluation and hardening complete; frontend work remains.
