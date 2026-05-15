# Phase 2B Plan — Admin Visual Control Plane Implementation

> **Status:** Authorized. Slice 1 ratifies this plan as the working framework;
> each subsequent slice still requires explicit per-slice user approval before
> implementation.
> **Date:** 2026-05-15
> **Prepared against:** HEAD `8f7d4e2`, anchor `0a19bae`; live state
> `PHASE_2A_COMPLETE_NOT_LIVE`; production `NOT_LIVE`.
> **Sources of truth:** `docs/design/UI_CONTRACT_v1.md` §3, §4.3, §9.2;
> `docs/execution/IMPLEMENTATION_PHASES.md` §Phase 2B;
> `docs/admin/CONTROL_PLANE_LOCK.md`; `apps/edr/app.py`;
> `apps/edr/persistence/postgres_store.py`; `frontend/src/routing/Router.tsx`;
> `frontend/src/screens/`.

---

## A. Pre-flight confirmation

| Item | Verified | Evidence |
|---|---|---|
| Phase 2A complete | ✓ | `docs/execution/PHASE_2A_REPORT.md`: U-01..U-16 PASSED; E2E PASS; status `PHASE_2A_COMPLETE_NOT_LIVE`. |
| Production not live | ✓ | `docs/ai/agent-state.json` `production_status: NOT_LIVE`, `must_not_deploy: true`. |
| Phase 2B explicitly gated | ✓ | `agent-state.next_allowed_phase: Phase 2B`. Each slice still gates on per-slice user approval. |
| Detectors clean at HEAD | ✓ | `scripts/check_doc_drift.py`, `scripts/check_ai_context.py`, `scripts/agent_preflight.py` all clean. |

---

## B. Phase 2B Objective

Implement the **seven Admin Visual Control Plane screens** wired to live
backend data, enforcing the **C-1 boundary** (admin sees system metadata only;
never report content, query text, evidence excerpts, or business-data
artifacts) and the **C-6 boundary** (no credential values displayed anywhere,
even partially masked).

Pass acceptance criteria **A-01 through A-23** from
`docs/design/UI_CONTRACT_v1.md` §9.2.

Production remains `NOT_LIVE`.

---

## C. In-Scope Work

### C.1 Seven admin screens (UI_CONTRACT §3.1–3.7)
1. **Dashboard** `/admin/dashboard`.
2. **Connectors & APIs** `/admin/connectors`.
3. **Permissions & Roles** `/admin/permissions` (3 tabs).
4. **Project Source Mapping** `/admin/source-mapping`.
5. **Approval Queue** `/admin/approvals`.
6. **Audit Log** `/admin/audit`.
7. **System Health** `/admin/health` (upgrade from Phase 1I static).

### C.2 Backend endpoints required
| Endpoint | Purpose | Backing data |
|---|---|---|
| `GET /admin/_authcheck` | Slice 1 self-test; admin-only stub | none |
| `GET /admin/dashboard/summary` | Cards + recent events | PostgreSQL `audit_log` aggregates + `/healthz` |
| `GET /admin/services` | Connector list with status pills | per-service probes + `.env` key presence + n8n workflow JSON inspection |
| `GET /admin/services/{name}` | Connector detail panel | adds last-success/last-error, latency, n8n workflow node count |
| `POST /admin/services/{name}/probe` | Read-only `[Test connection]` | reuses `_check_*` helpers |
| `GET /admin/entra-mappings` | Tab 2 group-mapping list | new `entra_group_mappings` PG table |
| `PUT /admin/entra-mappings/{group_id}` | Upsert mapping | emits `admin.role_mapping_changed` |
| `DELETE /admin/entra-mappings/{group_id}` | Remove mapping | emits audit event |
| `GET /admin/source-mappings` | List all project mappings with computed status | seed from `docs/config/project_source_mapping.json`; persist edits in PG |
| `GET /admin/source-mappings/{code}` | Single editor payload | as above |
| `POST /admin/source-mappings/{code}/validate` | Pre-save validation | structural + per-source reachability |
| `PUT /admin/source-mappings/{code}` | Save | emits `admin.source_mapping_changed` |
| `POST /admin/source-mappings/{code}/disable` | Soft-disable | emits `admin.source_mapping_disabled` |
| `GET /admin/approvals` | Approval queue list (staging + needs_review only) | `PostgresStore.list_audits` |
| `POST /admin/approvals/{id}/override-approve` | Admin override approve | emits `report.admin_override_approved`; mandatory comment |
| `POST /admin/approvals/{id}/override-reject` | Admin override reject | emits `report.admin_override_rejected`; mandatory comment |
| `GET /admin/audit` | Paginated event log with filters/search | projection over existing audit/review/upload/connector events |
| `GET /admin/audit/{event_id}` | Single event detail | as above |
| `GET /admin/audit/export.csv` | CSV export; cost/token redacted for non-admin | streaming response |
| `GET /admin/health/live` | Live latencies + 24h sparkline buckets | `/healthz` + per-service event store |
| `GET /admin/cost` | Cost-cap progress bars + LLM call breakdown | `audit_log.cost_total_usd` + `_CostTracker` |

