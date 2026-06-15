# Phase 2D Slice 7 — Go-Live Gate Readiness (updated 2026-06-15)

**Status:** Slice 7 **NOT STARTED / APPROVAL BLOCKED**.
`requires_explicit_user_approval_for_phase_2d = true`. System **NOT_LIVE**.
This document records readiness only; it does **not** start Slice 7 and does
**not** constitute approval.

## Readiness checklist

| Gate | State | Evidence |
|---|---|---|
| Generation provider live (DeepSeek, no fallback, cost capped) | **READY** | `DEEPSEEK_MODEL_NAME_FIX_2026-06-12.md`; this session: 5/5 HTTP 200, tokens 1238/2367, cost $0.0046 |
| Full report graph runs, DeepSeek-served | **READY** | Full 18-node run this session (2026-06-15); PASS all checks |
| Odoo evidence chain | **READY** | live `project.project` id 14435 (prior sessions) |
| Entra v2 token version + validator | **READY (config+code)** | `GO_LIVE_BLOCKER_RESOLUTION_2026-06-12.md` §A; pending one operator user-token smoke |
| upload_ids safe | **READY** | proven harmless + regression tests (`test_upload_ids_inert.py`) |
| Slice 6 UAT artifact exists | **READY** | `UAT_RUN_2026-06-12.md` |
| n8n Graph credential fix | **READY in repo — import pending** | `N8N_GRAPH_CREDENTIAL_FIX_2026-06-15.md`; operator must run `docker compose exec n8n n8n import:workflow` for sharepoint_search + email_search |
| SharePoint evidence into live report | **BLOCKED — import pending** | Fix is validated against live Graph (200 items); live n8n not yet updated |
| Mail evidence | **DESCOPED for go-live** | `N8N_GRAPH_CREDENTIAL_FIX_2026-06-15.md` §Mail; operator decision 2026-06-15; `EMAIL_EVIDENCE_DESCOPED_DESIGN_PENDING` |
| Deployed `/reports/staging` via real auth | **BLOCKED** | needs interactive Entra user token (§A of `GO_LIVE_BLOCKER_RESOLUTION_2026-06-12.md`) |
| Explicit operator go-live approval | **ABSENT** | no approval artifact anywhere under `docs/evidence/` |

## Remaining items before Slice 7 can start

1. **Import n8n fix** (one operator command):
   ```bash
   docker compose exec n8n n8n import:workflow --input=/workflows/sharepoint_search.json --separate
   docker compose exec n8n n8n import:workflow --input=/workflows/email_search.json --separate
   ```
   Then re-probe `sharepoint-search` webhook — should return `{"evidence": [...]}` with items.

2. **One operator user-token smoke** of `/reports/staging` through the deployed auth surface
   (`scripts/validate_entra_auth.py --base-url https://vantage.elrace.com --token "<user-token>"`).

3. **One clean end-to-end** deployed-API report with SharePoint+Odoo evidence flowing, quality
   gate passing, approval + publish + download captured → new `UAT_RUN_<date>.md`.

4. **Explicit written operator approval** for Phase 2D go-live (approval block below; separate
   from this document; never inferred from other actions).

## What is NOT a remaining blocker

- **Email evidence**: explicitly descoped for go-live by operator direction 2026-06-15.
  Documented as `EMAIL_EVIDENCE_DESCOPED_DESIGN_PENDING`; post-go-live design work.
- **upload_ids ingestion**: MEDIUM_RISK deferred, proven harmless, not a gate.
- **Langfuse tracing**: keys empty, tracing not configured, not a gate.
- **ownCloud**: disabled by design, not re-enabled.

## Approval block (operator to complete — left intentionally unsigned)

```
Phase 2D Go-Live Approval
  Approved by: ____________________   Role: ____________   Date: __________
  UAT_RUN reference: ______________   Commit: ____________
  I authorise production go-live.     Signature: ________________________
```

Until items 1–4 above are closed **and** this block is signed by an authorised operator,
the system remains **NOT_LIVE**. This session did not mark LIVE and holds no authority to.
