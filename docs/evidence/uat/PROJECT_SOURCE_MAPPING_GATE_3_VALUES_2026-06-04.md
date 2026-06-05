# Project Source Mapping — Gate 3 Values Verification

> **Final verdict:** `PROJECT_SOURCE_MAPPING_BLOCKED_FOR_GATE_3_NOT_LIVE`
> **Date:** 2026-06-04
> **Timestamp (UTC):** 2026-06-05T04:24:27Z
> **HEAD:** `fc54c64cd37adb234c01296bf34dd89274196602`
> **Branch:** `main` tracking `origin/main`
> **Production status:** NOT_LIVE
> **Gate 3 run:** Not started (blocked)
> **Slice 6 UAT:** Not started
> **Slice 7:** Not started

---

## 1. Git State

| Item | Value |
|------|-------|
| `git rev-parse HEAD` | `fc54c64cd37adb234c01296bf34dd89274196602` |
| `git status --short --branch` | `main...origin/main` with unstaged connector/node/frontend changes and untracked evidence files |

---

## 2. Graph Token Roles Summary

**Method:** Client credentials flow against `https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token`

**Scope:** `https://graph.microsoft.com/.default`

**Token value:** not recorded.

**Decoded roles (no secret printed):**

```json
["Files.Read.All", "Mail.Read"]
```

| Role | Status |
|------|--------|
| `Files.Read.All` | **Present** |
| `Mail.Read` | **Present** |
| `Sites.Read.All` | **Missing** |

---

## 3. Sites.Read.All Status

**Result:** `NOT_PRESENT_IN_TOKEN`

The operator reported that the `Sites.Read.All` application permission was added, but the
live client-credentials token issued by Microsoft does **not** include `Sites.Read.All` in
the `roles` claim. This indicates one of the following:

- Admin consent for `Sites.Read.All` has not yet been granted in the Entra app registration.
- The permission was added but not consented at the organization level.
- A token-refresh / propagation delay means the newly consented permission has not yet
  appeared in issued tokens.

**Required operator action:** Grant admin consent for `Sites.Read.All` on the API app
registration (`a2160d26-acc0-4d8c-b815-3a377f1fb5bd`) and acquire a fresh token. Do not
proceed with Gate 3 until `Sites.Read.All` appears in the token roles.

---

## 4. Placeholder Fields Before Verification

File inspected: `docs/config/project_source_mapping.json`

| # | Field path | Placeholder value |
|---|-----------|-------------------|
| 1 | `[PRJ-001].sharepoint.site_id` | `example-site-id-001` |
| 2 | `[PRJ-001].sharepoint.drive_id` | `example-drive-id-001` |
| 3 | `[PRJ-001].email.shared_mailboxes[0]` | `project-prj-001@example.com` |
| 4 | `[PRJ-001].email.document_control_mailbox` | `doc-control@example.com` |
| 5 | `[PRJ-002].sharepoint.site_id` | `example-site-id-002` |
| 6 | `[PRJ-002].sharepoint.drive_id` | `example-drive-id-002` |
| 7 | `[PRJ-002].email.shared_mailboxes[0]` | `project-prj-002@example.com` |
| 8 | `[PRJ-002].email.document_control_mailbox` | `doc-control-002@example.com` |

---

## 5. Resolved Fields After Verification

**No placeholders were resolved.**

Because `Sites.Read.All` is missing, SharePoint site/drive discovery cannot be performed
safely, and no real `site_id` or `drive_id` values were obtained. Mailbox candidates were
probed with `Mail.Read`, but none returned HTTP 200, so no verified mailbox addresses were
obtained.

| # | Field path | Resolved value |
|---|-----------|----------------|
| — | — | No verified values available. |

---

## 6. SharePoint Discovery

### Intended discovery endpoints

The following read-only endpoints were planned for SharePoint discovery once
`Sites.Read.All` is confirmed:

