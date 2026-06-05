# Microsoft Gate 2 — Graph Token and Permissions Validation

> **Verdict:** `MICROSOFT_GATE_2_GRAPH_PERMISSIONS_PASSED_NOT_LIVE`
> **Date:** 2026-06-04
> **Timestamp (UTC):** 2026-06-04T12:39:41Z
> **HEAD:** `fc54c64cd37adb234c01296bf34dd89274196602`
> **Branch:** main (tracking origin/main)
> **Phase:** 2D Slice 6 in progress
> **Service status:** NOT_LIVE

---

## 0. Revision History

| Run | Timestamp (UTC) | Result | Cause |
|-----|-----------------|--------|-------|
| 1 (initial) | 2026-06-04T12:03:21Z | **BLOCKED** | `ENTRA_CLIENT_SECRET` was secret ID (GUID), not secret value; AADSTS7000215 |
| 2 (this run) | 2026-06-04T12:39:41Z | **PASSED** | Operator replaced secret value; `len=40`, not GUID |

---

## 1. Gate 1 Dependency

| Item | Status |
|------|--------|
| Evidence file | `docs/evidence/uat/MICROSOFT_GATE_1_ENTRA_2026-06-04.md` |
| Gate 1 verdict | `MICROSOFT_GATE_1_ENTRA_PASSED_NOT_LIVE` |
| Dependency satisfied | **Yes** |

---

## 2. Git State

| Item | Value |
|------|-------|
| HEAD | `fc54c64cd37adb234c01296bf34dd89274196602` |
| Branch | `main` tracking `origin/main` |
| Unstaged changes | `apps/edr/connectors/{email,sharepoint}.py`, graph nodes, frontend auth files, related tests |
| Untracked | `docs/evidence/uat/` files, `apps/edr/connectors/graph_token.py`, `scripts/bind_n8n_webhook_auth.py` |

---

## 3. Runtime State

| Check | Result |
|-------|--------|
| App health (`GET /healthz`) | **HTTP 200** — postgres ok, redis ok, qdrant ok, minio ok |
| `ENTRA_TENANT_ID` | **PRESENT** (len=36) |
| `ENTRA_CLIENT_ID` | **PRESENT** (len=36) |
| `ENTRA_CLIENT_SECRET` | **PRESENT** (len=40) — not GUID-shaped; secret value confirmed |

---

## 4. Previous Failure Resolved

| Item | Run 1 (BLOCKED) | Run 2 (this run) |
|------|-----------------|------------------|
| `ENTRA_CLIENT_SECRET` len | 36 (GUID / secret ID) | **40 (secret value)** |
| HTTP status on token request | 401 Unauthorized | **200 OK** |
| Microsoft error | AADSTS7000215 invalid_client | **None — token issued** |

---

## 5. Graph Token Acquisition — PASS

**Method:** Client credentials flow  
**Endpoint:** `POST https://login.microsoftonline.com/14a72467-3f25-4572-a535-3d5eddb00cc5/oauth2/v2.0/token`  
**Scope:** `https://graph.microsoft.com/.default`  
**Implementation:** `apps/edr/connectors/graph_token.py` → `get_graph_token()`

| Claim | Value |
|-------|-------|
| `ver` | `1.0` (v1.0 expected for client-credentials → graph.microsoft.com) |
| `iss` | `https://sts.windows.net/14a72467-3f25-4572-a535-3d5eddb00cc5/` |
| `aud` | `https://graph.microsoft.com` |
| `appid` | `a2160d26-acc0-4d8c-b815-3a377f1fb5bd` |
| `roles` | `['Files.Read.All', 'Mail.Read']` |
| `scp` | `''` (correct — app-only token has no delegated scopes) |
| `exp_remaining_s` | `3600` |
| Expired | **No** |

Token value: **not recorded**.

---

## 6. Permission Checks — PASS

### 6.1 Files.Read.All

`Files.Read.All` as an **application permission** grants reading files within drives and
site document libraries. It does **not** grant `/sites?search=*` (that requires
`Sites.Read.All`). Probes used endpoints that are correct for this permission.

| Endpoint | HTTP | Result |
|----------|------|--------|
| `GET /users/younes@elrace.com/drive` | **200** | Drive name=`OneDrive` — user's OneDrive accessible |
| `GET /users/younes@elrace.com/drive/root/children?$top=3` | **200** | `items=3`, folders visible (`Attachments`, `Data`, `Desktop`) |
| `GET /sites/root` | **200** | Tenant root SharePoint site name=`Document Cloud` |
| `GET /sites/root/drives?$top=3` | **200** | `items=1`, drive=`Search Config List` |
| `GET /sites?search=*` | 403 | Expected — `Files.Read.All` does not grant site enumeration (`Sites.Read.All` required for that endpoint) |

**Files.Read.All verdict: PASS** — application permission functional for reading drives and site document libraries.

### 6.2 Mail.Read

| Endpoint | HTTP | Result |
|----------|------|--------|
| `GET /users/younes@elrace.com/mailFolders?$top=3` | **200** | `items=3`, folders: `Archive`, `Conversation History`, `Deleted Items` |
| `GET /users/younes@elrace.com/mailFolders/inbox/messages?$top=1` | **200** | `items=1`, message subject visible (redacted from evidence) |

**Mail.Read verdict: PASS** — application permission functional for reading mailbox folders and messages.

---

## 7. Read-Only Compliance

No write, send, delete, archive, upload, or create operations were performed.
All calls were `GET` requests with `$select` and `$top` limits.

---

## 8. Can Gate 3 Start?

**Yes.** Both `Files.Read.All` and `Mail.Read` application permissions are confirmed
functional against the live tenant. The remaining prerequisite for Gate 3 (n8n workflow
credential bindings and SharePoint/mailbox coordinates in `project_source_mapping.json`)
are operator-configuration items, not token/permission blockers.

---

## 9. Remaining Microsoft Blockers Before Full UAT

| Blocker | Impact |
|---------|--------|
| `project_source_mapping.json` still has placeholder `site_id`, `drive_id`, mailbox values | Gate 3 (connector live probes) cannot retrieve real content |
| n8n Graph OAuth2 credential binding to workflow nodes | SharePoint/email connectors will not authenticate Graph calls from n8n |

These are operator-configuration items, not token or permission issues.

---

## 10. Final Verdict

**`MICROSOFT_GATE_2_GRAPH_PERMISSIONS_PASSED_NOT_LIVE`**

The Microsoft Graph client-credentials token acquisition succeeded after `ENTRA_CLIENT_SECRET`
was corrected to the secret value. Both `Files.Read.All` and `Mail.Read` application
permissions are confirmed exercisable in read-only mode against the live tenant
`14a72467-3f25-4572-a535-3d5eddb00cc5`. Gate 2 is closed. Production remains `NOT_LIVE`.
