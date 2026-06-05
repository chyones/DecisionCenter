# Microsoft Gate 1 — Operator Runbook

> **Runbook purpose:** Unblock Gate 1 by resolving remaining configuration blockers.
> **Does NOT:** Execute Gate 1, prove Microsoft live behavior, or mark connectors LIVE_OK.
> **Date:** 2026-06-04
> **Timestamp (UTC):** 2026-06-04T05:54:32Z
> **HEAD:** `fc54c64cd37adb234c01296bf34dd89274196602`
> **Branch:** origin-main
> **Phase:** 2D Slice 6 incomplete, Slice 7 blocked
> **Service status:** NOT_LIVE

---

## 1. Evidence Files Referenced

| # | Path | Verdict | Purpose |
|---|------|---------|---------|
| 1 | `docs/evidence/uat/MICROSOFT_GATE_0_BASELINE_2026-06-04.md` | `MICROSOFT_GATE_0_BASELINE_RECORDED_NOT_LIVE` | Baseline inventory of all Microsoft config |
| 2 | `docs/evidence/uat/MICROSOFT_GATE_1_READINESS_2026-06-04.md` | `MICROSOFT_GATE_1_READINESS_BLOCKED_NOT_LIVE` | Readiness assessment with resolved vs remaining blockers |
| 3 | `docs/operations/entra_auth_validation.md` | — | Entra tenant/app/redirect URI topology and validation commands |
| 4 | `docs/operations/CONNECTORS_CONNECTION_GUIDE.md` | — | Connector maturity levels, permission lists, owner checklist |
| 5 | `docs/config/project_source_mapping.json` | — | Project-to-source mapping (contains placeholders) |
| 6 | `docs/config/project_source_mapping.example.json` | — | Example template for mapping |
| 7 | `n8n/README.md` | — | n8n workflow import instructions and I/O contracts |
| 8 | `apps/edr/rbac/roles.py` | — | 9 canonical roles and permissions |

---

## 2. Exact Remaining Blockers

These are the blockers that prevent Gate 1 from starting. Every step in this runbook targets one of these.

| # | Blocker | Source | Why It Blocks |
|---|---------|--------|---------------|
| B1 | **Project mapping placeholders** | `project_source_mapping.json` | 8 `example*` values — no real SharePoint site/drive IDs or mailbox addresses |
| B2 | **Missing n8n workflows** | SQLite `workflow_entity` | `sharepoint_search`, `email_search`, `owncloud_list` exist as JSON but are **not imported** into n8n |
| B3 | **Missing Microsoft Graph OAuth2 credential** | SQLite `credentials_entity` | n8n has no credential to authenticate Graph API calls |
| B4 | **Unbound webhook auth** | n8n workflow nodes | Imported workflows must be bound to the existing `DecisionCenter Webhook Header Auth` credential |
| B5 | **Inactive workflows** | n8n workflow state | Imported workflows must be activated before they accept webhook calls |
| B6 | **Missing Entra app roles** | API app manifest | 9 canonical roles must be defined and assigned to test users |
| B7 | **Missing admin consent** | API app registration | `Files.Read.All`, `Mail.Read`, `Mail.Read.Shared` must be admin-consented |
| B8 | **Unconfirmed redirect URI** | SPA app registration | `https://vantage.elrace.com` must be registered as a SPA platform redirect URI |
| B9 | **No live access token** | Environment | `validate_entra_auth.py` has never been run; no token exists for validation |

---

## 3. Pre-requisites

Before starting this runbook, confirm:

- [ ] You have `git` access to `/root/DecisionCenter` or can commit changes to the repo.
- [ ] You have Microsoft Entra admin center access for tenant `14a72467-3f25-4572-a535-3d5eddb00cc5`.
- [ ] You know the API app ID (`a2160d26-acc0-4d8c-b815-3a377f1fb5bd`) and SPA app ID (`97519dfa-650b-4c77-8895-f34a8169871b`).
- [ ] You have SSH access to the Hetzner server hosting DecisionCenter.
- [ ] You have the SharePoint site IDs, drive IDs, and mailbox addresses for projects PRJ-001 and PRJ-002 (or whichever projects are active).
- [ ] You have the `.env` values for `ENTRA_CLIENT_ID`, `ENTRA_TENANT_ID`, `ENTRA_CLIENT_SECRET` available (do not print them in runbook evidence).

