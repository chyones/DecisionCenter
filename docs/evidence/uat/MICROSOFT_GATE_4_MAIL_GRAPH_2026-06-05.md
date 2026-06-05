# Microsoft Gate 4 — Mail / Graph Read-Only Evidence

**Verdict:** `MICROSOFT_GATE_4_MAIL_GRAPH_BLOCKED_NOT_LIVE`
**Date:** 2026-06-05
**Timestamp (UTC):** 2026-06-05T05:53:40Z
**HEAD:** `fc54c64cd37adb234c01296bf34dd89274196602`
**Branch:** `main`
**Production status:** NOT_LIVE

---

## 1. Gate Dependencies

| Gate | Dependency | Status |
|------|-----------|--------|
| Gate 1 | Entra authentication | **PASSED** |
| Gate 2 | Graph permissions — `Files.Read.All`, `Mail.Read`, `Sites.Read.All` | **PASSED** |
| Gate 3 | SharePoint site + drive confirmed for PRJ-001 and PRJ-002 | **PASSED** |

---

## 2. Git State

| Item | Value |
|------|-------|
| HEAD | `fc54c64cd37adb234c01296bf34dd89274196602` |
| Branch | `main` |

---

## 3. Graph Token — Role Confirmation

**Flow:** client_credentials · **Scope:** `https://graph.microsoft.com/.default`

| Role | Status |
|------|--------|
| `Files.Read.All` | **PRESENT** |
| `Mail.Read` | **PRESENT** |
| `Sites.Read.All` | **PRESENT** |

Token acquired fresh at run time. No value recorded.

---

## 4. Mailbox Configuration — Current State

File: `docs/config/project_source_mapping.json`

| Field path | Value | Status |
|-----------|-------|--------|
| `[PRJ-001].email.shared_mailboxes[0]` | `project-prj-001@example.com` | **PLACEHOLDER** |
| `[PRJ-001].email.document_control_mailbox` | `doc-control@example.com` | **PLACEHOLDER** |
| `[PRJ-002].email.shared_mailboxes[0]` | `project-prj-002@example.com` | **PLACEHOLDER** |
| `[PRJ-002].email.document_control_mailbox` | `doc-control-002@example.com` | **PLACEHOLDER** |

All four email fields remain at placeholder values. No operator-confirmed addresses have been supplied.

---

## 5. Microsoft Graph Discovery Attempt

### 5a. User Enumeration (`GET /users`)

```
GET https://graph.microsoft.com/v1.0/users?$top=100&$select=id,displayName,...
HTTP 403 — Authorization_RequestDenied
"Insufficient privileges to complete the operation."
```

**Required but missing:** `User.Read.All` or `Directory.Read.All` application permission.

### 5b. Group Enumeration (`GET /groups`)

```
GET https://graph.microsoft.com/v1.0/groups?$top=50&$select=id,displayName,mail,...
HTTP 403 — Authorization_RequestDenied
"Insufficient privileges to complete the operation."
```

**Required but missing:** `Group.Read.All` or `Directory.Read.All` application permission.

### 5c. Result

| Check | HTTP | Result |
|-------|------|--------|
| Token acquisition | — | **PASS** |
| `Mail.Read` role present | — | **PASS** |
| `GET /users` (User.Read.All) | 403 | **BLOCKED** |
| `GET /groups` (Group.Read.All) | 403 | **BLOCKED** |
| Mailbox probes | — | **NOT RUN** (no addresses) |

---

## 6. Read-Only Mail Checks — Status

Gate 4 requires all four checks per mailbox:

| Check | Required | Result |
|-------|---------|--------|
| Mailbox reachable (`GET /users/{addr}/mailFolders/inbox`) | Real SMTP address | NOT RUN |
| `mailFolders` readable (`GET /users/{addr}/mailFolders`) | Real SMTP address | NOT RUN |
| Inbox messages readable (`GET /users/{addr}/messages?$top=3`) | Real SMTP address | NOT RUN |
| Redacted metadata/counts recorded | Real SMTP address | NOT RUN |

Checks cannot run without real SMTP addresses. Placeholder domains (`@example.com`) do not resolve to Graph mailboxes.

---

## 7. Why Enumeration is Blocked

The Entra application registration (`a2160d26-acc0-4d8c-b815-3a377f1fb5bd`) holds three application permissions:

