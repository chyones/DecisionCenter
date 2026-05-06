# DecisionCenter — Feature Matrix

> **Source of truth:** `docs/workflows/EDR-AGENTIC-RAG-v2.1.md`
> **Date:** 2026-05-06
> **Status:** Phase 0 documentation lock — reflects current skeleton state
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
| Auth and RBAC Gate | 16.1, 8, 9 | `node_01_auth.py` | All | `DecisionState` | `node: auth` | integration test ×3 (1B) | partial |
| Intent Classifier (Light) | 16.2 | `node_02_intent.py` | All | `DecisionState.outputs["intent"]` | `node: intent` | golden set eval (1H) | partial |
| Scope Resolver (Light) | 16.3 | `node_03_scope.py` | All | `DecisionState.outputs["scope"]` | `node: scope` | golden set eval (1H) | partial |
| Retrieval Plan (Light) | 16.4 | `node_04_plan.py` | All | `DecisionState.outputs["plan"]` | `node: plan` | golden set eval (1H) | partial |
| SharePoint Retrieval | 16.5, 4.1 | `node_05_sharepoint.py` | Per `docs/security/rbac_matrix.md` | `EvidenceObject` | `node: sharepoint` | curl test × n8n (1C) | partial |
| ownCloud Retrieval | 16.6, 4.2 | `node_06_owncloud.py` | Per `docs/security/rbac_matrix.md` | `EvidenceObject` | `node: owncloud` | curl test × n8n (1C) | partial |
| Email Retrieval | 16.7, 4.3, 10 | `node_07_email.py` | Per `docs/security/rbac_matrix.md` | `EvidenceObject` | `node: email` | curl test × n8n (1C) | partial |
| Odoo Facts Retrieval | 16.8, 4.4 | `node_08_odoo.py` | Per `docs/security/rbac_matrix.md` | `EvidenceObject` | `node: odoo` | curl test × n8n (1C) | partial |
| Normalize & Deduplicate | 16.9, 13 | `node_09_normalize.py` | All | `EvidencePack` | `node: normalize` | unit test: dedup (1D) | partial |
| Evidence Sufficiency Check | 16.10 | `node_10_sufficiency.py` | All | `DecisionState.outputs["sufficiency"]` | `node: sufficiency` | unit test: flag gaps (1D) | partial |
| Self-Correction Loop | 16.11, 17 | `node_11_self_correct.py` | All | `DecisionState.outputs["corrected"]` | `node: self_correct` | unit test: max 3 iterations (1E) | partial |
| Draft JSON Report (Heavy) | 16.12, 14, 15 | `node_12_draft_json.py` | All | `ExecutiveDecisionReport` | `node: draft_json` | schema validation (1E) | partial |
| Quality Gate | 16.13, 17 | `node_13_quality_gate.py` | All | `QualityGateResult` | `node: quality_gate` | unit test: false-pass blocked (1E) | partial |
| Compose Markdown Report | 16.14 | `node_14_compose_md.py` | All | `DecisionState.outputs["exported_reports"]` | `node: compose_md` | end-to-end export (1E) | partial |
| Save & Audit | 16.15 | `node_15_save_audit.py` | All | `AuditLog` | `node: save_audit` | MinIO + PostgreSQL verify (1F) | partial |
| Human Review Gate | 16.16 | `node_16_review.py` | Approval roles per `docs/security/rbac_matrix.md` | `DecisionState.outputs["human_review_status"]` | `node: review` | approval flow test (1G) | partial |
| Publish to /final | 16.17 | `node_17_publish.py` | Approval roles per `docs/security/rbac_matrix.md` | `DecisionState.outputs["publish_status"]` | `node: publish` | immutability test (1G) | partial |

---

## API Endpoints

| Feature | Spec Section | Endpoint | RBAC Role | Schema / Model | Audit Event | Validation Proof | Status |
|---------|--------------|----------|-----------|----------------|-------------|------------------|--------|
| Health check | 27 | `GET /healthz` | All (unauthenticated) | Static JSON | None | `make smoke`, CI | partial |
| Stage report | 27 | `POST /reports/staging` | All authenticated | `ReportRequest` → `DecisionState` | `request_id` generated | `make smoke` (1A) | partial |
| Download report | 27 | `GET /reports/staging/{id}/download/{fmt}` | Request owner + approver roles | MIME type response | `download` event | integration test (1F) | partial |
| Approve report | 27, 16.16 | `POST /reports/staging/{id}/approve` | Approval roles per `docs/security/rbac_matrix.md` | Approval record | `approval` event | integration test (1G) | missing |
| Reject report | 27, 16.16 | `POST /reports/staging/{id}/reject` | Approval roles per `docs/security/rbac_matrix.md` | Rejection record | `rejection` event | integration test (1G) | missing |

