# Microsoft Gate 0 — Baseline Inventory

> **Gate:** 0 (baseline inventory only)
> **Status:** NOT_LIVE — no live proof claimed
> **Date:** 2026-06-04
> **Timestamp (UTC):** 2026-06-04T05:16:30Z
> **HEAD:** `fc54c64cd37adb234c01296bf34dd89274196602`
> **Branch:** origin-main
> **Phase:** 2D Slice 6 incomplete, Slice 7 blocked
> **Service status:** NOT_LIVE

---

## 1. Scope

This document records the **presence or absence** of Microsoft/Entra/Graph/SharePoint/Mail configuration in the DecisionCenter codebase and runtime environment. It makes **no claims** about live connectivity, token validity, or working data retrieval. No secrets or token values are printed.

---

## 2. Files / Environment Sources Inspected

| # | Source | Purpose |
|---|--------|---------|
| 1 | `.env.example` (root) | Backend environment template |
| 2 | `.env` (root) | Backend runtime environment |
| 3 | `apps/edr/config.py` | Pydantic Settings loader (40-key lock) |
| 4 | `apps/edr/auth/validator.py` | Entra JWT validation (RS256, JWKS, v1.0+v2.0) |
| 5 | `apps/edr/auth/__init__.py` | Auth package init |
| 6 | `apps/edr/app.py` | FastAPI app — auth extraction & bypass logic |
| 7 | `apps/edr/connectors/sharepoint.py` | SharePoint → n8n webhook connector |
| 8 | `apps/edr/connectors/email.py` | Email → n8n webhook connector |
| 9 | `apps/edr/graph/node_05_sharepoint.py` | Workflow Node 5 (SharePoint retrieval) |
| 10 | `apps/edr/graph/node_07_email.py` | Workflow Node 7 (Email retrieval) |
| 11 | `apps/edr/admin/connector_status.py` | Connector truth-status service |
| 12 | `frontend/.env.example` | Frontend environment template |
| 13 | `frontend/.env.production` | Frontend production build environment |
| 14 | `frontend/src/auth/msalConfig.ts` | MSAL / Entra SPA configuration |
| 15 | `frontend/src/auth/LoginGate.tsx` | Production login gate |
| 16 | `frontend/src/vite-env.d.ts` | Vite env type declarations |
| 17 | `n8n/sharepoint_search.json` | n8n SharePoint search workflow |
| 18 | `n8n/email_search.json` | n8n Email search workflow |
| 19 | `docs/contracts/microsoft_graph_contract.md` | Graph API contract |
| 20 | `docs/contracts/email_graph_contract.md` | Email Graph contract |
| 21 | `docs/operations/entra_auth_validation.md` | Entra auth validation runbook |
| 22 | `docs/operations/CONNECTORS_CONNECTION_GUIDE.md` | Connector maturity guide |
| 23 | `docs/config/project_source_mapping.json` | Project → source mapping (live data) |
| 24 | `docs/config/project_source_mapping.example.json` | Example mapping template |
| 25 | `docs/policies/email_retrieval_policy.md` | Email retrieval policy |
| 26 | `docs/policies/shared_mailbox_access_policy.md` | Shared mailbox policy |
| 27 | `scripts/validate_entra_auth.py` | Live Entra validation script (operator tool) |
| 28 | `Caddyfile` | Reverse proxy / public edge config |

---

## 3. Entra Config Presence

### 3.1 Backend

| Key | `.env.example` | `.env` (runtime) | `config.py` | Note |
|-----|----------------|------------------|-------------|------|
| `ENTRA_CLIENT_ID` | present, empty | **present, length=36** | `str \| None = None` | API app audience |
| `ENTRA_TENANT_ID` | present, empty | **present, length=36** | `str \| None = None` | Tenant for JWKS |
| `ENTRA_CLIENT_SECRET` | present, empty | **present, length=36** | `str \| None = None` | Not used in JWT path; may be needed for token exchange |

- `apps/edr/auth/validator.py`: **Present** — `EntraJWTValidator` class implements RS256 via JWKS, accepts both v1.0 and v2.0 issuer/audience forms.
- `apps/edr/app.py`: **Present** — `_extract_claims()` uses validator when configured; bypass mode active when `ENTRA_CLIENT_ID` is absent; bypass blocked in production.
- `scripts/validate_entra_auth.py`: **Present** — operator script for OIDC discovery + JWKS + token validation + `/me` chain test.

### 3.2 Frontend

| Key | `.env.example` | `.env.production` | Source file | Note |
|-----|----------------|-------------------|-------------|------|
| `VITE_ENTRA_CLIENT_ID` | present, empty | **present, length=36** | `msalConfig.ts` | SPA app client ID |
| `VITE_ENTRA_TENANT_ID` | present, empty | **present, length=36** | `msalConfig.ts` | Authority tenant |
| `VITE_ENTRA_API_SCOPE` | present, empty | **present, length=57** | `msalConfig.ts` | API scope |

