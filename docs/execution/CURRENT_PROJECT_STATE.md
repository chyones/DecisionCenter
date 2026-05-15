# DecisionCenter — Current Project State

> **Audited HEAD:** `0a19bae` (Phase 2A E2E unblock base, before manual QA closeout commit).
> **Audit date:** 2026-05-14 (updated for Phase 2A manual QA closeout)
> **Audit scope:** Phases 0, 1A, 1B, 1B.5, 1C, 1D, 1D-fixup, 1E, 1F, 1G, 1H,
> 1I, and Phase 2A — verified against live repo files and local validation
> evidence captured during the Phase 2A manual QA closeout.

---

## Current Project Stage

DecisionCenter has completed Phase 2A (User Chat Workspace Implementation) and
is not live. The Phase 2A validation gate (end-to-end submit -> processing ->
quality_gate passed -> approve -> final -> download MD, plus U-01..U-16 manual
QA per `docs/design/UI_CONTRACT_v1.md` §9.1) passed locally on 2026-05-14. All
prior phases including the Phase 1D-fixup remain closed and locked. The backend
execution pipeline
runs end-to-end with evaluation coverage: authentication and RBAC at Node 01;
n8n connectors with Header Auth and `$env`-sourced credentials; Voyage
embeddings, Cohere reranking, tiktoken chunking, per-project Qdrant
collections, and a Redis-backed evidence cache; LLM nodes 02/03/04/11/12
(Haiku for Light, Sonnet for Heavy) with prompt-injection protection,
per-tier token caps, and a daily cost cap; deterministic claim checking at
Node 13; export gating at Node 14; MinIO + PostgreSQL persistence at Node 15
with hashed user IDs and staging artifacts; human review at Node 16;
write-once publish to immutable final artifacts at Node 17; and a 64-case
executable golden set with pass-rate and precision thresholds enforced in CI.

The frontend now contains the full Phase 2A workspace implementation. Query
Composer submits to live `POST /reports/staging` and loads role-scoped project
context from `GET /workspace/context`. Reports List consumes `GET /reports`.
Processing View consumes `GET /reports/{id}/status` and `DELETE /reports/{id}`.
Report View and Evidence Panel consume `GET /reports/{id}/content`; failed
quality gates suppress exports, needs-review requesters see flags only,
authorized reviewers see a watermarked draft, citations highlight evidence, and
final reports show immutable locked state. Upload Zone validates locally and
the server-side `POST /upload` endpoint enforces the same size/type rules.

Production is `NOT_LIVE`. Phase 2B is the safe next phase, but it may only
start after explicit user authorization. A push to `origin/main` is not a
deployment.

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
| Phase 1E — LLM Nodes | Complete | `apps/edr/llm.py` adds prompt-injection regex (11 patterns), per-tier token caps, and daily cost tracking. Nodes 02/03/04 run Haiku 4.5; node 11 implements the self-correct loop (max 3 iterations); node 12 runs Sonnet 4.6 with evidence-bound JSON; node 13 is the deterministic claim checker; node 14 only exports when `quality_gate == "passed"` and `report_json` is non-empty. Tests: `apps/edr/tests/integration/test_phase1e.py` (22 cases). |
| Phase 1F — Persistence and Audit | Complete | `apps/edr/persistence/postgres_store.py` defines `audit_log` and `review_decisions` schemas idempotently; `apps/edr/persistence/minio_store.py` lazily ensures the bucket via `_ensure_bucket()` and exposes `put_json`, `put_bytes`, `get_object`, `copy_to_final`. `scripts/init_minio.py` performs an explicit idempotent bucket create. Node 15 hashes user IDs and persists the four staging artifacts plus an audit row. Download endpoint enforces RBAC + quality gate. Tests: `apps/edr/tests/integration/test_phase1f.py` (12 cases). |
| Phase 1G — Human Review Gate | Complete | `POST /reports/staging/{request_id}/{approve,reject,request-revision}` enforce reviewer RBAC via `_check_reviewer_rbac` (auditor blocked, admin override is metadata-only with mandatory comment), self-approval blocking by hashed reviewer ID, and 409 on already-finalized reports. Node 16 reads `review_state` from PostgreSQL. Node 17 publishes only when `review_state == "approved"`, copies staging→final via write-once `MinioStore.copy_to_final` (raises `FileExistsError`), writes `approval-log.json` exactly once, and updates `review_state` to `final`. `GET /reports/final/{request_id}/download/{fmt}` only serves once finalized; quality-gate `failed` blocks all download paths. Tests: `apps/edr/tests/integration/test_phase1g.py` (22 cases). |
| Phase 1H — Evaluation and Hardening | Complete | Real evaluation runner (`apps/edr/evaluation/run.py`) with JSONL loader, per-case metrics, aggregate report, and non-zero exit on regression. 64 executable golden-set cases are currently exercised. Arabic PDF hardening with bundled Amiri font and RTL limitation disclaimer. Local-only load test with deterministic fallback. pip-audit triage completed: safe pins upgraded (`cryptography` 44.0.1, `python-dotenv` 1.2.2, `PyJWT` 2.12.0); remaining 19 advisories on 9 packages accepted as deferred. CI integration: `make eval` runs with `--min-pass-rate 0.95 --min-precision 0.90`. `N8N_TIMEOUT` setting prevents connector hangs in CI. Tests: `test_evaluation.py` (15), `test_load_test.py` (5), `test_pdf_arabic.py` (7). |
| Phase 1I — Frontend Foundation & Static Admin Scaffolds | Complete | Vite + React + TypeScript + Tailwind project in `frontend/`; design tokens (colors, typography, spacing, status pills); layout shell (Topbar, Sidebar, Main Content, Detail Panel); reusable components (StatusPill, Button, Modal, Toast, ConfirmDialog, SlideInPanel); role-guarded hash-based routing with 9 canonical roles; static scaffolds: Admin System Health, Permissions & Roles (Role Matrix tab), Source Mapping (read-only), Query Composer shell. Frontend lint and build wired into CI. |

