# DecisionCenter — Feature Matrix

> **Source of truth:** `docs/workflows/EDR-AGENTIC-RAG-v2.1.md`
> **Date:** 2026-05-15 (Phase 2B Slice 2 — Connectors & APIs read + probe)
> **Status:** Phases 1A–1I plus the Phase 1D-fixup and Phase 2A are complete. Phase 2B is the safe next phase and is in progress: Slice 1 (admin RBAC base) is complete and CI-green. Subsequent slices are gated on explicit per-slice user approval. Production is `NOT_LIVE`.
> **Control-plane lock:** `docs/admin/CONTROL_PLANE_LOCK.md`
> **RBAC lock:** `docs/security/rbac_matrix.md` uses the spec's 9 canonical roles.

---

## Legend

| Status | Meaning |
|--------|---------|
| `missing` | No file, no code, no plan beyond spec |
| `documented-only` | Spec and planning docs exist; no implementation |
| `partial` | Skeleton or stub exists; not functional |
| `implemented` | Complete and validated against spec |
| `blocked` | Cannot proceed due to upstream blocker |

---

## Graph Nodes (18 total)

| Feature | Spec Section | Graph Node / API | RBAC Role | Schema / Model | Audit Event | Validation Proof | Status |
|---------|--------------|------------------|-----------|----------------|-------------|------------------|--------|
| Workflow begin | 16.0 | `node_00_begin.py` | All | `DecisionState` | `node: begin` | `make smoke` node count = 18 | implemented |
| Auth and RBAC Gate | 16.1, 8, 9 | `node_01_auth.py` | All | `DecisionState` | `node: auth` | integration tests: valid role/project authorized; admin/auditor/unknown project denied | implemented |
| Intent Classifier (Light) | 16.2 | `node_02_intent.py` | All | `DecisionState.outputs["intent"]` | `node: intent` | Haiku 4.5 call with prompt-injection sanitization; `test_phase1e.py` covers 2 cases | implemented |
| Scope Resolver (Light) | 16.3 | `node_03_scope.py` | All | `DecisionState.outputs["scope"]` | `node: scope` | Haiku 4.5; `test_phase1e.py` covers 1 case | implemented |
| Retrieval Plan (Light) | 16.4 | `node_04_plan.py` | All | `DecisionState.outputs["plan"]` | `node: plan` | Haiku 4.5; `test_phase1e.py` covers 2 cases | implemented |
| SharePoint Retrieval | 16.5, 4.1 | `node_05_sharepoint.py` | Per `docs/security/rbac_matrix.md` | `EvidenceObject` | `node: sharepoint` | connector + retrieval tests | implemented |
| ownCloud Retrieval | 16.6, 4.2 | `node_06_owncloud.py` | Per `docs/security/rbac_matrix.md` | `EvidenceObject` | `node: owncloud` | connector tests + service-account credential test | implemented |
| Email Retrieval | 16.7, 4.3, 10 | `node_07_email.py` | Per `docs/security/rbac_matrix.md` | `EvidenceObject` | `node: email` | mailbox-allowlist tests + connector tests | implemented |
| Odoo Facts Retrieval | 16.8, 4.4 | `node_08_odoo.py` | Per `docs/security/rbac_matrix.md` | `EvidenceObject` | `node: odoo` | json-domain injection test + connector tests | implemented |
| Normalize & Deduplicate | 16.9, 13 | `node_09_normalize.py` | All | `EvidencePack` | `node: normalize` | dedup priority preservation | implemented |
| Evidence Sufficiency Check | 16.10 | `node_10_sufficiency.py` | All | `DecisionState.outputs["sufficiency"]` | `node: sufficiency` | financial-keyword and source-count check | implemented |
| Self-Correction Loop | 16.11, 17 | `node_11_self_correct.py` | All | `DecisionState.outputs["corrected"]` | `node: self_correct` | max 3 iterations enforced; `test_phase1e.py` covers 2 cases | implemented |
| Draft JSON Report (Heavy) | 16.12, 14, 15 | `node_12_draft_json.py` | All | `ExecutiveDecisionReport` | `node: draft_json` | Sonnet 4.6 with evidence-bound JSON; deterministic fallback; `test_phase1e.py` covers 2 cases | implemented |
| Quality Gate | 16.13, 17 | `node_13_quality_gate.py` | All | `QualityGateResult` | `node: quality_gate` | deterministic checker; rejects unsupported claims and missing-Odoo financials; `test_phase1e.py` covers 4 cases | implemented |
| Compose Markdown Report | 16.14 | `node_14_compose_md.py` | All | `DecisionState.outputs["exported_reports"]` | `node: compose_md` | export blocked unless `quality_gate == "passed"` (regression test); 5 formats verified | implemented |
| Save & Audit | 16.15 | `node_15_save_audit.py` | All | `AuditLog` | `node: save_audit` | MinIO + PostgreSQL persistence; includes internal `report-draft.json` when a draft exists; hashed-user-id invariant tested | implemented |
| Human Review Gate | 16.16 | `node_16_review.py` | Approval roles per `docs/security/rbac_matrix.md` | `DecisionState.outputs["human_review_status"]` | `node: review` | reads PG `review_decisions`; `test_phase1g.py` covers pending/approved/rejected/revision_requested | implemented |
| Publish to /final | 16.17 | `node_17_publish.py` | Approval roles per `docs/security/rbac_matrix.md` | `DecisionState.outputs["publish_status"]` | `node: publish` | write-once `copy_to_final` (`FileExistsError`) + single `approval-log.json`; `test_phase1g.py` covers immutability | implemented |