**Forbidden:** Do not run `prisma migrate reset`, `docker compose down -v`, or restart the postgres/minio/qdrant containers during this runbook.

---

## 4. Step-by-Step Operator Actions

### Section A — Project Mapping

#### Step A1: Replace placeholders in `project_source_mapping.json`

- **Owner:** Operator (repo committer)
- **Action:** Open `docs/config/project_source_mapping.json`. Replace every `example*` value with real data.
- **Required replacements per project:**
  - `sharepoint.site_id` — real SharePoint site GUID from Microsoft Graph
  - `sharepoint.drive_id` — real document library drive GUID from Microsoft Graph
  - `email.shared_mailboxes` — real shared mailbox SMTP addresses
  - `email.document_control_mailbox` — real document control mailbox SMTP address
- **How to find site/drive IDs:**
  ```bash
  # After admin consent is granted (Step C), use Graph Explorer or curl:
  curl -H "Authorization: Bearer $TOKEN" \
    "https://graph.microsoft.com/v1.0/sites?search=PRJ-001"
  # Then:
  curl -H "Authorization: Bearer $TOKEN" \
    "https://graph.microsoft.com/v1.0/sites/{site-id}/drives"
  ```
- **Expected evidence:** Commit diff shows real GUIDs and email addresses. `grep -c 'example' docs/config/project_source_mapping.json` returns `0`.
- **Pass condition:** File contains no `example` strings and JSON is valid (`python3 -m json.tool` parses without error).
- **Fail condition:** Any `example` string remains, or JSON is malformed, or mailboxes use `@example.com`.
- **Forbidden:** Do not commit this file with secrets (it contains only non-secret config, but never commit `.env`). Do not use fabricated GUIDs.

---

### Section B — n8n Access Setup

#### Step B1: Temporarily expose n8n UI to localhost

- **Owner:** Operator (server admin)
- **Action:** n8n port `5678` is internal to the Docker network only. To reach the UI via browser, temporarily bind it to `127.0.0.1` on the host.
- **Command:**
  ```bash
  cd /root/DecisionCenter
  # Add a temporary port mapping (do not commit this change to docker-compose.yml)
  sed -i '/expose:/i\    ports:\n      - "127.0.0.1:5678:5678"' docker-compose.yml
  docker compose up -d n8n
  # Verify binding
  ss -tlnp | grep 5678
  ```
- **Expected evidence:** `ss` output shows `127.0.0.1:5678` in `LISTEN` state.
- **Pass condition:** Port 5678 is bound to `127.0.0.1` on the host.
- **Fail condition:** Port is exposed to `0.0.0.0` or not bound at all.
- **Forbidden:** Do not bind n8n to `0.0.0.0:5678` (exposes credential UI to internet). Do not restart the entire compose stack.

#### Step B2: SSH tunnel to n8n UI

- **Owner:** Operator (local workstation)
- **Action:** From your local machine, create an SSH tunnel to the server.
- **Command:**
  ```bash
  ssh -L 5678:localhost:5678 <user>@<hetzner-server-ip>
  ```
- **Expected evidence:** Browser can open `http://localhost:5678` and shows n8n sign-in.
- **Pass condition:** n8n login page loads.
- **Fail condition:** Connection refused or timeout.
- **Forbidden:** Do not share the tunnel endpoint with others while configuring credentials.

#### Step B3: Sign in to n8n

- **Owner:** Operator
- **Action:** Use the n8n owner account.
- **Credentials source:** The owner user is `admin@decisioncenter.local` (found in SQLite `user` table). If the password is unknown, reset it via:
  ```bash
  cd /root/DecisionCenter
  docker exec -it decisioncenter-n8n-1 n8n user:reset-password --email=admin@decisioncenter.local
  ```
- **Expected evidence:** n8n Editor dashboard loads.
- **Pass condition:** Logged in as owner with full access.
- **Fail condition:** Login fails or user lacks owner role.
- **Forbidden:** Do not create a second owner user. Do not downgrade the existing owner.

