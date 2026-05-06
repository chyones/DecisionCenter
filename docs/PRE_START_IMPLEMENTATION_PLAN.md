# DecisionCenter — Pre-Start Implementation Plan

> **Date:** 2026-05-06
> **Scope:** `/root/DecisionCenter` only.
> **Type:** Planning/control document. No application logic, connector wiring, or code behavior changes.
> **Source of truth:** `docs/workflows/EDR-AGENTIC-RAG-v2.1.md` (locked spec, 1,700+ lines).

---

## VIPCODEEN Check

**NOT FOUND.** No file, directory, reference, or mention of `VIPCODEEN` exists anywhere inside
`/root/DecisionCenter`. The locked specification (`EDR-AGENTIC-RAG-v2.1.md`) does not define or
use this term.

---

## Phase 0 Control Lock Decisions

| Area | Locked Decision |
|---|---|
| Environment baseline | `.env.example` is authoritative and currently contains 36 keys. Earlier references to 50 keys were stale planning text. |
| Phase sequence | Phase 1A is Infrastructure Foundation. Product/node logic starts only in later assigned phases. |
| RBAC model | The canonical RBAC model is the 9-role matrix in `docs/security/rbac_matrix.md`, aligned to spec Sections 8 and 9. |
| n8n status | `n8n/*.json` files are placeholders with empty `nodes` arrays and are not functional retrieval workflows. |
| Evaluation baseline | One executable JSONL golden example exists. The spec requires 12 baseline categories and at least 50 executable cases before go-live. |
| Control plane | No Admin UI is specified. Control-plane coverage is documentation, configuration, RBAC/source mapping, audit/approval policy, CI, and operations. |
| Readiness after this cleanup | READY FOR PHASE 1, meaning Phase 1A Infrastructure Foundation only. |

---

## 1. Current Repo Reality

**Project:** Decision Center — an agentic RAG system that generates evidence-backed executive
decision reports by querying SharePoint, ownCloud, Email (Microsoft Graph), and Odoo, then
producing four output artifacts:

- `executive-decision-report.md`
- `evidence-pack.json`
- `audit-log.json`
- `quality-gate-result.json`

| Attribute | Value |
|-----------|-------|
| Deployment target | Single Hetzner CCX23 server |
| Stack | FastAPI + LangGraph + n8n + PostgreSQL + Redis + Qdrant + MinIO + Caddy |
| Target users | 5 senior managers |
| Phase 1 constraint | Read-only — no ERP writes, no email sending, no execution actions |
| Approval rule | Every report must pass human review before publishing to `/final` |
| Cost ceiling | USD 12/day · USD 300/month |
| Spec status | Locked — `docs/workflows/EDR-AGENTIC-RAG-v2.1.md` |
| Execution sequence | Phase 1A starts with Infrastructure Foundation after Phase 0 control cleanup |
| Code status | **Skeleton** — Phase 0 scaffolding complete, no node has real logic |

The system runs end-to-end today in under one millisecond by setting stub string values and
returning. Zero intelligence is produced.

---

## 2. What Is Ready

Assets that are usable as planning inputs before implementation begins.