- `frontend/src/auth/msalConfig.ts`: **Present** — `PublicClientApplication` configured with `authority`, `redirectUri: window.location.origin`, `cacheLocation: 'sessionStorage'`. Scope defaults to `api://{clientId}/.default` when blank.
- `frontend/src/auth/LoginGate.tsx`: **Present** — MSAL-based login gate, role resolution via `GET /me` or `GET /workspace/context`, token diagnostic (iss/aud/ver/roles only, never token value).
- `frontend/src/vite-env.d.ts`: **Present** — type declarations for `VITE_ENTRA_CLIENT_ID`, `VITE_ENTRA_TENANT_ID`, `VITE_ENTRA_API_SCOPE`.

### 3.3 Documentation

- `docs/operations/entra_auth_validation.md`: **Present** — records two app registrations (API app and SPA app), tenant ID, redirect URI (`https://vantage.elrace.com`), token-version fix, and validation commands. **No secrets printed.**
- `docs/operations/CONNECTORS_CONNECTION_GUIDE.md`: **Present** — §5.1 covers Entra ID maturity levels L0–L4.

### 3.4 Redirect URI

- Source: `frontend/src/auth/msalConfig.ts` — `redirectUri: typeof window !== 'undefined' ? window.location.origin : '/'`
- Source: `docs/operations/entra_auth_validation.md` — `https://vantage.elrace.com` (SPA platform, no trailing slash)
- **Status:** Configured in code and docs. Live registration state not proven in this Gate.

---

## 4. Graph Config Presence

### 4.1 n8n Workflows

| Workflow | File | Graph API Endpoint Pattern | Auth Method |
|----------|------|---------------------------|-------------|
| SharePoint search | `n8n/sharepoint_search.json` | `GET /v1.0/sites/{site_id}/drives/{drive_id}/root/search(q=...)` | `Bearer {access_token}` via header |
| Email search | `n8n/email_search.json` | `GET /v1.0/users/{user_mailbox}/messages?$search=...&$top=25` | `Bearer {access_token}` via header |

- Both workflows use `authentication: headerAuth` on the webhook receive node.
- Both workflows include a "Normalize Evidence" code node that emits `EvidenceObject`-shaped output.
- **No Graph credentials stored in Git.** The `access_token` is passed in the webhook payload at runtime.

### 4.2 Python Connector Layer

- `apps/edr/connectors/sharepoint.py`: **Present** — calls n8n webhook via `N8NWebhookClient`.
- `apps/edr/connectors/email.py`: **Present** — calls n8n webhook via `N8NWebhookClient`.
- `apps/edr/connectors/base.py`: **Present** — `N8NWebhookClient` sends `Authorization: Bearer {N8N_WEBHOOK_TOKEN}` when configured.

### 4.3 Graph Workflow Nodes

- `apps/edr/graph/node_05_sharepoint.py`: **Present** — RBAC gate (`can_access_sharepoint`), payload includes `site_id`, `drive_id`, `access_token: ""`.
- `apps/edr/graph/node_07_email.py`: **Present** — RBAC gate (`can_access_own_mailbox`), mailbox allowlist enforcement, payload includes `user_mailbox`, `allowed_mailboxes`, `access_token: ""`.

### 4.4 Contracts & Policies

- `docs/contracts/microsoft_graph_contract.md`: **Present** — rules for delegated/app permissions, RBAC, excerpts only.
- `docs/contracts/email_graph_contract.md`: **Present** — retrieval scope, excerpt-only storage policy.
- `docs/policies/email_retrieval_policy.md`: **Present** (4 lines).
- `docs/policies/shared_mailbox_access_policy.md`: **Present** (5 lines).

---

## 5. SharePoint Config Presence

| Config | Source | Status | Note |
|--------|--------|--------|------|
| `SHAREPOINT_SEARCH_WEBHOOK` | `.env` | **present, non-empty** | `/webhook/sharepoint-search` |
| `sharepoint_search_webhook` | `config.py` | **defined** | default `/webhook/sharepoint-search` |
| `site_id` / `drive_id` | `project_source_mapping.json` | **placeholder** | 8 occurrences of "example" — not real IDs |
| `site_id` / `drive_id` | `project_source_mapping.example.json` | **example template** | 4 occurrences of "example" |
| n8n workflow | `n8n/sharepoint_search.json` | **present** | 109 lines, 4 nodes |
| Connector spec | `connector_status.py` | **present** | `CONFIGURED_NOT_TESTED` cap by design |

- **No live SharePoint data has been retrieved.** No `LIVE_OK` claimed.

---

## 6. Mail / Graph Config Presence