---

### Section C — n8n Workflow Import

**Context:** The three missing workflows must be imported via the UI because the `n8n import:workflow` CLI fails with credential ownership errors when workflows use `authentication: "headerAuth"`.

#### Step C1: Import `sharepoint_search.json`

- **Owner:** Operator (n8n UI)
- **Action:**
  1. In n8n: **Workflows → Add Workflow** (or **Import from File**).
  2. Paste the contents of `/root/DecisionCenter/n8n/sharepoint_search.json`.
  3. Save the workflow with name `sharepoint_search`.
- **Expected evidence:** Workflow canvas shows 4 nodes: `Receive Request` → `Graph Search` → `Normalize Evidence` → `Respond`.
- **Pass condition:** All 4 nodes load without errors; no red error badges on nodes.
- **Fail condition:** Missing nodes, import error toast, or credential ID conflict warning.
- **Forbidden:** Do not change the webhook path from `sharepoint-search`. Do not modify the `Normalize Evidence` code node.

#### Step C2: Import `email_search.json`

- **Owner:** Operator (n8n UI)
- **Action:** Same as C1, using `/root/DecisionCenter/n8n/email_search.json`.
- **Expected evidence:** Workflow canvas shows 5 nodes: `Receive Request` → `Enforce Mailbox Allowlist` → `Graph Mail Search` → `Normalize Evidence` → `Respond`.
- **Pass condition:** All 5 nodes load without errors.
- **Fail condition:** Missing nodes or import errors.
- **Forbidden:** Do not remove the `Enforce Mailbox Allowlist` node. Do not change the webhook path from `email-search`.

#### Step C3: Import `owncloud_list.json`

- **Owner:** Operator (n8n UI)
- **Action:** Same as C1, using `/root/DecisionCenter/n8n/owncloud_list.json`.
- **Expected evidence:** Workflow canvas shows the standard 4-node pattern (webhook → HTTP Request → Normalize → Respond).
- **Pass condition:** Workflow loads without errors.
- **Fail condition:** Import errors or missing nodes.
- **Forbidden:** Do not change the webhook path from `owncloud-list`.

---

### Section D — n8n Credential Setup

#### Step D1: Create Microsoft Graph OAuth2 credential

- **Owner:** Operator (n8n UI)
- **Action:**
  1. **Credentials → Add Credential**.
  2. Search for **Microsoft Graph OAuth2 API**.
  3. Fill fields (presence only; do not print values in evidence):
     - **Client ID:** Use API app client ID (36 chars, from `.env` `ENTRA_CLIENT_ID`).
     - **Client Secret:** Use API app client secret (from `.env` `ENTRA_CLIENT_SECRET`).
     - **Tenant ID:** Use tenant ID (36 chars, from `.env` `ENTRA_TENANT_ID`).
     - **Scope:** `https://graph.microsoft.com/.default`
  4. Name the credential: `Microsoft Graph — DecisionCenter`.
  5. Save.
- **Expected evidence:** Credential appears in n8n Credentials list with type `microsoftGraphOAuth2Api`.
- **Pass condition:** Credential saved without validation errors. n8n does not flag it as "Connection failed" (a live connection test is NOT required in this step).
- **Fail condition:** Empty required fields, malformed GUIDs, or credential name collision.
- **Forbidden:** Do not use a delegated-workflow credential type. Do not save the credential with scope `api://...` — it must be `https://graph.microsoft.com/.default`. Do not print the secret in screenshots or evidence.

#### Step D2: Bind Graph credential to SharePoint workflow

- **Owner:** Operator (n8n UI)
- **Action:**
  1. Open `sharepoint_search` workflow.
  2. Click the `Graph Search` node.
  3. In **Credentials**, select `Microsoft Graph — DecisionCenter`.
  4. Save workflow.
- **Expected evidence:** `Graph Search` node shows the credential name in its header.
- **Pass condition:** Node no longer shows "No credentials selected" warning.
- **Fail condition:** Credential dropdown is empty or save fails.
- **Forbidden:** Do not create a duplicate credential. Do not select the webhook Header Auth credential here.

#### Step D3: Bind Graph credential to Email workflow

