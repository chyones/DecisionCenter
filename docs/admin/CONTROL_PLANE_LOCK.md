> **⚠ SUPERSEDED FOR THE OWNER-OPERATOR DEPLOYMENT (2026-05-31).**
> The separation-of-duties controls described below — admin content-blindness,
> two-person approval, and own-report-only visibility — were intentionally
> relaxed per the owner-approved
> [`SPEC_CHANGE_2026-05-31_owner_operator_model`](../execution/SPEC_CHANGE_2026-05-31_owner_operator_model.md).
> Admin is now a full owner; owners share report visibility; self-approval is
> allowed. The automated quality gate, audit logging, and the project-scoped
> email allowlist remain in force. Production remains `NOT_LIVE`.

# DecisionCenter — Control Plane Lock

> **Date:** 2026-05-24 (updated after Phase 2C audit reconciliation)
> **Scope:** Documentation and control state only.
> **Behavioral source of truth:** `docs/workflows/EDR-AGENTIC-RAG-v2.1.md`
> **Execution sequence source of truth:** `docs/execution/IMPLEMENTATION_PHASES.md`
> **Live state:** `PHASE_2C_COMPLETE_NOT_LIVE` (production is `NOT_LIVE`; Phase 2D is approval-gated).

This document locks the control expectations for the project. It does not add
application features and does not define an Admin UI.

## Phase 0 Decisions

| Area | Authoritative Decision | Evidence |
|---|---|---|
| Environment baseline | `.env.example` has 43 keys (40 original + `LLM_PROVIDER`, `DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL` added 2026-06-12); planning docs that said 50 were stale | `.env.example` |
| Config coverage | `apps/edr/config.py` loads all 43 keys from `.env.example` | `apps/edr/config.py` |
| Phase sequence | Phase 1A is Infrastructure Foundation before product/node logic | `docs/execution/IMPLEMENTATION_PHASES.md` |
| RBAC model | Use the 9 canonical spec roles | `docs/security/rbac_matrix.md` |
| n8n status | Four workflow JSON files contain real 4–5 node pipelines and require n8n Header Auth | `n8n/*.json` |
| Service-account credentials | Read from n8n container env (`$env.OWNCLOUD_*`, `$env.ODOO_*`); never sent through the webhook body | `n8n/owncloud_list.json`, `n8n/odoo_read.json`, `docker-compose.yml` |
| Mailbox allowlist | Enforced twice: `apps/edr/graph/node_07_email.py` (Python) and the `Enforce Mailbox Allowlist` n8n code node | `apps/edr/graph/node_07_email.py`, `n8n/email_search.json` |
| Evaluation baseline | A 64-case executable golden set covers the required baseline categories from spec Section 26; `make eval` enforces pass rate ≥ 0.95 and precision ≥ 0.90 in CI | `apps/edr/evaluation/goldenset/goldenset.jsonl`, `apps/edr/evaluation/run.py`, spec Section 26 |
| Bucket initialization | `scripts/init_minio.py` creates the configured MinIO bucket idempotently; runtime `_ensure_bucket()` covers any missed init | `scripts/init_minio.py`, `apps/edr/persistence/minio_store.py` |
| Readiness | Phase 1A-1I + Phase 1D-fixup and Phases 2A-2C are complete and not live; Phase 2D is the next allowed phase and is blocked pending explicit user approval | This document |

## Authoritative Environment Baseline

The authoritative env baseline is the current `.env.example` file. It contains exactly
these 43 keys:

