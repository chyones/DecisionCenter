# Project Source Mapping — Gate 3 Readiness

> **Verdict:** `PROJECT_SOURCE_MAPPING_BLOCKED_FOR_GATE_3_NOT_LIVE`
> **Date:** 2026-06-04
> **Timestamp (UTC):** 2026-06-04T12:53:30Z
> **HEAD:** `fc54c64cd37adb234c01296bf34dd89274196602`
> **File inspected:** `docs/config/project_source_mapping.json`
> **Production status:** NOT_LIVE

---

## 1. Current State of `project_source_mapping.json`

The file contains **2 projects** (`PRJ-001`, `PRJ-002`) with **8 placeholder values**
across SharePoint and email fields. No real values exist in the repo or any runtime
evidence scanned.

### Placeholder inventory

| # | Field path | Current value | Required |
|---|-----------|---------------|---------|
| 1 | `[PRJ-001].sharepoint.site_id` | `"example-site-id-001"` | Real SharePoint site GUID |
| 2 | `[PRJ-001].sharepoint.drive_id` | `"example-drive-id-001"` | Real document-library drive GUID |
| 3 | `[PRJ-001].email.shared_mailboxes[0]` | `"project-prj-001@example.com"` | Real shared mailbox SMTP address |
| 4 | `[PRJ-001].email.document_control_mailbox` | `"doc-control@example.com"` | Real doc-control mailbox SMTP address |
| 5 | `[PRJ-002].sharepoint.site_id` | `"example-site-id-002"` | Real SharePoint site GUID |
| 6 | `[PRJ-002].sharepoint.drive_id` | `"example-drive-id-002"` | Real document-library drive GUID |
| 7 | `[PRJ-002].email.shared_mailboxes[0]` | `"project-prj-002@example.com"` | Real shared mailbox SMTP address |
| 8 | `[PRJ-002].email.document_control_mailbox` | `"doc-control-002@example.com"` | Real doc-control mailbox SMTP address |

Fields **not** requiring changes (already correct or non-Microsoft):
- `sharepoint.root_path` — `/Projects/PRJ-001`, `/Projects/PRJ-002` (path within the drive; confirm with operator but format is correct)
- `owncloud.base_path` — ownCloud is `NOT_REQUIRED_FOR_GO_LIVE`
- `odoo.*` — Odoo external IDs; no change needed for Microsoft Gate 3
- `contract_numbers` — no change needed for Microsoft Gate 3

---

## 2. How These Values Are Used (Runtime Impact)

### 2.1 SharePoint (`site_id`, `drive_id`)

`node_05_sharepoint.py` reads the mapping and passes both values directly into the
`search_sharepoint()` payload:

```python
payload = {
    "query": state.query,
    "project_code": state.project_code,
    "site_id": sp_config.get("site_id"),
    "drive_id": sp_config.get("drive_id"),
}
```

The `sharepoint_search` n8n workflow constructs the Graph API URL as:

```
https://graph.microsoft.com/v1.0/sites/{site_id}/drives/{drive_id}/root/search(q='{query}')
```

With placeholder values, this URL resolves to a non-existent Graph resource and will
return **HTTP 404** from Microsoft Graph. Gate 3 would fail immediately.

### 2.2 Email (`shared_mailboxes`, `document_control_mailbox`)

`node_07_email.py` uses the mapping for the mailbox allowlist check:

```python
allowed = [mb.lower() for mb in state.allowed_mailboxes]
if user_mailbox not in allowed:
    state.outputs["email_status"] = "denied_mailbox_not_in_allowlist"
```

`search_email()` then passes `user_mailbox` to the `email_search` n8n workflow, which
constructs:

```
https://graph.microsoft.com/v1.0/users/{user_mailbox}/messages?$search="...query..."&$top=25
```

With `@example.com` addresses, the Graph call will return **HTTP 400** (invalid user) or
**HTTP 404** (mailbox not found in tenant). The allowlist check will also deny any real
user since no real address is in the allowlist.

### 2.3 Database Seeding

`postgres_store.py` seeds the `source_mappings` table from this file on first run:

```python
"site_id": sp.get("site_id", ""),
"drive_id": sp.get("drive_id", ""),
"shared_mailboxes": em.get("shared_mailboxes", []),
"document_control_mailbox": em.get("document_control_mailbox", ""),
```

The table already contains the placeholder values. After the operator updates the JSON
file, the app container must be restarted (or `init-qdrant` / mapping reseed run) to
propagate the real values into the database.

---

## 3. Real Values Are Not Available in Repo or Evidence