---

## API Endpoints

| Feature | Spec Section | Endpoint | RBAC Role | Schema / Model | Audit Event | Validation Proof | Status |
|---------|--------------|----------|-----------|----------------|-------------|------------------|--------|
| Health check | 27 | `GET /healthz` | All (unauthenticated) | Service status JSON | None | health proof + CI smoke | implemented |
| Stage report | 27 | `POST /reports/staging` | Report-capable roles only | `ReportRequest` → `DecisionState` | `request_id` generated (UUID) | smoke + RBAC integration tests | implemented |
| Download staging report | 27 | `GET /reports/staging/{id}/download/{fmt}` | Request owner or auditor; admin denied; blocked when approval required and `review_state != approved` | MIME type response | `download` event | `test_phase1f.py` + `test_phase1g.py` + Phase 2A admin-denial regression | implemented |
| Approve report | 27, 16.16 | `POST /reports/staging/{id}/approve` | Approval roles per `docs/security/rbac_matrix.md`; admin uses `admin_override` with mandatory comment; auditor blocked; self-approval blocked | Approval record | `approval` event | `test_phase1g.py` | implemented |
| Reject report | 27, 16.16 | `POST /reports/staging/{id}/reject` | Approval roles per `docs/security/rbac_matrix.md`; auditor blocked; self-rejection blocked | Rejection record (reason required) | `rejection` event | `test_phase1g.py` | implemented |
| Request revision | 27, 16.16 | `POST /reports/staging/{id}/request-revision` | Approval roles per `docs/security/rbac_matrix.md`; auditor blocked; self-request blocked | Revision record (reason required, optional comment) | `revision_requested` event | `test_phase1g.py` | implemented |
| Download final report | 27 | `GET /reports/final/{id}/download/{fmt}` | Request owner or auditor; admin denied; only when `review_state == final` | MIME type response | `download` event | `test_phase1g.py` + Phase 2A admin-denial regression | implemented |
| Workspace context | 27, UI_CONTRACT §2.1 | `GET /workspace/context` | Report-capable roles receive allowed projects; admin denied; non-generating roles get empty project set | `WorkspaceContextResponse` | None | `test_phase2a_backend.py` | implemented |
| List reports | 27, PHASE_2A_PLAN §F.2 | `GET /reports` | Own `user_id_hash` for normal roles; auditor sees all (read-only); admin denied | `ReportListResponse` (paginated `ReportSummary`) | None (read-only) | `test_phase2a_backend.py` (6 cases) | implemented |
| Get report metadata | 27, PHASE_2A_PLAN §F.2 | `GET /reports/{id}` | Owner or auditor; admin denied | `ReportDetail` + `ReviewDecisionView` history | None (read-only) | `test_phase2a_backend.py` (5 cases) | implemented |
| Get report status | 27, PHASE_2A_PLAN §F.2 | `GET /reports/{id}/status` | Owner or auditor; admin denied | `ReportStatusResponse` (state + node progress) | None (read-only) | `test_phase2a_backend.py` (3 cases) | implemented |
| Get report content | 27, UI_CONTRACT §2.3 | `GET /reports/{id}/content` | Owner, auditor, or authorized reviewer; admin denied; needs-review requester sees flags only | `ReportContentResponse` + evidence entries | None (read-only) | `test_phase2a_backend.py` | implemented |
| Cancel report | 27, PHASE_2A_PLAN §F.2 | `DELETE /reports/{id}` | Requester only; admin denied; blocked on terminal states (final/rejected/cancelled) | `CancelReportResponse`; writes `report.cancelled` review_decision | `report.cancelled` event | `test_phase2a_backend.py` | implemented |
| Upload attachment | 27, PHASE_2A_PLAN §F.2 | `POST /upload` | Authenticated non-admin; per-file ≤10 MB; type allowlist (PDF/DOCX/XLSX/TXT/MSG/EML) | `UploadResponse` (upload_id, sha256 hash); persisted under `uploads/{user_id_hash}/{upload_id}/{filename}` | None (storage only) | `test_phase2a_backend.py` | implemented |
| Admin auth-check | 27, PHASE_2B_PLAN §C.2, UI_CONTRACT §4.3 | `GET /admin/_authcheck` | Admin only (`_require_admin`); 403 for all 8 other canonical roles; 401 when claims absent | `{"ok": true, "role": "admin"}` — no business data, no credential values | None (read-only) | `test_phase2b_admin_rbac.py` (13 cases) | implemented |
| Admin connector list | 27, PHASE_2B_PLAN §C.2 | `GET /admin/services` | Admin only; 403 non-admin | `list[ServiceSummary]` — env key presence only, no values | None (read-only) | `test_phase2b_connectors.py` (45 cases) | implemented |
| Admin connector detail | 27, PHASE_2B_PLAN §C.2 | `GET /admin/services/{name}` | Admin only; 404 unknown service | `ServiceDetail` — last probe, latency, workflow node count | None (read-only) | `test_phase2b_connectors.py` | implemented |
| Admin connector probe | 27, PHASE_2B_PLAN §C.2 | `POST /admin/services/{name}/probe` | Admin only; 404 unknown service; read-only probe | `ProbeResult` — pass/fail + latency; writes `connector.probe_success` or `connector.error` | `connector.probe_success`, `connector.error`, `connector.latency_spike` | `test_phase2b_connectors.py` | implemented |
| Admin health live | 27, PHASE_2B_PLAN §C.2, UI_CONTRACT §3.7 | `GET /admin/health/live` | Admin only; per-service live probe latencies + 24h sparkline buckets from `connector_events` | `HealthLiveResponse` — no business content, no credentials | None (read-only) | `test_phase2b_health_cost.py` (28 cases) | implemented |
| Admin cost monitor | 27, PHASE_2B_PLAN §C.2, UI_CONTRACT §3.7 | `GET /admin/cost` | Admin only; daily/monthly caps, LLM call breakdown, warning/exceeded flags; emits `cost.daily_cap_warning` / `cost.daily_cap_exceeded` events | `CostResponse` — no business content, no credentials | `cost.daily_cap_warning`, `cost.daily_cap_exceeded` | `test_phase2b_health_cost.py` | implemented |
| Admin audit log list | 27, PHASE_2B_PLAN §C.2, UI_CONTRACT §3.8 | `GET /admin/audit` | Admin only; paginated, filterable by date/type; hard limit ≤ 200; UNION over audit_log, review_decisions, connector_events, admin_events | `AuditEventListResponse` — no query, no evidence, no report content | None (read-only) | `test_phase2b_audit.py` (18 cases) | implemented |
| Admin audit log export | 27, PHASE_2B_PLAN §C.2 | `GET /admin/audit/export.csv` | Admin only; CSV of up to 200 events | `text/csv` — no query, no evidence, no report content | None (read-only) | `test_phase2b_audit.py` | implemented |
| Admin audit log detail | 27, PHASE_2B_PLAN §C.2 | `GET /admin/audit/{event_id}` | Admin only; 404 if unknown composite id | `AuditEventDetail` — no query, no evidence, no report content | None (read-only) | `test_phase2b_audit.py` | implemented |

