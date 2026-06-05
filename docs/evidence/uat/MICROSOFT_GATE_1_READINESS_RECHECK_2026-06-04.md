# Microsoft Gate 1 — Readiness Recheck

> **Purpose:** Verify whether operator actions from the Gate 1 Operator Runbook have been completed.
> **Does NOT:** Execute Gate 1, run live tests, or claim any connector LIVE_OK.
> **Date:** 2026-06-04
> **Timestamp (UTC):** 2026-06-04T06:31:50Z
> **HEAD:** `fc54c64cd37adb234c01296bf34dd89274196602`
> **Branch:** origin-main
> **Phase:** 2D Slice 6 incomplete, Slice 7 blocked
> **Service status:** NOT_LIVE

---

## 1. Evidence Files Referenced

| # | Path | Verdict | Purpose |
|---|------|---------|---------|
| 1 | `docs/evidence/uat/MICROSOFT_GATE_0_BASELINE_2026-06-04.md` | `MICROSOFT_GATE_0_BASELINE_RECORDED_NOT_LIVE` | Baseline inventory |
| 2 | `docs/evidence/uat/MICROSOFT_GATE_1_READINESS_2026-06-04.md` | `MICROSOFT_GATE_1_READINESS_BLOCKED_NOT_LIVE` | Readiness assessment |
| 3 | `docs/evidence/uat/MICROSOFT_GATE_1_OPERATOR_RUNBOOK_2026-06-04.md` | `MICROSOFT_GATE_1_OPERATOR_RUNBOOK_CREATED_NOT_LIVE` | Step-by-step operator checklist |

---

## 2. Operator Runbook Reference

The runbook defined 14 step categories across 6 sections (A–F). This recheck inspects the concrete state of each step without executing any live validation.

---

## 3. Readiness Matrix

| Step | Runbook Section | Expected State | Actual State | Resolved? | Blocks Gate 1? |
|------|-----------------|----------------|--------------|-----------|----------------|
| A1 | Project mapping placeholders | Zero `example` strings, valid JSON | **Zero `example` strings, valid JSON, all fields populated** | **Yes** | No |
| B1 | n8n UI exposed | Temporary `127.0.0.1:5678` mapping | No host binding present (not needed if operator used alternate method) | Unknown | No |
| B2–B3 | n8n login | Owner signed in | Cannot verify | Unknown | No |
| C1 | Import `sharepoint_search.json` | Workflow in n8n DB, active | **Not imported** | **No** | **Yes** |
| C2 | Import `email_search.json` | Workflow in n8n DB, active | **Not imported** | **No** | **Yes** |
| C3 | Import `owncloud_list.json` | Workflow in n8n DB, active | **Not imported** | **No** | **Yes** |
| D1 | Create Microsoft Graph OAuth2 credential | Credential in n8n DB | **Not created** | **No** | **Yes** |
| D2–D4 | Bind credentials to workflows | Graph + Header Auth bound to nodes | Cannot verify (workflows missing) | **No** | **Yes** |
| D5 | Activate workflows | `active=1` for all three | Cannot verify (workflows missing) | **No** | **Yes** |
| D6 | Verify webhook paths | `sharepoint-search`, `email-search`, `owncloud-list` in `webhook_entity` | **Only `odoo-read` present** | **No** | **Yes** |
| D7 | Remove temporary port mapping | Port 5678 not bound to host | `ss` shows no host bind | **Yes** | No |
| E1 | Verify API app roles | 9 roles in manifest | No evidence file submitted | **No** | **Yes** |
| E2 | Assign app roles to users | Users mapped to roles | No evidence file submitted | **No** | **Yes** |
| E3 | Grant admin consent | `Files.Read.All`, `Mail.Read`, `Mail.Read.Shared` granted | No evidence file submitted | **No** | **Yes** |
| E4 | Confirm SPA redirect URI | `https://vantage.elrace.com` registered | No evidence file submitted | **No** | **Yes** |
| E5 | Confirm API permission | `access_as_user` delegated permission granted | No evidence file submitted | **No** | **Yes** |
| F1 | Acquire fresh token | Valid token in browser session storage | `/root/dc_token.txt` exists but **expired** | **No** | **Yes** |
| F2 | Decode token claims | Non-secret diagnostic confirms `iss`/`aud`/`ver`/`roles` | Not performed (token expired) | **No** | **Yes** |
| F3 | Run `validate_entra_auth.py` | Exit code `0`, all steps PASS | **Not run** | **No** | **Yes** |

---

## 4. Resolved Blockers

### 4.1 Project Mapping Placeholders (B1)