Searched:
- `docs/config/`, `docs/operations/`, `docs/evidence/` — no real `site_id` / `drive_id` values found
- `.env`, `.env.bak*` — no SharePoint coordinates
- n8n workflow JSONs — hardcode `$json.body.site_id` / `$json.body.drive_id` (received at runtime; not stored in workflow)
- Git history — `project_source_mapping.json` has never held non-placeholder SharePoint/email values

**Conclusion: the operator must supply these values. They cannot be derived from the codebase.**

---

## 4. Operator Checklist — Exact Values Required

The operator needs Microsoft Graph API access (`Files.Read.All` and `Mail.Read` are already
confirmed granted in Gate 2) and knowledge of which SharePoint sites/mailboxes belong to
each project.

### Step 1 — Find `site_id` and `drive_id` for each project

Use the Graph token acquired in Gate 2 (or acquire a fresh one) against the API confirmed
working in Gate 2:

```bash
# List tenant sites — find the site for PRJ-001
curl -s -H "Authorization: Bearer <graph_token>" \
  "https://graph.microsoft.com/v1.0/sites?search=PRJ-001&\$select=id,displayName,webUrl"

# Alternatively browse by known hostname:
curl -s -H "Authorization: Bearer <graph_token>" \
  "https://graph.microsoft.com/v1.0/sites/<hostname>:/sites/<site-name>?&\$select=id,displayName"

# Then list drives (document libraries) on that site:
curl -s -H "Authorization: Bearer <graph_token>" \
  "https://graph.microsoft.com/v1.0/sites/<site_id>/drives?&\$select=id,name"
```

`site_id` format: `<hostname>,<site-collection-id>,<web-id>` (e.g. `elrace.sharepoint.com,abc123...,def456...`)  
`drive_id` format: UUID string (e.g. `b!abc123...`)

### Step 2 — Confirm shared mailbox addresses for each project

Real SMTP addresses of the shared mailboxes that project team members use. These must
be mailboxes that exist in the `elrace.com` tenant (confirmed domain in Gate 1/2).

Typical format: `prj-001@elrace.com`, `doc-control-prj001@elrace.com` — the operator
knows the actual addresses.

Confirm each address is accessible with `Mail.Read` (already granted):

```bash
curl -s -H "Authorization: Bearer <graph_token>" \
  "https://graph.microsoft.com/v1.0/users/<mailbox_address>/mailFolders/inbox?\$top=1"
# Should return HTTP 200 if mailbox exists and is accessible
```

### Step 3 — Update `docs/config/project_source_mapping.json`

Replace all 8 placeholder values. Example structure (do not use these dummy values):

```json
[
  {
    "project_code": "PRJ-001",
    "sharepoint": {
      "site_id": "<real-site-id-from-step-1>",
      "drive_id": "<real-drive-id-from-step-1>",
      "root_path": "/Projects/PRJ-001"
    },
    "email": {
      "shared_mailboxes": ["<real-project-mailbox@elrace.com>"],
      "document_control_mailbox": "<real-doc-control@elrace.com>"
    },
    ...
  },
  {
    "project_code": "PRJ-002",
    "sharepoint": {
      "site_id": "<real-site-id-for-prj-002>",
      "drive_id": "<real-drive-id-for-prj-002>",
      "root_path": "/Projects/PRJ-002"
    },
    "email": {
      "shared_mailboxes": ["<real-project-mailbox-prj002@elrace.com>"],
      "document_control_mailbox": "<real-doc-control-prj002@elrace.com>"
    },
    ...
  }
]
```

### Step 4 — Reseed the database

After updating the JSON, restart the app container so `postgres_store.py` picks up the
new values:

```bash
docker compose up -d --build app
curl http://127.0.0.1:8000/healthz  # confirm HTTP 200
```

If the `source_mappings` table was already seeded with placeholder values, trigger a
reseed (or truncate and let the app re-seed on startup — confirm with ops runbook).

---

## 5. Gate 3 Start Condition

Gate 3 can start **only after all 8 placeholder values are replaced** and the app is
restarted. The connector live probes in Gate 3 will fail deterministically with
HTTP 404/400 from Microsoft Graph while any placeholder remains.

---

## 6. Final Verdict

**`PROJECT_SOURCE_MAPPING_BLOCKED_FOR_GATE_3_NOT_LIVE`**

`docs/config/project_source_mapping.json` contains 8 placeholder values across 4 fields
for 2 projects. No real SharePoint site/drive coordinates or tenant mailbox addresses are
available in the repo or runtime evidence — they must be supplied by the operator.
The operator checklist in §4 specifies the exact Graph API calls needed to obtain them.
Production remains `NOT_LIVE`.