---

## Retrieval & Vector Infrastructure

| Feature | Spec Section | Component | RBAC Role | Schema / Model | Audit Event | Validation Proof | Status |
|---------|--------------|-----------|-----------|----------------|-------------|------------------|--------|
| Token-based chunking | 19.1 | `apps/edr/retrieval/chunking.py` | N/A | `list[str]` | None | tiktoken-based 500–800 tokens, 100–150 overlap; char fallback only when tiktoken unavailable | implemented |
| Embedding | 19.2 | `apps/edr/retrieval/embeddings.py` | N/A | `list[float]` (1024-dim) | token count | Voyage-3-large async client; mock-backed integration test | implemented |
| Vector store (Qdrant) | 19.3 | `apps/edr/retrieval/qdrant_store.py` | N/A | Collection per `project_code` (`edr_*`) | None | init script delegates to runtime naming; round-trip test passes | implemented |
| Hybrid search (RRF) | 19.4 | `apps/edr/retrieval/hybrid_search.py` | N/A | Ranked `EvidenceObject` list | None | unit test: fusion rank | implemented |
| Reranking | 19.5 | `apps/edr/retrieval/rerank.py` | N/A | Ranked `EvidenceObject` list (top 10) | None | Cohere Rerank 3.5 async client; truncate-to-10 test | implemented |
| Query expansion | 19.6 | Not yet created | N/A | Expanded query strings | None | future phase | missing |
| RBAC-aware caching | 19.7 | `apps/edr/retrieval/cache.py` | N/A | Cache key includes `user_id` and `project_code` | None | unit test: key format with RBAC fingerprint | implemented |
| Qdrant collection init | 19.3 | `scripts/init_qdrant.py` | Admin | Collection config | `init_qdrant` | idempotent run + alignment test with runtime naming | implemented |
| MinIO bucket init | 20.4 | `scripts/init_minio.py` | Admin | Bucket | `init_minio` | idempotent create; runtime `_ensure_bucket()` covers any missed init | implemented |