### C.3 Frontend infrastructure
- New screens: `AdminDashboardScreen`, `AdminConnectorsScreen`,
  `AdminApprovalQueueScreen`, `AdminAuditLogScreen`.
- Upgrade existing Phase 1I static screens: `AdminHealthScreen`,
  `AdminPermissionsScreen`, `AdminSourceMappingScreen` — replace static
  fixtures with live data.
- New components as needed: `Sparkline`, `CostMonitorBar`,
  `EntraGroupMappingEditor`, `SourceMappingEditor`, `DiffPreviewModal`,
  `AuditEventDetailPanel`. Extend existing `ConfirmDialog` for typed
  confirmation if it does not already cover it.
- Extend `frontend/src/routing/Router.tsx` with the new routes.
- `frontend/src/routing/guards.ts` already blocks non-admin from `/admin/*`;
  inherit for new routes.
- `frontend/src/layout/Sidebar.tsx` and `Topbar.tsx` add admin nav entries
  visible only to the `admin` role.
- Extend `frontend/src/api/types.ts` with the new admin response types only;
  no widening of existing types.

### C.4 Persistence schema additions
| Table / store | Purpose |
|---|---|
| `entra_group_mappings(entra_group_id PK, role, created_at, created_by_hash, updated_at, updated_by_hash)` | Tab 2 editor data |
| `connector_events(id, ts, service, event_type, latency_ms?, status_code?, detail TEXT)` | Last-error/last-success + latency sparkline |
| `source_mappings` PG mirror of `docs/config/project_source_mapping.json` | Persist admin edits without rewriting checked-in JSON |
| Audit Log read-model | UNION/projection over `audit_log`, `review_decisions`, `connector_events`, plus new `admin_events` mini-table for `admin.*` and `upload.*` events |

All additions use the existing `CREATE TABLE IF NOT EXISTS` idempotent
pattern in `PostgresStore.init_schema`.

### C.5 RBAC rules (server-enforced)
- Every `/admin/*` endpoint: admin-only (HTTP 403 for non-admin) via the new
  `_require_admin(claims)` helper introduced in Slice 1.
- **C-1:** admin response payloads never include report content, query text,
  evidence excerpts, or evidence-pack data. Per-endpoint tests assert
  absence.
- **C-6:** admin response payloads never include password/token/secret/
  connection-string values. Only key-presence booleans, hostnames, auth
  mechanism types.
- **N-1:** admin override approve/reject emit
  `report.admin_override_approved` / `report.admin_override_rejected` —
  distinct from normal reviewer events — and require a mandatory comment.
  Self-approval is blocked.
- **N-2:** admin reads per-request `audit-log.json` content via the Audit
  Log UI only, not via the existing download API.

### C.6 Audit rules
- Every mutating admin endpoint writes the audit event **before** committing
  the change.
- Event types follow UI_CONTRACT §3.6:
  `admin.source_mapping_changed`, `admin.source_mapping_disabled`,
  `admin.role_mapping_changed`, `report.admin_override_approved`,
  `report.admin_override_rejected`, `connector.probe_success`,
  `connector.error`, `connector.latency_spike`.
- `user_id` is always rendered as HMAC-SHA256 hash
  (`apps/edr/persistence/hash.py`).
- Audit Log is immutable: no DELETE / UPDATE endpoint on audit data.

### C.7 Validation gates per A-01..A-23
Each acceptance criterion must have at least one integration test and a
manual QA pass in the closeout. The closeout report records a row per
criterion with PASS/FAIL evidence, mirroring
`docs/execution/PHASE_2A_REPORT.md` §U-01..U-16.

---

## D. Out-of-Scope Work

