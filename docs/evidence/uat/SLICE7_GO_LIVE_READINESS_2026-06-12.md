# Phase 2D Slice 7 — Go-Live Gate Readiness

**Date:** 2026-06-12. **Status:** Slice 7 **NOT STARTED / BLOCKED**.
`requires_explicit_user_approval_for_phase_2d = true`. System **NOT_LIVE**.
This document records readiness only; it does **not** start Slice 7 and does
**not** constitute approval.

## Readiness checklist

| Gate | State | Evidence |
|---|---|---|
| Generation provider live (DeepSeek, no fallback, cost capped) | **READY** | `DEEPSEEK_MODEL_NAME_FIX_2026-06-12.md`, `GO_LIVE_BLOCKER_RESOLUTION_2026-06-12.md` §D |
| Full report graph runs, DeepSeek-served | **READY** | §D, 5/5 HTTP 200, no fallback |
| Odoo evidence chain | **READY** | live `project.project` id 14435 |
| Entra v2 token version + validator | **READY (config+code)** | §A; pending one operator user-token smoke |
| upload_ids safe | **READY** | proven harmless + regression tests (§C) |
| Slice 6 UAT artifact exists | **READY** | `UAT_RUN_2026-06-12.md` |
| SharePoint/Mail evidence into live report | **BLOCKED** | n8n credential fix staged for approval + live import (§B); Mail group-mailbox design open |
| Deployed `/reports/staging` via real auth | **BLOCKED** | needs interactive Entra user token (§A) |
| Explicit operator go-live approval | **ABSENT** | no approval artifact anywhere under `docs/evidence/` |

## Open items before Slice 7 can start

1. **Approve + import** the staged n8n credential fix (and SharePoint query
   quoting) into live n8n; re-run the SharePoint evidence probe to green.
2. **Resolve Mail group-mailbox** retrieval (design decision) or explicitly
   descope email for go-live.
3. **One operator user-token smoke** of `/reports/staging` through the
   deployed auth surface (`scripts/validate_entra_auth.py` + a real login).
4. **One clean end-to-end** deployed-API report with SharePoint+Odoo evidence,
   quality gate passing, approval + publish + download captured to a new
   `UAT_RUN_<date>.md`.
5. **Explicit written operator approval** for Phase 2D go-live (separate,
   deliberate sign-off — never inferred).

## Approval block (operator to complete — left intentionally unsigned)

```
Phase 2D Go-Live Approval
  Approved by: ____________________   Role: ____________   Date: __________
  UAT_RUN reference: ______________   Commit: ____________
  I authorise production go-live.     Signature: ________________________
```

Until items 1–5 are closed **and** this block is signed by an authorised
operator, the system remains **NOT_LIVE**. This session did not mark LIVE and
holds no authority to.
