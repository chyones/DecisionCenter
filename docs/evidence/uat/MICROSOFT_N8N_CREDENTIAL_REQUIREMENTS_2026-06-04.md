# Microsoft / n8n Credential Requirements

> **Purpose:** Document the exact Microsoft Entra and n8n credential requirements
> needed before SharePoint and email connectors can be activated.
> **Does NOT:** Execute UAT, claim any connector LIVE_OK, or perform Microsoft Entra actions.
> **Date:** 2026-06-04
> **Timestamp (UTC):** 2026-06-04T09:47:48Z
> **HEAD:** `fc54c64cd37adb234c01296bf34dd89274196602`
> **Branch:** `main`
> **Phase:** 2D Slice 6 incomplete, Slice 7 blocked
> **Service status:** NOT_LIVE

---

## 1. Inspection Basis

All findings are derived from source inspection only. No secrets, tokens, passwords,
OAuth refresh tokens, or credential values are printed anywhere in this document.

| Source inspected | Method |
|---|---|
| `git rev-parse HEAD` | Confirmed `fc54c64` |
| `git status` | Working tree state |
| `n8n/sharepoint_search.json` | Workflow node parameters |
| `n8n/email_search.json` | Workflow node parameters |
| `n8n/owncloud_list.json` | Workflow node parameters |
| n8n SQLite DB (`decisioncenter_n8n-data`) | `credentials_entity`, `workflow_entity`, `webhook_entity` |
| `apps/edr/graph/node_05_sharepoint.py` | How SharePoint payload is built |
| `apps/edr/graph/node_07_email.py` | How email payload is built |
| `apps/edr/connectors/sharepoint.py` | Connector implementation |
| `apps/edr/connectors/email.py` | Connector implementation |
| `apps/edr/connectors/base.py` | N8N webhook client implementation |
| `apps/edr/config.py` | Settings / env-var presence (boolean only) |
| `apps/edr/admin/connector_status.py` | Connector spec definitions |
| `docs/operations/CONNECTORS_CONNECTION_GUIDE.md` | Architecture intent |
| `docker-compose.yml` | n8n service definition and WEBHOOK_URL |

---

## 2. n8n Container Status

| Item | Value |
|---|---|
| Image | `n8nio/n8n:1.91.3` |
| Internal host | `n8n` (compose network) |
| Internal port | `5678` |
| External exposure | None — `expose: ["5678"]` only, no host port binding |
| WEBHOOK_URL | `http://n8n:5678` (internal compose URL from `N8N_BASE_URL`) |
| n8n-data volume | `decisioncenter_n8n-data` — SQLite DB accessible on host |
| Editor access | SSH tunnel to port 5678 only |

> **Implication:** n8n has no public-facing URL. Its WEBHOOK_URL is internal.
> No n8n OAuth redirect URI is needed in Microsoft Entra (see Section 6).

---

## 3. Workflows Inspected

### 3.1 sharepoint_search

| # | Node name | Node type | Auth configuration | Credential binding (live DB) |
|---|-----------|-----------|-------------------|------------------------------|
| 1 | `Receive Request` | `n8n-nodes-base.webhook` v2 | `authentication: "headerAuth"` | **NONE BOUND** |
| 2 | `Graph Search` | `n8n-nodes-base.httpRequest` v4.2 | `authentication: "genericCredentialType"`, `genericAuthType: "httpHeaderAuth"` | **NONE BOUND** |
| 3 | `Normalize Evidence` | `n8n-nodes-base.code` v2 | N/A | N/A |
| 4 | `Respond` | `n8n-nodes-base.respondToWebhook` v1.2 | N/A | N/A |

**Webhook path registered in n8n DB:** `sharepoint-search` (POST)

**How Graph Search passes the token (exact node parameter):**
```
"Authorization": "={{ 'Bearer ' + $json.body.access_token }}"
```
The access token is read from `$json.body.access_token` — i.e., forwarded from the
HTTP request body sent by the app. n8n does NOT hold a stored Microsoft Graph credential.

---

### 3.2 email_search

