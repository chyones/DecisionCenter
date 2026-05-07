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

Each workflow follows the same pattern:

1. **Webhook Trigger** (`n8n-nodes-base.webhook`) — receives POST from Python backend.
2. **HTTP Request** (`n8n-nodes-base.httpRequest`) — calls the upstream API.
3. **Code Node** (`n8n-nodes-base.code`) — normalizes raw API response into evidence objects.
4. **Respond to Webhook** (`n8n-nodes-base.respondToWebhook`) — returns JSON payload.

## Input / Output Contracts

### Input (webhook body)

All workflows expect a JSON body. Required fields vary by source; typical fields include:

- `project_code`
- `query` or `domain` / `model`
- Authentication tokens (`access_token`, `username`/`password`, `api_key`)
- Source configuration (`site_id`, `drive_id`, `base_url`, `odoo_url`, etc.)

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

- **SharePoint**: Returns document metadata + excerpt. `hash_sha256` derived from item content hash.
- **Email**: Returns **excerpt only** (≤ 500 characters). Full email bodies are never stored.
- **ownCloud**: Returns WebDAV file metadata. Excerpt is file name or directory label.
- **Odoo**: Returns read-only record facts. Every evidence object includes `model`, `record_id`, and `timestamp`.

## Validation

Isolated Python tests in `apps/edr/tests/integration/test_connectors.py` mock n8n
responses and enforce schema validation for all four sources. Run with:

```bash
make test
```

## Import into n8n

1. Start the stack: `make up`
2. Open n8n at `http://localhost:5678`
3. Workflow → Import from JSON → paste the contents of the desired `.json` file.
4. Configure credentials (Microsoft Graph, WebDAV Basic Auth, Odoo API).
5. Activate the workflow.

> **Note:** The Docker Compose volume mounts `./n8n:/workflows:ro` inside the n8n
> container for reference, but n8n does not auto-import workflows on startup.
