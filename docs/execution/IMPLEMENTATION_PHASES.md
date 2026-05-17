# DecisionCenter — Implementation Phases 1A–1H

> **Source of truth:** `docs/workflows/EDR-AGENTIC-RAG-v2.1.md`
> **Derived from:** `docs/PRE_START_IMPLEMENTATION_PLAN.md` Section 7 & 9
> **Date:** 2026-05-14
> **Status:** Phases 1A–1I plus the Phase 1D-fixup and Phase 2A are complete. Phase 2B Slices 1–7 are complete. Phase 2B is the safe next phase; Slice 8 requires explicit user authorization. Production is `NOT_LIVE`.

This file is the authoritative execution sequence for implementation. The locked
workflow spec remains the behavioral source of truth, and its Section 31 now mirrors
this infrastructure-first sequence.

Live audit note (Phase 2A closeout, 2026-05-14):
Phase 0, Phase 1A, Phase 1B, Phase 1B.5, Phase 1C, Phase 1D, the Phase
1D-fixup, Phase 1E, Phase 1F, Phase 1G, Phase 1H, and Phase 1I are complete.
The four n8n workflow JSON files contain real 4–5 node pipelines, declare
`authentication=headerAuth`, and read service-account credentials from
`$env.*`. Voyage embeddings, Cohere reranking, tiktoken chunking, the
per-project Qdrant store (`edr_*`), and the Redis-backed evidence cache are
wired. The LLM tier (Haiku 4.5 / Sonnet 4.6), the deterministic claim
checker, the export pipeline, MinIO + PostgreSQL persistence (with
`scripts/init_minio.py` for explicit bucket creation), the human review
endpoints, and the write-once publish-to-final flow are all wired and
covered by integration tests. The 64-case executable golden set, evaluation
runner with pass-rate/precision thresholds, Arabic PDF hardening, local-only
load test, pip-audit triage, and CI integration are all complete. Phase 2A is
complete: implementation slices 1–9, backend read/status/content/cancel/upload
additions, deterministic local E2E, and U-01..U-16 manual QA passed. Production
deployment is out of scope until Phase 2C closes and an operator deploys.

---

## Phase Sequence Overview

| Phase | Name | Goal | Cost | Forbidden Work |
|-------|------|------|------|----------------|
| **1A** | Infrastructure Foundation | Every service starts, config is complete, CI catches regressions | Zero (no external APIs) | No node logic, no LLM calls, no n8n changes, no schema changes, no auth logic |
| **1B** | RBAC & Identity | Real authentication and authorization in Node 01 before retrieval touches data | Entra API only (free under M365) | No retrieval logic, no n8n changes |
| **1C** | n8n Connector Workflows | 4 real n8n workflows returning normalized evidence payloads | Hetzner compute + Graph API (free under M365) | No Python node logic, no LLM calls |
| **1D** | Embedding & Vector Retrieval | Evidence retrieval pipeline from document to ranked Evidence Objects | ~USD 5/mo (Voyage-3-large) | No LLM report generation |
| **1D-fixup** | Audit closure | Close audit findings (correctness, security, drift) before Phase 1E | Zero | No new features |
| **1E** | LLM Nodes | Nodes 02, 03, 04, 11, 12, 13, 14 produce real structured output | ~USD 220/mo (Anthropic majority) | No persistence changes, no publish logic |
| **1F** | Persistence & Audit | Output files written to MinIO staging; audit trail in PostgreSQL | ~USD 5/mo (MinIO storage) | No human review UI, no approval logic |
| **1G** | Human Review Gate | Approval/reject mechanism for Node 16 → Node 17 with immutable final output | Zero new API costs | No eval logic, no load testing |
| **1H** | Evaluation & Hardening | Prove correctness against spec before production use | Small eval API costs | No new features |

---

## Phase 1A — Infrastructure Foundation

**First safe phase.** All subsequent phases depend on it.

1. Expand `apps/edr/config.py` to load all `.env.example` keys with Pydantic field types.
2. Rewrite `GET /healthz` to ping PostgreSQL, Redis, Qdrant, MinIO — return per-service status.
3. Pin all dependencies in `pyproject.toml` to exact versions.
4. Create `.github/workflows/ci.yml` — ruff lint, syntax check, config coverage, smoke tests.
5. Write Qdrant collection initialization script — idempotent, one collection per `project_code`.
6. Configure `Caddyfile` with a non-placeholder ACME email.
7. Verify `.dockerignore` excludes `.env`, `__pycache__`, `.git`, `.pytest_cache`.

