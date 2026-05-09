# DecisionCenter — Feature Matrix

> **Source of truth:** `docs/workflows/EDR-AGENTIC-RAG-v2.1.md`
> **Date:** 2026-05-09
> **Status:** Phase 1A–1D plus the Phase 1D-fixup are complete; Phase 1E is the safe next phase
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
| Workflow begin | 16.0 | `node_00_begin.py` | All | `DecisionState` | `node: begin` | `make smoke` node count = 18 | partial |
| Auth and RBAC Gate | 16.1, 8, 9 | `node_01_auth.py` | All | `DecisionState` | `node: auth` | integration tests: valid role/project authorized; admin/auditor/unknown project denied | implemented |
| Intent Classifier (Light) | 16.2 | `node_02_intent.py` | All | `DecisionState.outputs["intent"]` | `node: intent` | golden set eval (1H) | partial |
| Scope Resolver (Light) | 16.3 | `node_03_scope.py` | All | `DecisionState.outputs["scope"]` | `node: scope` | golden set eval (1H) | partial |
| Retrieval Plan (Light) | 16.4 | `node_04_plan.py` | All | `DecisionState.outputs["plan"]` | `node: plan` | golden set eval (1H) | partial |
| SharePoint Retrieval | 16.5, 4.1 | `node_05_sharepoint.py` | Per `docs/security/rbac_matrix.md` | `EvidenceObject` | `node: sharepoint` | connector + retrieval tests | implemented |
| ownCloud Retrieval | 16.6, 4.2 | `node_06_owncloud.py` | Per `docs/security/rbac_matrix.md` | `EvidenceObject` | `node: owncloud` | connector tests + service-account credential test | implemented |
| Email Retrieval | 16.7, 4.3, 10 | `node_07_email.py` | Per `docs/security/rbac_matrix.md` | `EvidenceObject` | `node: email` | mailbox-allowlist tests + connector tests | implemented |
| Odoo Facts Retrieval | 16.8, 4.4 | `node_08_odoo.py` | Per `docs/security/rbac_matrix.md` | `EvidenceObject` | `node: odoo` | json-domain injection test + connector tests | implemented |
| Normalize & Deduplicate | 16.9, 13 | `node_09_normalize.py` | All | `EvidencePack` | `node: normalize` | dedup priority preservation | implemented |
| Evidence Sufficiency Check | 16.10 | `node_10_sufficiency.py` | All | `DecisionState.outputs["sufficiency"]` | `node: sufficiency` | financial-keyword and source-count check | implemented |
| Self-Correction Loop | 16.11, 17 | `node_11_self_correct.py` | All | `DecisionState.outputs["corrected"]` | `node: self_correct` | unit test: max 3 iterations (1E) | partial |
| Draft JSON Report (Heavy) | 16.12, 14, 15 | `node_12_draft_json.py` | All | `ExecutiveDecisionReport` | `node: draft_json` | schema validation (1E) | partial |
| Quality Gate | 16.13, 17 | `node_13_quality_gate.py` | All | `QualityGateResult` | `node: quality_gate` | unit test: false-pass blocked (1E) | partial |
| Compose Markdown Report | 16.14 | `node_14_compose_md.py` | All | `DecisionState.outputs["exported_reports"]` | `node: compose_md` | export blocked unless `quality_gate == "passed"` (regression test) | partial |
| Save & Audit | 16.15 | `node_15_save_audit.py` | All | `AuditLog` | `node: save_audit` | MinIO + PostgreSQL verify (1F) | partial |
| Human Review Gate | 16.16 | `node_16_review.py` | Approval roles per `docs/security/rbac_matrix.md` | `DecisionState.outputs["human_review_status"]` | `node: review` | approval flow test (1G) | partial |
| Publish to /final | 16.17 | `node_17_publish.py` | Approval roles per `docs/security/rbac_matrix.md` | `DecisionState.outputs["publish_status"]` | `node: publish` | immutability test (1G) | partial |

---

## API Endpoints

