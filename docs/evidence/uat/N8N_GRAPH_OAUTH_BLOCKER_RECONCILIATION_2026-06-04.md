# n8n Graph OAuth2 Credential Blocker — Reconciliation

> **Verdict:** `N8N_GRAPH_OAUTH_NOT_REQUIRED_NOT_LIVE`
> **Date:** 2026-06-04
> **Timestamp (UTC):** 2026-06-04T12:50:07Z
> **HEAD:** `fc54c64cd37adb234c01296bf34dd89274196602`
> **Context:** Gate 2 evidence (`MICROSOFT_GATE_2_GRAPH_PERMISSIONS_2026-06-04.md`) listed
> "n8n Graph OAuth2 credential not yet bound to workflow nodes" as a remaining blocker.
> This document reconciles that claim against the actual workflow definitions and backend code.

---

## 1. Question Being Answered

Do `sharepoint_search` and `email_search` n8n workflows require a Microsoft Graph OAuth2
credential stored in n8n, or do they receive the Graph access token via pass-through from
the backend payload?

---

## 2. n8n Workflow Node Analysis

### 2.1 Source: JSON files (`n8n/`)

Both workflow JSON files were inspected with `json.loads`.

#### `sharepoint_search` (4 nodes)

| Node | Type | Credentials | Token reference |
|------|------|-------------|-----------------|
| Receive Request | `webhook` | `httpHeaderAuth` (webhook gate) | — |
| **Graph Search** | `httpRequest` | **none** | **yes** |
| Normalize Evidence | `code` | none | — |
| Respond | `respondToWebhook` | none | — |

`Graph Search` → `headerParameters.Authorization`:
```
={{ 'Bearer ' + $json.body.access_token }}
```

#### `email_search` (5 nodes)

| Node | Type | Credentials | Token reference |
|------|------|-------------|-----------------|
| Receive Request | `webhook` | `httpHeaderAuth` (webhook gate) | — |
| Enforce Mailbox Allowlist | `code` | none | — |
| **Graph Mail Search** | `httpRequest` | **none** | **yes** |
| Normalize Evidence | `code` | none | — |
| Respond | `respondToWebhook` | none | — |

`Graph Mail Search` → `headerParameters.Authorization`:
```
={{ 'Bearer ' + $json.body.access_token }}
```

### 2.2 Source: n8n SQLite DB (live, in Docker volume)

DB path: `/var/lib/docker/volumes/decisioncenter_n8n-data/_data/database.sqlite`

Both workflows confirmed **active=1** in `workflow_entity`.  
DB node definitions match the JSON files exactly — `credentials` key is absent on both
Graph HTTP nodes; `Authorization` header value is `={{ 'Bearer ' + $json.body.access_token }}`.

**No n8n-stored credential is attached to either Graph HTTP node in the live DB.**

---

## 3. Backend Token Injection — Confirmed

### `apps/edr/connectors/sharepoint.py`

```python
async def search_sharepoint(payload: dict[str, Any]) -> list[EvidenceObject]:
    token = await get_graph_token()
    client = N8NWebhookClient(settings.n8n_base_url, settings.n8n_webhook_token)
    response = await client.post(
        settings.sharepoint_search_webhook,
        {**payload, "access_token": token},   # ← injected here
    )
```

### `apps/edr/connectors/email.py`

```python
async def search_email(payload: dict[str, Any]) -> list[EvidenceObject]:
    token = await get_graph_token()
    client = N8NWebhookClient(settings.n8n_base_url, settings.n8n_webhook_token)
    response = await client.post(
        settings.email_search_webhook,
        {**payload, "access_token": token},   # ← injected here
    )
```

### `apps/edr/connectors/graph_token.py`

Acquires a Graph access token via **client credentials flow** using `ENTRA_CLIENT_ID` /
`ENTRA_CLIENT_SECRET` / `ENTRA_TENANT_ID`. Returns an empty string when Entra is not
configured. Token is cached and refreshed 60 s before expiry. Gate 2 confirmed this token
acquisition succeeds and the token carries `['Files.Read.All', 'Mail.Read']` roles.

---

## 4. End-to-End Token Flow

```
Backend (FastAPI)
  │
  ├─ get_graph_token()
  │    └─ client_credentials → Entra → access_token (Files.Read.All, Mail.Read)
  │
  ├─ POST /webhook/sharepoint-search   (body: {...payload, access_token: <token>})
  │    └─ n8n: Receive Request (httpHeaderAuth validates webhook secret)
  │         └─ Graph Search  httpRequest
  │              Authorization: ={{ 'Bearer ' + $json.body.access_token }}
  │                           ↑ reads access_token from body, no n8n credential needed
  │
  └─ POST /webhook/email-search        (body: {...payload, access_token: <token>})
       └─ n8n: Receive Request (httpHeaderAuth validates webhook secret)
            └─ Graph Mail Search  httpRequest
                 Authorization: ={{ 'Bearer ' + $json.body.access_token }}
```

The pattern is deliberate: the backend (which already manages Entra credentials via
`ENTRA_CLIENT_ID`/`ENTRA_CLIENT_SECRET`) acquires the Graph token and passes it as a
plain body field. n8n reads it from `$json.body.access_token` and injects it as a Bearer
header. n8n never needs to store or manage Graph credentials itself.

---

## 5. Conclusion

**A Microsoft Graph OAuth2 credential stored in n8n is not required and was never part of
the intended architecture.**  The Gate 2 evidence file incorrectly listed it as a blocker;
that listing was based on earlier readiness documents that pre-dated the token pass-through
implementation.

The only n8n credential in use is `DecisionCenter Webhook Header Auth` (`httpHeaderAuth`),
which gates the webhook endpoint itself — confirmed bound to `Receive Request` nodes in
both workflows in the live DB.

---

## 6. Revised Blocker List Before Gate 3

| Former blocker | Status |
|----------------|--------|
| n8n Graph OAuth2 credential not bound to workflow nodes | **REMOVED — not required** |
| `project_source_mapping.json` placeholder `site_id`, `drive_id`, mailboxes | **REMAINS** — operator must supply real values |

The single remaining operator-configuration item before Gate 3 is replacing the
`example*` placeholder values in `docs/config/project_source_mapping.json`.

---

## 7. Final Verdict

**`N8N_GRAPH_OAUTH_NOT_REQUIRED_NOT_LIVE`**

Both `sharepoint_search` and `email_search` workflows use `={{ 'Bearer ' + $json.body.access_token }}`
in their Graph HTTP nodes and carry no n8n-stored Graph credential in either the JSON
definitions or the live DB. The backend injects a client-credentials Graph token into
every webhook payload. The Gate 2 blocker was incorrect and is now removed.
Production remains `NOT_LIVE`.