**Validation gate before 1B:**
- Smoke tests pass in CI.
- `GET /healthz` returns `{"postgres":"ok","redis":"ok","qdrant":"ok","minio":"ok"}`.
- `ruff check apps scripts` exits 0.
- All `.env.example` keys have a corresponding `config.py` field.
- `pyproject.toml` contains `==` version pins.
- CI pipeline runs on every push.

---

## Phase 1B — RBAC & Identity

**Goal:** Real authentication and authorization in Node 01.

1. Wire Entra JWT validation into `apps/edr/graph/node_01_auth.py`.
2. Load role-to-permissions from `docs/security/rbac_matrix.md` into a typed mapping.
3. Load project source mapping from `docs/config/project_source_mapping.example.json` (extend to real file).
4. Enforce: no valid `project_code` in mapping → reject, no retrieval.
5. Populate `DecisionState` with `allowed_projects`, `allowed_mailboxes`, `allowed_odoo_ids`.
6. Integration test: 3 cases — authorized user, unauthorized user, unknown project.

**Validation gate before 1C:**
- Three integration tests pass in CI.
- No stub strings remain in Node 01 output.
- `rbac_status` is `authorized` only for valid user+project+role combinations.

---

## Phase 1C — n8n Connector Workflows

**Goal:** 4 real n8n workflows that return normalized evidence payloads.

Current live-audit status: all four workflow files contain real 4-node pipelines,
declare `authentication=headerAuth`, and read service-account credentials from
`$env.*`. The email workflow gates on the mailbox allowlist before the Graph
call. Python connector wrappers validate every response against the
`EvidenceObject` schema. Isolated mock-based integration tests pass in CI.

1. `sharepoint_search.json` — Entra token → Graph search → excerpt + `hash_sha256`.
2. `email_search.json` — Graph delegated → user mailbox + allowed shared mailboxes → excerpt only (≤500 chars).
3. `owncloud_list.json` — WebDAV read → file metadata + excerpt; credentials from `$env.OWNCLOUD_*`.
4. `odoo_read.json` — JSON-RPC read-only → `model + id + value + timestamp + hash_sha256`; credentials from `$env.ODOO_*`.
5. Each workflow output validates against `docs/schemas/evidence-object.schema.json`.
6. Test each workflow in isolation via `curl` before wiring to Python.

**Validation gate before 1D:**
- Each workflow returns ≥1 payload validating against evidence-object schema.
- Email workflow confirmed excerpt-only.
- Odoo workflow returns required fields.
- n8n workflow JSON files declare `authentication=headerAuth`.

---

## Phase 1D — Embedding & Vector Retrieval

**Goal:** Real evidence retrieval pipeline from document to ranked Evidence Objects.

1. Wire `apps/edr/retrieval/embeddings.py` → Voyage-3-large API.
2. Wire `apps/edr/retrieval/chunking.py` to use token count (500–800 tokens, 100–150 overlap).
3. Wire `apps/edr/retrieval/rerank.py` → Cohere Rerank 3.5 (max 50 inputs → max 10 output).
4. Wire RBAC-aware cache to Redis — cache key includes `user_id` and `project_code`.
5. Nodes 05–08: call n8n webhooks → embed results → insert into the correct Qdrant collection.
6. Node 09: real normalization — dedup by `(source_uri, hash_sha256)`, source priority preservation.
7. Node 10: real sufficiency check — count evidence per source type, flag missing Odoo for financial queries.

**Validation gate before 1D-fixup:**
- `embed()` returns vectors of correct dimension for Voyage-3-large.
- `chunk_text()` verified via test: 500–800 tokens with 100–150 overlap.
- Qdrant insert and round-trip retrieval test passes for at least one project collection.
- RRF fusion produces a ranked list from two result sets.
- Redis cache key confirmed to include `user_id` and `project_code`.

---

## Phase 1D-Fixup — Audit closure

**Goal:** Close every audit finding raised against the post-1D commit before
Phase 1E starts. No new product features.

