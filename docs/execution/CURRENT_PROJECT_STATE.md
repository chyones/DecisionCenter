# DecisionCenter — Current Project State

> **Audited HEAD:** `d2353a937ab16b5c578cf8f803ccbdccc6cd3a43`
> **Audit date:** 2026-05-31 (Phase 2D Slice 6 governance truth reconciliation, Track B)
> **Audit scope:** Phases 0, 1A, 1B, 1B.5, 1C, 1D, 1D-fixup, 1E, 1F, 1G, 1H,
> 1I, Phase 2A, Phase 2B, Phase 2C closeout, **and Phase 2D Slices 1–6
> (`IMPLEMENTED_NOT_LIVE`)** — verified against live repo files and the
> required governance validation commands. Phase 2C audit baseline (`c3ab71d`,
> 2026-05-24) is preserved in the per-phase rows below; this header reflects
> the current Phase 2D-in-progress state at HEAD `d2353a9`.

---

## Current Project Stage

DecisionCenter has completed Phase 2C (UI Hardening & Acceptance Validation)
and is not live. Phase 2A's user workspace validation gate passed locally on
2026-05-14. Phase 2B's admin control-plane QA matrix and cross-screen
invariants are recorded in `docs/execution/PHASE_2B_REPORT.md`. Phase 2C's
closeout is recorded in `docs/execution/PHASE_2C_REPORT.md`: 54/54 Playwright
tests passed across Chromium, Firefox, and WebKit, with bundle budgets passing
at 91.33 kB JS gzip / 120 kB budget and 6.06 kB CSS gzip / 15 kB budget.

All prior phases including the Phase 1D-fixup remain closed and locked. The
backend execution pipeline runs end-to-end with evaluation coverage:
authentication and RBAC at Node 01; n8n connectors with Header Auth and
`$env`-sourced credentials; Voyage embeddings, Cohere reranking, tiktoken
chunking, per-project Qdrant collections, and a Redis-backed evidence cache;
LLM nodes with prompt-injection protection, per-tier token caps, and a daily
cost cap; deterministic claim checking; export gating; MinIO + PostgreSQL
persistence; human review; write-once publish; and a 64-case executable golden
set with pass-rate and precision thresholds enforced in CI.

The frontend contains the Phase 2A workspace implementation, the Phase 2B
admin visual control plane, and Phase 2C automated acceptance coverage. Query
Composer, Reports List, Processing View, Report View, Evidence Panel, Export
Panel, and Upload Zone consume live backend APIs. The admin area has seven
backend-integrated screens: Dashboard, System Health, Connectors, Permissions,
Source Mapping, Audit Log, and Approval Queue. Admin endpoints remain locked
to system metadata: no report content, query text, evidence excerpts, or
credential values are exposed.

Production is `NOT_LIVE`. Phase 2D is **in progress**: Slices 1–6 have been
explicitly approved and implemented (each `IMPLEMENTED_NOT_LIVE`); CI at HEAD
`d2353a9` is green (run `26397522011`). Slice 6 (Real UAT Flow) readiness is
in place, but the live UAT run has not produced evidence yet —
`docs/evidence/uat/` holds only `README.md` (no `UAT_RUN_<YYYY-MM-DD>.md`) —
so Slice 6 stays `IMPLEMENTED_NOT_LIVE` and does **not** advance to
`COMPLETE_NOT_LIVE`. Current verdict:
`PHASE_2D_SLICE_6_LIVE_UAT_PENDING_NOT_LIVE`. Slice 7 (Go-Live Gate) has not
started and is **blocked** until that evidence exists and a separate explicit
user approval is given in the active session. A push to `origin/main` is not a
deployment.