- **Owner:** Operator (n8n UI)
- **Action:** Same as D2, but on the `Graph Mail Search` node inside `email_search` workflow.
- **Expected evidence:** `Graph Mail Search` node shows the credential name.
- **Pass condition:** Credential bound successfully.
- **Fail condition:** Node shows "No credentials selected".
- **Forbidden:** Do not bind the wrong credential type.

#### Step D4: Bind Header Auth credential to all webhook nodes

- **Owner:** Operator (n8n UI)
- **Action:** For **each** of the three imported workflows (`sharepoint_search`, `email_search`, `owncloud_list`):
  1. Open the workflow.
  2. Click the first node (`Receive Request`).
  3. In **Credentials**, select `DecisionCenter Webhook Header Auth` (the existing `httpHeaderAuth` credential).
  4. Save workflow.
- **Expected evidence:** All three `Receive Request` nodes show `DecisionCenter Webhook Header Auth` bound.
- **Pass condition:** No webhook node shows "No credentials selected".
- **Fail condition:** Credential missing or wrong type selected.
- **Forbidden:** Do not create a new Header Auth credential — reuse the existing one.

#### Step D5: Activate all three workflows

- **Owner:** Operator (n8n UI)
- **Action:** For each imported workflow, toggle the **Inactive / Active** switch to **Active**.
- **Expected evidence:**
  - UI shows green "Active" badge on each workflow.
  - SQLite verification (optional): `SELECT name, active FROM workflow_entity;` returns all three with `active=1`.
- **Pass condition:** All three workflows are active.
- **Fail condition:** Any workflow remains inactive.
- **Forbidden:** Do not activate workflows before credentials are bound (unbound active webhooks return 401 and clutter execution logs).

#### Step D6: Verify webhook paths are registered

- **Owner:** Operator (server admin)
- **Action:** Query n8n SQLite to confirm webhook paths exist.
- **Command:**
  ```bash
  cd /root/DecisionCenter
  docker run --rm -v decisioncenter_n8n-data:/data keinos/sqlite3 \
    sqlite3 /data/database.sqlite \
    "SELECT name, active FROM workflow_entity;"
  docker run --rm -v decisioncenter_n8n-data:/data keinos/sqlite3 \
    sqlite3 /data/database.sqlite \
    "SELECT webhookPath, method FROM webhook_entity;"
  ```
- **Expected evidence:** Output includes:
  - `sharepoint_search|1`, `email_search|1`, `owncloud_list|1`
  - `sharepoint-search|POST`, `email-search|POST`, `owncloud-list|POST`
- **Pass condition:** All three webhook paths registered and workflows active.
- **Fail condition:** Missing webhook path or workflow inactive.
- **Forbidden:** Do not edit the SQLite database directly.

#### Step D7: Remove temporary n8n port mapping

- **Owner:** Operator (server admin)
- **Action:** Revert the temporary `docker-compose.yml` change.
- **Command:**
  ```bash
  cd /root/DecisionCenter
  git checkout docker-compose.yml
  docker compose up -d n8n
  ```
- **Expected evidence:** `ss -tlnp | grep 5678` returns nothing (port no longer bound to host).
- **Pass condition:** n8n is back to internal-only exposure.
- **Fail condition:** Port 5678 still bound to host.
- **Forbidden:** Do not leave n8n UI exposed to the internet.

---

### Section E — Entra App Registration

#### Step E1: Verify API app roles in manifest

- **Owner:** Operator (Microsoft Entra admin center)
- **Action:**
  1. Open Microsoft Entra admin center → App registrations → API app (`a2160d26-acc0-4d8c-b815-3a377f1fb5bd`).
  2. Go to **Manifest**.
  3. Verify `appRoles` array contains exactly these 9 roles (case-sensitive values must match `apps/edr/rbac/roles.py`):
     - `admin`
     - `executive`
     - `project_manager`
     - `finance`
     - `commercial`
     - `document_control`
     - `procurement`
     - `legal`
     - `auditor`
  4. Verify `accessTokenAcceptedVersion` is `2`.