- **Source inspected:** `docs/config/project_source_mapping.json`
- **Method:** `python3` scan for `example` strings + `json.tool` validation
- **Finding:**
  - `EXAMPLE_COUNT: 0`
  - JSON is valid.
  - Both projects (PRJ-001, PRJ-002) have non-empty values for:
    - `sharepoint.site_id`
    - `sharepoint.drive_id`
    - `email.shared_mailboxes` (1 entry each)
    - `email.document_control_mailbox`
- **Conclusion:** The operator replaced all placeholder values with real configuration.

---

## 5. Remaining Blockers

### 5.1 n8n Microsoft Workflows — NOT IMPORTED

- **Source inspected:** n8n SQLite `workflow_entity` table
- **Finding:**
  - `odoo_read` — imported, active (`active=1`)
  - `sharepoint_search` — **missing**
  - `email_search` — **missing**
  - `owncloud_list` — **missing**
- **Conclusion:** Operator has not imported the three Microsoft/ownCloud workflows.

### 5.2 n8n Microsoft Graph OAuth2 Credential — NOT CREATED

- **Source inspected:** n8n SQLite `credentials_entity` table
- **Finding:**
  - `DecisionCenter Webhook Header Auth` (`httpHeaderAuth`) — present
  - `microsoftGraphOAuth2Api` — **missing**
- **Conclusion:** Operator has not created the Graph OAuth2 credential required for SharePoint and Email API calls.

### 5.3 n8n Webhook Paths — NOT REGISTERED

- **Source inspected:** n8n SQLite `webhook_entity` table
- **Finding:**
  - `odoo-read|POST` — registered
  - `sharepoint-search|POST` — **missing**
  - `email-search|POST` — **missing**
  - `owncloud-list|POST` — **missing**
- **Conclusion:** Because the workflows are not imported, their webhook paths are not registered.

### 5.4 Entra App Roles — NO EVIDENCE

- **Source inspected:** `docs/evidence/uat/` directory, git status, repo files
- **Finding:** No new evidence file has been created since the operator runbook. No screenshot, transcript, or markdown file documents:
  - The 9 canonical app roles in the API app manifest
  - Role assignments to test users
- **Conclusion:** Operator has not submitted evidence that app roles are configured.

### 5.5 Entra Admin Consent — NO EVIDENCE

- **Source inspected:** `docs/evidence/uat/` directory, git status, repo files
- **Finding:** No evidence file documents admin consent for:
  - `Files.Read.All`
  - `Mail.Read`
  - `Mail.Read.Shared`
- **Conclusion:** Operator has not submitted evidence that admin consent was granted.

### 5.6 SPA Redirect URI — NO EVIDENCE

- **Source inspected:** `docs/evidence/uat/` directory, git status, repo files
- **Finding:** No evidence file confirms `https://vantage.elrace.com` is registered on the SPA app.
- **Conclusion:** Operator has not submitted evidence of redirect URI registration.

### 5.7 Access Token — EXPIRED

- **Source inspected:** `/root/dc_token.txt`
- **Finding:**
  - File exists (1618 bytes, created 2026-06-03 11:36).
  - JWT `exp` claim: `1780484064`.
  - Current timestamp: `1780554762`.
  - **Expired by ~70,698 seconds (~19.6 hours).**
- **Restriction applied:** Per task instructions, expired `/root/dc_token.txt` is **not used as proof**.
- **Conclusion:** No fresh, non-expired token is available.

---

## 6. Can Gate 1 Start?

**No.**

Gate 1 cannot start for the following exact reasons:

1. **n8n layer incomplete** — `sharepoint_search`, `email_search`, and `owncloud_list` workflows are not imported, not activated, and not bound to credentials. The Microsoft Graph OAuth2 credential does not exist in the n8n credential store.
2. **Entra configuration unproven** — No evidence exists in the repository that app roles are defined, users are assigned, admin consent is granted, or the SPA redirect URI is registered.
3. **No valid token** — The only token file on disk (`/root/dc_token.txt`) is expired. A fresh token must be acquired via browser login at Gate 1 run time.
4. **Validation script not run** — `scripts/validate_entra_auth.py` has never been executed with a live token.

Only **one** blocker from the runbook is resolved (project mapping placeholders). **Eight** blockers remain.

---

## 7. Final Verdict

**MICROSOFT_GATE_1_READINESS_BLOCKED_NOT_LIVE**

The readiness recheck confirms that the operator completed Step A1 (project mapping) but has not completed Steps C–F (n8n workflow import, credential creation, Entra app registration, token acquisition, and validation). No live proof is claimed. Production remains **NOT_LIVE**. Slice 7 remains blocked.