| Feature | Spec Section | Endpoint | RBAC Role | Schema / Model | Audit Event | Validation Proof | Status |
|---------|--------------|----------|-----------|----------------|-------------|------------------|--------|
| Health check | 27 | `GET /healthz` | All (unauthenticated) | Service status JSON | None | health proof + CI smoke | implemented |
| Stage report | 27 | `POST /reports/staging` | Report-capable roles only | `ReportRequest` → `DecisionState` | `request_id` generated (UUID) | smoke + RBAC integration tests | partial |
| Download report | 27 | `GET /reports/staging/{id}/download/{fmt}` | Request owner + approver roles | MIME type response | `download` event | integration test (1F) | partial |
| Approve report | 27, 16.16 | `POST /reports/staging/{id}/approve` | Approval roles per `docs/security/rbac_matrix.md` | Approval record | `approval` event | integration test (1G) | missing |
| Reject report | 27, 16.16 | `POST /reports/staging/{id}/reject` | Approval roles per `docs/security/rbac_matrix.md` | Rejection record | `rejection` event | integration test (1G) | missing |

---

## Retrieval & Vector Infrastructure

| Feature | Spec Section | Component | RBAC Role | Schema / Model | Audit Event | Validation Proof | Status |
|---------|--------------|-----------|-----------|----------------|-------------|------------------|--------|
| Token-based chunking | 19.1 | `apps/edr/retrieval/chunking.py` | N/A | `list[str]` | None | tiktoken-based 500–800 tokens, 100–150 overlap; char fallback only when tiktoken unavailable | implemented |
| Embedding | 19.2 | `apps/edr/retrieval/embeddings.py` | N/A | `list[float]` (1024-dim) | token count | Voyage-3-large async client; mock-backed integration test | implemented |
| Vector store (Qdrant) | 19.3 | `apps/edr/retrieval/qdrant_store.py` | N/A | Collection per `project_code` (`edr_*`) | None | init script delegates to runtime naming; round-trip test passes | implemented |
| Hybrid search (RRF) | 19.4 | `apps/edr/retrieval/hybrid_search.py` | N/A | Ranked `EvidenceObject` list | None | unit test: fusion rank | implemented |
| Reranking | 19.5 | `apps/edr/retrieval/rerank.py` | N/A | Ranked `EvidenceObject` list (top 10) | None | Cohere Rerank 3.5 async client; truncate-to-10 test | implemented |
| Query expansion | 19.6 | Not yet created | N/A | Expanded query strings | None | eval test (1H) | missing |
| RBAC-aware caching | 19.7 | `apps/edr/retrieval/cache.py` | N/A | Cache key includes `user_id` and `project_code` | None | unit test: key format with RBAC fingerprint | implemented |
| Qdrant collection init | 19.3 | `scripts/init_qdrant.py` | Admin | Collection config | `init_qdrant` | idempotent run + alignment test with runtime naming | implemented |

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
| Markdown export | 3.3, 16.14 | `apps/edr/exporters/markdown.py` | All | `.md` file | `export: md` | file content check (1E) | partial |
| Word export | 3.3, 16.14 | `apps/edr/exporters/word.py` | All | `.docx` file | `export: docx` | file content check (1E) | partial |
| Excel export | 3.3, 16.14 | `apps/edr/exporters/excel.py` | All | `.xlsx` file | `export: xlsx` | file content check (1E) | partial |
| PDF export | 3.3, 16.14 | `apps/edr/exporters/pdf.py` | All | `.pdf` file | `export: pdf` | file content check (1E) | partial |
| PowerPoint export | 3.3, 16.14 | `apps/edr/exporters/powerpoint.py` | All | `.pptx` file | `export: pptx` | file content check (1E) | partial |
| Arabic RTL PDF | 29, 1H | `apps/edr/exporters/pdf.py` | All | `.pdf` with Arabic TTF | `export: pdf` | visual render test (1H) | missing |

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
| Configuration loading | 20 | `apps/edr/config.py` | N/A | `Settings` (Pydantic) | None | field count = 39 (CI) | implemented |
| Dependency version pins | 20 | `pyproject.toml` | N/A | N/A | None | exact pins; PyJWT 2.10.1, cryptography 44.0.0 | implemented |
| CI/CD pipeline | 26.4 | `.github/workflows/ci.yml` | N/A | N/A | None | ruff + compileall + config coverage + smoke + integration + pip-audit | implemented |
| Async workflow runtime | 16 | `apps/edr/graph/runner.py`, all graph nodes | N/A | async `DecisionState` pipeline | None | tests invoke async runner/nodes with `asyncio.run()` | implemented |
| Docker Compose stack | 23 | `docker-compose.yml` | N/A | 7 services with healthchecks | None | internal services on compose network only; public ports on 127.0.0.1 | implemented |
| Reverse proxy | 23 | `Caddyfile` | N/A | Caddy config with HSTS | None | TLS via `PUBLIC_HOSTNAME`; `:80` fallback for local | implemented |
| PostgreSQL persistence | 20.4 | `docker-compose.yml` | N/A | `audit_log` table | N/A | `pg_isready` healthcheck; audit writes land in 1F | partial |
| Redis caching | 20.4 | `docker-compose.yml` | N/A | Redis key-value | N/A | `redis-cli ping` healthcheck; cache wired in 1D | implemented |
| MinIO object storage | 20.4 | `docker-compose.yml` | N/A | `/staging`, `/final` buckets | N/A | health endpoint healthcheck; bucket init lands in 1F | partial |
| Qdrant vector store | 20.4 | `docker-compose.yml`, `scripts/init_qdrant.py` | N/A | per-project collections | N/A | round-trip test + init script | implemented |
| n8n orchestration | 20.2 | `docker-compose.yml` | N/A | 4 workflow files (Header Auth) | N/A | mocked workflow + auth-required test | implemented |
| Langfuse tracing | 21.1 | `.env.example` only | N/A | Trace + span | token count | dashboard visible (1E) | missing |
| Cost cap enforcement | 18, 22 | `config.py` fields only | N/A | `daily_cost_cap_usd` | `cost_exceeded` | circuit breaker test (1H) | missing |