| Asset | Contents | Usable Now |
|-------|----------|------------|
| `docs/workflows/EDR-AGENTIC-RAG-v2.1.md` | Full 18-node spec, evidence priority, RBAC matrix, retrieval strategy, cost model, golden rules | Yes — source of truth |
| `docs/schemas/` (5 JSON Schema files) | Evidence object, evidence pack, executive report, audit log, quality gate | Yes — validate against these |
| `docs/policies/` (9 files) | Financial truth, RBAC, email excerpts, conflict resolution, prompt injection, data minimization, disaster recovery | Yes — enforce in every node |
| `docs/contracts/` (4 files) | SharePoint Graph, Email Graph, Odoo read-only, ownCloud WebDAV API contracts | Yes — wire n8n against these |
| `docs/evaluation/` (3 files) | 12 required baseline categories, golden set spec, metrics (precision, faithfulness, RBAC denial, QG false-pass) | Yes — write tests against these |
| `docs/operations/` (5 files) | Runbook, hosting guide, cost model, observability plan, backup/restore | Yes — reference during infra setup |
| `apps/edr/schemas/` (4 Python files) | `EvidenceObject`, `EvidencePack`, `ExecutiveDecisionReport`, `AuditLog`, `QualityGateResult` Pydantic models | Yes — match the JSON schemas |
| `apps/edr/prompts/` (3 markdown files) | `intent_classifier.md`, `draft_report.md`, `compose_markdown.md` — production-ready prompts | Yes — wire to LLM calls |
| `apps/edr/exporters/` (5 formats) | Markdown, Word, Excel, PDF, PowerPoint export structure | Partial — Arabic PDF not supported |
| `apps/edr/retrieval/hybrid_search.py` | Reciprocal Rank Fusion (RRF) algorithm | Yes — correct implementation |
| `apps/edr/retrieval/chunking.py` | `chunk_text()` and `normalize_chunks()` | Partial — uses char count, spec requires token count |
| `apps/edr/graph/runner.py` | 18-node sequential runner, `NODE_COUNT = 18` | Yes — chain is correct |
| `apps/edr/graph/state.py` | `DecisionState` dataclass with `mark()` method | Yes |
| `apps/edr/connectors/base.py` | `N8NWebhookClient` HTTP wrapper | Yes — correct pattern |
| `apps/edr/connectors/` (4 files) | SharePoint, Email, Odoo, ownCloud — each calls correct n8n webhook | Yes — shell correct, n8n workflows empty |
| `apps/edr/tests/smoke/test_smoke.py` | 2 tests: node count = 18, publish blocked until approval | Yes — passes now |
| `.env.example` | All 36 environment variables currently evidenced in the repo | Yes — authoritative env template |
| `docker-compose.yml` | All 7 services defined with volumes and health checks | Yes — not yet end-to-end validated |
| `Makefile` | `up`, `down`, `logs`, `smoke`, `test`, `eval`, `format` targets | Yes |
| `pyproject.toml` | Correct dependencies listed | Partial — no version pins |
| `n8n/` (4 JSON files) | File names and structure in place | No — all `"nodes": []` |

---

## 3. What Is Missing

### Code Gaps

| Component | What Is Missing |
|-----------|----------------|
| `config.py` | Loads only 6 of 36 `.env.example` keys — Anthropic, Voyage, Cohere, Qdrant, MinIO, Redis, Odoo, Langfuse, n8n credentials never read |
| All 18 graph nodes | Real logic — every node sets a stub string and returns |
| Node 01 (Auth) | Entra JWT validation, role resolution, project-scope enforcement — none exists |
| Nodes 02–04 (Light LLM) | Zero LLM calls — Haiku 4.5 never called |
| Nodes 05–08 (Retrieval) | n8n webhooks called but workflows are empty — no real retrieval |
| Node 09 (Normalize) | No deduplication, no `hash_sha256`, no confidence scoring |
| Node 10 (Sufficiency) | No evidence evaluation |
| Node 11 (Self-correct) | No gap detection, no retry loop |
| Node 12 (Draft JSON) | Zero LLM calls — Sonnet 4.6 never called |
| Node 13 (Quality Gate) | No claim-to-evidence validation |
| Node 15 (Save & Audit) | No MinIO write, no PostgreSQL insert |
| Node 16 (Human Review) | No approval endpoint, no polling, no timeout |
| Node 17 (Publish) | No file move to `/final`, no immutable lock |
| `EmbeddingClient.embed()` | Raises `NotImplementedError` |
| `Reranker.rerank()` | Raises `NotImplementedError` |
| `MemoryCache` | In-memory only — not wired to Redis, not RBAC-keyed |
| `chunk_text()` | Uses character count — spec requires token count (500–800 tokens) |
| 4 n8n workflows | All empty — `"nodes": []` |
| Qdrant collection seeding | No collection-creation script — Qdrant starts empty |
| `GET /healthz` | Returns static JSON — no DB/Redis/Qdrant/MinIO ping |
| `GET /reports/staging/{id}/download/{fmt}` | Returns 404 explicitly |
| PDF Arabic RTL | `pdf.py` uses Helvetica — no Arabic TTF font registered |
| Langfuse tracing | In `.env.example`, never imported or called in code |
| Cost cap enforcement | Fields exist in `config.py`, no token counting, no circuit breaker |
| Project source mapping loader | `example.json` exists — no code loads or validates it |
| CI/CD pipeline | `.github/workflows/` directory does not exist |
| Version pins | `pyproject.toml` has no `==` pins |
| Golden set | 1 executable example in `apps/edr/evaluation/goldenset/example.jsonl` — spec requires 12 baseline categories and at least 50 executable cases before go-live |
| `evaluation/run.py` | Prints "stubbed until Phase 1G" and exits |

