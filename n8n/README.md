# n8n Workflows

This directory contains the four connector workflow files consumed by the Python
connector wrappers in `apps/edr/connectors/`.

| Workflow file | Source | Webhook path | Status |
|---|---|---|---|
| `sharepoint_search.json` | Microsoft Graph / SharePoint | `sharepoint-search` | **Phase 1C — Implemented** |
| `email_search.json` | Microsoft Graph / Email | `email-search` | **Phase 1C — Implemented** |
| `owncloud_list.json` | ownCloud WebDAV | `owncloud-list` | **Phase 1C — Implemented** |
| `odoo_read.json` | Odoo JSON-RPC (read-only) | `odoo-read` | **Phase 1C — Implemented** |

## Workflow Structure

Each workflow follows the same baseline pattern:

1. **Webhook Trigger** (`n8n-nodes-base.webhook`) — receives POST from the Python backend.
   `authentication = "headerAuth"` is required; n8n will refuse the request without
   a matching Header Auth credential. **Operators must create that credential before
   activating any workflow** — see *Operator setup* below.
2. **HTTP Request** (`n8n-nodes-base.httpRequest`) — calls the upstream API.
3. **Code Node** (`n8n-nodes-base.code`) — normalizes the raw API response into
   evidence objects.
4. **Respond to Webhook** (`n8n-nodes-base.respondToWebhook`) — returns the
   evidence payload.

The `email_search` workflow has an additional **Enforce Mailbox Allowlist** code
node between the webhook and the Graph call — see *Source-specific rules*.

## Input / Output Contracts

### Input (webhook body)

All workflows expect a JSON body. The body carries **request-scoped data only**:

- `project_code`, `query`, `domain`, `model`, `fields`
- For SharePoint and Email: `access_token` (the user's delegated Microsoft Graph token)
- Source configuration sourced from the project mapping (`site_id`, `drive_id`,
  `base_url`, `root_path`)

Service-account credentials are **never** in the body. The ownCloud and Odoo
workflows read their credentials directly from n8n's process environment
(`$env.OWNCLOUD_USERNAME`, `$env.OWNCLOUD_PASSWORD`, `$env.ODOO_DATABASE`,
`$env.ODOO_USERNAME`, `$env.ODOO_API_KEY`, `$env.ODOO_URL`). docker-compose
forwards those env vars to the n8n container — **do not** put them on the wire
between the FastAPI app and n8n.

### Output (respond body)

```json
{
  "evidence": [
    {
      "evidence_id": "sp-001",
      "source_type": "sharepoint",
      "source_uri": "...",
      "title": "...",
      "project_code": "PRJ-001",
      "excerpt": "...",
      "hash_sha256": "...",
      "confidence": "high",
      "timestamp": "...",
      "tags": [...],
      "metadata": {...}
    }
  ]
}
```

Every item must validate against `docs/schemas/evidence-object.schema.json`.

## Source-Specific Rules

- **SharePoint**: returns document metadata + excerpt. `hash_sha256` derived
  from item content hash.
- **Email**: returns **excerpt only** (≤ 500 characters). Full email bodies
  are never stored. The mailbox allowlist is enforced twice — once in
  `apps/edr/graph/node_07_email.py` (Python) and once in the
  `Enforce Mailbox Allowlist` n8n code node, which throws if `user_mailbox`
  is not in `allowed_mailboxes`.
- **ownCloud**: returns WebDAV file metadata. Excerpt is the file name or
  directory label. Credentials come from `$env.OWNCLOUD_USERNAME` /
  `$env.OWNCLOUD_PASSWORD`.
- **Odoo**: returns read-only record facts. Credentials come from
  `$env.ODOO_DATABASE` / `$env.ODOO_USERNAME` / `$env.ODOO_API_KEY` and the
  RPC URL from `$env.ODOO_URL`. Every evidence object includes `model`,
  `record_id`, and `timestamp`.

## Validation

Isolated Python tests in `apps/edr/tests/integration/test_connectors.py` and
`apps/edr/tests/integration/test_phase1d_security.py` mock n8n responses and
enforce both schema validation and the security invariants described above.
Run with:

```bash
make test
```

## Operator setup

Before importing any workflow:

1. In n8n, **Credentials → New → Header Auth**:
   - Name: `Decision Center Webhook`
   - Header name: `Authorization`
   - Header value: `Bearer ${N8N_WEBHOOK_TOKEN}` (matching the value in `.env`).
2. Set the env vars on the n8n container (already wired in
   `docker-compose.yml`):
   `OWNCLOUD_USERNAME`, `OWNCLOUD_PASSWORD`, `ODOO_DATABASE`, `ODOO_USERNAME`,
   `ODOO_API_KEY`, `ODOO_URL`.
3. Workflow → Import from JSON → paste the contents of the desired `.json` file.
4. Bind the imported webhook node to the `Decision Center Webhook` credential.
5. Activate the workflow.

> **Note:** The Docker Compose volume mounts `./n8n:/workflows:ro` inside the
> n8n container for reference, but n8n does not auto-import workflows on
> startup.