| Group | Keys |
|---|---|
| App | `APP_ENV`, `APP_HOST`, `APP_PORT`, `PUBLIC_BASE_URL`, `PUBLIC_HOSTNAME` |
| Identity | `ENTRA_CLIENT_ID`, `ENTRA_TENANT_ID`, `ENTRA_CLIENT_SECRET` |
| LLM providers | `LLM_PROVIDER`, `ANTHROPIC_API_KEY`, `DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL`, `VOYAGE_API_KEY`, `COHERE_API_KEY` |
| Data stores | `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`, `REDIS_URL`, `QDRANT_URL`, `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_BUCKET` |
| Connector layer | `N8N_BASE_URL`, `N8N_WEBHOOK_TOKEN`, `N8N_TIMEOUT`, `SHAREPOINT_SEARCH_WEBHOOK`, `OWNCLOUD_LIST_WEBHOOK`, `EMAIL_SEARCH_WEBHOOK`, `ODOO_READ_WEBHOOK` |
| ownCloud | `OWNCLOUD_USERNAME`, `OWNCLOUD_PASSWORD` |
| Odoo | `ODOO_URL`, `ODOO_DATABASE`, `ODOO_USERNAME`, `ODOO_API_KEY` |
| Observability and budget | `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`, `DAILY_COST_CAP_USD`, `MONTHLY_COST_TARGET_USD` |

`apps/edr/config.py` loads these 43 fields and CI asserts the count.

## Phase 1D-Fixup (Closed before Phase 1E)

The audit at commit `c9ed521` raised four critical-correctness items, four
security items, and several drift/hygiene items. All were closed before
Phase 1E started:

| ID | Issue | Resolution |
|---|---|---|
| C-1 | Qdrant collection name disagreed between `scripts/init_qdrant.py` (`dc_*`) and the runtime `EvidenceStore` (`edr_*`) | Init script now delegates to `EvidenceStore._collection_name`; tests assert agreement |
| C-2 | Odoo domain built via f-string allowed `project_code` injection through `JSON.parse` in n8n | `node_08_odoo.py` builds the domain via `json.dumps`; regression test covers hostile project codes |
| C-3 | n8n webhooks accepted unauthenticated POSTs | All four webhook nodes now require `authentication=headerAuth`; CI test asserts this |
| C-4 | Email node sent requests for any mailbox | Node 07 rejects mailboxes not in the allowlist before any external call; n8n `Enforce Mailbox Allowlist` node enforces a second time |
| C-6 / S-1 | Service-account credentials flowed through the webhook body | ownCloud and Odoo workflows read credentials from `$env.*`; Python wrappers no longer include them; tests assert no leakage |
| C-7 / I-6 | `PyJWT==2.7.0` and `cryptography==41.0.7` carried CVEs | Upgraded to `PyJWT==2.10.1` and `cryptography==44.0.0` (later re-pinned in Phase 1H — see triage below) |
| C-8 | Node 14 exported on `needs_review` because it only blocked `failed` | Now requires `quality_gate == "passed"` and a non-empty `report_json` |
| L-2 / R-4 | JWT validator only surfaced first role; no JWKS cache | Validator caches the `PyJWKClient` and exposes the full `roles` tuple |
| L-5 | `EvidenceObject.metadata` rejected n8n's `recipients` list | Schema now accepts scalars and lists of scalars |
| O-1 | Misleading `"status": "stubbed"` from `POST /reports/staging` | Status now derived from `quality_gate` + export state; request_id is a UUID |
| O-2 | Caddy bound only port 80 | Caddy serves a `PUBLIC_HOSTNAME` site with TLS, HSTS, and a `:80` fallback for local dev |
| O-3 | Compose published Qdrant/MinIO/n8n on the public interface | Internal services use `expose:`; public-facing ports bound to `127.0.0.1` |
| O-4 | Stale evaluation message claiming Phase 1G | Updated to Phase 1H |

## Phase 1E–1H Closures

Phase 1E (LLM Nodes), Phase 1F (Persistence & Audit), Phase 1G (Human Review
Gate), and Phase 1H (Evaluation & Hardening) shipped after the fixup. Each is
locked here as evidence that the relevant control surface exists and is
exercised by tests.