---

## Policies (Enforcement Required)

| Feature | Spec Section | Policy Document | RBAC Role | Enforcement Point | Audit Event | Validation Proof | Status |
|---------|--------------|-----------------|-----------|-------------------|-------------|------------------|--------|
| RBAC enforcement | 8, 9 | `docs/security/rbac_matrix.md` + `apps/edr/rbac/roles.py` | All | Node 01 before retrieval | `rbac_denied` | integration tests for authorized, denied, and unknown project cases | implemented |
| Evidence priority | 6 | `docs/policies/evidence_priority_policy.md` | All | Node 09 | `priority_assigned` | source priority preserved on dedup | partial |
| Conflict resolution | 7 | `docs/policies/conflict_resolution_policy.md` | All | Node 09 / Node 12 | `conflict_flagged` | golden set eval (1H) | documented-only |
| Email excerpt limit | 4.3, 10 | `docs/policies/email_retrieval_policy.md` | All | Node 07 / n8n | `email_excerpt` | length ≤500 chars in n8n normalize | implemented |
| Mailbox allowlist | 10 | `docs/policies/shared_mailbox_access_policy.md` | All | Node 07 (Python) + n8n `Enforce Mailbox Allowlist` | `mailbox_access` | denial regression tests | implemented |
| Financial truth | 4.4 | `docs/policies/odoo_financial_truth_policy.md` | All | Node 12 / Node 13 | `finance_verified` | Odoo evidence required (1E) | documented-only |
| Prompt injection guard | 24.1 | `docs/policies/prompt_injection_policy.md` | All | Every LLM node | `injection_blocked` | red-team test (1H) | documented-only |
| Data minimization | 24.2 | `docs/policies/data_minimization_policy.md` | All | Every retrieval node | `minimization_check` | audit field review (1F) | documented-only |
| Disaster recovery | 25 | `docs/policies/disaster_recovery_policy.md` | Admin | Operations | `dr_test` | runbook execution | documented-only |

---

## Observability & Operations