- **Expected evidence:** Screenshot or transcript of manifest `appRoles` section showing all 9 roles.
- **Pass condition:** All 9 roles present; `accessTokenAcceptedVersion` = 2.
- **Fail condition:** Missing roles, typos, or `accessTokenAcceptedVersion` = null/1.
- **Forbidden:** Do not add roles beyond the 9 canonical roles. Do not rename existing roles (the backend resolves role by exact string match).

#### Step E2: Assign app roles to test users

- **Owner:** Operator (Microsoft Entra admin center)
- **Action:**
  1. API app → **Enterprise applications** → **Users and groups**.
  2. Add assignments:
     - At least one user → `admin`
     - At least one user → `executive`
     - At least one user → `project_manager`
     - At least one user → any other role (to prove multi-role resolution)
- **Expected evidence:** Assignment list shows users mapped to roles.
- **Pass condition:** Every role has at least one assigned user.
- **Fail condition:** Any canonical role has zero assignments.
- **Forbidden:** Do not assign roles to service principals or managed identities — only real users can acquire SPA tokens.

#### Step E3: Grant admin consent for application permissions

- **Owner:** Operator (Microsoft Entra admin center)
- **Action:**
  1. API app → **API permissions**.
  2. Verify these permissions are listed:
     - `Files.Read.All` (Microsoft Graph)
     - `Mail.Read` (Microsoft Graph)
     - `Mail.Read.Shared` (Microsoft Graph)
  3. Click **Grant admin consent for <tenant>**.
  4. Confirm consent status shows green checkmarks for all three.
- **Expected evidence:** Screenshot or transcript showing all three permissions with status "Granted for <tenant>".
- **Pass condition:** All three permissions have admin consent.
- **Fail condition:** Any permission shows "Not granted" or consent pending.
- **Forbidden:** Do not grant write permissions (`Files.ReadWrite.All`, `Mail.ReadWrite`). Do not grant `Mail.Send`.

#### Step E4: Confirm SPA redirect URI

- **Owner:** Operator (Microsoft Entra admin center)
- **Action:**
  1. SPA app (`97519dfa-650b-4c77-8895-f34a8169871b`) → **Authentication**.
  2. Under **Single-page application**, verify redirect URI:
     - `https://vantage.elrace.com`
  3. Verify **no trailing slash** is present.
- **Expected evidence:** Redirect URI list contains exactly `https://vantage.elrace.com`.
- **Pass condition:** URI matches Caddy public hostname and has no trailing slash.
- **Fail condition:** Missing URI, wrong domain, or trailing slash.
- **Forbidden:** Do not add `http://` redirect URIs. Do not add `localhost` redirect URIs to the SPA app in production.

#### Step E5: Confirm SPA has API permission for access_as_user

- **Owner:** Operator (Microsoft Entra admin center)
- **Action:**
  1. SPA app → **API permissions**.
  2. Verify delegated permission: `api://a2160d26-acc0-4d8c-b815-3a377f1fb5bd/access_as_user`.
  3. Status must be "Granted for <tenant>".
- **Expected evidence:** Permission listed with green checkmark.
- **Pass condition:** Delegated permission granted.
- **Fail condition:** Permission missing or not granted.
- **Forbidden:** Do not add application permissions to the SPA app.

---

### Section F — Token Acquisition & Validation (Gate 1 Entry)

**Context:** These steps are the boundary between readiness work and Gate 1 execution. The operator prepares the token and the validation script, but the actual `PASS/FAIL` verdict of Gate 1 is recorded separately.

#### Step F1: Acquire fresh access token via browser

- **Owner:** Operator (browser + SPA)
- **Action:**
  1. Open `https://vantage.elrace.com` in a browser.
  2. Click **Sign in with Microsoft**.
  3. Authenticate with a user who has an assigned app role (e.g., `executive`).
  4. After redirect back to the SPA, open browser DevTools → Application → Session Storage → `msal.*`.
  5. Find the access token for scope `api://a2160d26-acc0-4d8c-b815-3a377f1fb5bd/access_as_user`.
  6. Copy the token value (keep it private).
- **Expected evidence:** Token exists in session storage; token `aud` claim equals API app ID; `roles` claim contains the assigned role.
- **Pass condition:** User signs in successfully; SPA loads workspace; token has `roles` array.
- **Fail condition:** "Sign-in problem" screen; token missing `roles`; 401 from `/me`.
- **Forbidden:** Do not use an expired cached token. Do not use a token acquired from a different app registration. Do not print the token in logs or evidence.

