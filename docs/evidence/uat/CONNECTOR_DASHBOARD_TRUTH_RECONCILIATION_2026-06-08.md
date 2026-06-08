# Connector Dashboard Truth Reconciliation

**Date:** 2026-06-08
**Verdict:** `CONNECTOR_DASHBOARD_TRUTH_RECONCILED_NOT_LIVE`
**Production status:** NOT_LIVE
**Branch:** `main`
**HEAD at start:** `029de7c1a63c7f1b4e47abe5cf91c892743d46db`

---

## Scope

Reconcile the Connectors & APIs dashboard truth model and restore the Odoo
read-only webhook path without starting Gate 4, Gate 5, UAT, Slice 7, or LIVE.

Hard restrictions observed:

- No Odoo writes.
- No SharePoint writes.
- No Microsoft Graph writes.
- No ownCloud enablement.
- No AI provider configuration.
- No secrets or tokens printed.

---

## Initial State

Preflight:

- `python3 scripts/agent_preflight.py` ran.
- `check_ai_context.py`: clean.
- `check_doc_drift.py`: clean.
- Preflight failed only because the worktree was already dirty before this task.
  Existing uncommitted changes were left in place and not reverted.

Runtime n8n inspection, read-only before repair:

- n8n DB: `/var/lib/docker/volumes/decisioncenter_n8n-data/_data/database.sqlite`
- `workflow_entity`: 0 rows.
- `webhook_entity`: 0 rows.
- Direct Odoo webhook probe from app container:
  - `POST http://n8n:5678/webhook/odoo-read`
  - HTTP 404
  - n8n message: requested webhook was not registered.

Source mappings, read-only PostgreSQL snapshot:

| Project | Mapping | Enabled sources | Odoo ID | Microsoft group status | Members |
|---|---|---|---|---|---:|
| PRJ-001 | complete | email, odoo, sharepoint | 14602 | GROUP_MEMBERS_READ | 17 |
| PRJ-002 | complete | email, odoo, sharepoint | 14601 | GROUP_MEMBERS_READ | 18 |

ownCloud is not in `enabled_sources` for either project.

---

## Why Statuses Were Wrong

Entra showed `CONFIGURED_NOT_TESTED` because the existing server-side probe only
reaches OIDC discovery. It does not validate a fresh user token, and no current
live UAT token evidence exists in the repo. This remains intentionally not live.

SharePoint and Microsoft Graph / Email showed `CONFIGURED_NOT_TESTED` because
`apps/edr/admin/connector_status.py` had no evidence-ingestion path for current
source mapping rows or Microsoft group enrichment. The dashboard saw configured
webhook paths but did not reconcile the already persisted PRJ-001 / PRJ-002
read evidence.

Odoo showed `CONNECTED_NO_DATA` with HTTP 404 because the n8n production webhook
path `odoo-read` was not registered. The n8n database had no active workflows or
webhook registrations.

---

## Odoo Webhook Restoration

Actions:

1. Created a backup before n8n DB mutation:
   `/var/lib/docker/volumes/decisioncenter_n8n-data/_data/database.sqlite.backup.1780913741.connector_dashboard`
2. Tried n8n CLI import for `n8n/odoo_read.json`.
   - Result: failed on `workflow_entity.active` NOT NULL constraint.
3. Created the n8n Header Auth credential through `n8n import:credentials`.
   - Token came from existing `.env`.
   - Token value was not printed.
   - Transient plaintext import file was deleted immediately after import.
4. Stopped n8n, inserted `odoo_read` into `workflow_entity`, registered
   `odoo-read` in `webhook_entity`, bound Header Auth to the webhook node, and
   restarted n8n.

Post-repair n8n state:

- `workflow_entity`: 1 row.
- `webhook_entity`: 1 row.
- `odoo_read`: active=1, triggerCount=1.
- `odoo-read`: registered as POST.
- Webhook auth: `headerAuth`.
- Credential reference present: yes.

Probe results:

- Unauthenticated Odoo webhook call: HTTP 403, as expected.
- Authenticated read-only connector truth probe:
  - `network_ok=True`
  - `auth_ok=True`
  - `permission_ok=True`
  - `live_data_ok=True`
  - `sample_count=100`
  - evidence summary: Odoo webhook returned 100 Odoo evidence items.