| Area | Why out of scope |
|---|---|
| Phase 2C (UI hardening, a11y audit, Playwright/`make test:ui`, cross-browser) | Phase 2C scope |
| Production deployment | `must_not_deploy: true` |
| Spec changes | Locked spec |
| New LLM behavior / retrieval source / export format | Phase 1E/1D/1H scope |
| Pip-audit hard-gate promotion (gap G11) | Deferred per Phase 1H triage |
| Arabic bidi/reshaping (gap G10b) | Deferred |
| Live Langfuse dashboard verification (gap G9) | Deferred |
| Notifications, email delivery | UI_CONTRACT Appendix A |
| Mobile-native layout below 768px | UI_CONTRACT Appendix A |
| Hard delete of mappings, role hard delete, audit-log deletion | UI_CONTRACT §3.4, §3.6 |
| Credential editing/storage in DB | UI_CONTRACT §3.4, §8.3 |

---

## E. Slice Plan

Each slice is one commit, CI-green, and ends with a small governance
reconciliation if the anchor drifts beyond two commits behind HEAD.

| # | Slice | Backend | Frontend | Audit events | Acceptance |
|---|---|---|---|---|---|
| **1** | Plan ratification + admin RBAC base | `_require_admin`, `GET /admin/_authcheck` stub | none | n/a | A-01 |
| **2** | Connectors & APIs (read + probe) | `GET /admin/services`, `/{name}`, `POST /admin/services/{name}/probe`; new `connector_events` | New `AdminConnectorsScreen` + detail panel | `connector.probe_success`, `connector.error`, `connector.latency_spike` | A-03, A-04, A-05 |
| **3** | System Health + cost monitor | `GET /admin/health/live`, `GET /admin/cost` | Upgrade `AdminHealthScreen` to live; cost banners | `cost.daily_cap_warning`, `cost.daily_cap_exceeded` | A-14, A-15, A-16 |
| **4** | Audit Log screen | `GET /admin/audit`, `/{event_id}`, `/export.csv` | New `AdminAuditLogScreen` | n/a (read-only) | A-12, A-13 |
| **5** | Permissions & Roles | `GET /admin/entra-mappings`, `PUT/DELETE`; new `entra_group_mappings` table | Upgrade `AdminPermissionsScreen` Tab 2 + Tab 3 | `admin.role_mapping_changed` | A-17 |
| **6** | Project Source Mapping | `GET /admin/source-mappings`, `/{code}`, `/validate`, `PUT`, `/disable`; new `source_mappings` mirror | Upgrade `AdminSourceMappingScreen` editor + diff preview + typed-confirm | `admin.source_mapping_changed`, `admin.source_mapping_disabled` | A-06..A-08, A-18..A-23 |
| **7** | Approval Queue + admin override | `GET /admin/approvals`, `POST /admin/approvals/{id}/override-{approve,reject}` | New `AdminApprovalQueueScreen` + admin review panel (no content) | `report.admin_override_approved`, `report.admin_override_rejected` | A-09, A-10, A-11 |
| **8** | Dashboard | `GET /admin/dashboard/summary` | New `AdminDashboardScreen` | n/a | A-02 |
| **9** | Routing + admin nav | none | `Router.tsx`, `Sidebar`/`Topbar` admin entries | n/a | A-01 |
| **10** | Closeout + truth reconciliation | none | none | n/a | All A-* recorded |

---

## F. Files / Areas Likely Affected

**Backend:**
- `apps/edr/app.py` — new admin endpoint handlers + Pydantic response models.
- `apps/edr/persistence/postgres_store.py` — new tables and query helpers.
- New tests in `apps/edr/tests/integration/`: `test_phase2b_admin_rbac.py`,
  `test_phase2b_connectors.py`, `test_phase2b_health_cost.py`,
  `test_phase2b_audit.py`, `test_phase2b_permissions.py`,
  `test_phase2b_source_mapping.py`, `test_phase2b_approvals.py`,
  `test_phase2b_dashboard.py`.

**Frontend:**
- `frontend/src/routing/Router.tsx` — new admin routes.
- `frontend/src/routing/guards.ts` — admin-only inheritance for the new
  routes (no behavioural change expected).
- Admin screens upgraded or added under `frontend/src/screens/`.
- New components under `frontend/src/components/`.
- `frontend/src/api/types.ts` + `frontend/src/api/index.ts` — new admin
  response types only.
- `frontend/src/layout/Sidebar.tsx`, `Topbar.tsx` — admin nav entries.