#### Step F2: Decode token claims (non-secret diagnostic)

- **Owner:** Operator (local shell)
- **Action:** Decode the token header to confirm non-secret claims without verifying signature.
- **Command:**
  ```bash
  # Paste token into TOKEN env var, then:
  python3 -c "
  import jwt, sys, json
t = sys.argv[1]
claims = jwt.decode(t, options={'verify_signature': False})
print(json.dumps({k: claims.get(k) for k in ['iss', 'aud', 'ver', 'roles', 'oid']}, indent=2))
" "$TOKEN"
  ```
- **Expected evidence:** Output shows:
  - `iss`: `https://login.microsoftonline.com/14a72467-3f25-4572-a535-3d5eddb00cc5/v2.0`
  - `aud`: `a2160d26-acc0-4d8c-b815-3a377f1fb5bd` or `api://a2160d26-acc0-4d8c-b815-3a377f1fb5bd`
  - `ver`: `2.0`
  - `roles`: `["executive"]` (or other assigned role)
  - `oid`: a valid user object ID
- **Pass condition:** `iss`, `aud`, `ver`, and `roles` match expected values.
- **Fail condition:** `roles` missing, `aud` mismatch, `ver` = `1.0` with issuer mismatch, or `oid` absent.
- **Forbidden:** Do not treat decoded claims as trusted — this is diagnostic only. Do not log the full token.

#### Step F3: Run `validate_entra_auth.py` (Gate 1 execution)

- **Owner:** Operator (local shell, inside app container or with `.env` loaded)
- **Action:**
  ```bash
  cd /root/DecisionCenter
  # Option A: Inside the running app container
  docker exec -it decisioncenter-app-1 \
    python scripts/validate_entra_auth.py \
    --base-url https://vantage.elrace.com \
    --token "<fresh_token_from_F1>"
  ```
- **Expected evidence:** Script output shows:
  - `OIDC + JWKS OK`
  - `Token claims iss=... aud=... ver=2.0 roles=...`
  - `Validate PASS — role=...`
  - `GET /me OK — /me role=...`
  - `Result: PASS — Entra auth validated end-to-end`
  - Exit code `0`
- **Pass condition:** Exit code `0` and every step prints `OK` or `PASS`.
- **Fail condition:** Exit code `1` or any step prints `FAIL`.
- **Forbidden:** Do not use an expired token. Do not use a token from a different tenant. Do not run this step until Steps A–E are complete. Do not skip `--base-url` — the full Caddy proxy chain must be tested.

---

## 5. Runbook Completion Checklist

After all steps above, verify:

- [ ] `project_source_mapping.json` has zero `example` strings and valid JSON.
- [ ] n8n `workflow_entity` table shows `sharepoint_search`, `email_search`, `owncloud_list` all with `active=1`.
- [ ] n8n `webhook_entity` table shows `sharepoint-search`, `email-search`, `owncloud-list` all with `method=POST`.
- [ ] n8n `credentials_entity` table shows `Microsoft Graph — DecisionCenter` (type `microsoftGraphOAuth2Api`).
- [ ] Microsoft Entra admin center shows all 9 app roles defined and assigned.
- [ ] Microsoft Entra admin center shows `Files.Read.All`, `Mail.Read`, `Mail.Read.Shared` granted.
- [ ] Microsoft Entra admin center shows SPA redirect URI `https://vantage.elrace.com` (no trailing slash).
- [ ] `docker-compose.yml` port mapping reverted (n8n no longer exposed to host).
- [ ] `scripts/validate_entra_auth.py` returned exit code `0` with fresh token.

---

## 6. Final Statement

**This runbook does not execute Gate 1 and does not prove Microsoft live behavior.**

It is a configuration and setup guide. The actual Gate 1 evidence — live token validation, Graph data retrieval, SharePoint search results, and email excerpts — must be recorded in a separate Gate 1 evidence file created only after this runbook is fully completed. Production remains **NOT_LIVE**. Slice 7 remains blocked.
