# n8n SharePoint/Email Webhook Repair — 2026-06-15

**Status: NOT_LIVE (unchanged).** Server-side repair of the n8n webhook routing for
`sharepoint_search` and `email_search`, performed without the n8n UI, without re-importing
workflows, and **without restarting n8n**. No secrets printed. DeepSeek/Odoo untouched except
verification. ownCloud not re-enabled.

## Root cause (definitive)

The `Receive Request` webhook node in `sharepoint_search` and `email_search` was **missing its
node-level `webhookId`**. The known-good `odoo_read` node has `webhookId: dc-odoo-read`.

In `n8n-workflow` `NodeHelpers.getNodeWebhookPath(workflowId, node, path, isFullPath, …)`
(verified in the running container, n8n 1.91.3):

```js
if (node.webhookId === undefined) {
    webhookPath = `${workflowId}/${encodeURIComponent(node.name.toLowerCase())}/${path}`;
} else if (isFullPath === true) {
    return path;            // webhook node sets isFullPath: true
}
```

With `webhookId` undefined, n8n computed the production path as
`c349923e-…/receive%20request/sharepoint-search` instead of `sharepoint-search`. That:

1. registered a **malformed `webhook_entity` row** (`webhookId=NULL`, `pathLength=NULL`); and
2. at request time, `LiveWebhooks.executeWebhook` looked up the cached clean row
   (`webhookPath="sharepoint-search"`), then called
   `getNodeWebhooks(workflow, getNode("Receive Request")).find(w => w.path === "sharepoint-search")`.
   Because the node had no `webhookId`, `getNodeWebhooks` produced the long path, so `.find`
   returned `undefined` and `webhookData.node` threw **HTTP 500 "Cannot read properties of
   undefined (reading 'node')"** — before any execution (no `execution_entity` row created).

`odoo_read` (single clean row, node has `webhookId`) always worked, which isolated the fault.

## Why no restart was required

`LiveWebhooks.executeWebhook` loads the workflow **nodes fresh from the DB on every request**
(`workflowRepository.findOne(...)`); only the `webhook_entity` lookup is cached, and that
already returned the correct clean row. Writing the node-level `webhookId` to the DB is picked
up on the very next webhook call. The webhook node uses `isFullPath: true`, so with any defined
`webhookId` the computed path is `sharepoint-search` again — matching the cached clean row.
(The cache backend is in-memory — no queue mode — so it cannot be flushed externally; the
fix deliberately does not depend on it.)

## Repair performed (target workflows only)

Reusable script: `scripts/repair_n8n_webhooks.py` (idempotent; `--dry-run` supported).

1. **Backup** (timestamped, before any write):
   `…/decisioncenter_n8n-data/_data/database.sqlite.backup-20260615T095114Z`
   (integrity-checked; an earlier manual backup `…backup-20260615T093947Z` also exists).
2. **Set node `webhookId`** on `Receive Request`: `dc-sharepoint-search`, `dc-email-search`
   (reused from each workflow's existing clean `webhook_entity` row).
3. **Ensure** `authentication=headerAuth` + `credentials.httpHeaderAuth` =
   `90d9168a-…` (already bound; enforced idempotently).
4. **Delete malformed `webhook_entity` rows** (2 total) where
   `pathLength IS NULL OR webhookId IS NULL OR webhookPath != <prod path>` — target workflows
   only. `odoo_read` untouched.
5. Both workflows left **active**.

### Exact DB rows changed

| Table | Workflow | Change |
|---|---|---|
| `workflow_entity.nodes` | sharepoint_search | `Receive Request.webhookId` `∅ → dc-sharepoint-search` |
| `workflow_entity.nodes` | email_search | `Receive Request.webhookId` `∅ → dc-email-search` |
| `webhook_entity` | sharepoint_search | deleted row `c349923e-…/receive%20request/sharepoint-search` (NULL/NULL) |
| `webhook_entity` | email_search | deleted row `f80ee218-…/receive%20request/email-search` (NULL/NULL) |

### Post-repair `webhook_entity` (clean, one row per workflow)

```
odoo-read         webhookId=dc-odoo-read         pathLength=1
sharepoint-search webhookId=dc-sharepoint-search pathLength=1
email-search      webhookId=dc-email-search      pathLength=1
```
malformed rows remaining: **0**.

## Verification

| Check | Result |
|---|---|
| sharepoint_search active | yes |
| email_search active | yes |
| malformed webhook rows remaining | no (0) |
| webhook credential bound | yes (`90d9168a-…` on both) |
| SharePoint webhook (real Graph token) | **HTTP 200, 200 evidence items**, non-empty `{"evidence":[...]}` (2.5s) |
| Full PRJ-001 report graph | 18/18 nodes; `sharepoint_status: ok (89 items)`, `odoo_status: ok (1 items)` |
| SharePoint evidence in report | yes (89) |
| Odoo evidence in report | yes (1) |
| DeepSeek fallback | no (4 calls, all HTTP 200) |
| quality gate | passed |

`publish_status: blocked_until_approval` — expected for the in-process runner (host cannot
resolve the `postgres` container hostname; gracefully caught). The deployed API publishes
normally.

## Durability + recurrence prevention

- The fix survives future restarts/re-activations: with the node `webhookId` now present,
  n8n re-registers only the clean row (never the malformed one).
- Repo source updated so a future import is correct: `n8n/sharepoint_search.json` and
  `n8n/email_search.json` `Receive Request` nodes now include `webhookId`. (Import still strips
  the credential — re-run `scripts/bind_n8n_webhooks.py`/`repair_n8n_webhooks.py` after any
  import; never rely on import as the fix.)

## Verdict

`N8N_SHAREPOINT_WEBHOOK_REPAIRED_LIVE; SHAREPOINT+ODOO+DEEPSEEK_VERIFIED; NOT_LIVE` — webhook
routing restored server-side with no UI, no import, no restart. System remains **NOT_LIVE**
pending the deployed-API run with an interactive Entra user token and the signed go-live approval.
