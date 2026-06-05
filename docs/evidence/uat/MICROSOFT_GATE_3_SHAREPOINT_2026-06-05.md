# Microsoft Gate 3 — SharePoint Read-Only Evidence (Final)

**Verdict:** `MICROSOFT_GATE_3_SHAREPOINT_PASSED_NOT_LIVE`
**Date:** 2026-06-05
**Timestamp (UTC):** 2026-06-05T04:52:50Z
**HEAD:** `fc54c64cd37adb234c01296bf34dd89274196602`
**Branch:** `main` tracking `origin/main`
**Production status:** NOT_LIVE

---

## 1. Gate Dependencies

| Gate | Dependency | Status |
|------|-----------|--------|
| Gate 1 | Entra authentication | **PASSED** |
| Gate 2 | Graph API permissions (Files.Read.All, Mail.Read, Sites.Read.All) | **PASSED** |
| Sites.Read.All recheck | `SITES_READ_ALL_ROLE_RECHECK_2026-06-04.md` | **CONFIRMED** |
| n8n Graph OAuth2 | Backend injects token; pass-through Authorization header | **NOT_REQUIRED** |

---

## 2. Git State

| Item | Value |
|------|-------|
| HEAD | `fc54c64cd37adb234c01296bf34dd89274196602` |
| Branch | `main...origin/main` |

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

## 4. Operator-Confirmed Assignment

| project_code | SharePoint site | Confirmed by |
|---|---|---|
| PRJ-001 | CD Al Mirfa (`CivilDefenseCenterinAlMirfaAlDhafraRegionTypeD`) | Operator — 2026-06-05 |
| PRJ-002 | CD Madinat Zayed (`CivilDefenseCenterinIndustrialAreaofMadinatZayed`) | Operator — 2026-06-05 |
| root_path PRJ-001 | `/Projects/PRJ-001` | Operator — 2026-06-05 (metadata only) |
| root_path PRJ-002 | `/Projects/PRJ-002` | Operator — 2026-06-05 (metadata only) |

TestAlainProject was identified as a third candidate but not assigned to any project code.

---

## 5. Placeholder Fields — Before and After

File: `docs/config/project_source_mapping.json`

| Field path | Before | After |
|-----------|--------|-------|
| `[PRJ-001].sharepoint.site_id` | `example-site-id-001` | **[REDACTED — real value set]** |
| `[PRJ-001].sharepoint.drive_id` | `example-drive-id-001` | **[REDACTED — real value set]** |
| `[PRJ-001].sharepoint.root_path` | `/Projects/PRJ-001` | `/Projects/PRJ-001` (unchanged — operator confirmed) |
| `[PRJ-002].sharepoint.site_id` | `example-site-id-002` | **[REDACTED — real value set]** |
| `[PRJ-002].sharepoint.drive_id` | `example-drive-id-002` | **[REDACTED — real value set]** |
| `[PRJ-002].sharepoint.root_path` | `/Projects/PRJ-002` | `/Projects/PRJ-002` (unchanged — operator confirmed) |

Email placeholders remain unchanged — deferred to Gate 4.

---

## 6. Graph Discovery Endpoints Used (Read-Only)

```text
POST https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token
GET  https://graph.microsoft.com/v1.0/sites/{site_id}?$select=id,displayName,webUrl,lastModifiedDateTime
GET  https://graph.microsoft.com/v1.0/drives/{drive_id}?$select=id,name,webUrl,driveType
GET  https://graph.microsoft.com/v1.0/drives/{drive_id}/root:/{root_path}?$select=id,name,folder,size
GET  https://graph.microsoft.com/v1.0/drives/{drive_id}/root/children?$top=10&$select=id,name,folder,file,size,lastModifiedDateTime
```

No write, upload, delete, folder-creation, or permission operations were performed.

---

## 7. PRJ-001 — SharePoint Read-Only Verification

**Site:** Construction of Civil Defense Center in Al Mirfa, Al Dhafra Region – Type "D". CD Al Mirfa – D
**webUrl:** `https://elrace.sharepoint.com/sites/CivilDefenseCenterinAlMirfaAlDhafraRegionTypeD`
**Last modified:** 2026-06-05

| Check | Result |
|-------|--------|
| Site reachable (`GET /sites/{site_id}`) | HTTP 200 **PASS** |
| Drive reachable (`GET /drives/{drive_id}`) | HTTP 200 **PASS** (name=Documents, type=documentLibrary) |
| root_path `/Projects/PRJ-001` exists | HTTP 404 — path not present in drive (metadata only; `node_05_sharepoint.py` does not pass `root_path` in search payload) |
| Drive root/children readable | HTTP 200 **PASS** — 10 items |

### Drive root items (first 5)