The 2026-05-24 read-only audit verdict is
`NOT_GO_LIVE_READY_BUT_HEALTHY` with overall rating **7/10**. Five of the
original five Phase-2C-era go-live blockers have been **implemented** by
Phase 2D Slices 1–5 (production frontend delivery path; production
Entra/MSAL frontend auth; live integrations; backup/restore; production
hardening) but remain `NOT_LIVE` until the operator live UAT (Slice 6) and a
go-live approval (Slice 7) close them. Remaining open blockers are: **real
UAT flow not proven** (Slice 6 live UAT evidence missing) and **go-live
approval not completed** (Slice 7).

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
| Phase 1F — Persistence and Audit | Complete | `apps/edr/persistence/postgres_store.py` defines `audit_log` and `review_decisions` schemas idempotently; `apps/edr/persistence/minio_store.py` lazily ensures the bucket via `_ensure_bucket()` and exposes `put_json`, `put_bytes`, `get_object`, `copy_to_final`. `scripts/init_minio.py` performs an explicit idempotent bucket create. Node 15 hashes user IDs and persists the four staging artifacts plus an audit row; persistence write failures now report degraded state with sanitized operation names. Download endpoint enforces RBAC + quality gate. Tests: `apps/edr/tests/integration/test_phase1f.py` (14 cases). |
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

## Phase 2B Slice Progress

| Slice | Status | Evidence |
|---|---|---|
| Phase 2B Slice 1 — Plan ratification and admin RBAC base | Complete | `docs/execution/PHASE_2B_PLAN.md` authored; `_require_admin` helper and `GET /admin/_authcheck` stub added to `apps/edr/app.py`; 13 RBAC integration cases in `apps/edr/tests/integration/test_phase2b_admin_rbac.py`. CI green. |
| Phase 2B Slice 2 — Connectors & APIs (read + probe) | Complete | `GET /admin/services`, `GET /admin/services/{name}`, `POST /admin/services/{name}/probe`; `apps/edr/admin/services_catalog.py`; `connector_events` table; 45 integration cases in `test_phase2b_connectors.py`; `AdminConnectorsScreen.tsx` frontend. CI green. |
| Phase 2B Slice 3 — System Health + cost monitor | Complete | `GET /admin/health/live`, `GET /admin/cost`; `cost_events` table + sparkline buckets; 28 integration cases in `test_phase2b_health_cost.py`; live `AdminHealthScreen.tsx` frontend with auto-refresh, cost banners, and warning/exceeded thresholds. CI green. |
| Phase 2B Slice 4 — Audit Log screen | Complete | `GET /admin/audit`, `GET /admin/audit/export.csv`, `GET /admin/audit/{event_id}`; `admin_events` table + UNION read-model; 18 integration cases in `test_phase2b_audit.py`; `AdminAuditLogScreen.tsx` frontend with filters, pagination, CSV export, and detail panel. CI green. |
| Phase 2B Slice 5 — Permissions & Roles | Complete | `GET /admin/entra-mappings`, `PUT /admin/entra-mappings/{group_id}`, `DELETE /admin/entra-mappings/{group_id}`; `entra_group_mappings` table + `_validate_canonical_role()`; A-17 audit-before-save on upsert and delete; 33 integration cases in `test_phase2b_permissions.py`; live three-tab `AdminPermissionsScreen.tsx` frontend (Role Matrix, Entra Group Mapping CRUD, Project Role Assignments placeholder). CI green. |
| Phase 2B Slice 6 — Project Source Mapping | Complete | `GET /admin/source-mappings`, `GET /admin/source-mappings/{code}`, `POST /admin/source-mappings/{code}/validate`, `PUT /admin/source-mappings/{code}`, `POST /admin/source-mappings/{code}/disable`; `source_mappings` table + JSON seeding + `_compute_mapping_status()`; A-21 audit-before-save; A-20 guard in `stage_report()`; 53 integration cases in `test_phase2b_source_mapping.py`; live two-column `AdminSourceMappingScreen.tsx` frontend with diff preview and risky-change confirmation. CI green. |
| Phase 2B Slice 7 — Approval Queue + admin override | Complete | `GET /admin/approvals`, `GET /admin/approvals/{request_id}`, `POST /admin/approvals/{request_id}/override-approve`, `POST /admin/approvals/{request_id}/override-reject`; `list_approval_queue()` queries existing `audit_log` for `staging`/`needs_review` rows; A-10 self-approval block; N-1 audit-before-action; R13 failed-QG → 409; 49 integration cases in `test_phase2b_approvals.py` (RBAC ×4, 401, list, filter, detail, 404, 409, approve happy path, N-1 order, self-block 403, reject happy path, reject self-block, mandatory comment, C-1, C-6); live `AdminApprovalQueueScreen.tsx` frontend with filter bar, pagination, detail panel, QG flags, and admin override actions with mandatory comment. CI green. |
| Phase 2B Slice 8 — Dashboard | Complete | `GET /admin/dashboard/summary`; `dashboard_counts_today()` in PostgresStore; service health probes, approval queue count, cost data, today counts, recent events; 16 integration cases in `test_phase2b_dashboard.py` (RBAC ×8, 401, happy path, services all ok, degraded service, today counts, recent events, C-1, C-6); live `AdminDashboardScreen.tsx` with 6-card stat grid, external services grid, recent events table, and role-based default landing at `/admin/dashboard`; `/admin` redirects to `/admin/dashboard`. CI green. |
| Phase 2B Slice 9 — Routing + Admin Nav | Complete | Sidebar.tsx: Dashboard path fixed to `/admin/dashboard` (active-state highlight works); Audit Log and Approvals entries added. Topbar.tsx: breadcrumb labels added for `/admin/dashboard`, `/admin/connectors`, `/admin/audit`, `/admin/approvals`. Frontend-only slice; no backend changes; no test changes. CI green. |
| Phase 2B Slice 10 — Closeout + Truth Reconciliation | Complete | `docs/execution/PHASE_2B_REPORT.md` authored with A-01..A-23 QA matrix, cross-screen invariants table, audit event catalog, and validation evidence. Governance docs refreshed. No code changes. CI green. |