---

## Connectors (n8n Workflows)

| Feature | Spec Section | Workflow File | RBAC Role | Output Schema | Audit Event | Validation Proof | Status |
|---------|--------------|---------------|-----------|---------------|-------------|------------------|--------|
| SharePoint search | 4.1, 16.5 | `n8n/sharepoint_search.json` | Service account (Header Auth) | `EvidenceObject` | `connector: sharepoint` | schema validation + header-auth test | implemented |
| Email search | 4.3, 16.7 | `n8n/email_search.json` | Service account (Header Auth) | `EvidenceObject` (excerpt ≤500 chars) | `connector: email` | mailbox-allowlist enforce + schema validation | implemented |
| ownCloud list | 4.2, 16.6 | `n8n/owncloud_list.json` | Service account via `$env.OWNCLOUD_*` | `EvidenceObject` | `connector: owncloud` | $env-only credential test | implemented |
| Odoo read | 4.4, 16.8 | `n8n/odoo_read.json` | Service account via `$env.ODOO_*` | `EvidenceObject` | `connector: odoo` | $env-only credential test + JSON-domain injection test | implemented |

---

## Export Formats

| Feature | Spec Section | Component | RBAC Role | Schema / Model | Audit Event | Validation Proof | Status |
|---------|--------------|-----------|-----------|---------------|-------------|------------------|--------|
| Markdown export | 3.3, 16.14 | `apps/edr/exporters/markdown.py` | All | `.md` file | `export: md` | exporter wired into `node_14_compose_md`; gated by `quality_gate=="passed"` | implemented |
| Word export | 3.3, 16.14 | `apps/edr/exporters/word.py` | All | `.docx` file | `export: docx` | exporter wired; format selection via `output_formats` | implemented |
| Excel export | 3.3, 16.14 | `apps/edr/exporters/excel.py` | All | `.xlsx` file | `export: xlsx` | exporter wired; format selection via `output_formats` | implemented |
| PDF export | 3.3, 16.14 | `apps/edr/exporters/pdf.py` | All | `.pdf` file | `export: pdf` | exporter wired with Arabic font auto-selection | implemented |
| PowerPoint export | 3.3, 16.14 | `apps/edr/exporters/powerpoint.py` | All | `.pptx` file | `export: pptx` | exporter wired; format selection via `output_formats` | implemented |
| Arabic RTL PDF | 29 | `apps/edr/exporters/pdf.py` | All | `.pdf` with Arabic TTF | `export: pdf` | Amiri font registered, Arabic auto-detected, RTL disclaimer appended; `test_pdf_arabic.py` (7 cases); full bidi shaping/reshaping deferred | partial |

---

## Schemas & Data Models

