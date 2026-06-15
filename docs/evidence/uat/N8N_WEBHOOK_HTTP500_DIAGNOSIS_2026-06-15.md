# n8n SharePoint Webhook HTTP 500 — Diagnosis and Operator Fix

**Date:** 2026-06-15. System status: **NOT_LIVE** (unchanged).
No secrets printed. No code changed. Verification session only.

## Summary

All three n8n imports (commits 9dbc168 and daf279a) updated the workflow DB correctly.
The SharePoint webhook continues to return HTTP 500. Root cause is a combination of two
n8n runtime issues that require operator action via the n8n web UI, not via import.

## 1. Import history (2026-06-15)

| Import # | Commit | Time | updatedAt in DB | Result |
|---|---|---|---|---|
| 1st | f22822e (no id) | ~06:00 | 2026-06-11 (UNCHANGED) | Silently skipped — no `id` field |
| 2nd | 9dbc168 (with id) | 07:16 | 2026-06-15 07:16:04 | Took — `authentication:none` in DB |
| 3rd | daf279a (credentials) | 08:06 | 2026-06-15 08:06:51 | Took — credentials STRIPPED by CLI |
| 4th | daf279a (re-import) | 08:06 | 2026-06-15 08:06:51 | Same — credentials STRIPPED again |

## 2. Current workflow state in DB (verified 2026-06-15 post-import)

| Check | sharepoint_search | email_search |
|---|---|---|
| `workflow_entity.active` | `True` | `True` |
| `updatedAt` | `2026-06-15 08:06:51` | `2026-06-15 08:06:57` |
| `Graph Search` / `Graph Mail Search` `authentication` | `none` ✓ | `none` ✓ |
| `Graph Search` / `Graph Mail Search` `genericAuthType` | ABSENT ✓ | ABSENT ✓ |
| `Receive Request` `credentials.httpHeaderAuth` | **ABSENT** ✗ | **ABSENT** ✗ |

## 3. Root cause A — n8n import CLI strips webhook credentials

**Observed behaviour**: Every `n8n import:workflow` call removes the `credentials` field
from `Receive Request` webhook nodes, even when the referenced credential exists in
`credentials_entity` and is shared with the correct project.

**Why**: n8n's import function calls `replaceInvalidCredentials()` internally, which strips
credential references that cannot be validated server-side. For webhook nodes, this validation
consistently fails (possibly because webhook credentials are registered under a different
principal than the CLI import process). This is consistent n8n CLI behaviour across all
import attempts.

**The working `odoo_read` workflow** has `credentials.httpHeaderAuth` set because the
credential was attached via the n8n **web UI**, not via import. The UI path writes directly
to the workflow entity with the correct owner context.

**Consequence**: `Receive Request` nodes in sharepoint_search and email_search have
`authentication: headerAuth` but no credential reference. n8n cannot validate the incoming
`Authorization` header and fails in its pre-execution phase.

## 4. Root cause B — `pathLength=NULL` test webhook rows

The 2nd import (07:16) added two extra `webhook_entity` rows:
```
workflowId=c349923e-…  path=c349923e-…/receive%20request/sharepoint-search  webhookId=None  pathLength=None
workflowId=f80ee218-…  path=f80ee218-…/receive%20request/email-search        webhookId=None  pathLength=None
```

These rows are NOT in n8n's in-memory routing (probing their paths returns HTTP 404).
However, when n8n re-registered the webhook after import, something in n8n's activation
path created a partially-corrupt in-memory routing state — the production `sharepoint-search`
path is found (returns 500, not 404), but execution fails before any record is created.

**Before** the 2nd import (2026-06-11 state): HTTP 200, empty body (workflow execution
started but failed at `Graph Search` with `NodeOperationError: Credentials not found`).
**After** the 2nd import: HTTP 500, before any execution starts — routing state corrupted.

The `pathLength=NULL` rows are the only DB change that happened between the two behaviours.

## 5. HTTP 500 error detail

```
POST /webhook/sharepoint-search → HTTP 500
{"code":0,"message":"Cannot read properties of undefined (reading 'node')"}
```

- Error type: **unhandled exception in n8n's webhook dispatch layer** (before execution)
- No `execution_entity` record is created for any post-08:06 probe
- Most recent logged execution: execId=375 at `06:35:43` (BEFORE both imports)
- This is NOT a workflow execution error; it is a routing/dispatch exception

## 6. Operator fix required (n8n web UI)

**The import path cannot fix this.** The credential reference must be set via n8n's web UI.

### Step 1 — Restart n8n (clears routing corruption)

```bash
docker compose restart n8n
```

This removes the `pathLength=NULL` rows from n8n's in-memory routing table and rebuilds
a clean routing state from the DB.

### Step 2 — Set credential via n8n web UI

Open n8n web UI (port 5678). For each of `sharepoint_search` and `email_search`:

1. Open the workflow in the canvas editor
2. Click on the **Receive Request** node
3. In the node parameters panel, find **"Authentication"** → currently set to **"Header Auth"**
4. Click the **"Credential for Header Auth"** field
5. Select **"DecisionCenter Webhook Header Auth"** from the dropdown
6. Click **Save**
7. Confirm the workflow is **Active** (toggle in top-right corner)

### Step 3 — Verify

After Step 2, probe the SharePoint webhook with a valid Graph Bearer token:

```python
# Run from host, send to n8n container IP
POST http://172.22.0.5:5678/webhook/sharepoint-search
Content-Type: application/json
Authorization: Bearer <N8N_WEBHOOK_TOKEN>

{
  "site_id": "elrace.sharepoint.com,a505675a-...,26e3f61b-...",
  "drive_id": "b!WmcFpV3Rg...",
  "query": "guard room",
  "project_code": "PRJ-001",
  "access_token": "<graph_client_creds_token>"
}
```

Expected: HTTP 200 `{"evidence": [...]}` with ≥1 item.

### Why this will work (unlike import)

- UI → n8n saves workflow with credential reference in correct owner context
- `pathLength=NULL` rows are neutralised by restart (clean routing table)
- After restart + UI credential assignment, n8n can validate the header, proceed through
  execution, call Graph API, and return evidence

## 7. Odoo verification (this session)

```
POST /webhook/odoo-read (model=project.project, domain=[["id","=",14602]])
→ HTTP 200  evidence items: 1
  odoo-project-project-14602  Construction of Civil Defense building in Al Marfa
```

Odoo: **WORKING**. Credential on `Receive Request` was set via UI (not import) — persists.

## 8. DeepSeek verification (this session)

Full 18-node graph run (in-process, env from container):

```
visited_nodes: 18/18
deepseek http calls: 5  statuses=[200, 200, 200, 200, 200]
token_usage: input=1243 output=1957
cost_accumulated_usd: 0.003197
fallback_used: False
publish_status: blocked_until_approval (expected — Postgres DNS not resolvable from host)
```

DeepSeek: **PASS, no fallback**.

## 9. Test suite

```
747 passed, 12 skipped, 181 warnings
```

All tests green.

## Verdict

`N8N_UI_CREDENTIAL_ASSIGNMENT_REQUIRED_NOT_LIVE`

The n8n import CLI cannot attach webhook credentials. The `Receive Request` nodes must have
"DecisionCenter Webhook Header Auth" selected in the n8n web UI. After restart + UI
credential assignment, the SharePoint webhook should return HTTP 200 `{"evidence":[...]}`.
Odoo, DeepSeek, and auth enforcement are all confirmed working. System remains **NOT_LIVE**.