---

## Retrieval & Vector Infrastructure

| Feature | Spec Section | Component | RBAC Role | Schema / Model | Audit Event | Validation Proof | Status |
|---------|--------------|-----------|-----------|----------------|-------------|------------------|--------|
| Text chunking | 19.1 | `apps/edr/retrieval/chunking.py` | N/A | `list[str]` | None | unit test: token count (1D) | partial |
| Embedding | 19.2 | `apps/edr/retrieval/embeddings.py` | N/A | `list[float]` (1024-dim) | token count | round-trip test (1D) | partial |
| Vector store (Qdrant) | 19.3 | `qdrant-client` | N/A | Collection per `project_code` | None | init script + insert test (1A/1D) | partial |
| Hybrid search (RRF) | 19.4 | `apps/edr/retrieval/hybrid_search.py` | N/A | Ranked `EvidenceObject` list | None | unit test: fusion rank (1D) | implemented |
| Reranking | 19.5 | `apps/edr/retrieval/rerank.py` | N/A | Ranked `EvidenceObject` list (top 10) | None | unit test: top-k (1D) | partial |
| Query expansion | 19.6 | Not yet created | N/A | Expanded query strings | None | eval test (1H) | missing |
| RBAC-aware caching | 19.7 | `MemoryCache` / Redis | N/A | Cache key: `user_id:project_code:query_hash` | None | unit test: key format (1D) | partial |
| Qdrant collection init | 19.3 | `scripts/init_qdrant.py` | Admin | Collection config | `init_qdrant` | idempotent run ×2 (1A) | missing |

---

## Connectors (n8n Workflows)

| Feature | Spec Section | Workflow File | RBAC Role | Output Schema | Audit Event | Validation Proof | Status |
|---------|--------------|---------------|-----------|---------------|-------------|------------------|--------|
| SharePoint search | 4.1, 16.5 | `n8n/sharepoint_search.json` | Service account | `EvidenceObject` | `connector: sharepoint` | curl + schema validation (1C) | missing |
| Email search | 4.3, 16.7 | `n8n/email_search.json` | Service account | `EvidenceObject` (excerpt ≤500 chars) | `connector: email` | curl + schema validation (1C) | missing |
| ownCloud list | 4.2, 16.6 | `n8n/owncloud_list.json` | Service account | `EvidenceObject` | `connector: owncloud` | curl + schema validation (1C) | missing |
| Odoo read | 4.4, 16.8 | `n8n/odoo_read.json` | Service account | `EvidenceObject` | `connector: odoo` | curl + schema validation (1C) | missing |

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
| Evidence Object (Pydantic) | 12 | `apps/edr/schemas/evidence.py` | N/A | `EvidenceObject` | None | import + typecheck | implemented |
| Evidence Pack (Pydantic) | 12 | `apps/edr/schemas/evidence.py` | N/A | `EvidencePack` | None | import + typecheck | implemented |
| Executive Report (Pydantic) | 14, 15 | `apps/edr/schemas/report.py` | N/A | `ExecutiveDecisionReport` | None | import + typecheck | implemented |
| Audit Log (Pydantic) | 21 | `apps/edr/schemas/audit.py` | N/A | `AuditLog` | None | import + typecheck | implemented |
| Quality Gate (Pydantic) | 17 | `apps/edr/schemas/quality_gate.py` | N/A | `QualityGateResult` | None | import + typecheck | implemented |

---

## Infrastructure & DevOps