| Feature | Spec Section | File | RBAC Role | Schema / Model | Audit Event | Validation Proof | Status |
|---------|--------------|------|-----------|---------------|-------------|------------------|--------|
| Evidence Object | 12 | `docs/schemas/evidence-object.schema.json` | N/A | JSON Schema | None | schema test (1C) | implemented |
| Evidence Pack | 12 | `docs/schemas/evidence-pack.schema.json` | N/A | JSON Schema | None | schema test | implemented |
| Executive Report | 14, 15 | `docs/schemas/executive-decision-report.schema.json` | N/A | JSON Schema | None | schema test (1E) | implemented |
| Audit Log | 21 | `docs/schemas/audit-log.schema.json` | N/A | JSON Schema | None | schema test | implemented |
| Quality Gate Result | 17 | `docs/schemas/quality-gate-result.schema.json` | N/A | JSON Schema | None | schema test (1E) | implemented |
| Evidence Object (Pydantic) | 12 | `apps/edr/schemas/evidence.py` | N/A | `EvidenceObject` (metadata accepts scalars + lists) | None | nested-dict rejection + list metadata test | implemented |
| Evidence Pack (Pydantic) | 12 | `apps/edr/schemas/evidence.py` | N/A | `EvidencePack` | None | import + typecheck | implemented |
| Executive Report (Pydantic) | 14, 15 | `apps/edr/schemas/report.py` | N/A | `ExecutiveDecisionReport` | None | import + typecheck | implemented |
| Audit Log (Pydantic) | 21 | `apps/edr/schemas/audit.py` | N/A | `AuditLog` | None | import + typecheck | implemented |
| Quality Gate (Pydantic) | 17 | `apps/edr/schemas/quality_gate.py` | N/A | `QualityGateResult` | None | import + typecheck | implemented |

---

## Infrastructure & DevOps

| Feature | Spec Section | Component | RBAC Role | Schema / Model | Audit Event | Validation Proof | Status |
|---------|--------------|-----------|-----------|---------------|-------------|------------------|--------|
| Configuration loading | 20 | `apps/edr/config.py` | N/A | `Settings` (Pydantic) | None | field count = 40 (CI asserts) | implemented |
| Dependency version pins | 20 | `pyproject.toml` | N/A | N/A | None | exact pins; PyJWT 2.12.0, cryptography 44.0.1, python-dotenv 1.2.2, anthropic 0.42.0, asyncpg 0.29.0 | implemented |
| CI/CD pipeline | 26.4 | `.github/workflows/ci.yml` | N/A | N/A | None | ruff + compileall + config coverage + doc-drift (incl. anchor-currency invariant) + AI-context + smoke + integration + evaluation suite + frontend lint/build + pip-audit | implemented |
| Async workflow runtime | 16 | `apps/edr/graph/runner.py`, all graph nodes | N/A | async `DecisionState` pipeline | None | tests invoke async runner/nodes with `asyncio.run()` | implemented |
| Docker Compose stack | 23 | `docker-compose.yml` | N/A | 7 services with healthchecks | None | internal services on compose network only; public ports on 127.0.0.1 | implemented |
| Reverse proxy | 23 | `Caddyfile` | N/A | Caddy config with HSTS | None | TLS via `PUBLIC_HOSTNAME`; `:80` fallback for local | implemented |
| PostgreSQL persistence | 20.4 | `apps/edr/persistence/postgres_store.py` + `docker-compose.yml` | N/A | `audit_log` + `review_decisions` (idempotent schema) | `audit_persisted`, `review_decision` | `pg_isready` healthcheck; `test_phase1f.py` + `test_phase1g.py` | implemented |
| Redis caching | 20.4 | `docker-compose.yml` | N/A | Redis key-value | N/A | `redis-cli ping` healthcheck; cache wired in 1D | implemented |
| MinIO object storage | 20.4 | `apps/edr/persistence/minio_store.py` + `scripts/init_minio.py` + `docker-compose.yml` | N/A | `/staging`, `/final` prefixes; configured bucket | N/A | health endpoint healthcheck; idempotent init script; runtime `_ensure_bucket()` | implemented |
| Qdrant vector store | 20.4 | `docker-compose.yml`, `scripts/init_qdrant.py` | N/A | per-project collections | N/A | round-trip test + init script | implemented |
| n8n orchestration | 20.2 | `docker-compose.yml` | N/A | 4 workflow files (Header Auth); `N8N_TIMEOUT` bounds connector calls | N/A | mocked workflow + auth-required test; CI uses `N8N_TIMEOUT: 5` | implemented |
| Langfuse tracing | 21.1 | `apps/edr/llm.py`, `.env.example` | N/A | Trace + span | token count | every LLM call hooked; falls back when `LANGFUSE_*` keys unset; live dashboard verification deferred (see gap G9) | partial |
| Cost cap enforcement | 18, 22 | `apps/edr/llm.py` (`_CostTracker`, `CostCapExceededError`, `TokenCapExceededError`) | N/A | `daily_cost_cap_usd`, per-tier token caps | `cost_exceeded` | pre-call estimate raises before every LLM call; load test exercises the deterministic fallback path | implemented |

