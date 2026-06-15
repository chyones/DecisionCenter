# n8n Import Verification — 2026-06-15

**Date:** 2026-06-15. System status: **NOT_LIVE** (unchanged).
No secrets printed. No code changed (n8n JSON workflow IDs added — config only).

## 1. n8n health + auth

| Check | Result |
|---|---|
| n8n `/healthz` | **HTTP 200 `{"status":"ok"}`** |
| n8n PID | 1830774 (restarted from prior 714203 — restart confirmed) |
| SharePoint webhook (no auth token) | **HTTP 403** — header auth enforced |
| SharePoint webhook (with token) | HTTP 200 (see §3) |

## 2. Import did NOT take — root cause and fix

### What the operator ran

```
docker compose exec n8n n8n import:workflow --input=/workflows/sharepoint_search.json --separate
docker compose exec n8n n8n import:workflow --input=/workflows/email_search.json --separate
```

### Why it failed

`n8n import:workflow` matches existing workflows by the `id` field in the JSON. The repo
JSON files had **no `id` field**, so n8n could not find the existing workflows to update.
The import silently created no new entries (name collision guard) and left the existing
workflows unchanged.

**SQLite evidence** (read immediately after restart):
```
sharepoint_search  id=c349923e-…  active=True  updatedAt=2026-06-11 09:38:03.618
email_search       id=f80ee218-…  active=True  updatedAt=2026-06-11 09:38:03.620
```
`updatedAt` still shows 2026-06-11 — the import date before the fix was written. Confirmed
unchanged.

### Fix applied to repo JSON (2026-06-15)

The live n8n workflow UUIDs have been added to the repo source files:
- `n8n/sharepoint_search.json`: top-level `"id": "c349923e-8772-4a8d-9fdb-f2738e60344e"`
- `n8n/email_search.json`: top-level `"id": "f80ee218-ef6e-40c5-a229-bfe2d4f66755"`

### Required operator action (one command each)

```bash
docker compose exec n8n n8n import:workflow --input=/workflows/sharepoint_search.json --separate
docker compose exec n8n n8n import:workflow --input=/workflows/email_search.json --separate
```

With the workflow `id` now present in the JSON, n8n will find the existing workflows by ID
and update them in place. After import, re-probe the `sharepoint-search` webhook with a valid
Graph Bearer token — it should return `{"evidence": [...]}` with ≥1 item.

## 3. SharePoint webhook — current state (pre-fix-import)

Probe with bearer-auth header included, PRJ-001 site/drive IDs, placeholder Graph token
(verifies the `"access_token"` placeholder reaches Graph — Graph rejects it, not n8n):

```
HTTP 200  body: 0 bytes (EMPTY)
```

**Cause**: live n8n `Graph Search` node still has `authentication: genericCredentialType`
(the broken pre-fix value) — `NodeOperationError: Credentials not found` before any Graph
call is even attempted. Confirmed by SQLite node-param inspection.

**Expected state after re-import**: probe with valid Graph Bearer token should return
`{"evidence": [...]}` because:
- The credential defect will be removed (`authentication: none`)
- The OData query quoting will be fixed (`search(q='term')`)
- This combination was validated in a prior session against live Graph → HTTP 200, 200 items

## 4. Odoo — WORKING

Direct webhook probe with PRJ-001 domain `[["id", "=", 14602]]`:
```
HTTP 200  evidence items: 1
  odoo-project-project-14602  Construction of Civil Defense building in Al Marfa
```

Note: The graph node uses domain `[["project_external_id", "=", "14602"]]` which returns
0 items (no such field in `project.project`). This is a pre-existing code issue —
not changed per "do not change code" rule. The connector and Odoo credentials are fully live;
the domain field name in the graph node needs a separate fix.

## 5. Mail — DESCOPED (unchanged)

Decision from 2026-06-15 operator directive unchanged: `EMAIL_EVIDENCE_DESCOPED_DESIGN_PENDING`.
See `N8N_GRAPH_CREDENTIAL_FIX_2026-06-15.md` §Mail.

## 6. DeepSeek — PASS (no fallback)

Full 18-node graph run (in-process, runtime env from container PID 1830774):

```
visited_nodes: all 18 (node_00_begin … node_17_publish)
deepseek http calls: 5  statuses=[200, 200, 200, 200, 200]
token usage: {'input': 1265, 'output': 2201}
cost_accumulated_usd: 0.004315
draft_report_status: generated
fallback_used: False
```

`odoo_status: error: name resolution` and `sharepoint_status: error: name resolution` are
expected — the in-process runner uses the Docker internal hostname `n8n:5678` which only
resolves inside the compose network. Generation is DeepSeek-served regardless.

## 7. Pending operator actions

| # | Action | Command |
|---|---|---|
| 1 | Re-import fixed SharePoint workflow | `docker compose exec n8n n8n import:workflow --input=/workflows/sharepoint_search.json --separate` |
| 2 | Re-import fixed email workflow | `docker compose exec n8n n8n import:workflow --input=/workflows/email_search.json --separate` |
| 3 | Verify SharePoint webhook | Probe `sharepoint-search` with valid Graph Bearer token in body; expect non-empty `{"evidence":[...]}` |
| 4 | Interactive Entra user token smoke | `python scripts/validate_entra_auth.py --base-url https://vantage.elrace.com --token <user-token>` |
| 5 | Clean end-to-end deployed report | POST to real API, SharePoint+Odoo evidence, capture UAT_RUN_<date>.md |
| 6 | Explicit go-live approval | Sign `SLICE7_GO_LIVE_READINESS_2026-06-15.md` approval block |

## Verdict

`N8N_IMPORT_RETRY_REQUIRED_NOT_LIVE` — JSON IDs added to repo; re-import required before
SharePoint evidence can be verified live. DeepSeek, Odoo connectivity, n8n health, and auth
enforcement all confirmed. System remains **NOT_LIVE**.