**Governance:**
- This file (`docs/execution/PHASE_2B_PLAN.md`).
- New at closeout: `docs/execution/PHASE_2B_REPORT.md`.
- Updates per slice and at closeout: `docs/admin/CONTROL_PLANE_LOCK.md`,
  `docs/admin/FEATURE_MATRIX.md`, `docs/execution/CURRENT_PROJECT_STATE.md`,
  `docs/execution/IMPLEMENTATION_PHASES.md`, `docs/ai/SHARED_CONTEXT.md`,
  `docs/ai/AGENT_HANDOFF.md`, `docs/ai/agent-state.json`.
- `scripts/check_ai_context.py` — `ALLOWED_STATUSES` extended with
  `PHASE_2B_SLICE_{1..10}_COMPLETE_NOT_LIVE` and `PHASE_2B_COMPLETE_NOT_LIVE`.

---

## G. Validation Plan

### Per-slice gate
- `ruff check apps scripts` clean
- `python3 -m compileall apps scripts` clean
- `python3 scripts/check_doc_drift.py` clean
- `python3 scripts/check_ai_context.py` clean
- `python3 scripts/agent_preflight.py` clean
- `make smoke` 2 passed
- `make test` — new slice tests + existing suite all green
- `make eval` 64/64 passed
- `cd frontend && npm run lint` clean
- `cd frontend && npm run build` success
- Each new endpoint covered by ≥1 RBAC denial test + ≥1 happy-path test +
  ≥1 boundary test (404/400/409 where applicable)
- Each new mutation covered by an audit-event test (event row written
  before the side effect)

### Phase 2B closeout gate
- A-01..A-23 manual QA matrix recorded in `PHASE_2B_REPORT.md`
- `make phase2a-e2e` regression remains green
- Cross-screen invariants tested:
  - A-16 same status visible in Dashboard + Connectors + Health
  - C-1: every admin response payload tested for absence of report content
    / evidence / query text
  - C-6: every admin response payload tested for absence of credential
    values
- `python3 scripts/agent_postflight.py --allow-no-evidence` clean
- GitHub Actions CI on the closeout commit completes / success

---

## H. Blockers & Risks

| # | Risk / Blocker | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | C-1 leakage in admin endpoints | Medium | Critical | Pydantic response models that omit business-content fields; per-endpoint test asserting forbidden field absence |
| R2 | C-6 credential leakage | Medium | Critical | Connector serializer rule: only key-presence boolean + hostname + auth-mechanism type; per-endpoint regex test |
| R3 | Source-mapping write storage (currently file-based JSON) | High | High | Move state to PG `source_mappings`; seed from JSON on first start; planned in Slice 6 |
| R4 | Audit Log event-source unification | High | Medium | Build a read-model projection; document event-type → table mapping in Slice 4 plan |
| R5 | Entra group validation requires live Entra | Medium | Low | Allow save with warning in bypass mode; production rejects unverified IDs; tests gated on `settings.entra_client_id` |
| R6 | n8n workflow status: local JSON vs n8n API | Low | Low | Read local JSON for `empty`/`deployed`; n8n-API check is Phase 2C enhancement |
| R7 | Cost data quality for A-14/A-15 | Low | Medium | Audit `_CostTracker` in Slice 3; add monthly aggregate test if missing |
| R8 | Auditor audit-access path collision | Medium | Low | Keep auditor audit access out of `/admin/*`; defer scoped workspace audit to Phase 2C unless tiny |
| R9 | Slice ordering / scope creep | Medium | Medium | Strict slice boundaries; one commit per slice; per-slice user approval |
| R10 | Backend list pagination of admin queries | Low (Phase 2B) | Medium | Mandatory `limit`/`offset` with 200 hard cap; date filters required for unbounded ranges |
| R11 | Anchor-currency invariant (≤3 commits behind HEAD) | High | Low | Plan small `docs:` reconciliation commits between slice pairs |
| R12 | No frontend test runner yet | Already known | Low (Phase 2B) | Manual QA per Phase 2A pattern; Playwright/`make test:ui` is Phase 2C scope (gap G5) |
| R13 | `quality_gate = "failed"` interaction with admin override | Low | High | Slice 7 test: admin override approve on `failed` QG report → 403 |

No documentation-consistency blocker was found during plan preparation.

---

## I. Final note

This plan is the working framework. Each slice is its own commit, CI-green
on push, and requires explicit user approval before it starts.
