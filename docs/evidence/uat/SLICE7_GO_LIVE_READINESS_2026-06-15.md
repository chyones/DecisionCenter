# Phase 2D Slice 7 — Go-Live Gate Readiness (updated 2026-06-15)

**Status:** Slice 7 **NOT STARTED / APPROVAL BLOCKED**.
`requires_explicit_user_approval_for_phase_2d = true`. System **NOT_LIVE**.
This document records readiness only; it does **not** start Slice 7 and does
**not** constitute approval. Execution steps: `GO_LIVE_RUNBOOK_2026-06-15.md`.

## Readiness checklist

| Gate | State | Evidence |
|---|---|---|
| Generation provider live (DeepSeek, no fallback, cost capped) | **READY** | `DEEPSEEK_MODEL_NAME_FIX_2026-06-12.md`; 5/5 HTTP 200, no fallback |
| Full report graph runs, DeepSeek-served | **READY** | full 18-node run 2026-06-15 |
| App deployed + infra healthy | **READY** | `/healthz` ok (postgres/redis/qdrant/minio), `APP_ENV=production` |
| Public HTTPS edge | **READY** | `https://vantage.elrace.com/healthz` → 200 (cloudflared up) |
| Secret rotation (no change-me) | **READY** | `POSTGRES_PASSWORD` + `MINIO_SECRET_KEY` rotated; app boots under fail-fast |
| Entra v2 token version + validator | **READY (config+code)** | `GO_LIVE_BLOCKER_RESOLUTION_2026-06-12.md` §A; pending one operator user-token smoke |
| upload_ids safe | **READY** | proven harmless + regression tests (`test_upload_ids_inert.py`) |
| **Odoo evidence into report** | **FIX IN REPO — app rebuild pending** | node_08/node_11 queried bad field/columns → 0 items; fixed via `build_project_query()` (query by `id`); proven 1 item live. Needs `docker compose up -d --build app` |
| SharePoint evidence into live report | **FIX IN REPO — bind+restart pending** | Graph node fix live in n8n DB; webhook 500 from stripped credential. `bind_n8n_webhook_auth.py` + `docker compose restart n8n`. See `N8N_WEBHOOK_HTTP500_DIAGNOSIS_2026-06-15.md` |
| Mail evidence | **DESCOPED for go-live** | group-mailbox design; `EMAIL_EVIDENCE_DESCOPED_DESIGN_PENDING` |
| Odoo financial/cost evidence | **DESCOPED for go-live** | `budget`/`actual_cost` live in `account.analytic.line`; deferred 2026-06-15 (owner) |
| Deployed `/reports/staging` via real auth | **BLOCKED** | needs interactive Entra user token |
| Explicit operator go-live approval | **ABSENT** | no approval artifact anywhere under `docs/evidence/` |

## Remaining items before Slice 7 can start

Full commands in `GO_LIVE_RUNBOOK_2026-06-15.md`. In short:

1. **Rebuild app** for the Odoo evidence fix: `docker compose up -d --build app`.
2. **Fix n8n webhook**: `python scripts/bind_n8n_webhook_auth.py` then
   `docker compose restart n8n`; re-probe `sharepoint-search` → `{"evidence":[...]}`.
3. **Entra user-token smoke** of `/reports/staging`
   (`scripts/validate_entra_auth.py --base-url https://vantage.elrace.com --token "<user-token>"`).
4. **One clean end-to-end** deployed-API PRJ-001 report with SharePoint + Odoo evidence flowing,
   quality gate passing, approve + publish + download → new `UAT_RUN_2026-06-15.md`.
5. **Explicit written operator approval** (block below).

## What is NOT a remaining blocker

- **Email evidence** — descoped 2026-06-15 (`EMAIL_EVIDENCE_DESCOPED_DESIGN_PENDING`).
- **Odoo financial/cost** — descoped 2026-06-15; project-record evidence (name/dates/manager/
  client) flows; cost from `account.analytic.line` is post-go-live work.
- **upload_ids ingestion** — MEDIUM_RISK deferred, proven harmless, not a gate.
- **Langfuse tracing** — keys empty, not a gate.
- **ownCloud** — disabled by design, not re-enabled.

## Approval block (operator to complete — left intentionally unsigned)

```
Phase 2D Go-Live Approval
  Approved by: ____________________   Role: ____________   Date: __________
  UAT_RUN reference: ______________   Commit: ____________
  I authorise production go-live.     Signature: ________________________
```

Until items 1–5 above are closed **and** this block is signed by an authorised operator,
the system remains **NOT_LIVE**. This session did not mark LIVE and holds no authority to.