---

## 4. Blockers Before Implementation

Listed in dependency order. Each blocks the next.

### B1 — `config.py` loads 6 of 36 env vars

Every node that touches an LLM, Qdrant, MinIO, Redis, Odoo, or n8n will raise `AttributeError`
on `settings.<missing_field>`. This is the root blocker — all other blockers depend on it.

### B2 — n8n workflows are empty

Nodes 05–08 call the correct webhook URLs. The workflows respond with nothing because
`"nodes": []`. No retrieval is possible until all 4 workflows contain real logic.

### B3 — RBAC is a stub

Node 01 sets `"rbac_status": "stubbed"` and continues. Any user ID passes any project. This
violates the spec's primary security constraint and must be real before any retrieval node runs.
Policy document ready at `docs/security/rbac_matrix.md`. Enforcement code: none.

### B4 — Embedding raises `NotImplementedError`

`EmbeddingClient.embed()` is an unimplemented placeholder. Any code path reaching it crashes.
Voyage-3-large is the locked model per spec Section 20.

### B5 — Reranking raises `NotImplementedError`

`Reranker.rerank()` is an unimplemented placeholder. Cohere Rerank 3.5 is the locked model per
spec Section 19.

### B6 — No LLM calls exist anywhere

Prompts for Nodes 02, 03, 04, 12, and 14 are written and correct. No node calls any LLM. The
system produces zero intelligence.

### B7 — Human review gate has no mechanism

Node 16 sets `"human_review_status": "pending"` and exits. No API endpoint for approval, no
polling loop, no timeout. Node 17 can never legitimately execute. No report can ever reach
`/final`.

### B8 — Qdrant has no collections

The Qdrant service starts empty. No code creates per-project collections. The first real
embedding insert will fail.

---

## 5. Risks

| Risk | Severity | Evidence in Codebase |
|------|----------|----------------------|
| `quality_gate` stub returns `"needs_review"` — Node 14 treats this as non-failed and exports fire on empty data | **Critical** | `node_14_compose_md.py`: checks `quality_gate != "failed"` only |
| RBAC stub allows every user to access every project | **Critical** | `node_01_auth.py`: `outputs["rbac_status"] = "stubbed"` |
| 30 missing `config.py` fields — services start, crash silently on first real use | **High** | `config.py` vs. `.env.example` |
| Chunking uses character limits, not token limits — chunk sizes wrong by factor of 3–5 | **High** | `chunking.py` vs. spec Section 19 |
| Caddyfile ACME email is `admin@example.com` — Let's Encrypt will reject cert issuance | **High** | `Caddyfile` line 2 |
| No token cost tracking — a runaway Sonnet 4.6 call can exceed monthly budget with no circuit breaker | **High** | `config.py` has field, no enforcement |
| n8n starts with no credentials — first `make up` produces a blank n8n with no connections | **Medium** | `docker-compose.yml`: no seed data |
| PDF Arabic RTL renders as gibberish — Helvetica does not support Arabic glyphs | **Medium** | `pdf.py`: Helvetica only |
| No version pins — `pip install` in a new environment may produce a broken dependency tree | **Medium** | `pyproject.toml` |
| Golden set has 1 executable case; spec requires 12 baseline categories and 50 go-live cases — evaluation is not meaningful yet | **Medium** | `apps/edr/evaluation/goldenset/example.jsonl`, spec Section 26 |
| No CI/CD — regressions go undetected between phases | **Medium** | `.github/` directory absent |
| No Qdrant collection enforcement — misconfigured `project_code` could mix evidence across projects | **Medium** | No collection-creation code found |

---

## 6. Pre-Start Checklist

Complete every item before writing any node logic. Each item is verifiable.

### Environment