| # | Node name | Node type | Auth configuration | Credential binding (live DB) |
|---|-----------|-----------|-------------------|------------------------------|
| 1 | `Receive Request` | `n8n-nodes-base.webhook` v2 | `authentication: "headerAuth"` | **NONE BOUND** |
| 2 | `Enforce Mailbox Allowlist` | `n8n-nodes-base.code` v2 | N/A | N/A |
| 3 | `Graph Mail Search` | `n8n-nodes-base.httpRequest` v4.2 | `authentication: "genericCredentialType"`, `genericAuthType: "httpHeaderAuth"` | **NONE BOUND** |
| 4 | `Normalize Evidence` | `n8n-nodes-base.code` v2 | N/A | N/A |
| 5 | `Respond` | `n8n-nodes-base.respondToWebhook` v1.2 | N/A | N/A |

**Webhook path registered in n8n DB:** `email-search` (POST)

**How Graph Mail Search passes the token (exact node parameter):**
```
"Authorization": "={{ 'Bearer ' + $json.body.access_token }}"
```
Same pass-through pattern. n8n does NOT hold a stored Microsoft Graph credential.

---

### 3.3 owncloud_list

| # | Node name | Node type | Auth configuration | Credential binding (live DB) |
|---|-----------|-----------|-------------------|------------------------------|
| 1 | `Receive Request` | `n8n-nodes-base.webhook` v2 | `authentication: "headerAuth"` | **NONE BOUND** |
| 2 | `WebDAV PROPFIND` | `n8n-nodes-base.httpRequest` v4.2 | `authentication: "genericCredentialType"`, `genericAuthType: "httpHeaderAuth"` | **NONE BOUND** |
| 3 | `Normalize Evidence` | `n8n-nodes-base.code` v2 | N/A | N/A |
| 4 | `Respond` | `n8n-nodes-base.respondToWebhook` v1.2 | N/A | N/A |

**Webhook path registered in n8n DB:** `owncloud-list` (POST)

**How WebDAV PROPFIND authenticates (exact node parameters):**
```
"Authorization": "={{ 'Basic ' + Buffer.from(($env.OWNCLOUD_USERNAME || '') + ':' +
                   ($env.OWNCLOUD_PASSWORD || '')).toString('base64') }}"
```
ownCloud uses HTTP Basic Auth built from `$env.OWNCLOUD_USERNAME` and `$env.OWNCLOUD_PASSWORD`
— docker-compose environment variables, NOT a stored n8n credential.

---

## 4. Credentials Found in n8n (Live DB — name/type only, no values)

| Credential name | Credential type | Status |
|---|---|---|
| `DecisionCenter Webhook Header Auth` | `httpHeaderAuth` | **Present** |

**No Microsoft Graph OAuth2 credential exists in n8n.**

---

## 5. Missing Credentials

| Credential | Where needed | Current state |
|---|---|---|
| Microsoft Graph OAuth2 | **Not needed in n8n** (see Section 7) | N/A — architecture uses pass-through |
| `DecisionCenter Webhook Header Auth` binding on `sharepoint_search` → `Receive Request` | n8n workflow node | **NOT BOUND** |
| `DecisionCenter Webhook Header Auth` binding on `email_search` → `Receive Request` | n8n workflow node | **NOT BOUND** |
| `DecisionCenter Webhook Header Auth` binding on `owncloud_list` → `Receive Request` | n8n workflow node | **NOT BOUND** |
| Graph access token acquisition in app code | `node_05_sharepoint.py` line 28, `node_07_email.py` line 38 | **HARDCODED `""`** (placeholder — code not yet written) |
| `OWNCLOUD_USERNAME` / `OWNCLOUD_PASSWORD` in `.env` | `docker-compose.yml` env vars → n8n `$env` | **EMPTY** |
| `ANTHROPIC_API_KEY` | AI report generation | **EMPTY** |
| `VOYAGE_API_KEY` | Embeddings | **EMPTY** |
| `COHERE_API_KEY` | Reranking | **EMPTY** |

---

## 6. Critical Architectural Finding — Token Pass-Through Design

> **This section corrects a prior assumption in earlier runbooks.**

Prior runbooks (MICROSOFT_GATE_1_OPERATOR_RUNBOOK_2026-06-04.md) stated that
n8n must hold a "Microsoft Graph OAuth2 credential". **This is incorrect based
on the actual workflow implementation.**

**What the workflows actually do:**