| Phase | Closure evidence |
|---|---|
| 1E — LLM Nodes | `apps/edr/llm.py` adds prompt-injection regex (11 patterns), per-tier token caps, and a daily cost tracker with `CostCapExceededError` / `TokenCapExceededError`. Nodes 02/03/04 use Haiku 4.5; node 11 implements the self-correct loop (max 3); node 12 uses Sonnet 4.6 with evidence-bound JSON output; node 13 is the deterministic claim checker; node 14 exports only when `quality_gate == "passed"` and `report_json` is non-empty. Tests: `apps/edr/tests/integration/test_phase1e.py` (22 cases). |
| 1F — Persistence and Audit | `apps/edr/persistence/postgres_store.py` defines `audit_log` and `review_decisions` schemas idempotently. `apps/edr/persistence/minio_store.py` lazily ensures the configured bucket exists and persists staging artifacts; `scripts/init_minio.py` performs an explicit idempotent bucket create. Node 15 hashes user IDs (no raw IDs stored), persists report/evidence/quality/audit artifacts plus internal `report-draft.json` when a draft exists, and writes the audit row. The download endpoint `GET /reports/staging/{request_id}/download/{fmt}` enforces RBAC plus quality-gate state. Tests: `apps/edr/tests/integration/test_phase1f.py`. |
| 1G — Human Review Gate | `POST /reports/staging/{request_id}/{approve,reject,request-revision}` with role-aware action selection (`_check_reviewer_rbac`), self-approval blocking by hashed reviewer ID, mandatory comment for `admin_override`, and 409 on already-finalized reports. Node 16 reads review state from PostgreSQL; node 17 publishes only when `review_state == "approved"`, copies staging→final via `MinioStore.copy_to_final` (write-once via `FileExistsError`), writes `approval-log.json` exactly once, and updates `review_state` to `final`. `GET /reports/final/{request_id}/download/{fmt}` only serves once finalized; quality-gate `failed` blocks all download paths. Tests: `apps/edr/tests/integration/test_phase1g.py` (22 cases). |
| 1H — Evaluation and Hardening | `apps/edr/evaluation/run.py` is a real runner (JSONL loader, single-node and full-workflow cases, dot-notation expectation resolution, aggregate pass-rate/precision/refusal metrics, non-zero exit on regression). `apps/edr/evaluation/goldenset/goldenset.jsonl` holds 64 executable cases. `node_13_quality_gate.py` enforces claim-to-evidence binding and Odoo-backed financial fields. `apps/edr/exporters/pdf.py` bundles `Amiri-Regular.ttf` (OFL), auto-detects Arabic, and appends an RTL limitation disclaimer (full bidi shaping deferred). `apps/edr/evaluation/load_test.py` is a local-only deterministic load test (baseline-only). `pip-audit` triage completed (see below). `.github/workflows/ci.yml` adds the `Evaluation suite` step (`--min-pass-rate 0.95 --min-precision 0.90`) and job-level `N8N_TIMEOUT: 5`. Tests: `test_evaluation.py` (15), `test_load_test.py` (5), `test_pdf_arabic.py` (7). Report: `docs/execution/PHASE_1H_REPORT.md`. |

## Standing Control Invariants

These hold for every phase, including the next one:

- Documentation must agree on the 43-key environment baseline.
- Documentation must agree that Phases 1A–1H plus the Phase 1D-fixup are complete.
- RBAC documentation must use the 9 canonical roles from the locked spec.
- n8n workflows must declare `authentication=headerAuth` and read service-account
  credentials from environment variables.
- Service-account credentials must never be logged or transmitted via the
  webhook body.
- CI must enforce: ruff, compileall, config coverage (43 keys), doc-drift
  check (including the anchor-currency invariant), AI-context check, smoke
  tests, integration tests, the evaluation suite (`make eval` thresholds),
  frontend lint and build, and `pip-audit` (non-blocking; see triage below).
- The governance anchor (`docs/ai/agent-state.json.current_commit`) must be
  HEAD itself or no more than three commits behind HEAD on the current
  branch. `scripts/check_doc_drift.py` enforces this.