---

## Phase 2C Progress

| Phase | Evidence |
|---|---|
| Phase 2C — UI Hardening & Acceptance Validation | Complete. All four slices are closed; `docs/execution/PHASE_2C_REPORT.md` records 54/54 Playwright tests across Chromium, Firefox, and WebKit plus passing bundle, accessibility, responsive, security-DOM, performance, and golden-path coverage. |

---

## Phase 2D Progress

Phase 2D is in progress. Each slice was explicitly approved before
implementation. Production remains `NOT_LIVE`.

| Phase / Slice | Status | Evidence |
|---|---|---|
| Phase 2D Slice 1 — Production frontend delivery path | `IMPLEMENTED_NOT_LIVE` | Caddy SPA + reverse proxy; commit `1edecaa`; CI green. |
| Phase 2D Slice 2 — Production Entra/MSAL auth + `GET /me` | `IMPLEMENTED_NOT_LIVE` | MSAL login, `Authorization: Bearer` API calls, canonical-role `GET /me`, production rejection of `x-user-role`/`x-user-id` bypass headers; local dev and CI retain the RoleSwitcher bypass; real Entra login is operator-verified (no live tenant in CI). See `docs/execution/PHASE_2D_SLICE_2_REPORT.md`. |
| Phase 2D Slice 3 — Live integration validation | `IMPLEMENTED_NOT_LIVE` | Live integration probes (infra + webhook failure-mode) green; `live_probe` marker excluded from CI integration run. See `docs/execution/PHASE_2D_SLICE_3_REPORT.md`. |
| Phase 2D Slice 4 — Backup and restore | `IMPLEMENTED_NOT_LIVE` | PostgreSQL + MinIO backup/restore scripts, operator runbook, DR policy, rehearsal evidence. See `docs/execution/PHASE_2D_SLICE_4_REPORT.md`. |
| Phase 2D Slice 5 — Production hardening | `IMPLEMENTED_NOT_LIVE` | Hardening checklist, secrets policy, automated `check_hardening.py`, and operator-run SSH/firewall evidence. See `docs/execution/PHASE_2D_SLICE_5_REPORT.md`. |
| Phase 2D Slice 6 — Real UAT flow readiness | `IMPLEMENTED_NOT_LIVE` — live-UAT evidence **MISSING** | Operator UAT runbook (`docs/operations/uat_runbook.md`), CI-safe readiness checker (`scripts/uat_check.py` — 6/6 PASS), real-backend no-mock driver (`scripts/uat_flow.py`), integration test (`apps/edr/tests/integration/test_phase2d_slice6_uat.py`), evidence path (`docs/evidence/uat/README.md`). The dated `docs/evidence/uat/UAT_RUN_<YYYY-MM-DD>.md` does not exist. Verdict: `PHASE_2D_SLICE_6_LIVE_UAT_PENDING`. See `docs/execution/PHASE_2D_SLICE_6_REPORT.md`. |
| Phase 2D Slice 7 — Go-Live Gate | **Not started — BLOCKED** | Requires Slice 6 live-UAT evidence and a separate explicit user approval. `requires_explicit_user_approval_for_phase_2d = true`. |

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