Both `Graph Search` (sharepoint_search) and `Graph Mail Search` (email_search)
are `httpRequest` nodes using `genericAuthType: "httpHeaderAuth"` and injecting:
```
Authorization: Bearer {{ $json.body.access_token }}
```
The token comes from the request body sent by the DecisionCenter app backend.

**What the app backend currently sends:**
- `node_05_sharepoint.py` line 28: `"access_token": ""`
- `node_07_email.py` line 38: `"access_token": ""`

Both are hardcoded empty strings — **Graph token acquisition is not yet implemented**.

**Design intent (from CONNECTORS_CONNECTION_GUIDE.md):**
The app should acquire a Microsoft Graph token using **client credentials flow**
(application permissions, `scope: https://graph.microsoft.com/.default`), then
pass it to n8n in the request body. The app already has:
- `entra_client_id` set in `.env`
- `entra_tenant_id` set in `.env`
- `entra_client_secret` present in `.env` (boolean confirmed, value not read)

**Consequence for n8n:**
- No Microsoft Graph OAuth2 credential needs to be created in n8n
- No n8n OAuth redirect URL needs to be registered in Microsoft Entra
- The credential bindings needed in n8n are only the webhook header auth bindings
  on the 3 `Receive Request` nodes — the AI will complete these after Microsoft actions

---

## 7. n8n OAuth Redirect / Callback URL — NOT REQUIRED

**Question:** What n8n OAuth redirect URL must be registered in Microsoft Entra?

**Answer: None.**

Reason: The workflows do not use n8n's built-in OAuth2 credential flow.
The access token is acquired by the app backend (client credentials flow)
and forwarded to n8n in the HTTP POST body. Client credentials flow does not
use a redirect URI at all.

n8n's WEBHOOK_URL (`http://n8n:5678`) is also an internal compose address and
could not receive OAuth callbacks from the Microsoft authorization endpoint.

---

## 8. Microsoft Entra App Registration Context

| Item | Value |
|---|---|
| SPA client (frontend login) | `97519dfa-650b-4c77-8895-f34a8169871b` |
| API app (token validator + Graph token source) | `a2160d26-acc0-4d8c-b815-3a377f1fb5bd` |
| Tenant | `14a72467-3f25-4572-a535-3d5eddb00cc5` |
| Client secret presence | **Confirmed present** in `.env` (boolean only — value not read) |
| App roles currently defined | Unknown — no evidence file from Azure; must be verified |
| Graph permissions currently granted | Unknown — no admin consent evidence file exists |

---

## 9. Required Microsoft Graph Permissions

**Target registration:** API app `a2160d26-acc0-4d8c-b815-3a377f1fb5bd`

**Permission type:** Application permissions (not delegated).

> **Why application, not delegated:**
> The DecisionCenter backend acquires a Graph token using client credentials
> (app authenticates as itself, not on behalf of a user). Delegated permissions
> require a signed-in user context; the LangGraph pipeline runs server-side.
> Evidence: `config.py` has `entra_client_secret`; CONNECTORS_CONNECTION_GUIDE.md
> specifies `scope: https://graph.microsoft.com/.default` (client credentials scope).

| Permission | Type | Scope | Required for | Admin consent? |
|---|---|---|---|---|
| `Files.Read.All` | Application | Microsoft Graph | SharePoint file search | **Yes** |
| `Mail.Read` | Application | Microsoft Graph | User mailbox search | **Yes** |
| `Mail.Read.Shared` | Application | Microsoft Graph | Shared/project mailbox search | **Yes** |

**Forbidden permissions (do not grant):**
- `Files.ReadWrite.All` — write access not needed
- `Mail.ReadWrite` — write access not needed
- `Mail.Send` — send access not needed
- Any permission beyond read-only scope above

---

## 10. Delegated vs Application Permissions Determination

**Evidence reviewed:**
1. `node_05_sharepoint.py:28` — payload includes `"access_token": ""` sent from backend (not from a user session)
2. `node_07_email.py:38` — same pass-through pattern
3. `CONNECTORS_CONNECTION_GUIDE.md:211` — "Application permission: `Files.Read.All`"
4. `CONNECTORS_CONNECTION_GUIDE.md:105` — "Registered app client ID (application permissions: `Files.Read.All`, `Mail.Read`)"
5. `config.py:18` — `entra_client_secret` (present) — required for client credentials flow