- Production must remain `NOT_LIVE` until an operator runs the deployment
  steps in `docs/operations/runbook.md`. A push to `origin/main` is not a
  deployment.

## Phase 2A Progress Lock

Phase 2A is complete and not live. Implementation slices 1–9, backend
read/status/content/cancel/upload additions, deterministic local E2E, and
U-01..U-16 manual QA are complete. See
`docs/execution/PHASE_2A_REPORT.md`.

| Slice | Status | Evidence |
|---|---|---|
| 1 — API client foundation and auth wiring | Complete | `frontend/src/api/*`; controlled `fetch` usage is contained in the API client. Commit `840e954`. |
| 2 — Query Composer submit | Complete | `frontend/src/screens/QueryComposerScreen.tsx`; submit is wired to `POST /reports/staging`; final closeout wiring loads backend project context. |
| 3 — Reports List read-only listing | Complete | `frontend/src/screens/ReportsListScreen.tsx`; unavailable/empty state because `GET /reports` is absent. Commit `89a4e49`. |
| 4 — Processing View status shell | Complete | `frontend/src/screens/ProcessingScreen.tsx`; static status shell because `GET /reports/{id}/status` and `DELETE /reports/{id}` are absent. Commit `5674581`. |
| 5 — Report View and Evidence Panel | Complete | `frontend/src/screens/ReportViewScreen.tsx` and `frontend/src/screens/EvidencePanel.tsx`; unavailable/static shell because `GET /reports/{id}` is absent. Commit `35f561d`. |
| 6 — Export Panel | Complete | `frontend/src/screens/ExportPanel.tsx`; wired to existing `GET /reports/{staging,final}/{id}/download/{fmt}`; artifact rows disabled because no artifact-fetch endpoint exists. Commit `96ec4b9`. |
| 7 — Upload Zone | Complete | `frontend/src/screens/UploadZone.tsx`; drag-and-drop + client-side validation; backend `POST /upload` enforces matching rules. |
| 8 — Routing integration + role guards | Complete | `frontend/src/layout/Sidebar.tsx`, `Topbar.tsx`, `routing/guards.ts`. Commit `a5aedfc`. |
| 9 — Error handling and polish | Complete | `frontend/src/components/ToastProvider.tsx`; error surfaces unified across workspace screens. Commit `e37b0c1`. |
| Phase 2A backend additions (gap G12) | Complete | Backend endpoints in `apps/edr/app.py`: `GET /workspace/context`, `GET /reports`, `GET /reports/{id}`, `GET /reports/{id}/status`, `GET /reports/{id}/content`, `DELETE /reports/{id}`, `POST /upload`. RBAC enforced server-side; QA regressions in `test_phase2a_backend.py`. |
| Phase 2A validation gate | Complete | `make phase2a-e2e` passed; U-01..U-16 manual QA passed; `make smoke`, `make test`, `make eval`, ruff, compileall, frontend lint/build, doc drift, AI context, and postflight form the closeout gate. |

## Phase 2B Progress Lock

Phase 2B is complete. All ten slices are closed and CI-green, as documented in
`docs/execution/PHASE_2B_REPORT.md`. Phase 2C is also complete; see
`docs/execution/PHASE_2C_REPORT.md` for the 54/54 Playwright cross-browser
closeout evidence.