| # | Name | Size | Last Modified | Children |
|---|------|------|--------------|---------|
| 1 | 00. Close-Out Documents | 1.3 MB | 2026-04-21 | 1 |
| 2 | 01. QHSE FIles | 0 B | 2026-04-21 | 0 |
| 3 | 02. MOM | 3.1 MB | 2026-04-21 | 3 |
| 4 | 1. Pre Qualification | 2.12 GB | 2025-12-19 | 4 |
| 5 | 1.a New Prequalification Files | 2.34 GB | 2026-03-05 | 4 |

**Result: PASS** — site reachable, drive reachable, root/children readable.

---

## 8. PRJ-002 — SharePoint Read-Only Verification

**Site:** Construction of Civil Defense Center in Industrial Area of Madinat Zayed, Al Dhafra Region – Type "D". CD Madinat Zayed – D
**webUrl:** `https://elrace.sharepoint.com/sites/CivilDefenseCenterinIndustrialAreaofMadinatZayed`
**Last modified:** 2026-06-05

| Check | Result |
|-------|--------|
| Site reachable (`GET /sites/{site_id}`) | HTTP 200 **PASS** |
| Drive reachable (`GET /drives/{drive_id}`) | HTTP 200 **PASS** (name=Documents, type=documentLibrary) |
| root_path `/Projects/PRJ-002` exists | HTTP 404 — path not present in drive (metadata only) |
| Drive root/children readable | HTTP 200 **PASS** — 10 items |

### Drive root items (first 5)

| # | Name | Size | Last Modified | Children |
|---|------|------|--------------|---------|
| 1 | 00. Close-Out Files | 0 B | 2026-04-21 | 0 |
| 2 | 01. QHSE Files | 3.5 MB | 2026-04-21 | 1 |
| 3 | 1. Pre Qualification | 2.28 GB | 2025-12-18 | 9 |
| 4 | 10. Work Inspection Request | 3.70 GB | 2025-12-18 | 4 |
| 5 | 11. Programs & Schedules | 19.3 MB | 2025-12-18 | 4 |

**Result: PASS** — site reachable, drive reachable, root/children readable.

---

## 9. root_path Note

Both `/Projects/PRJ-001` and `/Projects/PRJ-002` return HTTP 404 when accessed as a path within the respective drives. This is expected: the actual drive folder structure uses numbered conventions (`01. QHSE Files`, `10. Work Inspection Request`, etc.) rather than a `Projects/` hierarchy.

`root_path` is stored as metadata in `project_source_mapping.json` but is **not included in the n8n search payload** — `node_05_sharepoint.py` sends only `site_id`, `drive_id`, `query`, and `project_code`. The n8n workflow performs a drive-level search (`/root/search(q='...')`), not a path-scoped search. Therefore the missing path does not affect runtime behaviour and is not a Gate 3 blocker.

The operator may update `root_path` to reflect the actual folder conventions at their discretion before production go-live.

---

## 10. Config Change Verification

`docs/config/project_source_mapping.json` was updated with real `site_id` and `drive_id` for both projects.

| Check | Result |
|-------|--------|
| `ruff check .` | **All checks passed** |
| `python3 -m compileall apps scripts` | **Clean** |
| `test_phase2b_source_mapping` (38 tests) | **All passed** |
| `test_connectors` (25 tests) | **All passed** |
| Total | **63/63 passed** |

---

## 11. Email Mapping — Deferred to Gate 4

Email placeholders (`shared_mailboxes`, `document_control_mailbox`) for PRJ-001 and PRJ-002 remain `@example.com` placeholder values. Gate 4 scope. Operator must supply real SMTP addresses.

---

## 12. Can Gate 4 Start?

**Yes** — Gate 3 is complete. Gate 4 (email mailbox verification and mapping) may start.

Gate 4 requires the operator to supply:
- `[PRJ-001].email.shared_mailboxes[0]` — real shared mailbox SMTP address
- `[PRJ-001].email.document_control_mailbox` — real doc-control SMTP address
- `[PRJ-002].email.shared_mailboxes[0]` — real shared mailbox SMTP address
- `[PRJ-002].email.document_control_mailbox` — real doc-control SMTP address

---

## 13. Remaining Microsoft Blockers

| # | Blocker | Owner | Gate |
|---|---------|-------|------|
| 1 | Supply real shared mailbox SMTP for PRJ-001 and PRJ-002 | Operator | Gate 4 |
| 2 | Supply real doc-control mailbox SMTP for PRJ-001 and PRJ-002 | Operator | Gate 4 |

No Gate 3 blockers remain.

---

## 14. Final Verdict

```
MICROSOFT_GATE_3_SHAREPOINT_PASSED_NOT_LIVE
```

Both project SharePoint sites are confirmed reachable and readable.
Real `site_id` and `drive_id` values are written to `docs/config/project_source_mapping.json`.
All 63 config/connector tests pass. Production remains NOT_LIVE.

---

*Evidence generated by Claude Code Gate 3 re-run — 2026-06-05T04:52:50Z*
