# Microsoft Mapping Rescan — Implementation Evidence

**Verdict:** `MICROSOFT_MAPPING_RESCAN_IMPLEMENTED_NOT_LIVE`
**Date:** 2026-06-05
**HEAD:** `fc54c64cd37adb234c01296bf34dd89274196602`
**Production status:** NOT_LIVE

---

## 1. Feature Summary

Implemented a read-only Microsoft Graph rescan workflow for the admin panel.
When new projects are added, the system automatically discovers SharePoint sites,
drives, and mailboxes, then scores candidates against existing project mappings.

No Microsoft Graph write operations are performed at any point.

---

## 2. Files Created / Modified

| File | Change |
|------|--------|
| `apps/edr/admin/microsoft_rescan.py` | **NEW** — discovery engine (~275 lines) |
| `apps/edr/app.py` | **MODIFIED** — 2 new endpoints appended |
| `apps/edr/tests/integration/test_microsoft_rescan.py` | **NEW** — 37 tests |
| `frontend/src/api/types.ts` | **MODIFIED** — 7 new TypeScript interfaces appended |
| `frontend/src/api/index.ts` | **MODIFIED** — new types re-exported |
| `frontend/src/screens/AdminSourceMappingScreen.tsx` | **MODIFIED** — RescanPanel + handlers |

---

## 3. Backend — Endpoints

### `POST /admin/microsoft-mapping/rescan`

- Admin-only (`_require_admin`).
- Loads all source mappings from DB. If `project_codes` is non-empty, filters to those.
- A-21: `insert_admin_event("admin.microsoft_rescan_run", ...)` before scan.
- Calls `run_microsoft_rescan(projects)` — **no DB writes**.
- Returns `MicrosoftRescanResponse` with per-project results.

### `POST /admin/microsoft-mapping/{code}/confirm`

- Admin-only (`_require_admin`).
- 404 if project code not found.
- 409 if existing `site_id` is non-placeholder and differs from `body.site_id`.
- Merges SharePoint fields only; preserves email, odoo, owncloud, related_people.
- A-21: `insert_admin_event("admin.microsoft_mapping_confirmed", ...)` before upsert.
- Returns `SourceMappingDetail` of the updated row.

---

## 4. Discovery Engine (`apps/edr/admin/microsoft_rescan.py`)

### Mapping statuses returned

| Status | Meaning |
|--------|---------|
| `AUTO_MAPPED` | Deterministic strong match, or existing valid site confirmed |
| `NEEDS_CONFIRMATION` | Multiple candidates or medium/weak match only |
| `MISSING_SHAREPOINT` | No candidates found |
| `MISSING_MAILBOX` | No accessible mailboxes found |
| `CONFLICT` | Existing confirmed mapping differs from best candidate |
| `DISABLED` | Project mapping_status is "disabled" — skipped |

### Match scoring

| Strength | Condition |
|----------|-----------|
| `existing` | Non-placeholder site_id responds 200 on probe |
| `strong` | Project code in site displayName, or ≥80% keyword overlap |
| `medium` | 50–79% keyword overlap |
| `weak` | Any keyword overlap |
| `none` | No overlap |

Stop words filtered: the, and, for, with, from, area, type, region, center, centre, in, of, at, to, by, a, an, this, that, will, its.

### Auto-mapping rules

- `existing` strength → `AUTO_MAPPED` (existing site confirmed).
- Single `strong` candidate → `AUTO_MAPPED`.
- Multiple `strong` candidates → `NEEDS_CONFIRMATION`.
- No `strong` candidate → `NEEDS_CONFIRMATION` (with medium/weak candidates) or `MISSING_SHAREPOINT`.

### Safety guarantees

- Read-only Microsoft Graph.  No writes to SharePoint, Mail, or any Graph API.
- Token value is never logged, printed, or returned.
- Does not write to the database; caller decides to confirm.
- `contentstorage` system URLs filtered from site discovery results.

---

## 5. Frontend — `AdminSourceMappingScreen.tsx`

### "Rescan Microsoft Sources" button