| Feature | Spec Section | Document / Code | RBAC Role | Schema / Model | Audit Event | Validation Proof | Status |
|---------|--------------|-----------------|-----------|---------------|-------------|------------------|--------|
| Tracing | 21.1 | `docs/operations/observability.md` | N/A | Langfuse traces | `trace` | dashboard check (1E) | documented-only |
| Metrics | 21.2 | `docs/operations/observability.md` | N/A | Prometheus-style | `metric` | endpoint check | documented-only |
| Alerts | 21.3 | `docs/operations/observability.md` | N/A | Alert rules | `alert_fired` | simulated failure | documented-only |
| Logs | 21.4 | `docs/operations/observability.md` | N/A | Structured JSON | `log` | grep `request_id` | documented-only |
| Runbook | 21 | `docs/operations/runbook.md` | Admin | N/A | N/A | manual review | implemented |
| Hosting guide | 23 | `docs/operations/hosting.md` | Admin | N/A | N/A | manual review | implemented |
| Cost model | 22 | `docs/operations/cost_model.md` | Admin | N/A | N/A | manual review | implemented |
| Backup & restore | 23.4, 25 | `docs/operations/backup_restore.md` | Admin | N/A | N/A | manual review | implemented |

---

## Evaluation & Testing

| Feature | Spec Section | Component | RBAC Role | Schema / Model | Audit Event | Validation Proof | Status |
|---------|--------------|-----------|-----------|---------------|-------------|------------------|--------|
| Smoke tests | 26 | `apps/edr/tests/smoke/test_smoke.py` | N/A | N/A | N/A | `make smoke` passes | partial |
| Golden set | 26.1 | `apps/edr/evaluation/goldenset/example.jsonl` | N/A | 1 executable case; 12 baseline categories documented; 50 go-live cases required | N/A | `make eval` passes (1H) | partial |
| Evaluation runner | 26.4 | `apps/edr/evaluation/run.py` | N/A | Metrics dict | N/A | `make eval` exits 0 (1H) | partial |
| Test cases spec | 26.1 | `docs/evaluation/edr_test_cases.md` | N/A | 12 baseline categories defined | N/A | N/A | implemented |
| Metrics spec | 26.2 | `docs/evaluation/edr_metrics.md` | N/A | Precision, faithfulness, RBAC denial, QG false-pass | N/A | N/A | implemented |
| Golden set spec | 26.1 | `docs/evaluation/edr_goldenset.md` | N/A | JSONL format | N/A | N/A | implemented |
| Promptfoo config | 26.4 | `apps/edr/evaluation/promptfoo.config.yaml` | N/A | Placeholder with empty providers/tests | N/A | CI integration (1H) | partial |

---

## Frontend & UI (Phases 1I–2C)

Source of truth: `docs/design/UI_CONTRACT_v1.md`. All UI feature rows remain
`missing` until Phase 1I. See `docs/execution/IMPLEMENTATION_PHASES.md` for the
full phase scope.

---

## Identified Gaps

| ID | Gap | Location | Impact | Phase to Fix |
|----|-----|----------|--------|--------------|
| G1 | Nodes 11–17 still return stub statuses | `apps/edr/graph/node_11_self_correct.py` through `node_17_publish.py` | No LLM analysis, no persistence, no human-review flow | 1E (11–14), 1F (15), 1G (16–17) |
| G2 | MinIO bucket initialization is missing | No init script/startup hook found | First Phase 1F write would fail if bucket is absent | Before 1F |
| G3 | Only 1 executable golden example exists | `apps/edr/evaluation/goldenset/example.jsonl` | Evaluation is not meaningful yet | 1H |
| G4 | No `frontend/` directory exists | Repository root | No UI codebase to scaffold | 1I |
| G5 | No `make test:ui` target in Makefile | `Makefile` | No CI gate for UI acceptance | 2C |
| G6 | Langfuse tracing is unwired | `apps/edr/` | No observability for LLM calls | 1E |
| G7 | Cost cap circuit breaker is unwired | `apps/edr/` | Daily cap not enforced at runtime | 1H |