| Permission | Granted | Sufficient for |
|-----------|---------|----------------|
| `Sites.Read.All` | Yes | SharePoint site/drive discovery (Gate 3) |
| `Files.Read.All` | Yes | Drive content reads |
| `Mail.Read` | Yes | Reading any mailbox **once address is known** |
| `User.Read.All` | **No** | Enumerating users to discover mailbox addresses |
| `Directory.Read.All` | **No** | Enumerating directory objects |

`Mail.Read` as an application permission grants read access to any tenant mailbox — but requires knowing the mailbox UPN or SMTP address first. Without `User.Read.All` or `Directory.Read.All`, the address list cannot be derived from Graph alone.

---

## 8. Blockers

| # | Blocker | Owner | Resolution |
|---|---------|-------|-----------|
| B-1 | `shared_mailboxes` for PRJ-001 are placeholder | **Operator** | Supply real shared mailbox SMTP |
| B-2 | `document_control_mailbox` for PRJ-001 is placeholder | **Operator** | Supply real doc-control SMTP |
| B-3 | `shared_mailboxes` for PRJ-002 are placeholder | **Operator** | Supply real shared mailbox SMTP |
| B-4 | `document_control_mailbox` for PRJ-002 is placeholder | **Operator** | Supply real doc-control SMTP |
| B-5 | `User.Read.All` / `Directory.Read.All` not granted | **Entra admin** | Grant permission, or skip enumeration by supplying SMTP directly (resolves B-1—B-4) |

**Minimum to unblock:** Operator supplies the four real SMTP addresses directly (resolves B-1 through B-4 without requiring Entra admin involvement).

---

## 9. What `Mail.Read` Can Do Once Unblocked

With real SMTP addresses, `Mail.Read` enables the following read-only checks (no write, delete, or move operations):

```
GET /users/{addr}/mailFolders/inbox             → reachability check
GET /users/{addr}/mailFolders?$top=20           → folder names + counts
GET /users/{addr}/messages?$top=3&$select=...   → recent message metadata only
```

Message body, sender, and recipients are NOT requested. Only `receivedDateTime` and `hasAttachments` are captured.

---

## 10. No Config Changes

No changes were made to `docs/config/project_source_mapping.json` because no verified SMTP addresses were available. The mapping is updated only after operator confirmation.

---

## 11. Static Analysis

```
ruff check .          → All checks passed
python3 -m compileall → Clean (no errors)
check_doc_drift.py    → Documentation drift check: clean
check_ai_context.py   → AI context check: clean
agent_postflight.py   → Post-flight: clean
```

---

## 12. Can Gate 5 Start?

**No** — Gate 4 is blocked. Gate 5 depends on confirmed mailbox mappings.

Gate 5 requires:
- `[PRJ-001].email.shared_mailboxes[0]` — confirmed and accessible via `Mail.Read`
- `[PRJ-001].email.document_control_mailbox` — confirmed and accessible
- `[PRJ-002].email.shared_mailboxes[0]` — confirmed and accessible
- `[PRJ-002].email.document_control_mailbox` — confirmed and accessible

---

## 13. Remaining Blockers to Gate 5

| # | Blocker | Gate |
|---|---------|------|
| 1 | PRJ-001 `shared_mailboxes[0]` real address — operator must supply | Gate 4 |
| 2 | PRJ-001 `document_control_mailbox` real address — operator must supply | Gate 4 |
| 3 | PRJ-002 `shared_mailboxes[0]` real address — operator must supply | Gate 4 |
| 4 | PRJ-002 `document_control_mailbox` real address — operator must supply | Gate 4 |

---

## 14. Final Verdict

```
MICROSOFT_GATE_4_MAIL_GRAPH_BLOCKED_NOT_LIVE
```

`Mail.Read` application permission is confirmed present in the Graph token.
Mailbox read-only checks cannot run because all four project mailbox fields remain at
placeholder values (`@example.com`). Graph user/group enumeration is not permitted with
current application permissions (`User.Read.All` is not granted).

Gate 4 unblocks when the operator supplies the four real SMTP addresses for PRJ-001 and PRJ-002.
Production remains NOT_LIVE.

---

*Evidence generated by Claude Code Gate 4 — 2026-06-05T05:53:40Z*
