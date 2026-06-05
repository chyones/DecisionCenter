# Microsoft Gate 1 — Readiness Assessment

> **Gate:** 1 readiness (preparation only — Gate 1 itself is not run)
> **Status:** NOT_LIVE — no live proof claimed
> **Date:** 2026-06-04
> **Timestamp (UTC):** 2026-06-04T05:25:19Z
> **HEAD:** `fc54c64cd37adb234c01296bf34dd89274196602`
> **Branch:** origin-main
> **Phase:** 2D Slice 6 incomplete, Slice 7 blocked
> **Service status:** NOT_LIVE
> **Gate 0 Evidence:** `docs/evidence/uat/MICROSOFT_GATE_0_BASELINE_2026-06-04.md`

---

## 1. Scope

This document assesses whether the blockers identified in Gate 0 have been resolved sufficiently to allow Gate 1 (live Microsoft validation) to begin. It makes **no live claims** and performs **no live tests** against Microsoft services.

---

## 2. Gate 0 Blockers Recap

Gate 0 identified six blockers:

1. **Real project mapping required** — `project_source_mapping.json` contained 8 `example*` placeholders.
2. **n8n credential store configuration required** — Microsoft Graph OAuth2 credential missing; workflows not imported/activated.
3. **App registration admin consent required** — `Files.Read.All`, `Mail.Read`, `Mail.Read.Shared` must be admin-consented.
4. **Live token validation required** — `scripts/validate_entra_auth.py` must be run with a real access token.
5. **Public edge / Caddy required** — Gate 0 incorrectly stated `PUBLIC_HOSTNAME` was `localhost`.
6. **No expired tokens** — tokens used in Gate 1 must be currently valid.

---

## 3. Resolved Blockers

### 3.1 Public Edge / Caddy / Redirect URI

**Gate 0 error corrected.** `PUBLIC_HOSTNAME` is **not** `localhost`.

| Check | Source | Finding |
|-------|--------|---------|
| `PUBLIC_HOSTNAME` | `.env` (root) | `vantage.elrace.com` (lines 6, 13) |
| Caddy container | `docker compose ps` | `decisioncenter-caddy-1` — Up 43 hours |
| Cloudflare Tunnel | `docker compose ps` | `decisioncenter-cloudflared-1` — Up 43 hours |
| Caddy config | Container `/etc/caddy/Caddyfile` | `http://{$PUBLIC_HOSTNAME:localhost}` block present; proxies `/healthz`, `/me`, `/reports`, `/workspace`, `/upload`, `/admin` to `app:8000`; serves SPA fallback |
| Frontend build | `frontend/dist/` | Present (`index.html`, hashed JS/CSS assets) |
| App health | `curl http://127.0.0.1:8000/healthz` | HTTP 200 |
| Redirect URI | `frontend/src/auth/msalConfig.ts` | `window.location.origin` (resolves to `https://vantage.elrace.com` in production) |

**Verdict:** Public edge infrastructure is locally configured and running. The redirect URI domain matches the Entra app registration documented in `docs/operations/entra_auth_validation.md` (`https://vantage.elrace.com`).

### 3.2 n8n Infrastructure

| Check | Source | Finding |
|-------|--------|---------|
| n8n container | `docker compose ps` | `decisioncenter-n8n-1` — Up 18 hours |
| n8n version | Container image | `n8nio/n8n:1.91.3` (pinned) |
| n8n data volume | `docker volume ls` | `decisioncenter_n8n-data` exists |
| n8n owner user | SQLite `user` table | `admin@decisioncenter.local` (role: global:owner) |
| Workflow mount | Container `/workflows/` | 4 JSON files mounted from `./n8n` (read-only) |
| Webhook credential | SQLite `credentials_entity` | `DecisionCenter Webhook Header Auth` (`httpHeaderAuth`) — present |
| Webhook token | `.env` | `N8N_WEBHOOK_TOKEN` present, length=43 |

**Verdict:** n8n core infrastructure is running and the webhook security credential is configured.

---

## 4. Remaining Blockers