```text
GET https://graph.microsoft.com/v1.0/sites?search=PRJ-001&$select=id,displayName,webUrl
GET https://graph.microsoft.com/v1.0/sites?search=PRJ-002&$select=id,displayName,webUrl
GET https://graph.microsoft.com/v1.0/sites?search=Projects&$select=id,displayName,webUrl
GET https://graph.microsoft.com/v1.0/sites?search=elrace&$select=id,displayName,webUrl
GET https://graph.microsoft.com/v1.0/sites/{site_id}/drives?$select=id,name,webUrl
GET https://graph.microsoft.com/v1.0/drives/{drive_id}/root/children?$top=3
```

### Actual execution

**No SharePoint discovery endpoints were called** because the token lacks `Sites.Read.All`.
Calling `/sites?search=...` without that role would return HTTP 403, as demonstrated in
Gate 2 evidence (`MICROSOFT_GATE_2_GRAPH_PERMISSIONS_2026-06-04.md`).

### Drive read-only verification result

**Not executed.** Pending confirmation of `Sites.Read.All` and discovery of real site/drive
IDs.

---

## 7. Mailbox Verification

### Candidate addresses probed

Using `Mail.Read`, the following candidate `@elrace.com` shared-mailbox addresses were
probed read-only via:

```text
GET https://graph.microsoft.com/v1.0/users/{mailbox_address}/mailFolders/inbox?$top=1
```

| Candidate address | HTTP status | Accessible |
|-------------------|-------------|------------|
| `prj-001@elrace.com` | 404 | No |
| `prj-002@elrace.com` | 404 | No |
| `doc-control@elrace.com` | 404 | No |
| `doc-control-prj001@elrace.com` | 404 | No |
| `doc-control-prj002@elrace.com` | 404 | No |
| `project-prj-001@elrace.com` | 404 | No |
| `project-prj-002@elrace.com` | 404 | No |

### Interpretation

All candidate addresses returned HTTP 404. This means either:

- The mailboxes do not exist in the tenant under these exact SMTP addresses, **or**
- The application lacks `User.Read.All` and Microsoft Graph returns 404 for any unknown
  or non-enumerable user/mailbox.

Because the addresses could not be verified as real and accessible, the mailbox
placeholders **must remain blocked** until the operator supplies the exact real shared
mailbox and document-control mailbox SMTP addresses for `PRJ-001` and `PRJ-002`.

**Missing exact values required from operator:**

- `[PRJ-001].email.shared_mailboxes[0]` — real shared mailbox SMTP address
- `[PRJ-001].email.document_control_mailbox` — real document-control mailbox SMTP address
- `[PRJ-002].email.shared_mailboxes[0]` — real shared mailbox SMTP address
- `[PRJ-002].email.document_control_mailbox` — real document-control mailbox SMTP address

---

## 8. Can Gate 3 Start?

**No.**

Gate 3 is blocked by two unresolved issues:

1. `Sites.Read.All` is **not present** in the Graph token. Admin consent / token refresh is
   required before any SharePoint site/drive discovery can succeed.
2. All 8 placeholder values in `docs/config/project_source_mapping.json` remain
   unresolved:
   - 4 SharePoint placeholders (`site_id`, `drive_id` for PRJ-001 and PRJ-002)
   - 4 email placeholders (shared mailbox and document-control mailbox for PRJ-001 and
     PRJ-002)

No write operations were performed. No secrets, tokens, or client secret values are
recorded in this evidence file.

---

## 9. Final Verdict

**`PROJECT_SOURCE_MAPPING_BLOCKED_FOR_GATE_3_NOT_LIVE`**

`Sites.Read.All` was reported as added but does not yet appear in the live
client-credentials token. Until admin consent propagates and a fresh token confirms
`Sites.Read.All`, SharePoint discovery is blocked. Additionally, none of the candidate
mailbox addresses returned HTTP 200, so no verified real mailbox values are available to
replace the `@example.com` placeholders. Gate 3 must not be started. Production remains
`NOT_LIVE`.