**Verdict: Application permissions only. No OBO/delegated flow in scope.**

---

## 11. Microsoft-Only Operator Checklist

> The operator performs ONLY these steps. n8n is not touched.
> Values to provide back to AI are described in Section 13.

---

### Step A — Open the correct app registration

Navigate to: [portal.azure.com](https://portal.azure.com) → Azure Active Directory →
App registrations → Search for `a2160d26-acc0-4d8c-b815-3a377f1fb5bd` → Open it.

---

### Step B — Verify / add the redirect URI (SPA client only)

> This step is for the **SPA client** `97519dfa`, not the API app.
> Client credentials flow (API app) does NOT use a redirect URI.

- Open App registrations → `97519dfa-650b-4c77-8895-f34a8169871b`
- Click **Authentication**
- Under **Single-page application** platform, confirm both of these are listed:
  - `https://vantage.elrace.com`
  - `https://vantage.elrace.com/`  ← trailing slash variant
- If missing, click **Add URI** and add them
- Click **Save**

---

### Step C — Verify the client secret exists on the API app

- Open API app `a2160d26-acc0-4d8c-b815-3a377f1fb5bd`
- Click **Certificates & secrets** → **Client secrets** tab
- Confirm at least one secret exists and its **Expires** date is in the future
- If expired or missing: click **New client secret** → set expiry → copy the Value
  (value needed once for `.env` — will be provided to AI via secure channel, not chat)

---

### Step D — Add Microsoft Graph application permissions

- Open API app `a2160d26-acc0-4d8c-b815-3a377f1fb5bd`
- Click **API permissions** → **Add a permission** → **Microsoft Graph** → **Application permissions**
- Search and add:
  - `Files.Read.All`  (under Files)
  - `Mail.Read`  (under Mail)
  - `Mail.Read.Shared`  (under Mail)
- Click **Add permissions**

> If these already appear in the list with status "Granted for [tenant]", skip to Step E.

---

### Step E — Grant admin consent

- Still on **API permissions** for app `a2160d26`
- Click **Grant admin consent for [tenant name]**
- Confirm in the popup
- Verify all three permissions show status: **Granted for [tenant]** (green checkmark)

---

### Step F — Verify app roles are defined

- Open API app `a2160d26-acc0-4d8c-b815-3a377f1fb5bd`
- Click **App roles**
- Confirm these two roles exist with exact values:

  | Display name | Value | Allowed member types |
  |---|---|---|
  | `Admin` (or similar) | **`admin`** | Users/Groups |
  | `Executive` (or similar) | **`executive`** | Users/Groups |

- If missing: click **Create app role** and add them with those exact `Value` strings

---

### Step G — Assign users to app roles

- Navigate to: Azure Active Directory → **Enterprise applications** → Search for
  `a2160d26-acc0-4d8c-b815-3a377f1fb5bd`
- Click **Users and groups** → **Add user/group**
- Assign yourself (`ch.yones@gmail.com`) the **admin** role
- Assign other company owners the **executive** role
- Save

---

## 12. Values the Operator Must Provide Back (without exposing in chat)

| Value | How to provide |
|---|---|
| Screenshot or text confirmation that `Files.Read.All`, `Mail.Read`, `Mail.Read.Shared` are granted | Post screenshot in chat (no secret values visible) |
| Screenshot or text confirmation of app roles (`admin`, `executive`) defined and assigned | Post screenshot or confirm in text |
| Screenshot of SPA redirect URIs confirmed | Post screenshot |
| If the client secret was rotated or a new one created: the new secret value | Place in `/root/DecisionCenter/.env` as `ENTRA_CLIENT_SECRET=<value>` and tell AI "secret updated in .env" — do NOT paste value in chat |

---

## 13. What the AI Completes After Microsoft Actions

> These require no browser or Microsoft portal access. Performed entirely in code.

| # | Task | File(s) affected |
|---|------|-----------------|
| 1 | Implement Graph token acquisition (client credentials flow) in a new `apps/edr/connectors/graph_token.py`; replace `"access_token": ""` in node_05 and node_07 with the acquired token | `node_05_sharepoint.py`, `node_07_email.py`, new `graph_token.py` |
| 2 | Bind `DecisionCenter Webhook Header Auth` credential to the `Receive Request` node in `sharepoint_search`, `email_search`, `owncloud_list` workflows via Python DB update (no browser) | n8n SQLite DB |
| 3 | Rebuild app container: `docker compose up -d --build app` | Docker |
| 4 | Run `python scripts/validate_entra_auth.py --base-url https://vantage.elrace.com` with a fresh token | Validation script |
| 5 | Live-probe SharePoint and email connectors via `GET /admin/connectors/truth?probe=true` | Backend |

---

## 14. What Still Requires Manual Browser Login

| # | Action | Why manual |
|---|--------|-----------|
| 1 | Obtain a fresh Entra access token for `validate_entra_auth.py` | PKCE login flow — browser only |
| 2 | Sign in to `vantage.elrace.com` to confirm role resolution after app roles are assigned | User-interactive session |
| 3 | Live end-to-end report generation with a real project | Requires human judgment + sign-in |

---

## 15. Current State Summary

### Credentials

| Credential | Location | State |
|---|---|---|
| `DecisionCenter Webhook Header Auth` | n8n DB | **Present but unbound** on 3 Receive Request nodes |
| Microsoft Graph OAuth2 | n8n DB | **Not present — not needed** (pass-through architecture) |
| `entra_client_secret` | `.env` | **Present** |
| `n8n_webhook_token` | `.env` | **Present** |
| `ANTHROPIC_API_KEY` | `.env` | **Empty** — blocks report generation |
| `VOYAGE_API_KEY` | `.env` | **Empty** — blocks embeddings |
| `COHERE_API_KEY` | `.env` | **Empty** — blocks reranking |
| `OWNCLOUD_USERNAME/PASSWORD` | `.env` | **Empty** — ownCloud NOT_CONFIGURED |

### Workflows

| Workflow | Active | Webhook paths registered | Credentials bound |
|---|---|---|---|
| `sharepoint_search` | Yes | `sharepoint-search` | Receive Request: **none** |
| `email_search` | Yes | `email-search` | Receive Request: **none** |
| `owncloud_list` | Yes | `owncloud-list` | Receive Request: **none** |
| `odoo_read` | Yes | `odoo-read` | Receive Request: `httpHeaderAuth` ✓ |

### App backend

| Check | State |
|---|---|
| `app_env` | `production` — Entra auth enforced |
| Graph token acquisition code | **NOT IMPLEMENTED** — `access_token: ""` hardcoded |
| `entra_client_secret` | Present (for future client_credentials implementation) |

---

## 16. Readiness Percentage

| Area | Items | Ready | % |
|---|---|---|---|
| Platform / infra | 8 | 6 | 75% |
| Microsoft Entra (permissions, consent, roles) | 5 | 0 | 0% |
| n8n credential bindings | 3 | 0 | 0% |
| App code (Graph token acquisition) | 1 | 0 | 0% |
| AI providers (Anthropic/Voyage/Cohere) | 3 | 0 | 0% |
| ownCloud credentials | 2 | 0 | 0% |
| **Total** | **22** | **6** | **27%** |

---

## 17. Can Microsoft Gate 1 Start?

**No.**

Microsoft Gate 1 requires:
1. Microsoft Graph application permissions (`Files.Read.All`, `Mail.Read`, `Mail.Read.Shared`) added and admin-consented — **NOT DONE**
2. App roles (`admin`, `executive`) defined and users assigned — **NOT CONFIRMED**
3. SPA redirect URI confirmed — **NOT CONFIRMED**
4. n8n `Receive Request` nodes bound to `DecisionCenter Webhook Header Auth` — **NOT DONE** (operator not touching n8n yet — AI task after Microsoft actions)
5. Graph token acquisition code implemented — **NOT DONE** (AI task after Microsoft actions)
6. Fresh access token available for validation — **NOT AVAILABLE** (token in `/root/dc_token.txt` is expired)

---

## 18. Final Verdict

**`MICROSOFT_N8N_REQUIREMENTS_READY_NOT_LIVE`**

All inspection tasks are complete. The exact Microsoft Entra operator checklist
(Steps A–G) is fully specified and ready for the operator to execute.
The n8n credential binding and Graph token acquisition code will be completed
by the AI after the Microsoft portal actions are confirmed.
Production remains **NOT_LIVE**.