### 4.1 Real Project Mapping — STILL BLOCKED

- `docs/config/project_source_mapping.json` still contains **8 occurrences** of `example*` placeholders:
  - `example-site-id-001`, `example-drive-id-001`
  - `example-site-id-002`, `example-drive-id-002`
  - `project-prj-001@example.com`, `doc-control@example.com`
  - `project-prj-002@example.com`, `doc-control-002@example.com`
- **Impact:** Without real SharePoint `site_id`/`drive_id` and real mailbox addresses, no live Microsoft data can be retrieved even if all other systems are working.
- **Resolution:** Operator must provide real values per project.

### 4.2 n8n Microsoft Workflows — STILL BLOCKED

- **Missing from n8n database:**
  - `sharepoint_search` workflow (JSON exists in `/workflows`, **not imported**)
  - `email_search` workflow (JSON exists in `/workflows`, **not imported**)
  - `owncloud_list` workflow (JSON exists in `/workflows`, **not imported**)
- **Present in n8n database:**
  - `odoo_read` workflow — **imported and active** (`active=1`, webhook `odoo-read` registered)
- **Missing credential:**
  - Microsoft Graph OAuth2 credential — **not created** in n8n credential store.
  - Only `httpHeaderAuth` (webhook token) exists.
- **Import attempt:** `n8n import:workflow` CLI was attempted for the three missing workflows. All three failed with:
  > "The credential with ID 'undefined' is already owned by the user ... It can't be re-owned ..."
  This is an n8n CLI import limitation when workflows use `authentication: "headerAuth"` without an explicit pre-created credential binding.
- **Impact:** SharePoint and Email connectors cannot be invoked until workflows are imported, activated, and bound to credentials.
- **Resolution:** Operator must import via n8n UI and create the Microsoft Graph OAuth2 credential manually (see §6).

### 4.3 Entra App Registration Admin Consent — STILL BLOCKED

- **Required application permissions** (documented in `docs/operations/CONNECTORS_CONNECTION_GUIDE.md` §5.2–5.3):
  - `Files.Read.All` (SharePoint)
  - `Mail.Read` (user mailboxes)
  - `Mail.Read.Shared` (shared mailboxes)
- **App roles** (documented in `docs/operations/entra_auth_validation.md` and `apps/edr/rbac/roles.py`):
  - 9 canonical roles must be defined in the API app manifest: `admin`, `executive`, `project_manager`, `finance`, `commercial`, `document_control`, `procurement`, `legal`, `auditor`.
  - Roles must be assigned to test users.
- **Impact:** Without admin consent, Graph API returns 403. Without app roles, tokens carry no `roles` claim and RBAC falls back to bypass mode.
- **Resolution:** Operator actions in Microsoft Entra admin center (see §6).

### 4.4 Live Token Validation — STILL BLOCKED

- `scripts/validate_entra_auth.py` exists but **has not been run** with a live token.
- **Impact:** The RS256/JWKS validation chain is implemented in code but not proven against the real tenant.
- **Resolution:** Operator must sign in via the production SPA (or acquire a token via MSAL test harness) and run the validation script.

### 4.5 Token Freshness — STILL BLOCKED

- No live token exists in the environment.
- **Impact:** Gate 1 must use a currently valid token; expired tokens are not acceptable proof.
- **Resolution:** Acquire fresh token at Gate 1 run time.

---

## 5. Operator-Required Actions

The following actions require access to external systems (Microsoft Entra admin center, SharePoint admin, Exchange admin, n8n UI) and cannot be performed from code alone.

