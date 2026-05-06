# DecisionCenter — Phase 0 Control Plane Lock

> **Date:** 2026-05-06
> **Scope:** Documentation and control state only.
> **Behavioral source of truth:** `docs/workflows/EDR-AGENTIC-RAG-v2.1.md`
> **Execution sequence source of truth:** `docs/execution/IMPLEMENTATION_PHASES.md`

This document locks the control expectations that must be clear before application
implementation starts. It does not add application features and does not define an
Admin UI.

## Phase 0 Decisions

| Area | Authoritative Decision | Evidence |
|---|---|---|
| Environment baseline | `.env.example` has 36 keys; planning docs that said 50 were stale | `.env.example` |
| Config coverage | `apps/edr/config.py` loads all 36 keys from `.env.example` | `apps/edr/config.py` |
| Phase sequence | Phase 1A is Infrastructure Foundation before product/node logic | `docs/execution/IMPLEMENTATION_PHASES.md` |
| RBAC model | Use the 9 canonical spec roles | `docs/security/rbac_matrix.md` |
| n8n status | Four workflow JSON files exist and are placeholders with empty `nodes` arrays | `n8n/*.json` |
| Evaluation baseline | One JSONL golden example exists; 12 baseline categories and 50 go-live cases are required by spec | `apps/edr/evaluation/goldenset/example.jsonl`, spec Section 26 |
| Readiness | Phase 1A infrastructure readiness is 10/10 | This document and validation proof |

## Authoritative Environment Baseline

The authoritative env baseline is the current `.env.example` file. It contains exactly
these 36 keys:

| Group | Keys |
|---|---|
| App | `APP_ENV`, `APP_HOST`, `APP_PORT`, `PUBLIC_BASE_URL` |
| Identity | `ENTRA_CLIENT_ID`, `ENTRA_TENANT_ID`, `ENTRA_CLIENT_SECRET` |
| LLM providers | `ANTHROPIC_API_KEY`, `VOYAGE_API_KEY`, `COHERE_API_KEY` |
| Data stores | `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`, `REDIS_URL`, `QDRANT_URL`, `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_BUCKET` |
| Connector layer | `N8N_BASE_URL`, `N8N_WEBHOOK_TOKEN`, `SHAREPOINT_SEARCH_WEBHOOK`, `OWNCLOUD_LIST_WEBHOOK`, `EMAIL_SEARCH_WEBHOOK`, `ODOO_READ_WEBHOOK` |
| Odoo | `ODOO_URL`, `ODOO_DATABASE`, `ODOO_USERNAME`, `ODOO_API_KEY` |
| Observability and budget | `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`, `DAILY_COST_CAP_USD`, `MONTHLY_COST_TARGET_USD` |

`apps/edr/config.py` now loads these 36 fields.

## Must Be Controlled Before Phase 1A

- Documentation must agree on the 36-key environment baseline.
- Documentation must agree that Phase 1A is infrastructure-only.
- RBAC documentation must use the 9 canonical roles from the locked spec.
- n8n workflows must be documented as placeholders, not functional retrieval.
- Evaluation status must state the actual one-case golden set without inventing cases.
- Missing files and future artifacts must be marked as missing or to-create.

## Must Be Controlled Before Phase 1B

- `apps/edr/config.py` loads all 36 `.env.example` keys.
- `GET /healthz` checks PostgreSQL, Redis, Qdrant, and MinIO.
- Dependencies are pinned to exact runtime versions.
- CI exists and runs safe lint, config coverage, and smoke checks on push and pull request.
- Qdrant collection initialization exists and is idempotent.
- The Caddy ACME email uses a non-placeholder contact.

## Can Wait Until Later Phases

- Real Entra JWT validation and role resolution can wait until Phase 1B.
- Real n8n workflow implementation can wait until Phase 1C.
- Embeddings, vector insertion, reranking, and Redis-backed cache can wait until Phase 1D.
- LLM calls, claim checking, and report drafting can wait until Phase 1E.
- MinIO persistence and PostgreSQL audit writes can wait until Phase 1F.
- Approval and reject endpoints can wait until Phase 1G.
- Full golden-set execution, prompt regression, Arabic PDF hardening, and load testing can wait until Phase 1H.

## Admin And Control-Plane Coverage

The locked spec defines an `admin` RBAC role but does not define an Admin UI. The current
control plane is therefore documentation, configuration, CI, RBAC mapping, source mapping,
audit policy, approval policy, and operational runbooks.

The `admin` role is configuration-only. It MUST NOT grant business-data visibility by default.
Any future Admin UI, admin screen, or control-panel feature is outside the current spec and
must be treated as a spec change before implementation.

## Final Phase 0 Readiness Decision

**READY FOR PHASE 1B.**

Phase 1A Infrastructure Foundation is implemented locally. The next safe step is Phase 1B
RBAC and Identity. This does not authorize product retrieval logic, LLM calls, n8n workflow
implementation, approval logic, audit logic, or Admin UI work before their assigned phases.