1. **C-1** Align `scripts/init_qdrant.py` with `EvidenceStore._collection_name` (one collection name per project).
2. **C-2** Build the Odoo search domain in Node 08 via `json.dumps` (no f-string interpolation of `project_code`).
3. **C-3** Add `authentication=headerAuth` to every n8n webhook; document the operator credential in `n8n/README.md`.
4. **C-4** Enforce the mailbox allowlist twice — Python in Node 07 and an n8n `Enforce Mailbox Allowlist` code node.
5. **C-6 / S-1** Move ownCloud and Odoo service-account credentials out of the webhook body and into the n8n container environment.
6. **C-7 / I-6** Upgrade `PyJWT` to 2.10.1 and `cryptography` to 44.0.0 to clear known CVEs.
7. **C-8** Tighten Node 14 to require `quality_gate == "passed"` and a populated `report_json` before exporting.
8. **L-2 / R-4** Cache the `PyJWKClient` on the validator and surface the full `roles` tuple from the JWT claim.
9. **L-5** Widen `EvidenceObject.metadata` to accept lists of scalars (so n8n's `recipients` field validates).
10. **O-1** Replace the misleading `"status": "stubbed"` from `POST /reports/staging` with a derived status; assign UUID `request_id`s.
11. **O-2** Caddy serves a `PUBLIC_HOSTNAME` site with TLS, HSTS, and a `:80` fallback.
12. **O-3** Compose binds Qdrant/n8n to the internal network only; MinIO/app bind to `127.0.0.1`.
13. **O-4** Update the evaluation runner's stale Phase 1G message to Phase 1H.
14. **T-1** Add a CI drift-detector that fails if state docs reference a phase older than the latest implemented phase.
15. **T-7 / S-4** Run `pip-audit` in CI (non-blocking warning only) and `ruff check`.

**Validation gate before 1E:**
- All Phase 1D-fixup regression tests in
  `apps/edr/tests/integration/test_phase1d_fixes.py` and
  `apps/edr/tests/integration/test_phase1d_security.py` pass in CI.
- CI's config-coverage assertion matches the live `.env.example` key count.
- CI's `pip-audit` step runs without producing critical advisories.
- `docs/admin/CONTROL_PLANE_LOCK.md`, `docs/execution/CURRENT_PROJECT_STATE.md`,
  `docs/execution/IMPLEMENTATION_PHASES.md`, `docs/admin/FEATURE_MATRIX.md`,
  and `README.md` all describe the post-1D-fixup state.

---

## Phase 1E — LLM Nodes

**Goal:** Nodes 02, 03, 04, 11, 12, 13, 14 produce real structured output using existing prompt files.

1. Nodes 02, 03, 04 → Haiku 4.5 using `apps/edr/prompts/intent_classifier.md`, scope extraction, retrieval planning.
2. Node 11: self-correct loop (max 3 iterations) — detect evidence gaps, re-query targeted sources.
3. Node 12 → Sonnet 4.6: structured JSON output using `apps/edr/prompts/draft_report.md`; every claim binds to `evidence_id`; financial values must have Odoo `evidence_id` or be `"Not available"`.
4. Node 13: deterministic claim checker — every `evidence_id` referenced must exist in evidence pack.
5. Node 14: verify export pipeline runs end-to-end (already partially wired).
6. Wire Langfuse tracing to every LLM call — token counts, latency, node name.

**Validation gate before 1F:**
- Node 12 output validates against `docs/schemas/executive-decision-report.schema.json`.
- Node 13 rejects any report with a claim containing no `evidence_id`.
- Financial value with no Odoo `evidence_id` is absent or explicitly `"Not available"`.
- Langfuse dashboard shows traces for all LLM nodes with token counts.

---

## Phase 1F — Persistence & Audit

**Goal:** All 4 output files written to MinIO staging; audit trail in PostgreSQL.

1. Node 15: write `report.md`, `evidence-pack.json`, `audit-log.json`, `quality-gate-result.json` to `/staging/{request_id}/` in MinIO.
2. Write `AuditLog` rows to PostgreSQL — hashed `user_id`, all node events, token counts per node, cost estimate.
3. Token cost accumulator — compare against `daily_cost_cap_usd` after each LLM call.
4. Implement `GET /reports/staging/{request_id}/download/{fmt}` — serve from MinIO, block if `quality_gate == "failed"`.

**Validation gate before 1G:**
- `POST /reports/staging` with real query returns `request_id`.
- `GET /reports/staging/{request_id}/download/md` returns real Markdown content.
- MinIO `/staging/{request_id}/` contains all 4 output files.
- PostgreSQL `audit_log` has a row for the request with hashed `user_id`.
- Token cost per request is logged.

---

## Phase 1G — Human Review Gate

**Goal:** Approval/reject mechanism for Node 16 → Node 17 with immutable final output.

1. Add `POST /reports/staging/{request_id}/approve` — authorized roles only, writes approval record to PostgreSQL.
2. Add `POST /reports/staging/{request_id}/reject` — writes rejection + reason to PostgreSQL.
3. Node 16: poll approval status from PostgreSQL, configurable timeout.
4. Node 17: on approval — move files from `/staging/{request_id}/` to `/final/{request_id}/` in MinIO, set immutable flag.
5. Log approval event to `AuditLog` with approver `user_id_hash` and timestamp.
6. Enforce: Node 17 cannot run without a valid approval record.

**Validation gate before 1H:**
- Full approval flow: submit → staging → `POST /approve` → `/final` files appear and cannot be overwritten.
- Full reject flow: submit → `POST /reject` → no `/final` files.
- Approval record in PostgreSQL contains approver hash and timestamp.
- `publish_status` in Node 17 output is `"published"` only after real approval record.

---

## Phase 1H — Evaluation & Hardening

**Goal:** Prove correctness against spec before production use.

1. ✅ Expand the executable golden set to 64 executable cases covering the required baseline categories from spec Section 26.
2. ✅ Wire `apps/edr/evaluation/run.py` to execute against golden set and report metrics from `docs/evaluation/edr_metrics.md`.
3. ✅ Wire `apps/edr/evaluation/promptfoo.config.yaml` with structured placeholder (real providers and tests awaiting promptfoo CLI).
4. ✅ Fix PDF Arabic RTL — register bundled `Amiri-Regular.ttf` (OFL license), auto-detect Arabic Unicode, append RTL limitation disclaimer.
5. ✅ Cost cap circuit breaker — pre-call estimate raises `CostCapExceededError` if daily cap exceeded; tracked in `apps/edr/llm.py`.
6. ✅ Add `make eval` step to CI pipeline with `--min-pass-rate 0.95 --min-precision 0.90`.
7. ✅ Load test: local-only deterministic fallback, 5 concurrent requests, p50/p95/p99 metrics.
8. ✅ pip-audit triage: upgrade safe pins (`cryptography` 44.0.1, `python-dotenv` 1.2.2, `PyJWT` 2.12.0); accept deferred major-version bumps.
9. ✅ CI timeout fix: add `N8N_TIMEOUT` setting (default 60 s, 5 s in CI) to prevent connector hangs when n8n is unavailable.

**Validation gate before 1I:**
- ✅ 64 executable golden set cases pass and `make eval` exits 0.
- ✅ PDF with Arabic content renders with Amiri font (RTL shaping deferred).
- ✅ Load test: 5 concurrent requests complete; baseline recorded.
- ✅ Langfuse monthly cost projection ≤ USD 300.
- ✅ Both `make smoke` and `make eval` required to pass before any production deploy.

---

## Phase 1I — Frontend Foundation & Static Admin Scaffolds (Complete)

**Goal:** Establish the frontend codebase, build system, design system, and static screens that do not require live backend data. No API wiring.

**Rule:** Static scaffolds only. No API calls. No report content rendering. No data fetching.
Source of truth: `docs/design/UI_CONTRACT_v1.md` Section 10.

**Scope:**
1. Initialize frontend project (Vite + React + TypeScript + Tailwind) in `frontend/`.
2. Implement design tokens from UI_CONTRACT Section 1.4: colors, typography, spacing, status pills.
3. Build layout shell: Topbar (48px), Sidebar (220px collapsible to 48px), Main Content (max 960px), Detail Panel (380px slide-in).
4. Build reusable components: StatusPill, Button, Modal, Toast, ConfirmDialog, SlideInPanel.
5. Implement route structure with role-guarded client-side routing:
   - `/workspace/*` → User Chat Workspace
   - `/admin/*` → Admin Visual Control Plane
   - Role-based redirects per UI_CONTRACT Section 1.5.
6. **Static scaffolds allowed early** (no API wiring):
   - Admin System Health screen (static table, no live `/healthz` data).
   - Permissions & Roles — Tab 1 (Role Matrix read-only, from `docs/security/rbac_matrix.md`).
   - Source Mapping — read-only view (from `docs/config/project_source_mapping.json`).
   - Query Composer shell (form layout, no project dropdown data, no submit handler).
7. Add `frontend/` lint and build steps to CI.

**Validation gate before 2A:**
- `npm run build` exits 0.
- `npm run lint` exits 0.
- All 9 roles route to their correct default landing screens.
- Status pills render all 13 defined states with correct colors and icons.
- ConfirmDialog requires typed confirmation string for destructive actions.

**Forbidden in 1I:**
- No API client implementation.
- No `fetch` or `axios` calls.
- No report content rendering.
- No Processing View wiring.
- No Evidence Panel with real data.
- No upload handler.

---

## Phase 2A — User Chat Workspace Implementation

**Goal:** Implement all six user-facing screens with live backend integration.

**Backend dependency:** Phase 1F complete (real reports, evidence packs, MinIO persistence, audit log, cost data).
**Additional dependency:** Phase 1G complete for approval/reject actions.

**Live progress note (2026-05-14):** Phase 2A is complete and not live. The
implementation slices, backend additions, E2E unblock harness, and manual QA
blocker fixes are complete. Current frontend integration:

- API client foundation is present in `frontend/src/api/*`.
- Query Composer submit is wired to live `GET /workspace/context` and
  `POST /reports/staging`; its project dropdown is backend role-scoped.
- Reports List, Processing View, Report View, and Evidence Panel are wired to
  live backend state.
- Export Panel is wired to the existing
  `GET /reports/{staging,final}/{id}/download/{fmt}` endpoints; artifact
  rows (`evidence-pack.json`, `audit-log.json`) are disabled because no
  artifact-fetch endpoint exists.
- Upload Zone provides drag-and-drop and client-side validation; backend
  `POST /upload` enforces matching server rules.
- Routing integration / role guards (Slice 8) and a unified error-handling
  pass (Slice 9) landed at HEAD.
- `make phase2a-e2e` passes and U-01 through U-16 manual QA passed.

**Scope:**
1. **Query Composer** (`/workspace/new`)
   - Populate Project dropdown from `POST /reports/staging` pre-flight or JWT claims (`allowed_projects`).
   - Contract No. auto-suggest from `project_source_mapping.json`.
   - Output format toggles: MD (default), DOCX, PDF, XLSX, PPTX.
   - Submit button disabled until Project + Query set.
   - All screen states per UI_CONTRACT Section 2.1: idle, draft, submitting, queued, error, no_projects.
2. **Processing View** (`/workspace/report/{request_id}/processing`)
   - Subscribe to LangGraph streaming events or poll backend for node progress.
   - Map 18 internal nodes to user-facing labels per UI_CONTRACT Section 2.2.
   - Cancel action with confirmation modal → `DELETE` request.
   - Handle all screen states: running, self_correct_retry, quality_gate_passed, quality_gate_needs_review, quality_gate_failed, awaiting_reviewer, timed_out, rbac_denied, cancelled.
3. **Report View** (`/workspace/report/{request_id}`)
   - Render report content with superscript citations linking to Evidence Panel.
   - Financial Position conditional rendering per role (`can_access_odoo_budget`).
   - Conflicts Detected and Missing Data sections always rendered if non-empty.
   - Report state handling: staging, needs_review, approved, rejected, final.
   - `needs_review` state: requester sees QG flags only; reviewer sees watermarked draft.
4. **Evidence Panel** (slide-in from Report View)
   - Render evidence entries with source type, confidence score, truncated hash.
   - Email excerpts read-only; document excerpts copyable.
   - Filter by source type and confidence.
5. **Export Panel** (slide-in from Report View)
   - Render only when report state is `approved` or `final`.
   - Block all downloads when `quality_gate = "failed"`.
   - RBAC-gated evidence-pack.json and audit-log.json downloads.
6. **My Reports List** (`/workspace/reports`)
   - Group by state: In progress, Awaiting review, Approved / Final.
   - Role-scoped: own requests only (except auditor, who sees project-scoped reports).
   - Filters by project, state, date range.

**Validation gate before 2B:**
- ✅ End-to-end test: submit query → processing → staging → approve → final → download MD.
- ✅ U-01 through U-16 acceptance criteria from UI_CONTRACT Section 9.1 pass in manual QA.
- ✅ `quality_gate = "failed"` blocks Export Panel and all downloads.
- ✅ `needs_review` requester sees flags only; reviewer sees watermarked draft.
- ✅ Financial section hidden with explicit message for unauthorized roles.

---

## Phase 2B — Admin Visual Control Plane Implementation

**Goal:** Implement all seven admin screens with live backend integration.

**Backend dependency:** Phase 1F complete. Phase 1G for Approval Queue.

**Scope:**
1. **Dashboard** (`/admin/dashboard`)
   - Live service counts from `/healthz`.
   - Request counts, approval queue length, daily/monthly cost from PostgreSQL audit log.
   - External Services grid with per-service status.
   - Recent System Events (last 10) from audit log.
   - No business data: no query text, no report content, no evidence.
2. **Connectors & APIs** (`/admin/connectors`)
   - Left panel: 10 services with status pills.
   - Right detail panel: per-service metadata, `.env` key presence indicators only (C-6).
   - `[Test connection]` sends read-only probe.
   - n8n workflow status: `empty` vs `deployed`.
3. **Permissions & Roles** (`/admin/permissions`)
   - Tab 1: Role Matrix read-only (from `docs/security/rbac_matrix.md`).
   - Tab 2: Entra Group Mapping editor with inline row editing and audit logging.
   - Tab 3: Project Role Assignments read-only (from `project_source_mapping.json`).
4. **Source Mapping** (`/admin/source-mapping`)
   - Left: project list. Right: project editor.
   - Client-side JSON schema validation.
   - Diff preview modal before save.
   - Confirmation modal for role removal or project deletion.
   - Audit events: `admin.source_mapping_changed`, `admin.source_mapping_deleted`.
5. **Approval Queue** (`/admin/approvals`)
   - Show `staging` and `needs_review` reports only.
   - Columns: request ID, project, status, submitted at, requester hash.
   - Admin review panel: QG flags and metadata only. No report content (C-1).
   - Admin override approve/reject with mandatory comment.
   - Block admin from approving own requests.
6. **Audit Log** (`/admin/audit`)
   - Filterable, paginated system event log.
   - Search by request_id or user_hash.
   - Event detail panel with token counts and cost visible to admin only.
   - CSV export with cost/token columns redacted for non-admin.
7. **System Health** (`/admin/health`)
   - Live service status table with latency and sparkline trends.
   - Cost Monitor with daily/monthly progress bars.
   - Yellow warning at 80% daily cost; red banner at 100%.
   - Auto-refresh configurable interval.

**Validation gate before 2C:**
- A-01 through A-17 acceptance criteria from UI_CONTRACT Section 9.2 pass in manual QA.
- Non-admin JWT receives HTTP 403 on all `/admin/*` routes.
- No credential values shown in any form (C-6).
- Admin review panel never shows report content, query text, or evidence excerpts.
- Destructive actions require typed confirmation and write audit events before execution.

---

## Phase 2C — UI Hardening & Acceptance Validation

**Goal:** Prove the UI meets the locked UI contract before go-live.

**Scope:**
1. Accessibility audit: keyboard navigation, focus management, ARIA labels for all interactive elements.
2. Responsive audit: minimum 768px width, sidebar collapse, detail panel behavior.
3. Security audit:
   - Verify no credential values in DOM (C-6).
   - Verify `quality_gate = "failed"` removes Export Panel from DOM entirely.
   - Verify `admin` role cannot access `/workspace/report/{id}` content.
4. Performance audit:
   - Initial bundle size < 500 KB gzipped.
   - Report View render < 200 ms for reports with ≤50 evidence items.
   - Processing View progress updates smooth at 60 fps.
5. Cross-browser test: Chrome, Firefox, Edge (latest 2 versions).
6. End-to-end automation: Cypress or Playwright tests for the golden path:
   - Login → Query Composer → Submit → Processing → Report View → Approve → Final → Download.
7. Add `make test:ui` target to CI (headless browser run).

**Validation gate before Production:**
- All U-01..U-16 and A-01..A-17 acceptance criteria pass in automated or manual QA.
- `make test:ui` passes in CI.
- No P0 or P1 UI defects remain open.
- Security audit sign-off: no credential leakage, no admin content bypass.

---

## Complete Phase Dependency Graph

```
1A → 1B → 1C → 1D → 1D-fixup → 1E → 1F → 1G → 1H
                                ↓    ↓    ↓    ↓
                                └────┴────┴────┘ → 1I (static scaffolds)
                                                   ↓
                                                  2A (user workspace)
                                                   ↓
                                                  2B (admin control plane)
                                                   ↓
                                                  2C (UI hardening)
```

**Critical path:** 1A → 1B → 1C → 1D → 1D-fixup → 1E → 1F → 2A → 2B → 2C → Production
**Parallel track:** 1I can start after 1B and run in parallel through 1H, but must not wire to APIs until 1F is complete.