---

## Policies (Enforcement Required)

| Feature | Spec Section | Policy Document | RBAC Role | Enforcement Point | Audit Event | Validation Proof | Status |
|---------|--------------|-----------------|-----------|-------------------|-------------|------------------|--------|
| RBAC enforcement | 8, 9 | `docs/security/rbac_matrix.md` + `apps/edr/rbac/roles.py` | All | Node 01 before retrieval; review endpoints; download endpoints | `rbac_denied` | integration tests for authorized, denied, and unknown project cases; reviewer/auditor/admin paths | implemented |
| Evidence priority | 6 | `docs/policies/evidence_priority_policy.md` | All | Node 09 | `priority_assigned` | source priority preserved on dedup | implemented |
| Conflict resolution | 7 | `docs/policies/conflict_resolution_policy.md` | All | Node 09 / Node 12 | `conflict_flagged` | golden set covers conflicting evidence category | implemented |
| Email excerpt limit | 4.3, 10 | `docs/policies/email_retrieval_policy.md` | All | Node 07 / n8n | `email_excerpt` | length ≤500 chars in n8n normalize | implemented |
| Mailbox allowlist | 10 | `docs/policies/shared_mailbox_access_policy.md` | All | Node 07 (Python) + n8n `Enforce Mailbox Allowlist` | `mailbox_access` | denial regression tests | implemented |
| Financial truth | 4.4 | `docs/policies/odoo_financial_truth_policy.md` | All | Node 12 / Node 13 | `finance_verified` | quality gate rejects financial values without Odoo `evidence_id`; `test_phase1e.py` covers it | implemented |
| Prompt injection guard | 24.1 | `docs/policies/prompt_injection_policy.md` | All | Every LLM node via `apps/edr/llm.py` `sanitize_evidence` | `injection_blocked` | 11 regex patterns; `test_phase1e.py` blocks 3 patterns | implemented |
| Data minimization | 24.2 | `docs/policies/data_minimization_policy.md` | All | Every retrieval node + audit artifact | `minimization_check` | `audit-log.json` contains metadata only; raw user_id is hashed; `test_phase1f.py` asserts no raw id stored | implemented |
| Disaster recovery | 25 | `docs/policies/disaster_recovery_policy.md` | Admin | Operations | `dr_test` | runbook execution | documented-only |

---

## Observability & Operations

| Feature | Spec Section | Document / Code | RBAC Role | Schema / Model | Audit Event | Validation Proof | Status |
|---------|--------------|-----------------|-----------|---------------|-------------|------------------|--------|
| Tracing | 21.1 | `docs/operations/observability.md` + `apps/edr/llm.py` | N/A | Langfuse traces | `trace` | LLM-call hook present; live dashboard check deferred (gap G9) | partial |
| Metrics | 21.2 | `docs/operations/observability.md` | N/A | Prometheus-style | `metric` | endpoint check deferred | documented-only |
| Alerts | 21.3 | `docs/operations/observability.md` | N/A | Alert rules | `alert_fired` | simulated failure deferred | documented-only |
| Logs | 21.4 | `docs/operations/observability.md` | N/A | Structured JSON | `log` | `request_id` correlation check deferred | documented-only |
| Runbook | 21 | `docs/operations/runbook.md` | Admin | N/A | N/A | manual review | implemented |
| Hosting guide | 23 | `docs/operations/hosting.md` | Admin | N/A | N/A | manual review | implemented |
| Cost model | 22 | `docs/operations/cost_model.md` | Admin | N/A | N/A | manual review | implemented |
| Backup & restore | 23.4, 25 | `docs/operations/backup_restore.md` | Admin | N/A | N/A | manual review | implemented |

---

## Evaluation & Testing