- [ ] Copy `.env.example` to `.env` and fill all 36 values with real credentials
- [ ] Confirm Anthropic API key has access to `claude-haiku-4-5` and `claude-sonnet-4-6`
- [ ] Confirm Voyage API key is active (`voyage-3-large`)
- [ ] Confirm Cohere API key is active (`rerank-multilingual-v3.0`)
- [ ] Confirm Qdrant reachable on configured host and port
- [ ] Confirm MinIO reachable and bucket structure planned (`/staging`, `/final`)
- [ ] Confirm PostgreSQL connection string is valid
- [ ] Confirm Redis connection string is valid
- [ ] Confirm n8n reachable and admin credentials set
- [ ] Confirm Langfuse project key and host are valid
- [ ] Confirm Odoo read-only API user exists with correct permissions — test with deliberate write attempt to verify it is blocked
- [ ] Confirm Entra application is registered with delegated `User.Read`, `Mail.Read`, `Sites.Read.All` permissions
- [ ] Replace `admin@example.com` in `Caddyfile` with real email before first `make up`

### Codebase

- [ ] Verify `make up` starts all 7 services without error
- [ ] Verify `make smoke` passes (2 existing tests)
- [ ] Verify `GET /healthz` responds (static response acceptable at this stage)
- [ ] Verify `pyproject.toml` lists correct package names — cross-reference with actual import names in code
- [ ] Confirm `docs/config/project_source_mapping.example.json` matches at least one real project before Phase 1B

### Spec Alignment

- [ ] Read spec Sections 5, 6, 8, 13, 15–18 before touching any node
- [ ] Confirm the 9-role RBAC matrix in `docs/security/rbac_matrix.md` matches current Entra group structure
- [ ] Confirm the 13-level evidence priority in spec Section 6 is understood by every developer on the project
- [ ] Confirm Odoo read-only user cannot write

### Decisions Required Before Coding