| Config | Source | Status | Note |
|--------|--------|--------|------|
| `EMAIL_SEARCH_WEBHOOK` | `.env` | **present, non-empty** | `/webhook/email-search` |
| `email_search_webhook` | `config.py` | **defined** | default `/webhook/email-search` |
| Shared mailboxes | `project_source_mapping.json` | **placeholder** | `example.com` addresses |
| Mailbox allowlist | `node_07_email.py` | **enforced** | Denies search if mailbox not in allowlist |
| n8n workflow | `n8n/email_search.json` | **present** | 130 lines, 5 nodes (includes allowlist code node) |
| Connector spec | `connector_status.py` | **present** | `CONFIGURED_NOT_TESTED` cap by design |

- **No live email data has been retrieved.** No `LIVE_OK` claimed.

---

## 7. Token Presence Status (No Values Printed)

| Token / Secret | Location | Presence | Length | Note |
|----------------|----------|----------|--------|------|
| `ENTRA_CLIENT_ID` | `.env` | present | 36 | API app audience |
| `ENTRA_TENANT_ID` | `.env` | present | 36 | JWKS / OIDC discovery |
| `ENTRA_CLIENT_SECRET` | `.env` | present | 36 | Not used in JWT validation; may be used for token exchange or n8n OAuth |
| `N8N_WEBHOOK_TOKEN` | `.env` | present | 43 | Secures Python → n8n webhook calls |
| `VITE_ENTRA_CLIENT_ID` | `frontend/.env.production` | present | 36 | SPA app client ID |
| `VITE_ENTRA_TENANT_ID` | `frontend/.env.production` | present | 36 | SPA authority tenant |
| `VITE_ENTRA_API_SCOPE` | `frontend/.env.production` | present | 57 | API scope for access token |

- **No expired tokens** found in any committed file.
- **No cached Graph access tokens** found in repository.
- **No token values** are printed in this document.

---

## 8. Blockers for Gate 1

Gate 1 is defined as the first **live** validation of Microsoft Entra, Graph, SharePoint, and/or Mail. The following must be resolved before Gate 1 can claim success:

1. **Real project mapping required**
   - `docs/config/project_source_mapping.json` still contains 8 `example*` placeholder values.
   - Real SharePoint `site_id` and `drive_id` per project must be provided.
   - Real shared mailbox addresses per project must be provided.

2. **n8n credential store configuration required**
   - n8n workflow JSON files exist in Git, but n8n **credentials** (Microsoft Graph OAuth2) live in the n8n encrypted credential store (Docker volume), not in Git.
   - The credential store must be configured with tenant ID, client ID, client secret, and scope `https://graph.microsoft.com/.default`.
   - Workflows must be imported into n8n and activated.

3. **App registration admin consent required**
   - Application permissions (`Files.Read.All`, `Mail.Read`, `Mail.Read.Shared`) must be admin-consented in the Entra tenant.
   - App roles must be assigned to test users.

4. **Live token validation required**
   - `scripts/validate_entra_auth.py` must be run with a real access token to prove the JWKS + RS256 validation chain works end-to-end.
   - The SPA redirect flow must be tested in a browser to confirm `window.location.origin` matches the registered redirect URI.

5. **Public edge / Caddy required for full chain**
   - `PUBLIC_HOSTNAME` is currently `localhost` in `.env`.
   - For a real redirect-URI test, Caddy must serve HTTPS on the production domain.

6. **No expired tokens**
   - Any token used in Gate 1 must be currently valid. Expired tokens must not be used as proof.

---

## 9. Baseline Matrix

| Component | Config Present | Values Present | Live Proven | Verdict |
|-----------|---------------|----------------|-------------|---------|
| Entra (backend) | ✅ | ✅ (3 keys) | ❌ | Configured, not tested |
| Entra (frontend SPA) | ✅ | ✅ (3 keys) | ❌ | Configured, not tested |
| MSAL / redirect URI | ✅ | ✅ (dynamic origin) | ❌ | Configured, not tested |
| Graph API (SharePoint workflow) | ✅ | ✅ (n8n JSON) | ❌ | Configured, not tested |
| Graph API (Email workflow) | ✅ | ✅ (n8n JSON) | ❌ | Configured, not tested |
| SharePoint site/drive mapping | ✅ | ⚠️ (placeholder) | ❌ | Example data only |
| Email mailbox mapping | ✅ | ⚠️ (placeholder) | ❌ | Example data only |
| N8N webhook token | ✅ | ✅ | ❌ | Configured, not tested |
| Auth validator (RS256/JWKS) | ✅ | N/A | ❌ | Code present, not live-tested |
| Entra validation script | ✅ | N/A | ❌ | Script present, not run |

---

## 10. Final Verdict

**MICROSOFT_GATE_0_BASELINE_RECORDED_NOT_LIVE**

All Microsoft/Entra/Graph/SharePoint/Mail configuration **keys, code paths, workflow files, and documentation** are present in the repository and runtime environment. No secrets were printed. No connector is claimed live. No expired tokens were used as evidence. Production remains **NOT_LIVE**. Slice 7 remains blocked.

Gate 1 may **not** start until blockers in §8 are addressed.
