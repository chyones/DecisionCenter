# DecisionCenter — Control Plane Lock

> **Date:** 2026-05-10
> **Scope:** Documentation and control state only.
> **Behavioral source of truth:** `docs/workflows/EDR-AGENTIC-RAG-v2.1.md`
> **Execution sequence source of truth:** `docs/execution/IMPLEMENTATION_PHASES.md`
> **Live state:** `PHASE_1H_COMPLETE_NOT_LIVE` (production is `NOT_LIVE`).

This document locks the control expectations for the project. It does not add
application features and does not define an Admin UI.

## Phase 0 Decisions

| Area | Authoritative Decision | Evidence |
|---|---|---|
| Environment baseline | `.env.example` has 40 keys; planning docs that said 50 were stale | `.env.example` |
| Config coverage | `apps/edr/config.py` loads all 40 keys from `.env.example` | `apps/edr/config.py` |
| Phase sequence | Phase 1A is Infrastructure Foundation before product/node logic | `docs/execution/IMPLEMENTATION_PHASES.md` |
| RBAC model | Use the 9 canonical spec roles | `docs/security/rbac_matrix.md` |
| n8n status | Four workflow JSON files contain real 4–5 node pipelines and require n8n Header Auth | `n8n/*.json` |
| Service-account credentials | Read from n8n container env (`$env.OWNCLOUD_*`, `$env.ODOO_*`); never sent through the webhook body | `n8n/owncloud_list.json`, `n8n/odoo_read.json`, `docker-compose.yml` |
| Mailbox allowlist | Enforced twice: `apps/edr/graph/node_07_email.py` (Python) and the `Enforce Mailbox Allowlist` n8n code node | `apps/edr/graph/node_07_email.py`, `n8n/email_search.json` |
| Evaluation baseline | A 65-case executable golden set covers all 12 baseline categories from spec Section 26; `make eval` enforces pass rate ≥ 0.95 and precision ≥ 0.90 in CI | `apps/edr/evaluation/goldenset/goldenset.jsonl`, `apps/edr/evaluation/run.py`, spec Section 26 |
| Bucket initialization | `scripts/init_minio.py` creates the configured MinIO bucket idempotently; runtime `_ensure_bucket()` covers any missed init | `scripts/init_minio.py`, `apps/edr/persistence/minio_store.py` |
| Readiness | Phase 1A–1H + Phase 1D-fixup are complete; Phase 1I is the safe next phase | This document |

## Authoritative Environment Baseline

The authoritative env baseline is the current `.env.example` file. It contains exactly
these 40 keys:

| Group | Keys |
|---|---|
| App | `APP_ENV`, `APP_HOST`, `APP_PORT`, `PUBLIC_BASE_URL`, `PUBLIC_HOSTNAME` |
| Identity | `ENTRA_CLIENT_ID`, `ENTRA_TENANT_ID`, `ENTRA_CLIENT_SECRET` |
| LLM providers | `ANTHROPIC_API_KEY`, `VOYAGE_API_KEY`, `COHERE_API_KEY` |
| Data stores | `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`, `REDIS_URL`, `QDRANT_URL`, `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_BUCKET` |
| Connector layer | `N8N_BASE_URL`, `N8N_WEBHOOK_TOKEN`, `N8N_TIMEOUT`, `SHAREPOINT_SEARCH_WEBHOOK`, `OWNCLOUD_LIST_WEBHOOK`, `EMAIL_SEARCH_WEBHOOK`, `ODOO_READ_WEBHOOK` |
| ownCloud | `OWNCLOUD_USERNAME`, `OWNCLOUD_PASSWORD` |
| Odoo | `ODOO_URL`, `ODOO_DATABASE`, `ODOO_USERNAME`, `ODOO_API_KEY` |
| Observability and budget | `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`, `DAILY_COST_CAP_USD`, `MONTHLY_COST_TARGET_USD` |