| # | Action | System | Priority |
|---|--------|--------|----------|
| 1 | **Replace placeholders** in `docs/config/project_source_mapping.json` with real `site_id`, `drive_id`, and mailbox addresses per project. | DecisionCenter repo | Critical |
| 2 | **Import n8n workflows** `sharepoint_search.json`, `email_search.json`, `owncloud_list.json` via n8n UI (CLI import blocked by credential ownership). | n8n UI (SSH tunnel to port 5678) | Critical |
| 3 | **Create Microsoft Graph OAuth2 credential** in n8n: tenant ID, client ID, client secret, scope `https://graph.microsoft.com/.default`. | n8n UI | Critical |
| 4 | **Bind webhook node** in each imported workflow to the existing `DecisionCenter Webhook Header Auth` credential. | n8n UI | Critical |
| 5 | **Activate** the three imported workflows. | n8n UI | Critical |
| 6 | **Verify app roles** in the API app manifest match the 9 canonical roles in `apps/edr/rbac/roles.py`. | Microsoft Entra admin center | Critical |
| 7 | **Assign app roles** to at least one test user per role (especially `executive`, `project_manager`, `admin`). | Microsoft Entra admin center | Critical |
| 8 | **Grant admin consent** for `Files.Read.All`, `Mail.Read`, `Mail.Read.Shared` on the API app registration. | Microsoft Entra admin center | Critical |
| 9 | **Confirm redirect URI** `https://vantage.elrace.com` (SPA platform, no trailing slash) is registered on the SPA app. | Microsoft Entra admin center | High |
| 10 | **Confirm API app** `accessTokenAcceptedVersion` is set to `2` (recommended in `docs/operations/entra_auth_validation.md`). | Microsoft Entra admin center | High |
| 11 | **Acquire live token** via browser login to the SPA and run `scripts/validate_entra_auth.py --base-url https://vantage.elrace.com --token <token>`. | Local shell + browser | Gate 1 entry |
| 12 | **Confirm token is not expired** before using it as Gate 1 evidence. | Local shell | Gate 1 entry |

---

## 6. Readiness Matrix

| Component | Gate 0 State | Readiness Action Taken | Current State | Blocks Gate 1? |
|-----------|--------------|------------------------|---------------|----------------|
| Entra backend config | Configured, not tested | Verified `.env` values present | Configured, not tested | No |
| Entra frontend config | Configured, not tested | Verified `.env.production` values present | Configured, not tested | No |
| MSAL / redirect URI | Configured, not tested | Verified Caddy + Cloudflare + domain running | Configured, not tested | No |
| Public edge (Caddy) | Incorrectly listed as localhost | **Corrected** — `vantage.elrace.com` active | Running | No |
| Graph API (SharePoint workflow) | Configured, not tested | Discovered **not imported** into n8n | **Missing in n8n** | **Yes** |
| Graph API (Email workflow) | Configured, not tested | Discovered **not imported** into n8n | **Missing in n8n** | **Yes** |
| SharePoint site/drive mapping | Example placeholders | None — requires real IDs | Example placeholders | **Yes** |
| Email mailbox mapping | Example placeholders | None — requires real addresses | Example placeholders | **Yes** |
| N8N webhook token | Configured, not tested | Verified credential exists in n8n DB | Configured | No |
| Microsoft Graph OAuth2 credential | Assumed needed | Verified **not created** | **Missing** | **Yes** |
| Auth validator (RS256/JWKS) | Code present | No change | Code present | No |
| Entra validation script | Script present | No change | Script present | No |
| App roles / admin consent | Documented only | No change | Not done | **Yes** |
| Live token | None | No change | None | **Yes** |

---

## 7. Can Gate 1 Start?

**No.**

Gate 1 requires at minimum:
1. Real project mapping (SharePoint site/drive IDs, mailbox addresses).
2. n8n Microsoft workflows imported, activated, and bound to credentials.
3. Microsoft Graph OAuth2 credential created in n8n.
4. Entra app roles assigned and admin consent granted.
5. A fresh, non-expired access token available for validation.

None of these are satisfied yet.

---

## 8. Final Readiness Verdict

**MICROSOFT_GATE_1_READINESS_BLOCKED_NOT_LIVE**

Gate 1 cannot start. The public edge and core n8n infrastructure are running, but the Microsoft-specific integration layer (n8n workflows, Graph credential, project mapping, Entra app roles, and admin consent) remains unconfigured. All required next steps are documented as operator actions in §5. No secrets were printed. No live proof was claimed. Production remains **NOT_LIVE**.