Added to page header (top-right). Triggers `handleRescan()` → `POST /admin/microsoft-mapping/rescan`. Shows loading state via `isLoading`.

### `RescanPanel` modal

Opened automatically after rescan completes. Shows:

- Scan timestamp, `Sites.Read.All` and `Mail.Read` token status pills.
- Total sites discovered.
- Per-project card: SharePoint status pill, mailbox status pill, reason string.
- For `NEEDS_CONFIRMATION` projects: list of candidates with `Accept` button per candidate.
- For `AUTO_MAPPED` projects: displays the matched site name and drive ID prefix.

Accepting a candidate calls `POST /admin/microsoft-mapping/{code}/confirm`, then re-runs a single-project rescan to refresh the panel in-place without closing it.

---

## 6. TypeScript Types Added (`frontend/src/api/types.ts`)

| Interface | Purpose |
|-----------|---------|
| `MicrosoftMappingStatus` | Union type for rescan status values |
| `SiteCandidate` | Single SharePoint site candidate with scoring fields |
| `MailboxCandidate` | Single mailbox probe result |
| `ProjectRescanResult` | Per-project rescan output |
| `MicrosoftRescanResponse` | Full rescan endpoint response |
| `MicrosoftRescanRequest` | Rescan request body |
| `MicrosoftMappingConfirmRequest` | Confirm request body |

---

## 7. Test Coverage

**File:** `apps/edr/tests/integration/test_microsoft_rescan.py`

| Test group | Count |
|-----------|-------|
| Pure-function unit tests | 8 |
| `run_microsoft_rescan` with mocked Graph | 5 |
| RBAC denial (8 non-admin roles × 2 endpoints) | 17 |
| Endpoint happy path + error cases | 7 |
| **Total** | **37** |

**Total test count across all integration tests: 100 / 100 passed.**

| Suite | Tests | Result |
|-------|-------|--------|
| `test_microsoft_rescan.py` | 37 | All passed |
| `test_phase2b_source_mapping.py` | 38 | All passed |
| `test_connectors.py` | 25 | All passed |

---

## 8. Compliance

| Control | Check |
|---------|-------|
| C-1: No query content in audit events | Token marked `[REDACTED]` in audit detail |
| C-6: No credential values in responses | Token never returned; site_id/drive_id redacted in audit |
| A-21: Audit before save | `insert_admin_event` called before `upsert_source_mapping` (verified by test) |
| RBAC: Admin-only | `_require_admin(claims)` is first operation in both endpoints |

---

## 9. Static Analysis

```
ruff check .          → All checks passed
python3 -m compileall → Clean (no errors)
check_doc_drift.py    → Documentation drift check: clean
check_ai_context.py   → AI context check: clean
agent_postflight.py   → Post-flight: clean
```

---

## 10. What This Unlocks

When new projects are created via the Source Mapping admin panel, the operator can:
1. Click "Rescan Microsoft Sources".
2. Review per-project results — auto-mapped projects require no action.
3. For `NEEDS_CONFIRMATION` projects, choose from scored candidates.
4. Click "Accept" — the mapping is immediately confirmed and the panel refreshes.

No manual copy/paste of site_id or drive_id is required for strong matches.

---

## 11. Production Readiness

| Item | Status |
|------|--------|
| Backend endpoints deployed | NOT_LIVE (pending app rebuild) |
| Frontend build deployed | NOT_LIVE (pending npm build) |
| Entra token roles | All 3 confirmed (Gate 3 evidence) |
| SharePoint mappings | PRJ-001 and PRJ-002 confirmed (Gate 3) |

Production remains NOT_LIVE pending full UAT sign-off.

---

## 12. Final Verdict

```
MICROSOFT_MAPPING_RESCAN_IMPLEMENTED_NOT_LIVE
```

Feature is fully implemented: backend discovery engine, two admin endpoints,
React UI with accept/reject workflow, TypeScript types, and 37 tests (all passing).
Production deployment requires app rebuild. No Microsoft Graph write operations
were performed at any point during implementation or testing.

---

*Evidence generated by Claude Code — 2026-06-05*