| Feature | Spec Section | Component | RBAC Role | Schema / Model | Audit Event | Validation Proof | Status |
|---------|--------------|-----------|-----------|---------------|-------------|------------------|--------|
| Configuration loading | 20 | `apps/edr/config.py` | N/A | `Settings` (Pydantic) | None | field count = 36 (1A) | partial |
| Dependency version pins | 20 | `pyproject.toml` | N/A | N/A | None | `pip install` reproducible (1A) | partial |
| CI/CD pipeline | 26.4 | `.github/workflows/ci.yml` | N/A | N/A | None | push triggers green build (1A) | missing |
| Docker Compose stack | 23 | `docker-compose.yml` | N/A | 7 services | None | `make up` healthy (1A) | partial |
| Reverse proxy | 23 | `Caddyfile` | N/A | Caddy config | None | cert issuance works (1A) | partial |
| PostgreSQL persistence | 20.4 | `docker-compose.yml` | N/A | `audit_log` table | N/A | health ping (1A) | partial |
| Redis caching | 20.4 | `docker-compose.yml` | N/A | Redis key-value | N/A | health ping (1A) | partial |
| MinIO object storage | 20.4 | `docker-compose.yml` | N/A | `/staging`, `/final` buckets | N/A | health ping + write test (1A/1F) | partial |
| Qdrant vector store | 20.4 | `docker-compose.yml` | N/A | per-project collections | N/A | health ping + init script (1A/1D) | partial |
| n8n orchestration | 20.2 | `docker-compose.yml` | N/A | 4 workflow files | N/A | workflow responds to curl (1C) | partial |
| Langfuse tracing | 21.1 | `.env.example` only | N/A | Trace + span | token count | dashboard visible (1E) | missing |
| Cost cap enforcement | 18, 22 | `config.py` fields only | N/A | `daily_cost_cap_usd` | `cost_exceeded` | circuit breaker test (1H) | missing |

---

## Policies (Enforcement Required)

| Feature | Spec Section | Policy Document | RBAC Role | Enforcement Point | Audit Event | Validation Proof | Status |
|---------|--------------|-----------------|-----------|-------------------|-------------|------------------|--------|
| RBAC enforcement | 8, 9 | `docs/security/rbac_matrix.md` | All | Node 01 + every retrieval node | `rbac_denied` | integration test ×3 (1B) | documented-only |
| Evidence priority | 6 | `docs/policies/evidence_priority_policy.md` | All | Node 09 | `priority_assigned` | unit test: 13 levels (1D) | documented-only |
| Conflict resolution | 7 | `docs/policies/conflict_resolution_policy.md` | All | Node 09 / Node 12 | `conflict_flagged` | golden set eval (1H) | documented-only |
| Email excerpt limit | 4.3, 10 | `docs/policies/email_retrieval_policy.md` | All | Node 07 / n8n | `email_excerpt` | length ≤500 chars (1C) | documented-only |
| Financial truth | 4.4 | `docs/policies/odoo_financial_truth_policy.md` | All | Node 12 / Node 13 | `finance_verified` | Odoo evidence required (1E) | documented-only |
| Prompt injection guard | 24.1 | `docs/policies/prompt_injection_policy.md` | All | Every LLM node | `injection_blocked` | red-team test (1H) | documented-only |
| Data minimization | 24.2 | `docs/policies/data_minimization_policy.md` | All | Every retrieval node | `minimization_check` | audit field review (1F) | documented-only |
| Disaster recovery | 25 | `docs/policies/disaster_recovery_policy.md` | Admin | Operations | `dr_test` | runbook execution | documented-only |
| Shared mailbox access | 10 | `docs/policies/shared_mailbox_access_policy.md` | All | Node 01 + Node 07 | `mailbox_access` | integration test (1B) | documented-only |

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

## Identified Gaps

| ID | Gap | Location | Impact | Phase to Fix |
|----|-----|----------|--------|--------------|
| G1 | Entra group-to-role mapping is not present | No mapping file found | Cannot enforce the 9-role model yet | 1B |
| G2 | `apps/edr/evaluation/promptfoo.config.yaml` has empty providers/tests | `apps/edr/evaluation/promptfoo.config.yaml` | Cannot run automated prompt regression yet | 1H |
| G3 | `apps/edr/evaluation/run.py` prints "stubbed until Phase 1G" while evaluation is now Phase 1H | `apps/edr/evaluation/run.py` | Stale runtime message; no behavior implemented | 1H |
| G4 | No `POST /approve` or `POST /reject` endpoints exist | `apps/edr/app.py` | Human review gate has no API surface | 1G |
| G5 | `apps/edr/config.py` loads 6 of 36 env keys | `apps/edr/config.py`, `.env.example` | Real service calls will hit missing settings | 1A |
| G6 | n8n workflows are present but empty placeholders | `n8n/*.json` | No retrieval possible | 1C |
| G7 | Only 1 executable golden example exists | `apps/edr/evaluation/goldenset/example.jsonl` | Evaluation is not meaningful yet | 1H |