No Odoo write was performed.

---

## Dashboard Truth Reconciliation

Code changes:

- `apps/edr/admin/connector_status.py`
  - Added `VERIFIED_FROM_EVIDENCE` connector state.
  - Added `data_source="evidence"` so persisted runtime evidence cannot be
    confused with a fresh live probe.
  - Added DB-first, file-fallback source mapping reconciliation for PRJ-001 and
    PRJ-002.
  - SharePoint moves to `VERIFIED_FROM_EVIDENCE` only when both projects have
    complete mappings, enabled SharePoint source, and real site/drive IDs.
  - Microsoft Graph / Email moves to `VERIFIED_FROM_EVIDENCE` only when both
    projects have enabled email source, `GROUP_MEMBERS_READ`, real mail-enabled
    group mailboxes, exact member counts 17 and 18, and no enrichment blockers.
  - Odoo still requires a real live webhook probe for `LIVE_OK`.
  - Historical docs are not parsed and cannot make a connector live.
- `apps/edr/app.py`
  - Mapped `VERIFIED_FROM_EVIDENCE` to System Health `ok`.
- `frontend/src/api/types.ts`
  - Added the new connector state and `evidence` data source.
- `frontend/src/screens/ConnectorTruthPanel.tsx`
  - Added explicit UI label: `Verified from evidence`.

Source-tree verification:

```text
sharepoint|VERIFIED_FROM_EVIDENCE|blocks=False|data=evidence|sample=2
microsoft_graph|VERIFIED_FROM_EVIDENCE|blocks=False|data=evidence|sample=35
```

Runtime note:

The running app container is image-built and does not bind-mount source files.
The n8n Odoo webhook repair is live in the running runtime. The dashboard code
change is verified in the source tree and tests, but the app image was not
rebuilt in this session to avoid baking unrelated pre-existing dirty worktree
changes into the running app.

---

## Tests Added

`apps/edr/tests/integration/test_connector_truth.py` now covers:

- `data_source="evidence"` maps to `VERIFIED_FROM_EVIDENCE`, not `LIVE_OK`.
- Verified PRJ-001 / PRJ-002 SharePoint mapping marks SharePoint verified.
- Verified PRJ-001 / PRJ-002 group membership marks Microsoft Graph / Email verified.
- Incomplete group membership stays `CONFIGURED_NOT_TESTED` and blocks.

Existing coverage retained:

- ownCloud disabled does not block go-live.
- AI providers missing block report generation.
- Odoo HTTP 404 maps to `CONNECTED_NO_DATA`.
- No credential values appear in connector truth responses.

---

## Validation

Host system `pytest ...test_connector_truth.py` failed before collection because
the global Python environment has a FastAPI/Pydantic import mismatch
(`fastapi._compat.PYDANTIC_V2`). The repo `.venv` was used for pytest validation.

| Check | Result |
|---|---|
| `ruff check .` | PASS |
| `python3 -m compileall apps scripts` | PASS |
| `.venv/bin/python -m pytest apps/edr/tests/integration/test_connector_truth.py -q` | PASS — 31 passed |
| `.venv/bin/python -m pytest apps/edr/tests/integration/test_email_group_enrichment.py -q` | PASS — 30 passed |
| `.venv/bin/python -m pytest apps/edr/tests/integration/test_phase2b_source_mapping.py -q` | PASS — 68 passed |
| `npm --prefix frontend run lint` | PASS |
| `npm --prefix frontend run build` | PASS — existing Vite large-chunk warning |
| `python3 scripts/check_doc_drift.py` | PASS — clean |
| `python3 scripts/check_ai_context.py` | PASS — clean |

Postflight is run after this evidence file is written.

---

## Final Verdict

```text
CONNECTOR_DASHBOARD_TRUTH_RECONCILED_NOT_LIVE
```

The Odoo read-only webhook is restored in the runtime n8n layer. The dashboard
truth model now distinguishes current persisted Microsoft source-mapping
evidence from fresh live probes, so SharePoint and Microsoft Graph / Email no
longer remain `CONFIGURED_NOT_TESTED` when PRJ-001 and PRJ-002 evidence is
present. ownCloud remains disabled, AI providers remain not configured, Entra
still requires a fresh user-token validation path, and production remains
NOT_LIVE.
