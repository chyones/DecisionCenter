# Post-Operator Verification — 2026-06-15

**Status: NOT_LIVE (unchanged).** Verify-only session after operator rebuilt the app on
commit `4d0e861`, ran `scripts/bind_n8n_webhook_auth.py`, and restarted n8n. No code changed,
no workflows imported, no secrets printed, LIVE not marked.

## Results

| Check | Result |
|---|---|
| App health (`/healthz`, container + `vantage.elrace.com`) | **OK** — status ok, postgres/redis/qdrant/minio ok, 18 nodes |
| Deployed app carries the Odoo fix | **YES** — `build_project_query()` present in container `connectors/odoo.py` + `node_08_odoo.py` (app pid restarted) |
| n8n health (`/healthz`) | **OK** (n8n 1.91.3) |
| n8n webhook credential bound | **YES** — bind script worked; `Receive Request` httpHeaderAuth.id=90d9168a on both sharepoint_search + email_search |
| Graph node auth | **OK** — `authentication=none` on Graph Search / Graph Mail Search |
| **Odoo evidence via live webhook** | **WORKING** — `odoo-read` → HTTP 200, **1 item**, new fields (name, date_start, date, user_id, partner_id) |
| **Odoo evidence reaches report graph** | **YES** — full 18-node PRJ-001 run: `odoo_status: ok (1 items)`, evidence by source `{odoo: 1}` |
| **DeepSeek fallback** | **NO** — 4 calls, all HTTP 200, `fallback_used: False`, cost $0.0095 |
| Quality gate | passed |
| **SharePoint webhook** | **STILL HTTP 500** — `{"code":0,"message":"Cannot read properties of undefined (reading 'node')"}`, instant (0.0s) |
| SharePoint evidence in report | **0 items** — `sharepoint_status: error 500` |

## SharePoint 500 — root cause NOT fully cleared by bind+restart

The bind script fixed the **credential** (now bound), but the HTTP 500 persists. It is a
**pre-execution routing error**, not a credential/execution error:

- The probe returns 500 in 0.0s; **no `execution_entity` row is created** (newest SharePoint
  execution is execId=375 at 06:35:43, before this session's probes).
- The single-row `odoo-read` webhook works (HTTP 200); only `sharepoint-search` and
  `email-search` 500.
- The structural difference: `webhook_entity` still contains two malformed rows
  (`webhookId=NULL`, `pathLength=NULL`) for the long test-style paths
  `<workflowId>/receive%20request/sharepoint-search` and `…/email-search`. n8n's dynamic
  webhook router orders/matches by `pathLength`; a NULL value breaks the lookup
  (`reading 'node'` of undefined). The n8n restart re-registered these rows from the DB rather
  than clearing them, so the credential fix alone did not resolve routing.

## Remaining blocker (1) — exact operator fix (no import, no code change)

Remove the malformed `webhook_entity` rows, then restart n8n. Either:

- **n8n UI (preferred):** open each workflow (`sharepoint_search`, `email_search`), toggle
  **Active → off → Save**, then **Active → on → Save**. Deactivation removes the workflow's
  webhook registrations; reactivation re-creates only the correct ones.
- **or DB cleanup:** delete the rows where `pathLength IS NULL` from `webhook_entity`, then
  `docker compose restart n8n`.

Then re-probe `sharepoint-search` with a real Graph Bearer token → expect HTTP 200 non-empty
`{"evidence":[...]}`. (Optional permanent hardening from the runbook: replace the stored-credential
headerAuth with an inline Code-node bearer check so future imports can't reintroduce this.)

## UAT status

**UAT_RUN_2026-06-15.md NOT written** — the end-to-end run is not clean: Odoo + DeepSeek pass,
but SharePoint evidence is absent (webhook 500). Re-run after the routing fix above to capture a
clean UAT with both `sharepoint` and `odoo` evidence.

## Verdict

`ODOO_FIX_CONFIRMED_LIVE; SHAREPOINT_WEBHOOK_ROUTING_STILL_BLOCKED; NOT_LIVE` — the Odoo
evidence fix is verified working end-to-end through the live webhook and report graph, DeepSeek
is fallback-free, app + n8n healthy. One blocker remains: n8n SharePoint/email webhook routing
(stale `pathLength=NULL` rows) needs a deactivate→reactivate (or NULL-row delete) + restart.