`apps/edr/config.py` loads these 40 fields and CI asserts the count.

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
| 1F — Persistence and Audit | `apps/edr/persistence/postgres_store.py` defines `audit_log` and `review_decisions` schemas idempotently. `apps/edr/persistence/minio_store.py` lazily ensures the configured bucket exists and persists the four staging artifacts; `scripts/init_minio.py` performs an explicit idempotent bucket create. Node 15 hashes user IDs (no raw IDs stored), persists the four artifacts and the audit row. The download endpoint `GET /reports/staging/{request_id}/download/{fmt}` enforces RBAC plus quality-gate state. Tests: `apps/edr/tests/integration/test_phase1f.py` (12 cases). |
| 1G — Human Review Gate | `POST /reports/staging/{request_id}/{approve,reject,request-revision}` with role-aware action selection (`_check_reviewer_rbac`), self-approval blocking by hashed reviewer ID, mandatory comment for `admin_override`, and 409 on already-finalized reports. Node 16 reads review state from PostgreSQL; node 17 publishes only when `review_state == "approved"`, copies staging→final via `MinioStore.copy_to_final` (write-once via `FileExistsError`), writes `approval-log.json` exactly once, and updates `review_state` to `final`. `GET /reports/final/{request_id}/download/{fmt}` only serves once finalized; quality-gate `failed` blocks all download paths. Tests: `apps/edr/tests/integration/test_phase1g.py` (22 cases). |
| 1H — Evaluation and Hardening | `apps/edr/evaluation/run.py` is a real runner (JSONL loader, single-node and full-workflow cases, dot-notation expectation resolution, aggregate pass-rate/precision/refusal metrics, non-zero exit on regression). `apps/edr/evaluation/goldenset/goldenset.jsonl` holds 65 executable cases across all 12 baseline categories (stale `example.jsonl` deleted). `node_13_quality_gate.py` enforces claim-to-evidence binding and Odoo-backed financial fields. `apps/edr/exporters/pdf.py` bundles `Amiri-Regular.ttf` (OFL), auto-detects Arabic, and appends an RTL limitation disclaimer (full bidi shaping deferred). `apps/edr/evaluation/load_test.py` is a local-only deterministic load test (baseline-only). `pip-audit` triage completed (see below). `.github/workflows/ci.yml` adds the `Evaluation suite` step (`--min-pass-rate 0.95 --min-precision 0.90`) and job-level `N8N_TIMEOUT: 5`. Tests: `test_evaluation.py` (15), `test_load_test.py` (5), `test_pdf_arabic.py` (7). Report: `docs/execution/PHASE_1H_REPORT.md`. |

## Standing Control Invariants

These hold for every phase, including the next one:

- Documentation must agree on the 40-key environment baseline.
- Documentation must agree that Phases 1A–1H plus the Phase 1D-fixup are complete.
- RBAC documentation must use the 9 canonical roles from the locked spec.
- n8n workflows must declare `authentication=headerAuth` and read service-account
  credentials from environment variables.
- Service-account credentials must never be logged or transmitted via the
  webhook body.
- CI must enforce: ruff, compileall, config coverage (40 keys), doc-drift
  check, AI-context check, smoke tests, integration tests, the evaluation suite
  (`make eval` thresholds), and `pip-audit` (non-blocking; see triage below).
- Production must remain `NOT_LIVE` until an operator runs the deployment
  steps in `docs/operations/runbook.md`. A push to `origin/main` is not a
  deployment.

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
- Frontend / Admin UI work is out of scope until Phase 1I and is governed by the
  locked UI contract; any Admin UI beyond the locked contract is a spec change.

## Admin And Control-Plane Coverage

The locked spec defines an `admin` RBAC role but does not define an Admin UI. The current
control plane is therefore documentation, configuration, CI, RBAC mapping, source mapping,
audit policy, approval policy, and operational runbooks.

The `admin` role is configuration-only. It MUST NOT grant business-data visibility by default.
Any future Admin UI, admin screen, or control-panel feature is outside the current spec and
must be treated as a spec change before implementation.

## Final Readiness Decision

**READY FOR PHASE 1I — production is NOT_LIVE.**

Phases 1A–1H plus the Phase 1D-fixup are complete and validated by CI on HEAD.
The next safe step is Phase 1I (Frontend Foundation & Static Admin Scaffolds)
and it requires explicit user approval before it starts. This does not authorize
deployment, API wiring inside the frontend, or any spec change.