- [ ] Which Arabic TTF font will be bundled for PDF export? (e.g. Amiri, Scheherazade)
- [ ] What is the approval UI for Node 16? REST endpoint only, or email notification + approval link?
- [ ] What is the Entra token strategy? Delegated user token passed per request, or app-level token with user context?
- [ ] Which token-counting library? (`tiktoken` for OpenAI-compatible counting, or Anthropic's own tokenizer)

---

## 7. Recommended Phases

---

### Phase 1A — Infrastructure Foundation

**Goal:** Every service starts, config is complete, CI catches regressions.
No LLM calls. No n8n changes. No node logic.

**Scope:**
- Expand `config.py` to load all 36 `.env.example` keys with Pydantic field types
- Rewrite `GET /healthz` to ping PostgreSQL, Redis, Qdrant, MinIO — per-service status in response
- Pin all dependencies in `pyproject.toml` to exact current versions
- Create `.github/workflows/ci.yml` — ruff lint, type check, `make smoke`
- Write Qdrant collection initialization script — idempotent, one collection per `project_code`
- Fix `Caddyfile` ACME email to a real address
- Validate `.dockerignore` excludes `.env`, `__pycache__`, `.git`, `.pytest_cache`

**Development cost:** Zero — no external API calls.

---

### Phase 1B — RBAC & Identity

**Goal:** Real authentication and authorization in Node 01 before any retrieval touches real data.

**Scope:**
- Wire Entra JWT validation into Node 01
- Load role-to-permissions from `docs/security/rbac_matrix.md` into a typed mapping
- Load project source mapping from `project_source_mapping.json` (extend the example)
- Enforce: no valid `project_code` in mapping → reject, no retrieval
- Populate `DecisionState` with `allowed_projects`, `allowed_mailboxes`, `allowed_odoo_ids`
- Integration test: 3 cases — authorized user, unauthorized user, unknown project

**Development cost:** Entra API calls only (free under Microsoft 365 license).

---

### Phase 1C — n8n Connector Workflows

**Goal:** 4 real n8n workflows that return normalized evidence payloads.

**Scope:**
- Build `sharepoint_search.json` — Entra token → Graph search → excerpt + `hash_sha256`
- Build `email_search.json` — Graph delegated → user mailbox + allowed shared mailboxes → excerpt only (no full body — `docs/policies/email_retrieval_policy.md`)
- Build `owncloud_list.json` — WebDAV read → file metadata + excerpt
- Build `odoo_read.json` — JSON-RPC read-only → `model + id + value + timestamp + hash_sha256`
- Each workflow output validates against `docs/schemas/evidence-object.schema.json`
- Test each workflow in isolation via `curl` before wiring to Python

**Development cost:** Storage/compute on Hetzner only. Graph API calls free under Microsoft 365.

---

### Phase 1D — Embedding & Vector Retrieval

**Goal:** Real evidence retrieval pipeline from document to ranked Evidence Objects.

**Scope:**
- Wire `EmbeddingClient.embed()` to Voyage-3-large API
- Fix `chunk_text()` to use token count — not character count (500–800 tokens, 100–150 overlap)
- Wire `Reranker.rerank()` to Cohere Rerank 3.5 (max 50 inputs → max 10 output)
- Wire RBAC-aware `MemoryCache` to Redis — cache key must include `user_id` and `project_code`
- Nodes 05–08: call n8n webhooks → embed results → insert into correct Qdrant collection
- Node 09: real normalization — dedup by `source_uri` + `hash_sha256`, 13-level confidence scoring per spec Section 13
- Node 10: real sufficiency check — count evidence per source type, flag missing Odoo for financial queries

**Development cost:** Voyage-3-large embedding calls begin (~USD 5/month estimated).

---

### Phase 1E — LLM Nodes

**Goal:** Nodes 02, 03, 04, 11, 12, 13, 14 produce real structured output using existing prompt files.

**Scope:**
- Nodes 02, 03, 04 → Haiku 4.5 using `intent_classifier.md`, scope extraction, retrieval planning
- Node 11: self-correct loop (max 3 iterations per spec Section 17) — detect evidence gaps, re-query targeted sources
- Node 12 → Sonnet 4.6: structured JSON output only using `draft_report.md`; every claim binds to `evidence_id`; financial values must have Odoo `evidence_id` or be `"Not available"`
- Node 13: deterministic claim checker — every `evidence_id` referenced in report must exist in evidence pack; remove or flag any that do not
- Node 14: verify export pipeline runs end-to-end (already partially wired)
- Wire Langfuse tracing to every LLM call — token counts, latency, node name

**Development cost:** Anthropic API calls begin (majority of USD 220/month estimated).

---

### Phase 1F — Persistence & Audit

**Goal:** All 4 output files written to MinIO staging, audit trail in PostgreSQL.

**Scope:**
- Node 15: write `report.md`, `evidence-pack.json`, `audit-log.json`, `quality-gate-result.json` to `/staging/{request_id}/` in MinIO
- Write `AuditLog` rows to PostgreSQL — hashed `user_id`, all node events, token counts per node, cost estimate
- Token cost accumulator — compare against `daily_cost_cap_usd` after each LLM call
- Implement `GET /reports/staging/{request_id}/download/{fmt}` — serve from MinIO, block if `quality_gate == "failed"`

**Development cost:** MinIO storage on Hetzner only (~USD 5/month).

---

### Phase 1G — Human Review Gate

**Goal:** Approval/reject mechanism for Node 16 → Node 17 with immutable final output.

**Scope:**
- Add `POST /reports/staging/{request_id}/approve` — authorized roles only, writes approval record to PostgreSQL
- Add `POST /reports/staging/{request_id}/reject` — writes rejection + reason to PostgreSQL
- Node 16: poll approval status from PostgreSQL, configurable timeout
- Node 17: on approval — move files from `/staging/{request_id}/` to `/final/{request_id}/` in MinIO, set immutable flag
- Log approval event to `AuditLog` with approver `user_id_hash` and timestamp
- Enforce: Node 17 cannot run without a valid approval record

**Development cost:** Zero new API costs.

---

### Phase 1H — Evaluation & Hardening

**Goal:** Prove correctness against spec before production use.

**Scope:**
- Expand the executable golden set from 1 example toward the 12 required baseline categories and 50 go-live cases from spec Section 26
- Wire `evaluation/run.py` to execute against golden set and report metrics from `docs/evaluation/edr_metrics.md`
- Wire `apps/edr/evaluation/promptfoo.config.yaml` with real providers and test cases
- Fix PDF Arabic RTL — register a bundled Arabic TTF font (Amiri or Scheherazade)
- Cost cap circuit breaker — abort request and return structured error if daily cap exceeded at any LLM node
- Add `make eval` step to CI pipeline
- Load test: 5 concurrent requests per spec deployment profile

**Development cost:** Small additional Anthropic/Voyage/Cohere calls for eval runs.

---

## 8. First Safe Phase to Start

**Phase 1A — Infrastructure Foundation.**

### Why this is the correct first move

Every phase from 1B onward requires `config.py` to successfully load credentials. Today it loads
6 of 36. That gap will cause `AttributeError` crashes in every node the moment a real service is
contacted. Fixing it first means all subsequent phases can be developed without fighting silent
config failures.

CI/CD must exist before any real credentials or LLM calls are added — otherwise a broken node
goes undetected until production.

The health check with real dependency pings will surface environment issues (wrong Qdrant port,
wrong Redis password, wrong MinIO bucket) before a single line of node logic is written.

Qdrant collection seeding must happen before Phase 1D — collections must exist before any
embedding insert is attempted.

Phase 1A touches zero business logic and zero security-sensitive code.

### What Phase 1A contains — exactly

1. Expand `config.py` — all 36 `.env.example` keys, Pydantic types matching each value
2. Rewrite `GET /healthz` — ping PostgreSQL, Redis, Qdrant, MinIO; return per-service status
3. Pin all dependencies in `pyproject.toml` to current exact versions
4. Create `.github/workflows/ci.yml` — ruff, type check, `make smoke`
5. Write Qdrant collection init script — idempotent, one collection per `project_code`
6. Fix `Caddyfile` ACME email to a real address
7. Verify `.dockerignore` excludes `.env`, `__pycache__`, `.git`

### What Phase 1A does not contain

No node logic. No LLM calls. No n8n changes. No schema changes. No auth logic.

---

## 9. Validation Proof Required Before Moving to Next Phase

| Phase | All Must Pass Before Proceeding |
|-------|--------------------------------|
| **1A → 1B** | `make smoke` passes in CI with zero warnings. `GET /healthz` returns `{"postgres": "ok", "redis": "ok", "qdrant": "ok", "minio": "ok"}`. `ruff check` exits 0. All 36 `.env.example` keys have a corresponding `config.py` field. `pyproject.toml` contains `==` version pins for all dependencies. CI pipeline runs on every push. |
| **1B → 1C** | Three integration tests pass: (1) authorized user + valid `project_code` receives `rbac_status: authorized` and populated `allowed_projects`; (2) user with no project mapping receives HTTP 403; (3) user with correct project but insufficient role receives HTTP 403. All three in CI. No stub strings remain in Node 01 output. |
| **1C → 1D** | Each of the 4 n8n workflows tested independently via `curl` — each returns at least 1 payload that validates against `docs/schemas/evidence-object.schema.json`. Email workflow confirmed to return excerpt only (field length ≤ 500 characters). Odoo workflow confirmed to return `model`, `id`, `value`, `timestamp`, `hash_sha256`. n8n workflow JSON files in repo are no longer empty. |
| **1D → 1E** | `embed()` returns vectors of correct dimension for Voyage-3-large. `chunk_text()` verified via test to produce chunks of 500–800 tokens (not characters) with 100–150 token overlap. Qdrant insert and round-trip retrieval test passes for at least one project collection. RRF fusion produces a ranked list from two result sets. Redis cache key confirmed to include both `user_id` and `project_code`. |
| **1E → 1F** | End-to-end test with real query and real evidence: (1) Node 12 output validates against `docs/schemas/executive-decision-report.schema.json`; (2) Node 13 rejects any report with a claim containing no `evidence_id`; (3) financial value with no Odoo `evidence_id` is absent or explicitly `"Not available"`; (4) Langfuse dashboard shows traces for all LLM nodes with token counts. |
| **1F → 1G** | `POST /reports/staging` with real query returns `request_id`. `GET /reports/staging/{request_id}/download/md` returns real Markdown content. MinIO `/staging/{request_id}/` contains all 4 output files. PostgreSQL `audit_log` has a row for the request with hashed `user_id`. Token cost per request is logged. |
| **1G → 1H** | Full approval flow verified: submit → staging files appear → `POST /approve` → `/final` files appear and cannot be overwritten. Full reject flow verified: submit → `POST /reject` → no `/final` files. Approval record in PostgreSQL contains approver hash and timestamp. `publish_status` in Node 17 output is `"published"` only after a real approval record — never from stub. |
| **1H → Production** | At least 50 executable golden set cases pass and `make eval` exits 0 in CI. PDF with Arabic content renders correctly. Load test: 5 concurrent requests complete within spec-defined latency bounds. Langfuse monthly cost projection ≤ USD 300. Both `make smoke` and `make eval` required to pass before any production deploy. |

---

*This document was generated from a read-only inspection of `/root/DecisionCenter` on 2026-05-06.
It reflects the state of the repository at that point in time. Update this file as phases are completed.*