| Feature | Spec Section | Component | RBAC Role | Schema / Model | Audit Event | Validation Proof | Status |
|---------|--------------|-----------|-----------|---------------|-------------|------------------|--------|
| Smoke tests | 26 | `apps/edr/tests/smoke/test_smoke.py` | N/A | N/A | N/A | `make smoke` passes (2 cases) | implemented |
| Integration tests | 26 | `apps/edr/tests/integration/*.py` | N/A | N/A | N/A | `make test`: 184 passed with smoke, integration, evaluation, load, PDF, Phase 2A backend/content regressions, and doc drift | implemented |
| Golden set | 26.1 | `apps/edr/evaluation/goldenset/goldenset.jsonl` | N/A | 64 executable cases | N/A | `make eval`: 64/64 passed, pass rate 100.00%, precision 92.19% | implemented |
| Evaluation runner | 26.4 | `apps/edr/evaluation/run.py` | N/A | JSONL loader, per-case metrics, aggregate report, non-zero on regression | N/A | `make eval` exits 0 in CI | implemented |
| Load test | 26 | `apps/edr/evaluation/load_test.py` | N/A | Local-only deterministic fallback; latency percentiles | N/A | `test_load_test.py` (5 cases); `make load-test` baseline; no permanent thresholds | implemented |
| Test cases spec | 26.1 | `docs/evaluation/edr_test_cases.md` | N/A | 12 baseline categories defined | N/A | N/A | implemented |
| Metrics spec | 26.2 | `docs/evaluation/edr_metrics.md` | N/A | Precision, faithfulness, RBAC denial, QG false-pass | N/A | N/A | implemented |
| Golden set spec | 26.1 | `docs/evaluation/edr_goldenset.md` | N/A | JSONL format | N/A | N/A | implemented |
| Promptfoo config | 26.4 | `apps/edr/evaluation/promptfoo.config.yaml` | N/A | Structured placeholder with providers and test categories | N/A | Awaiting promptfoo CLI availability; CI does not gate on it | partial |

---

## Frontend & UI (Phases 1I–2C)

Source of truth: `docs/design/UI_CONTRACT_v1.md`. Frontend foundation and
static scaffolds are complete in Phase 1I. Phase 2A user workspace
implementation and the U-01..U-16 manual QA closeout are complete. See
`docs/execution/IMPLEMENTATION_PHASES.md` for the full phase scope and
`docs/execution/PHASE_2A_REPORT.md` for the closeout report.

| Feature | Route / Component | Backend integration | Validation proof | Status |
|---|---|---|---|---|
| Frontend foundation | `frontend/` | N/A | Phase 1I CI closeout | implemented |
| API client foundation | `frontend/src/api/*` | Controlled `fetch` wrapper with dev role header wiring | Commit `840e954`; CI green | implemented |
| Query Composer submit | `/workspace/new` | Live `GET /workspace/context` + `POST /reports/staging`; project dropdown is backend role-scoped | Phase 2A U-01/U-02/U-04 QA; frontend lint/build | implemented |
| Reports List | `/workspace/reports` | Live `GET /reports` with role-scoped filters | Phase 2A U-03 QA; frontend lint/build | implemented |
| Processing View | `/workspace/report/{request_id}/processing` | Live `GET /reports/{id}/status` and `DELETE /reports/{id}` | Phase 2A U-05/U-16 QA; `make phase2a-e2e` | implemented |
| Report View | `/workspace/report/{request_id}` | Live `GET /reports/{id}/content`; review actions use existing approval endpoints | Phase 2A U-06/U-07/U-08/U-09/U-14/U-15 QA | implemented |
| Evidence Panel | Slide-in from Report View | Evidence entries come from `GET /reports/{id}/content` | Phase 2A U-10/U-11 QA | implemented |
| Export Panel | Slide-in from Report View | Live downloads via `GET /reports/{staging,final}/{id}/download/{fmt}`; rendered only for approved/final non-failed reports | Phase 2A U-06/U-08 QA | implemented |
| Upload Zone | Query Composer | Frontend validates before upload; backend `POST /upload` enforces matching 10 MB and type rules | Phase 2A U-12/U-13 QA | implemented |
| Routing integration + role guards | `frontend/src/routing/*`, `Sidebar`, `Topbar` | UX-only guards; server enforces RBAC | Commit `a5aedfc`; CI run `25798446018` success | implemented |
| Error handling polish | `frontend/src/components/ToastProvider.tsx` + workspace screens | Network-error and inline-error surfaces unified | Commit `e37b0c1`; CI run `25799899473` success | implemented |
| Phase 2A validation gate | E2E + U-01..U-16 manual QA | Complete | `docs/execution/PHASE_2A_REPORT.md` | implemented |
| Admin System Health screen | `/admin/health` | Live `GET /admin/health/live` + `GET /admin/cost`; auto-refresh; sparklines; cost banners with warning/exceeded thresholds | Phase 2B Slice 3; frontend lint/build | implemented |
| Admin Connectors screen | `/admin/connectors` | Live `GET /admin/services`, `GET /admin/services/{name}`, `POST /admin/services/{name}/probe` | Phase 2B Slice 2; frontend lint/build | implemented |
| Admin Audit Log screen | `/admin/audit` | Live `GET /admin/audit`, `GET /admin/audit/export.csv`, `GET /admin/audit/{event_id}`; filters, pagination, CSV export, detail panel | Phase 2B Slice 4; frontend lint/build | implemented |