## Active Phase Progress

| Phase / Slice | Status | Evidence |
|---|---|---|
| Phase 2A Slice 1 — API client foundation and auth wiring | Complete | `frontend/src/api/client.ts`, `frontend/src/api/types.ts`, `frontend/src/api/useApi.ts`, and `frontend/src/api/index.ts`; fetch is contained in the approved API client. Commit `840e954`; CI green. |
| Phase 2A Slice 2 — Query Composer submit | Complete | `frontend/src/screens/QueryComposerScreen.tsx` submits to `POST /reports/staging`; final closeout wiring loads project context from `GET /workspace/context`. |
| Phase 2A Slice 3 — Reports List read-only listing | Complete | `frontend/src/screens/ReportsListScreen.tsx` renders grouped read-only unavailable states because `GET /reports` is absent. Commit `89a4e49`; CI green. |
| Phase 2A Slice 4 — Processing View status shell | Complete | `frontend/src/screens/ProcessingScreen.tsx` renders the 18-node progress shell and disabled cancel action because `GET /reports/{id}/status` and `DELETE /reports/{id}` are absent. Commit `5674581`; CI green. |
| Phase 2A Slice 5 — Report View and Evidence Panel | Complete | `frontend/src/screens/ReportViewScreen.tsx` and `frontend/src/screens/EvidencePanel.tsx`; final closeout wiring consumes `GET /reports/{id}/content`. |
| Phase 2A Slice 6 — Export Panel | Complete | `frontend/src/screens/ExportPanel.tsx`; slide-in panel wired to the existing `GET /reports/{staging,final}/{id}/download/{fmt}` endpoints; report-state and quality-gate gating implemented per `docs/design/UI_CONTRACT_v1.md` §2.4; artifact rows disabled because no artifact-fetch endpoint exists. Commit `96ec4b9`; CI run `25795083507` success. |
| Phase 2A Slice 7 — Upload Zone | Complete | `frontend/src/screens/UploadZone.tsx`; drag-and-drop, file picker, per-file (10 MB) and total-size (30 MB) limits, count limit (5), preview list with remove action; backend `POST /upload` enforces matching server rules. |
| Phase 2A Slice 8 — Routing integration and role guards | Complete | `frontend/src/layout/Sidebar.tsx`, `Topbar.tsx`, `frontend/src/routing/guards.ts` updated for the new workspace screens. Commit `a5aedfc`; CI run `25798446018` success. |
| Phase 2A Slice 9 — Error handling and polish | Complete | `frontend/src/components/ToastProvider.tsx`; unified error surfaces and retry paths across `QueryComposerScreen`, `ReportsListScreen`, `ProcessingScreen`, `ReportViewScreen`, `EvidencePanel`, `ExportPanel`, and `UploadZone`. Commit `e37b0c1`; CI run `25799899473` success. |
| Phase 2A backend additions — read/status/cancel/upload endpoints | Complete | `apps/edr/app.py` includes `GET /reports`, `GET /reports/{id}`, `GET /reports/{id}/status`, `DELETE /reports/{id}`, `POST /upload`, plus `GET /workspace/context` and `GET /reports/{id}/content` with server-enforced RBAC. `test_phase2a_backend.py` covers the QA contracts. Closes gap G12. |
| Phase 2A E2E unblock harness | Complete | `make phase2a-e2e` drives submit -> processing -> quality_gate passed -> approve -> final -> download MD using deterministic local fixture evidence through the existing quality gate. |
| Phase 2A manual QA closeout | Complete | U-01 through U-16 passed. `make phase2a-e2e`, `make smoke`, `make test`, `make eval`, ruff, compileall, frontend lint/build, doc drift, AI context, and postflight form the closeout gate. |