### Implemented by Phase 2D Slices 1–5 (NOT_LIVE — close at go-live)

| Original Phase-2C-era blocker | Phase 2D resolution | Status |
|---|---|---|
| Production frontend delivery path missing | Slice 1 — Caddy SPA + reverse proxy | `IMPLEMENTED_NOT_LIVE` |
| Production Entra/MSAL frontend auth missing | Slice 2 — MSAL + `GET /me`; prod rejects dev bypass | `IMPLEMENTED_NOT_LIVE` |
| Live integrations not proven | Slice 3 — Live integration probes + documented operator workflow | `IMPLEMENTED_NOT_LIVE` |
| Backup/restore evidence missing | Slice 4 — Backup/restore scripts, runbook, DR policy, rehearsal evidence | `IMPLEMENTED_NOT_LIVE` |
| Production hardening evidence missing | Slice 5 — Checklist, secrets policy, `check_hardening.py`, operator evidence | `IMPLEMENTED_NOT_LIVE` |

### Remaining

| Blocker | Blocks | Evidence |
|---|---|---|
| Pip-audit advisories | Promotion of `pip-audit` to a hard CI gate | `pip-audit --progress-spinner off` reports 19 advisories on 9 packages; CI keeps `continue-on-error: true`. Triage list captured in `docs/admin/CONTROL_PLANE_LOCK.md`. |
| Real UAT flow not proven (Slice 6 live-UAT evidence) | Slice 6 closeout + Slice 7 start + go-live | Slice 6 readiness is `IMPLEMENTED_CI_GREEN` (run `26397522011` at HEAD `d2353a9`); `docs/evidence/uat/UAT_RUN_<YYYY-MM-DD>.md` does not exist; `scripts/uat_flow.py` correctly SKIPs without a target. Requires an authorized operator on the target environment. |
| Go-live approval not completed (Slice 7) | Production cutover | Slice 7 has not started; `requires_explicit_user_approval_for_phase_2d = true`; depends on Slice 6 evidence. |

---

## Current Active Phase

Phase 2D is the active implementation phase. Slices 1–6 are committed
(`IMPLEMENTED_NOT_LIVE`); CI is green at HEAD `d2353a9` (run `26397522011`).
**No coding work is currently authorized.** The next required action is an
operator live UAT on the target environment (Slice 6 evidence capture); this
is an out-of-band human-operator action, not an AI task. Slice 7 (Go-Live
Gate) is not started and is blocked until Slice 6 evidence exists and a
separate explicit user approval is given.
`docs/ai/agent-state.json.requires_explicit_user_approval_for_phase_2d` is
`true`. Production remains `NOT_LIVE`.

## Standing Forbidden Work

Do not deploy. Do not change `production_status` from `NOT_LIVE`. Do not start
Phase 2D Slice 7 without explicit current-session user approval. Do not
fabricate UAT evidence; do not create `docs/evidence/uat/UAT_RUN_*.md` without
a real target and real tokens. Do not weaken `_require_admin` or any RBAC
check. Do not change the locked spec unless an explicit spec-change ticket is
approved. Do not commit secrets in workflows, docs, code, logs, or tests.

---

## README And Truth Doc Freshness

The Phase 2C audit reconciliation refreshed `CURRENT_PROJECT_STATE.md`,
`IMPLEMENTATION_PHASES.md`, `FEATURE_MATRIX.md`, `CONTROL_PLANE_LOCK.md`,
`README.md`, the AI context (`SHARED_CONTEXT.md`, `AGENT_HANDOFF.md`,
`agent-state.json`), and the drift/context checks to reflect Phase 2C
completion, production `NOT_LIVE`, and Phase 2D as approval-gated.

The 2026-05-31 Phase 2D Slice 6 governance truth reconciliation (Track B)
refreshed `agent-state.json.current_commit` to HEAD `d2353a9` and
`latest_verified_ci` to run `26397522011`, and reconciled the stale Phase 2D
narratives in `IMPLEMENTATION_PHASES.md`, `FEATURE_MATRIX.md`, and this file
so they record Slices 1–6 as `IMPLEMENTED_NOT_LIVE` and Slice 7 as blocked.
No code changed; production remains `NOT_LIVE`; Slice 6 was **not** marked
complete and no UAT evidence was fabricated.