---

## Pip-audit Triage (Decided in Phase 1H — Promotion Still Deferred)

`pip-audit` runs in CI as `continue-on-error: true`. Phase 1H triaged the
advisories present against the pinned dependency set: the safe pins were
upgraded — `cryptography` 44.0.0 → 44.0.1, `python-dotenv` 1.0.0 → 1.2.2,
`PyJWT` 2.10.1 → 2.12.0 — and the remaining advisories (major-version bumps on
the LangChain/LangGraph stack, Starlette, and pytest) were accepted as deferred
to avoid regressing tested behavior. Promotion of `pip-audit` from advisory to a
hard CI gate remains deferred to a later phase. See
`docs/execution/PHASE_1H_REPORT.md` for the closeout decision.

The table below is the **pre-triage advisory snapshot**; the "Pinned" column
reflects the versions in effect when the triage was performed.

| Package | Pinned (pre-triage) | Advisory IDs | Suggested fix |
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

---

## Identified Gaps

| ID | Gap | Location | Impact | Phase to Fix |
|----|-----|----------|--------|--------------|
| G4 | No `frontend/` directory exists | Repository root | No UI codebase to scaffold | Closed in 1I |
| G5 | No `make test:ui` target in Makefile | `Makefile` | No CI gate for UI acceptance | 2C |
| G9 | Langfuse dashboard not yet observed live | `apps/edr/llm.py` | Tracing hook exists; trace correctness in production-like config not validated | Later phase (2+) |
| G10b | Arabic PDF lacks bidirectional shaping/reshaping | `apps/edr/exporters/pdf.py` | RTL text is not reshaped; a disclaimer is appended | Later phase (2+) |
| G11 | `pip-audit` not promoted to a hard CI gate | `.github/workflows/ci.yml` | 19 advisories on 9 packages accepted as deferred; gate stays `continue-on-error` | Later phase (2+) |
| G12 | Phase 2A backend read/status/cancel/upload endpoint gap | `apps/edr/app.py` | Reports List, Processing, Report View, Evidence Panel, Upload Zone originally rendered unavailable shells | Closed in Phase 2A backend additions and final QA blocker fixes |
| G13 | Phase 2A validation gate (E2E + U-01..U-16 manual QA) not exercised | Manual QA / running stack | Phase 2A could not be marked fully complete until the gate was run | Closed in Phase 2A manual QA closeout |

Closed gaps:
- G1 (nodes 11–17 stubs) — closed by Phase 1E/1F/1G.
- G2 (MinIO bucket init) — closed by `scripts/init_minio.py` and runtime `_ensure_bucket()`.
- G3 (only one executable golden example) — closed in Phase 1H: executable `goldenset.jsonl`; stale `example.jsonl` deleted.
- G6 (Langfuse unwired) — closed in Phase 1E (tracing hook present); live dashboard validation tracked as G9 above.
- G7 (cost cap not load-tested) — closed in Phase 1H: `load_test.py` exercises the deterministic path; baseline recorded.
- G8 (pip-audit advisories untriaged) — closed in Phase 1H: triage completed, safe pins upgraded; hard-gate promotion tracked as G11 above.
- G10 (Arabic RTL PDF render not validated) — closed in Phase 1H: Amiri font, Arabic auto-detection, RTL disclaimer, `test_pdf_arabic.py`; remaining bidi-shaping work tracked as G10b above.
- G12 (Phase 2A backend read/status/cancel/upload endpoints) — closed in Phase 2A backend additions and final QA blocker fixes.
- G13 (Phase 2A validation gate) — closed in Phase 2A manual QA closeout: E2E and U-01..U-16 passed.
