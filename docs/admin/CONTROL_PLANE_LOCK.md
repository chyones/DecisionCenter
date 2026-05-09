# DecisionCenter — Phase 0 Control Plane Lock

> **Date:** 2026-05-09
> **Scope:** Documentation and control state only.
> **Behavioral source of truth:** `docs/workflows/EDR-AGENTIC-RAG-v2.1.md`
> **Execution sequence source of truth:** `docs/execution/IMPLEMENTATION_PHASES.md`

This document locks the control expectations that must be clear before application
implementation starts. It does not add application features and does not define an
Admin UI.

## Phase 0 Decisions

| Area | Authoritative Decision | Evidence |
|---|---|---|
| Environment baseline | `.env.example` has 39 keys; planning docs that said 50 were stale | `.env.example` |
| Config coverage | `apps/edr/config.py` loads all 39 keys from `.env.example` | `apps/edr/config.py` |
| Phase sequence | Phase 1A is Infrastructure Foundation before product/node logic | `docs/execution/IMPLEMENTATION_PHASES.md` |
| RBAC model | Use the 9 canonical spec roles | `docs/security/rbac_matrix.md` |
| n8n status | Four workflow JSON files contain real 4-node pipelines and require n8n Header Auth | `n8n/*.json` |
| Service-account credentials | Read from n8n container env (`$env.OWNCLOUD_*`, `$env.ODOO_*`); never sent through the webhook body | `n8n/owncloud_list.json`, `n8n/odoo_read.json`, `docker-compose.yml` |
| Mailbox allowlist | Enforced twice: `apps/edr/graph/node_07_email.py` (Python) and the `Enforce Mailbox Allowlist` n8n code node | `apps/edr/graph/node_07_email.py`, `n8n/email_search.json` |
| Evaluation baseline | One JSONL golden example exists; 12 baseline categories and 50 go-live cases are required by spec | `apps/edr/evaluation/goldenset/example.jsonl`, spec Section 26 |
| Readiness | Phase 1A–1D infrastructure + retrieval + Phase 1D-fixup are complete; entering Phase 1E | This document |

## Authoritative Environment Baseline

The authoritative env baseline is the current `.env.example` file. It contains exactly
these 39 keys:

| Group | Keys |
|---|---|
| App | `APP_ENV`, `APP_HOST`, `APP_PORT`, `PUBLIC_BASE_URL`, `PUBLIC_HOSTNAME` |
| Identity | `ENTRA_CLIENT_ID`, `ENTRA_TENANT_ID`, `ENTRA_CLIENT_SECRET` |
| LLM providers | `ANTHROPIC_API_KEY`, `VOYAGE_API_KEY`, `COHERE_API_KEY` |
| Data stores | `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`, `REDIS_URL`, `QDRANT_URL`, `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_BUCKET` |
| Connector layer | `N8N_BASE_URL`, `N8N_WEBHOOK_TOKEN`, `SHAREPOINT_SEARCH_WEBHOOK`, `OWNCLOUD_LIST_WEBHOOK`, `EMAIL_SEARCH_WEBHOOK`, `ODOO_READ_WEBHOOK` |
| ownCloud | `OWNCLOUD_USERNAME`, `OWNCLOUD_PASSWORD` |
| Odoo | `ODOO_URL`, `ODOO_DATABASE`, `ODOO_USERNAME`, `ODOO_API_KEY` |
| Observability and budget | `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`, `DAILY_COST_CAP_USD`, `MONTHLY_COST_TARGET_USD` |

`apps/edr/config.py` now loads these 39 fields and CI asserts the count.

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
| C-7 / I-6 | `PyJWT==2.7.0` and `cryptography==41.0.7` carried CVEs | Upgraded to `PyJWT==2.10.1` and `cryptography==44.0.0` |
| C-8 | Node 14 exported on `needs_review` because it only blocked `failed` | Now requires `quality_gate == "passed"` and a non-empty `report_json` |
| L-2 / R-4 | JWT validator only surfaced first role; no JWKS cache | Validator caches the `PyJWKClient` and exposes the full `roles` tuple |
| L-5 | `EvidenceObject.metadata` rejected n8n's `recipients` list | Schema now accepts scalars and lists of scalars |
| O-1 | Misleading `"status": "stubbed"` from `POST /reports/staging` | Status now derived from `quality_gate` + export state; request_id is a UUID |
| O-2 | Caddy bound only port 80 | Caddy serves a `PUBLIC_HOSTNAME` site with TLS, HSTS, and a `:80` fallback for local dev |
| O-3 | Compose published Qdrant/MinIO/n8n on the public interface | Internal services use `expose:`; public-facing ports bound to `127.0.0.1` |
| O-4 | Stale evaluation message claiming Phase 1G | Updated to Phase 1H |

## Must Be Controlled Before Phase 1E

- Documentation must agree on the 39-key environment baseline.
- Documentation must agree that Phase 1D and the Phase 1D-fixup are complete.
- RBAC documentation must use the 9 canonical roles from the locked spec.
- n8n workflows must declare `authentication=headerAuth` and read service-account
  credentials from environment variables.
- Service-account credentials must never be logged or transmitted via the
  webhook body.
- CI must enforce: ruff, compileall, config coverage (39 keys), smoke tests,
  integration tests, the n8n auth invariant, and `pip-audit` (non-blocking).

## Can Wait Until Later Phases

- LLM calls, claim checking, and report drafting can wait until Phase 1E.
- MinIO persistence and PostgreSQL audit writes can wait until Phase 1F.
- Approval and reject endpoints can wait until Phase 1G.
- Full golden-set execution, prompt regression, Arabic PDF hardening, and load
  testing can wait until Phase 1H.

## Admin And Control-Plane Coverage

The locked spec defines an `admin` RBAC role but does not define an Admin UI. The current
control plane is therefore documentation, configuration, CI, RBAC mapping, source mapping,
audit policy, approval policy, and operational runbooks.

The `admin` role is configuration-only. It MUST NOT grant business-data visibility by default.
Any future Admin UI, admin screen, or control-panel feature is outside the current spec and
must be treated as a spec change before implementation.

## Final Phase 0 Readiness Decision

**READY FOR PHASE 1E.**

Phase 1A–1D plus the Phase 1D-fixup are complete. The next safe step is Phase 1E
(LLM Nodes). This does not authorize persistence work, approval/reject endpoints,
publish logic, or Admin UI work before their assigned phases.