---

## Active Phase 2B Progress

| Slice | Status | Evidence |
|---|---|---|
| Phase 2B Slice 1 — Plan ratification and admin RBAC base | Complete | `docs/execution/PHASE_2B_PLAN.md` authored; `_require_admin` helper and `GET /admin/_authcheck` stub added to `apps/edr/app.py`; 13 RBAC integration cases in `apps/edr/tests/integration/test_phase2b_admin_rbac.py`. CI green. |
| Phase 2B Slice 2 — Connectors & APIs (read + probe) | Complete | `GET /admin/services`, `GET /admin/services/{name}`, `POST /admin/services/{name}/probe`; `apps/edr/admin/services_catalog.py`; `connector_events` table; 45 integration cases in `test_phase2b_connectors.py`; `AdminConnectorsScreen.tsx` frontend. CI green. |
| Phase 2B Slice 3 — System Health + cost monitor | Complete | `GET /admin/health/live`, `GET /admin/cost`; `cost_events` table + sparkline buckets; 28 integration cases in `test_phase2b_health_cost.py`; live `AdminHealthScreen.tsx` frontend with auto-refresh, cost banners, and warning/exceeded thresholds. CI green. |

---

## Not-Started Functional Phases

| Phase | Evidence |
|---|---|
| Phase 2B, 2C — later UI phases | Admin control-plane live integration and UI hardening/acceptance are not started. Phase 2B requires explicit user authorization. |

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
| Governance anchor drift after Phase 2A Slices 6–9 | Slice 9 closeout (this audit) re-anchored governance at HEAD `e37b0c1`; extended `scripts/check_ai_context.py` to recognize Slice 6–9 statuses and added an anchor-currency invariant to `scripts/check_doc_drift.py`. |
| Phase 2A backend read/status/cancel/upload endpoint gap (G12) | Closed in Phase 2A backend additions and final QA blocker fixes: workspace context, report listing/status/content, cancel, upload, and server-side RBAC are implemented and covered by integration tests. |

### Remaining

| Blocker | Blocks | Evidence |
|---|---|---|
| Pip-audit advisories | Promotion of `pip-audit` to a hard CI gate | `pip-audit --progress-spinner off` reports 19 advisories on 9 packages; CI keeps `continue-on-error: true`. Triage list captured in `docs/admin/CONTROL_PLANE_LOCK.md`. |

---

## Safe Next Phase

Phase 2B Slice 4 (Audit Log screen) is the safe next work item, but it
requires explicit per-slice user authorization before any implementation starts.

Allowed next work is limited to explicitly authorized Phase 2B slices or later
maintenance requested by the user. Do not start Slice 4 by inference.

## Standing Forbidden Work

Do not deploy. Do not change the locked spec unless an explicit spec-change
ticket is approved. Do not commit secrets in workflows, docs, code, logs, or
tests. Do not start Phase 2B Slice 4 without explicit per-slice user authorization.

---

## README And Truth Doc Freshness

This audit refreshed `CURRENT_PROJECT_STATE.md`, `IMPLEMENTATION_PHASES.md`,
`FEATURE_MATRIX.md`, `CONTROL_PLANE_LOCK.md`, `README.md`, the AI context
(`SHARED_CONTEXT.md`, `AGENT_HANDOFF.md`, `agent-state.json`), the locked
workflow spec's internal draft-artifact note, and
`scripts/check_doc_drift.py` to reflect Phase 2A completion.

---

## Readiness Ratings

| Rating | Score | Reason |
|---|---:|---|
| Architecture quality | 8/10 | Clear phase plan, fixed 18-node graph, separated docs/contracts/policies, explicit service boundaries. |
| Code foundation | 8/10 | Pinned dependencies, CI with config coverage + doc/AI checks (incl. anchor-currency invariant) + integration tests + drift detector, async runtime, retrieval pipeline + LLM + persistence + review gate working. |
| Phase 2A readiness | 10/10 | Phase 2A implementation, local E2E, and U-01 through U-16 manual QA are complete. |
| Product readiness | 8/10 | Pipeline produces structured, evidence-bound reports with human approval; 64-case golden set and Arabic PDF hardening validate the core path. Production remains `NOT_LIVE`. |
| Overall maturity | 8/10 | Strong controlled foundation; functional backend implementation through review/publish; Phase 2A workspace complete; Phase 2B/admin UI and production readiness remain future work. |