| Slice | Status | Evidence |
|---|---|---|
| 1 — Plan ratification and admin RBAC base | Complete | `apps/edr/app.py` `_require_admin` helper + `GET /admin/_authcheck` stub; 13 RBAC integration cases in `apps/edr/tests/integration/test_phase2b_admin_rbac.py` (admin allowed, 8 non-admin roles denied, missing role 403, unknown role 403, missing claims 401, helper-level invariants); `docs/execution/PHASE_2B_PLAN.md` ratified. |
| 2 — Connectors & APIs (read + probe) | Complete | `GET /admin/services`, `GET /admin/services/{name}`, `POST /admin/services/{name}/probe` in `apps/edr/app.py`; `apps/edr/admin/services_catalog.py` registry + probe logic; `connector_events` table in `postgres_store.py`; 45 integration cases in `test_phase2b_connectors.py` (RBAC, A-03, A-04, A-05, C-1, C-6, write-before-return); `AdminConnectorsScreen.tsx` frontend. |
| 3 — System Health + cost monitor | Complete | `GET /admin/health/live`, `GET /admin/cost`; `cost_events` table + sparkline buckets; 28 integration cases in `test_phase2b_health_cost.py`; live `AdminHealthScreen.tsx` frontend with auto-refresh, cost banners, and warning/exceeded thresholds. |
| 4 — Audit Log screen | Complete | `GET /admin/audit`, `GET /admin/audit/export.csv`, `GET /admin/audit/{event_id}`; `admin_events` table + UNION read-model; 18 integration cases in `test_phase2b_audit.py`; `AdminAuditLogScreen.tsx` frontend with filters, pagination, CSV export, and detail panel. |
| 5 — Permissions & Roles | Complete | `GET /admin/entra-mappings`, `PUT /admin/entra-mappings/{group_id}`, `DELETE /admin/entra-mappings/{group_id}`; `entra_group_mappings` table + `_validate_canonical_role()`; A-17 audit-before-save on upsert and delete; 33 integration cases in `test_phase2b_permissions.py` (RBAC, 401, happy paths, invalid role 400, A-17 order, 404 delete, C-1, C-6); live three-tab `AdminPermissionsScreen.tsx` frontend. |
| 6 — Project Source Mapping | Complete | `GET /admin/source-mappings`, `GET /admin/source-mappings/{code}`, `POST /admin/source-mappings/{code}/validate`, `PUT /admin/source-mappings/{code}`, `POST /admin/source-mappings/{code}/disable`; `source_mappings` table + JSON seeding + `_compute_mapping_status()`; A-21 audit-before-save; A-20 guard in `stage_report()`; 53 integration cases in `test_phase2b_source_mapping.py` (RBAC, 401, list, detail, validate, upsert, A-21, disable 204/404/409, C-1, C-6); live two-column `AdminSourceMappingScreen.tsx` frontend with diff preview and risky-change confirmation. |
| 7 — Approval Queue + admin override | Complete | `GET /admin/approvals`, `GET /admin/approvals/{request_id}`, `POST /admin/approvals/{request_id}/override-approve`, `POST /admin/approvals/{request_id}/override-reject`; `list_approval_queue()` queries `audit_log`; A-10 self-block; N-1 audit-before-action; R13 failed-QG → 409; 49 integration cases in `test_phase2b_approvals.py`; live `AdminApprovalQueueScreen.tsx` frontend. CI green. |
| 8 — Dashboard | Complete | `GET /admin/dashboard/summary`; `dashboard_counts_today()` in PostgresStore; service probes, approval count, cost, today counts, recent events; 16 integration cases in `test_phase2b_dashboard.py`; live `AdminDashboardScreen.tsx` with stat grid, service dots, recent events; `/admin` redirects to `/admin/dashboard`. CI green. |
| 9 — Routing + admin nav | Complete | Sidebar.tsx: Dashboard path `/admin/dashboard`, Audit Log and Approvals entries added; Topbar.tsx: breadcrumb labels for all admin routes. Frontend-only. CI green. |
| 10 — Phase 2B closeout | Complete | PHASE_2B_REPORT.md authored; A-01..A-23 QA matrix recorded; cross-screen invariants verified; all 10 audit event types documented. Phase 2B is closed. |

## Pip-audit Triage (Decided in Phase 1H — Promotion Still Deferred)