---

## Readiness Ratings

| Rating | Score | Reason |
|---|---:|---|
| Architecture quality | 8/10 | Clear phase plan, fixed 18-node graph, separated docs/contracts/policies, explicit service boundaries. |
| Code foundation | 8/10 | Pinned dependencies, CI with config coverage + doc/AI checks (incl. anchor-currency invariant) + integration tests + drift detector, async runtime, retrieval pipeline + LLM + persistence + review gate working. |
| Phase 2A readiness | 10/10 | Phase 2A implementation, local E2E, and U-01 through U-16 manual QA are complete. |
| Phase 2B readiness | 10/10 | Phase 2B admin control plane implementation, A-01 through A-23 manual QA, and CI evidence are complete. |
| Product readiness | 7/10 | Pipeline produces structured, evidence-bound reports with human approval; Phase 2C acceptance coverage is complete. Production remains `NOT_LIVE` because go-live blockers remain. |
| Overall maturity | 7/10 | Healthy controlled foundation with Phase 2C complete, but go-live readiness is blocked by missing production frontend delivery, production Entra/MSAL auth, live integration proof, backup/restore evidence, and production hardening evidence. Final audit recommendation: `NOT_GO_LIVE_READY_BUT_HEALTHY`. |

## Spec Changes

- **2026-05-31 — Owner-operator governance model** (`docs/execution/SPEC_CHANGE_2026-05-31_owner_operator_model.md`; owner-approved; `IMPLEMENTED_NOT_LIVE` on branch `feat/owner-operator-model`): the `admin` role is elevated to a full owner (business powers + system settings), report visibility is shared across owner roles, and self-approval is allowed (two-person rule removed). The automated quality/claim gate, audit logging, and the project-scoped email allowlist remain in force. Production remains `NOT_LIVE`; Slice 6 UAT and Slice 7 go-live approval are unaffected and still required.


## Connector Status Truth (added 2026-06-01)

The dashboard and Connectors screen now report **honest connector states** and
never claim an unconfigured or unproven integration is working. Source of truth:
`apps/edr/admin/connector_status.py`; admin endpoint `GET /admin/connectors/truth`.

Truth states: `NOT_CONFIGURED`, `CONFIGURED_NOT_TESTED`, `AUTH_FAILED`,
`PERMISSION_FAILED`, `NETWORK_FAILED`, `CONNECTED_NO_DATA`, `LIVE_OK`,
`MOCK_ONLY`, `DISABLED`, `UNKNOWN`. A connector is shown green only on a real
`LIVE_OK` probe — container-up, route-exists and fixture-exists are not evidence.
Fixture/mock data is capped at `MOCK_ONLY` and can never be `LIVE_OK`.

Real current connector states (config-derived; live probes execute in-container):

- Core platform (PostgreSQL, Redis, Qdrant, MinIO): live-probed — reachability is
  the liveness proof → `LIVE_OK` when reachable.
- Public edge (Cloudflare Tunnel + Caddy): live-probed via HTTPS `/healthz`.
- Microsoft Entra authentication: `CONFIGURED_NOT_TESTED` — no server-side token
  validation exists, so login is not asserted green here.
- n8n, SharePoint, email / mailbox, ownCloud, Odoo: `NOT_CONFIGURED` — required
  webhook token / connector credentials are absent (Odoo lacks
  `ODOO_URL`/`ODOO_DATABASE`/`ODOO_USERNAME`/`ODOO_API_KEY`; ownCloud lacks its
  username/password). They are never shown green from n8n reachability.
- AI providers (Anthropic, Voyage, Cohere): `NOT_CONFIGURED` → report generation
  is `BLOCKED` until the provider keys are set.

Readiness banner: `READY_FOR_UAT` only when every required dependency is
`LIVE_OK`; `PARTIAL_READY` when core/edge/login are up but connectors/providers
are pending; `NOT_READY` otherwise. Production remains NOT_LIVE; this change did
not alter that. The legacy `_probe_with_latency` no longer maps workflow
connectors to n8n reachability (that was false green) — they report `unknown`
there and their authoritative status is the truth endpoint.
