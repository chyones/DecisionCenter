# DecisionCenter — Implementation Phases 1A–1H

> **Source of truth:** `docs/workflows/EDR-AGENTIC-RAG-v2.1.md`
> **Derived from:** `docs/PRE_START_IMPLEMENTATION_PLAN.md` Section 7 & 9
> **Date:** 2026-05-06
> **Status:** Planning document — Phase 0 lock

This file is the authoritative execution sequence for implementation. The locked
workflow spec remains the behavioral source of truth, and its Section 31 now mirrors
this infrastructure-first sequence.

---

## Phase Sequence Overview

| Phase | Name | Goal | Cost | Forbidden Work |
|-------|------|------|------|----------------|
| **1A** | Infrastructure Foundation | Every service starts, config is complete, CI catches regressions | Zero (no external APIs) | No node logic, no LLM calls, no n8n changes, no schema changes, no auth logic |
| **1B** | RBAC & Identity | Real authentication and authorization in Node 01 before retrieval touches data | Entra API only (free under M365) | No retrieval logic, no n8n changes |
| **1C** | n8n Connector Workflows | 4 real n8n workflows returning normalized evidence payloads | Hetzner compute + Graph API (free under M365) | No Python node logic, no LLM calls |
| **1D** | Embedding & Vector Retrieval | Evidence retrieval pipeline from document to ranked Evidence Objects | ~USD 5/mo (Voyage-3-large) | No LLM report generation |
| **1E** | LLM Nodes | Nodes 02, 03, 04, 11, 12, 13, 14 produce real structured output | ~USD 220/mo (Anthropic majority) | No persistence changes, no publish logic |
| **1F** | Persistence & Audit | All 4 output files written to MinIO staging; audit trail in PostgreSQL | ~USD 5/mo (MinIO storage) | No human review UI, no approval logic |
| **1G** | Human Review Gate | Approval/reject mechanism for Node 16 → Node 17 with immutable final output | Zero new API costs | No eval logic, no load testing |
| **1H** | Evaluation & Hardening | Prove correctness against spec before production use | Small eval API costs | No new features |

---

## Phase 1A — Infrastructure Foundation

**First safe phase.** All subsequent phases depend on it.

1. Expand `apps/edr/config.py` to load all 36 `.env.example` keys with Pydantic field types (currently loads 6).
2. Rewrite `GET /healthz` to ping PostgreSQL, Redis, Qdrant, MinIO — return per-service status.
3. Pin all dependencies in `pyproject.toml` to exact current versions (currently uses `>=`).
4. Create `.github/workflows/ci.yml` — ruff lint, type check, `make smoke`.
5. Write Qdrant collection initialization script — idempotent, one collection per `project_code`.
6. Fix `Caddyfile` ACME email (`admin@example.com` → real address).
7. Verify `.dockerignore` excludes `.env`, `__pycache__`, `.git`, `.pytest_cache`.

**Validation gate before 1B:**
- `make smoke` passes in CI with zero warnings.
- `GET /healthz` returns `{"postgres":"ok","redis":"ok","qdrant":"ok","minio":"ok"}`.
- `ruff check` exits 0.
- All 36 `.env.example` keys have a corresponding `config.py` field.
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

Current Phase 0 status: all four workflow files exist, but each has `"nodes": []`.
They are placeholders and are required before retrieval phases can pass validation.

1. `sharepoint_search.json` — Entra token → Graph search → excerpt + `hash_sha256`.
2. `email_search.json` — Graph delegated → user mailbox + allowed shared mailboxes → excerpt only (≤500 chars).
3. `owncloud_list.json` — WebDAV read → file metadata + excerpt.
4. `odoo_read.json` — JSON-RPC read-only → `model + id + value + timestamp + hash_sha256`.
5. Each workflow output validates against `docs/schemas/evidence-object.schema.json`.
6. Test each workflow in isolation via `curl` before wiring to Python.

**Validation gate before 1D:**
- Each workflow returns ≥1 payload validating against evidence-object schema.
- Email workflow confirmed excerpt-only.
- Odoo workflow returns required fields.
- n8n workflow JSON files are no longer empty (`"nodes": []`).

---

## Phase 1D — Embedding & Vector Retrieval

**Goal:** Real evidence retrieval pipeline from document to ranked Evidence Objects.

1. Wire `apps/edr/retrieval/embeddings.py` → Voyage-3-large API.
2. Fix `apps/edr/retrieval/chunking.py` to use token count (500–800 tokens, 100–150 overlap).
3. Wire `apps/edr/retrieval/rerank.py` → Cohere Rerank 3.5 (max 50 inputs → max 10 output).
4. Wire RBAC-aware `MemoryCache` to Redis — cache key includes `user_id` and `project_code`.
5. Nodes 05–08: call n8n webhooks → embed results → insert into correct Qdrant collection.
6. Node 09: real normalization — dedup by `source_uri` + `hash_sha256`, 13-level confidence scoring.
7. Node 10: real sufficiency check — count evidence per source type, flag missing Odoo for financial queries.

**Validation gate before 1E:**
- `embed()` returns vectors of correct dimension for Voyage-3-large.
- `chunk_text()` verified via test: 500–800 tokens with 100–150 overlap.
- Qdrant insert and round-trip retrieval test passes for at least one project collection.
- RRF fusion produces a ranked list from two result sets.
- Redis cache key confirmed to include `user_id` and `project_code`.

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

1. Expand the executable golden set from 1 example toward the 12 required baseline categories and 50 go-live cases from spec Section 26.
2. Wire `apps/edr/evaluation/run.py` to execute against golden set and report metrics from `docs/evaluation/edr_metrics.md`.
3. Wire `apps/edr/evaluation/promptfoo.config.yaml` with real providers and test cases.
4. Fix PDF Arabic RTL — register a bundled Arabic TTF font (Amiri or Scheherazade).
5. Cost cap circuit breaker — abort request and return structured error if daily cap exceeded.
6. Add `make eval` step to CI pipeline.
7. Load test: 5 concurrent requests per spec deployment profile.

**Validation gate before Production:**
- At least 50 executable golden set cases pass and `make eval` exits 0 in CI.
- PDF with Arabic content renders correctly.
- Load test: 5 concurrent requests complete within spec-defined latency bounds.
- Langfuse monthly cost projection ≤ USD 300.
- Both `make smoke` and `make eval` required to pass before any production deploy.