`pip-audit` is wired into CI as `continue-on-error: true`. Phase 1H triaged the
advisories present against the pinned dependency set: the safe pins were
upgraded — `cryptography` 44.0.0 → 44.0.1, `python-dotenv` 1.0.0 → 1.2.2,
`PyJWT` 2.10.1 → 2.12.0 — and the remaining advisories (major-version bumps on
the LangChain/LangGraph stack, Starlette, and pytest) were accepted as deferred.
Promotion of `pip-audit` from advisory to a hard CI gate remains deferred to a
later phase. The per-package residual list is recorded in
`docs/execution/PHASE_1H_REPORT.md` and `docs/admin/FEATURE_MATRIX.md`.

The table below is the **pre-triage advisory snapshot** kept for traceability;
the "Pinned" column reflects the versions in effect when the triage was performed.

| Package | Pinned (pre-triage) | Advisory IDs | Suggested fix version |
|---|---|---|---|
| cryptography | 44.0.0 | GHSA-79v4-65xg-pq4g, GHSA-r6ph-v2qm-q3c2, GHSA-m959-cc7f-wv43 | 44.0.1 / 46.0.5 / 46.0.6 |
| langchain-core | 0.2.43 | GHSA-6qv9-48xg-fc7f, GHSA-c67j-w6g6-q2cm, GHSA-2g6r-c272-w58r, GHSA-926x-3r5x-gfhw, GHSA-pjwx-r37v-7724 | 0.3.x / 1.x line |
| langgraph | 0.2.0 | GHSA-g48c-2wqr-h844 | 1.0.10 |
| langgraph-checkpoint | 1.0.12 | GHSA-wwqv-p2pp-99h5, GHSA-mhr3-j7m5-c7c9 | 3.0.0 / 4.0.0 |
| langsmith | 0.1.147 | GHSA-rr7j-v2q5-chgv | 0.7.31 |
| pyjwt | 2.10.1 | GHSA-752w-5fwx-jx9f | 2.12.0 |
| pytest | 8.0.0 | GHSA-6w46-j5rx-g56g | 9.0.3 |
| python-dotenv | 1.0.0 | GHSA-mf9w-mj56-hr94 | 1.2.2 |
| starlette | 0.38.6 | GHSA-f96h-pmfr-66vw, GHSA-2c2j-9gv5-cj73 | 0.40.0 / 0.47.2 |

No code in Phases 1E–1G was re-pinned until Phase 1H validated the safe-pin
upgrade path; the remaining major-version bumps stay deferred until they can be
regression-tested.

## Can Wait Until Later Phases

- Full Arabic bidirectional shaping/reshaping in PDF export, permanent
  load-test p95 thresholds, promptfoo CLI integration, live Langfuse dashboard
  validation, and promotion of `pip-audit` to a hard gate are all deferred past
  Phase 1H.
- Frontend / Admin UI foundation is complete in Phase 1I and is governed by the
  locked UI contract.
- Phase 2B Admin Visual Control Plane implementation is complete.
- Phase 2C UI Hardening & Acceptance Validation is complete.
- Phase 2D is blocked until explicit user approval.

## Admin And Control-Plane Coverage

The locked spec defines an `admin` RBAC role. The current control plane includes
documentation, configuration, CI, RBAC mapping, source mapping, audit policy,
approval policy, operational runbooks, and the Phase 2B admin visual control
plane.

The `admin` role MUST NOT grant business-data visibility by default. Future
admin features beyond the locked Phase 2B control plane are spec changes
unless explicitly approved in a future phase.

## Final Readiness Decision

**PHASE_2C_COMPLETE_NOT_LIVE — production is NOT_LIVE.**

Phases 1A–1I plus the Phase 1D-fixup and Phases 2A–2C are complete. This does
not authorize deployment, Phase 2D work, or any spec change. All admin
endpoints remain locked. The latest read-only audit rated the project **7/10**
with final recommendation `NOT_GO_LIVE_READY_BUT_HEALTHY`.

Go-live blockers recorded by the audit:

- Production frontend delivery path missing.
- Production Entra/MSAL frontend auth missing.
- Live integrations not proven.
- Backup/restore evidence missing.
- Production hardening evidence missing.
